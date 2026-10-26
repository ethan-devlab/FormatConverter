import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from server.format_converter import config, jobs
from server.format_converter.api import create_app
from server.format_converter.schemas import JobRequest


@pytest.fixture
def service(tmp_path, monkeypatch):
    data = tmp_path / "settings"
    monkeypatch.setattr(config, "DATA", data)
    monkeypatch.setattr(jobs, "DATA", data)
    root = tmp_path / "files"
    root.mkdir()
    output = root / "output"
    output.mkdir()
    for name, color in [("one.png", "red"), ("two.png", "blue")]:
        Image.new("RGB", (120, 80), color).save(root / name)
    app = create_app()
    with TestClient(app) as client:
        client.headers["X-Format-Converter"] = "1"
        assert client.post("/api/session").status_code == 200
        assert client.post("/api/roots", json={"path": str(root)}).status_code == 200
        yield client, app, root, output


def wait_job(client, identity):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{identity}").json()
        if job["status"] not in {"queued", "running"}:
            return job
        time.sleep(0.1)
    pytest.fail("Conversion job timed out")


def test_origin_auth_and_root_boundaries(service, tmp_path):
    client, app, root, _ = service
    assert client.get("/api/bootstrap", headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert client.get("/api/bootstrap", headers={"Host": "untrusted.example"}).status_code == 403
    assert client.get("/api/directory", params={"path": str(tmp_path)}).status_code == 403
    client.cookies.clear()
    assert client.get("/api/bootstrap").status_code == 401
    assert client.post("/api/session", headers={"X-Format-Converter": ""}).status_code == 403


def test_local_instances_do_not_overwrite_each_others_session_cookie(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path / "settings")
    monkeypatch.setattr(jobs, "DATA", tmp_path / "settings")
    first_app, second_app = create_app(), create_app()
    with TestClient(first_app, base_url="http://127.0.0.1:8765") as first, TestClient(second_app, base_url="http://127.0.0.1:8769") as second:
        for client in (first, second):
            client.headers["X-Format-Converter"] = "1"
        response = first.post("/api/session")
        assert response.status_code == 200
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        second.cookies.update(first.cookies)
        assert second.post("/api/session").status_code == 200
        # Browser cookies share a host across ports. Merge the second response
        # back into the first jar to reproduce a user visiting both instances.
        first.cookies.update(second.cookies)
        assert first.get("/api/roots").status_code == 200
        assert second.get("/api/roots").status_code == 200


def test_pdf_inspection_reports_roles(service):
    import pymupdf
    client, app, root, _ = service
    source = root / "protected.pdf"
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(source, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="reader")
    response = client.post("/api/files/inspect-pdf", json={"sources": [{"path": str(source), "password": "reader"}, {"path": str(source), "password": "owner"}, {"path": str(source)}]})
    assert response.status_code == 200, response.text
    reader, owner, missing = response.json()
    assert reader["encrypted"] and reader["readable"] and not reader["can_decrypt"]
    assert owner["owner"] and owner["can_decrypt"]
    assert not missing["readable"]


def test_native_watch_updates_and_hidden_visibility(service):
    client, app, root, _ = service
    before = client.get("/api/events").json()["version"]
    hidden = root / ".watch-test.txt"
    hidden.write_text("synthetic", "utf-8")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        events = client.get("/api/events", params={"after": before}).json()
        if any(e.get("path") == str(hidden) for e in events["events"]):
            break
        time.sleep(.1)
    else:
        pytest.fail("Native directory change was not delivered")
    normal = client.get("/api/directory", params={"path": str(root)}).json()
    visible = client.get("/api/directory", params={"path": str(root), "hidden": True}).json()
    assert hidden.name not in {e["name"] for e in normal["entries"]}
    assert hidden.name in {e["name"] for e in visible["entries"]}


def test_windows_recycle_bin_has_no_permanent_delete_fallback(service):
    import os
    if os.name != "nt":
        pytest.skip("Windows recycle-bin integration")
    client, app, root, _ = service
    source = root / "format-converter-disposable-recycle-test.txt"
    source.write_text("Synthetic disposable test fixture", "utf-8")
    response = client.post("/api/files/operation", json={"action": "delete", "paths": [str(source)], "confirmed": True})
    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["ok"], response.text
    assert not source.exists()


def test_lazy_directory_refresh_and_file_operations(service):
    client, app, root, output = service
    listing = client.get("/api/directory", params={"path": str(root), "limit": 2}).json()
    assert len(listing["entries"]) == 2 and listing["has_more"]
    source = root / "one.png"
    response = client.post("/api/files/operation", json={"action": "rename", "paths": [str(source)], "name": "renamed.png"})
    assert response.status_code == 200
    renamed = root / "renamed.png"
    assert renamed.exists() and not source.exists()
    assert client.post("/api/files/operation", json={"action": "copy", "paths": [str(renamed)]}).status_code == 200
    assert client.post("/api/files/operation", json={"action": "paste", "destination": str(output)}).json()["results"][0]["ok"]
    assert (output / "renamed.png").read_bytes() == renamed.read_bytes()
    assert client.post("/api/files/operation", json={"action": "rename", "paths": [str(renamed)], "name": "../escape"}).status_code == 400
    assert client.post("/api/files/operation", json={"action": "delete", "paths": [str(renamed)]}).status_code == 400
    assert renamed.exists()
    assert client.post("/api/files/operation", json={"action": "delete", "paths": [str(root)], "confirmed": True}).status_code == 400


def test_explorer_filter_api_searches_before_paging_and_refresh_keeps_roots(service):
    client, app, root, output = service
    for index in range(205):
        (root / f"item-{index:03}.txt").write_text("synthetic")
    (root / "z-match.txt").write_text("match")
    result = client.get("/api/directory", params={"path": str(root), "query": "z-match", "refresh": True}).json()
    assert [e["name"] for e in result["entries"] if not e["directory"]] == ["z-match.txt"]
    assert not result["has_more"]
    roots = client.get("/api/roots", params={"refresh": True})
    assert roots.status_code == 200
    assert roots.json() == [{"path": str(root), "name": root.name, "available": True}]


def test_preview_commit_reuses_output_and_cleans_temporary(service):
    client, app, root, output = service
    body = {"tool": "images_pdf", "sources": [{"path": str(root / "one.png")}], "preview": True, "parameters": {}}
    response = client.post("/api/jobs", json=body)
    assert response.status_code == 200, response.text
    identity = response.json()["id"]
    job = wait_job(client, identity)
    assert job["status"] == "done", job
    artifact = job["tasks"][0]["outputs"][0]
    data = client.get(artifact["url"]).content
    assert data.startswith(b"%PDF")
    assert not list(output.iterdir())
    body.update(preview=False, output_directory=str(output))
    response = client.post(f"/api/jobs/{identity}/commit", json=body)
    assert response.status_code == 200, response.text
    final = response.json()["tasks"][0]["outputs"][0]
    assert Path(final["path"]).read_bytes() == data
    assert not (app.state.manager.session / identity).exists()
    assert client.get(artifact["url"]).status_code == 404


def test_mixed_encrypted_batch_reports_each_error_and_measured_size(service):
    import pymupdf as fitz
    client, _, root, _ = service
    plain = root / "plain.pdf"
    locked = root / "locked.pdf"
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 70), "Synthetic batch check")
        doc.save(plain)
        doc.save(locked, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="test-open", owner_pw="test-owner")
    response = client.post("/api/jobs", json={"tool":"compress", "preview":True,
        "sources":[{"path":str(plain)},{"path":str(locked)}]})
    assert response.status_code == 200
    job = wait_job(client, response.json()["id"])
    assert job["status"] == "partial"
    good, bad = job["tasks"]
    assert good["state"] == "done" and good["outputs"][0]["size"] > 0
    assert good["source_sizes"] == [plain.stat().st_size]
    assert bad["state"] == "failed" and "PASSWORD_REQUIRED_OR_INCORRECT" in bad["error"]
    assert bad["source_sizes"] == [locked.stat().st_size]
    assert bad["outputs"] == []


def test_source_changes_invalidate_preview(service):
    client, app, root, output = service
    source = root / "one.png"
    body = {"tool": "images_pdf", "sources": [{"path": str(source)}], "preview": True}
    identity = client.post("/api/jobs", json=body).json()["id"]
    assert wait_job(client, identity)["status"] == "done"
    Image.new("RGB", (60, 60), "green").save(source)
    body.update(preview=False, output_directory=str(output))
    response = client.post(f"/api/jobs/{identity}/commit", json=body)
    assert response.status_code == 400 and "SOURCE_CHANGED" in response.text
    assert not list(output.iterdir())


def test_text_pdf_image_warnings_and_changed_dependency(service):
    from server.format_converter.browsers import browser_paths
    if not browser_paths()["edge"]:
        pytest.skip("Installed Edge is required for the Markdown integration case")
    client, app, root, output = service
    source = root / "document.md"
    source.write_text("# Text test\n\n![ok](one.png) ![missing](missing.png)", "utf-8")
    body = {"tool": "text_pdf", "sources": [{"path": str(source)}], "preview": True}
    identity = client.post("/api/jobs", json=body).json()["id"]
    complete = wait_job(client, identity)
    assert complete["status"] == "done", [task["error"] for task in complete["tasks"]]
    assert complete["tasks"][0]["warnings"] == ["IMAGE_UNAVAILABLE: missing.png"]
    Image.new("RGB", (121, 81), "yellow").save(root / "one.png")
    body.update(preview=False, output_directory=str(output))
    response = client.post(f"/api/jobs/{identity}/commit", json=body)
    assert response.status_code == 400 and "SOURCE_CHANGED" in response.text
    assert not list(output.iterdir())


@pytest.mark.parametrize("text", ["Bad formula $\\notARealCommand{x}$", "```mermaid\nflowchart this is not valid !!!\n```"])
def test_text_pdf_invalid_math_or_mermaid_fails_without_output(service, text):
    from server.format_converter.browsers import browser_paths
    if not browser_paths()["edge"]:
        pytest.skip("Installed Edge is required for the Markdown integration case")
    client, _, root, output = service
    source = root / "bad.md"
    source.write_text(text, "utf-8")
    identity = client.post("/api/jobs", json={"tool": "text_pdf", "sources": [{"path": str(source)}],
                           "output_directory": str(output)}).json()["id"]
    failed = wait_job(client, identity)
    assert failed["status"] == "failed", failed
    assert "MARKDOWN_RENDER_ERROR" in failed["tasks"][0]["error"]
    assert failed["tasks"][0]["outputs"] == [] and not list(output.iterdir())


def test_concurrent_collisions_get_unique_outputs(service):
    client, app, root, output = service
    ids = []
    for name in ("one.png", "two.png"):
        result = client.post("/api/jobs", json={"tool": "image", "sources": [{"path": str(root / name)}], "output_directory": str(output), "filename": "same.png"})
        assert result.status_code == 200, result.text
        ids.append(result.json()["id"])
    complete = [wait_job(client, identity) for identity in ids]
    assert all(job["status"] == "done" for job in complete), complete
    assert {path.name for path in output.iterdir()} == {"same.png", "same_01.png"}
    assert (output / "same.png").read_bytes() != (output / "same_01.png").read_bytes()


def test_cancel_and_retry_do_not_leave_partial_outputs(service):
    client, app, root, output = service
    body = {"tool": "images_pdf", "sources": [{"path": str(root / "one.png")}], "output_directory": str(output)}
    identity = client.post("/api/jobs", json=body).json()["id"]
    cancelled = client.post(f"/api/jobs/{identity}/cancel").json()
    assert cancelled["status"] == "cancelled"
    assert not list(output.iterdir())
    retried = client.post(f"/api/jobs/{identity}/retry").json()
    result = wait_job(client, retried["id"])
    assert result["status"] == "done", result
    assert len(list(output.iterdir())) == 1


def test_preferences_never_store_credentials_or_document_names(service):
    client, app, root, _ = service
    response = client.put("/api/preferences", json={"password": "do-not-store", "filename": "private.pdf", "language": "zh-TW", "presets": {"test": {"password": "secret", "pages": "1", "quality": 70, "filename": "private.pdf"}}})
    assert response.status_code == 200
    data = (config.DATA / "preferences.json").read_text("utf-8")
    assert "secret" not in data and "do-not-store" not in data and "private.pdf" not in data
    assert response.json()["language"] == "zh-TW"
    assert response.json()["presets"]["test"] == {"quality": 70}


def test_browser_preferences_persist_and_presets_do_not_override_them(service):
    client, _, _, _ = service
    response = client.put("/api/preferences", json={"text_browser": "firefox", "text_browser_path": "D:/Apps/Firefox/firefox.exe",
        "presets": {"old": {"text_browser": "edge", "text_browser_path": "old.exe", "quality": 70}}})
    assert response.status_code == 200
    prefs = client.get("/api/bootstrap").json()["preferences"]
    assert prefs["text_browser"] == "firefox"
    assert prefs["text_browser_path"] == "D:/Apps/Firefox/firefox.exe"
    assert prefs["presets"]["old"] == {"quality": 70}
    assert config.read_preferences()["text_browser"] == "firefox"


def test_single_output_dialog_name_cancel_and_exact_save(service, monkeypatch):
    from server.format_converter import api as api_module
    client, app, root, output = service
    body = {"tool": "images_pdf", "sources": [{"path": str(root / n)} for n in ["one.png", "two.png"]], "preview": True}
    job = wait_job(client, client.post("/api/jobs", json=body).json()["id"])
    assert job["status"] == "done"
    calls = []
    def choose(name="", directory=""):
        calls.append((name, directory))
        return {"path": ""}
    monkeypatch.setattr(api_module, "native_pick_folder", choose)
    body["filename"] = "my.report"
    chosen = client.post(f"/api/jobs/{job['id']}/pick-output", json=body)
    assert chosen.status_code == 200 and chosen.json() == {"path": "", "single": True}
    assert calls[0][0] == "my.pdf"
    assert list(output.iterdir()) == []
    body.update(preview=False, output_directory=str(output), output_filename="my.report.pdf", collision="overwrite")
    response = client.post(f"/api/jobs/{job['id']}/commit", json=body)
    assert response.status_code == 200, response.text
    assert (output / "my.report.pdf").is_file()
    assert not (output / "my.pdf").exists()


def test_multiple_outputs_use_folder_and_reject_exact_filename(service, monkeypatch):
    from server.format_converter import api as api_module
    client, _, root, output = service
    body = {"tool": "image", "sources": [{"path": str(root / n)} for n in ["one.png", "two.png"]],
        "parameters": {"format": "JPEG"}, "preview": True}
    job = wait_job(client, client.post("/api/jobs", json=body).json()["id"])
    calls = []
    monkeypatch.setattr(api_module, "native_pick_folder", lambda name, directory: calls.append(name) or {"path": str(output)})
    chosen = client.post(f"/api/jobs/{job['id']}/pick-output", json=body)
    assert chosen.json()["single"] is False and calls == [""]
    body.update(preview=False, output_directory=str(output), output_filename="wrong.jpg")
    assert client.post(f"/api/jobs/{job['id']}/commit", json=body).status_code == 400
    assert list(output.iterdir()) == []
    body["output_filename"] = ""
    assert client.post(f"/api/jobs/{job['id']}/commit", json=body).status_code == 200
    assert len(list(output.iterdir())) == 2
