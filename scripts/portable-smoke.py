"""Exercise the frozen build with synthetic files and isolated preferences."""
import http.cookiejar
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent.parent
work = root / "tests" / ".work" / "portable-smoke"
work.mkdir(parents=True, exist_ok=True)
env = os.environ | {"FORMAT_CONVERTER_DATA": str(work / "settings")}
process = subprocess.Popen([str(root / "release/FormatConverter/FormatConverter.exe"), "--no-browser", "--port", "8766"], env=env, creationflags=subprocess.CREATE_NO_WINDOW)
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
base = "http://127.0.0.1:8766"


def request(path, body=None, method=None):
    data = None if body is None else json.dumps(body).encode()
    response = opener.open(urllib.request.Request(base + "/api" + path, data=data, method=method,
                           headers={"X-Format-Converter": "1", "Content-Type": "application/json"}), timeout=10)
    return json.load(response)


def wait(identity):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        job = request(f"/jobs/{identity}")
        if job["status"] not in {"queued", "running"}:
            assert job["status"] == "done", job
            return job
        time.sleep(.2)
    raise TimeoutError("Frozen worker timed out")


try:
    deadline = time.monotonic() + 45
    while True:
        try:
            request("/session", {})
            break
        except OSError:
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError(f"Frozen service did not start; exit={process.poll()}")
            time.sleep(.3)
    request("/clients/heartbeat", {"id": "portable-smoke"})
    fixtures = root / "tests/.work/ui-fixtures"
    request("/roots", {"path": str(fixtures)})
    boot = request("/bootstrap")
    assert "HEIF" in boot["capabilities"]["encoders"]
    assert opener.open(base).read().startswith(b"<!doctype html>")
    body = {"tool": "image", "sources": [{"path": str(fixtures / "notes.heic")}], "parameters": {"format": "PNG"}, "preview": True}
    job = wait(request("/jobs", body)["id"])
    artifact = job["tasks"][0]["outputs"][0]
    expected = opener.open(base + artifact["url"]).read()
    body.update(preview=False, output_directory=str(fixtures / "output"), filename="portable-heif.png")
    committed = request(f"/jobs/{job['id']}/commit", body)
    assert Path(committed["tasks"][0]["outputs"][0]["path"]).read_bytes() == expected
    protected = wait(request("/jobs", {"tool": "encrypt", "sources": [{"path": str(fixtures / "sample.pdf")}],
                    "parameters": {"opening_password": "reader", "owner_password": "owner", "restrict": True,
                                   "allow_modify": True, "allow_print": False},
                    "output_directory": str(fixtures / "output"), "filename": "portable-protected.pdf"})["id"])
    protected_path = protected["tasks"][0]["outputs"][0]["path"]
    compressed = wait(request("/jobs", {"tool": "compress", "sources": [{"path": protected_path}],
                     "parameters": {"password": "reader"}, "preview": True})["id"])
    import pymupdf
    with pymupdf.open(stream=opener.open(base + compressed["tasks"][0]["outputs"][0]["url"]).read(), filetype="pdf") as doc:
        assert doc.needs_pass and doc.authenticate("reader") == 2
        assert not doc.permissions & pymupdf.PDF_PERM_PRINT
    job = wait(request("/jobs", {"tool": "ocr", "sources": [{"path": str(fixtures / "cover.png")}], "parameters": {"ocr_output": "txt", "ocr_language": "eng+chi_tra", "ocr_chinese_first": True}, "preview": True})["id"])
    assert job["tasks"][0]["outputs"][0]["name"].endswith(".txt")
    recognized = opener.open(base + job["tasks"][0]["outputs"][0]["url"]).read().decode("utf-8")
    assert recognized.strip(), "Frozen OCR did not recognize any text"
    request("/clients/close", {"id": "portable-smoke"})
    process.wait(timeout=40)
    assert process.returncode == 0
    result = {"service": "passed", "static_ui": "passed", "spawned_HEIF_worker": "passed", "preview_commit_bytes": "passed", "compression_preserves_encryption": "passed", "native_OCR": "passed", "ocr_text_characters": len(recognized), "close_last_client_shutdown": "passed", "temporary_clean": not any((work / "settings/temporary").iterdir())}
    (work / "result.json").write_text(json.dumps(result, indent=2), "utf-8")
    print(json.dumps(result))
finally:
    if process.poll() is None:
        import psutil
        for child in psutil.Process(process.pid).children(recursive=True):
            child.terminate()
        process.terminate()
