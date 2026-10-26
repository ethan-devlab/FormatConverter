"""Compare frozen builds with isolated synthetic fixtures. Never use UI fixtures."""
import argparse
import hashlib
import http.cookiejar
import io
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import psutil
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from pillow_heif import register_heif_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

parser = argparse.ArgumentParser()
parser.add_argument("executable", type=Path)
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--work", type=Path, required=True)
parser.add_argument("--text-pdf", action="store_true")
args = parser.parse_args()
work = args.work.resolve()
work.mkdir(parents=True, exist_ok=False)
sources = work / "sources"
sources.mkdir()
output = work / "output"
output.mkdir()
register_heif_opener()
image = Image.new("RGBA", (320, 160), (180, 90, 60, 128))
image.save(sources / "alpha.png")
image.convert("RGB").save(sources / "source.heic", format="HEIF")
image.save(sources / "frames.tiff", save_all=True,
           append_images=[Image.new("RGBA", image.size, "yellow")])
scan = Image.new("RGB", (1600, 400), "white")
draw = ImageDraw.Draw(scan)
draw.text((30, 30), "FORMAT CONVERTER TEST", fill="black",
          font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 60))
draw.text((30, 160), "繁體中文測試", fill="black",
          font=ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 80))
scan.save(sources / "scan.png")
with fitz.open() as doc:
    for index in range(3):
        page = doc.new_page()
        page.insert_text((40, 70), f"SYNTHETIC PAGE {index + 1}", fontsize=24)
        page.insert_image(fitz.Rect(40, 110, 360, 270), filename=str(sources / "alpha.png"))
    doc.save(sources / "sample.pdf")
with fitz.open() as doc:
    page = doc.new_page(width=800, height=200)
    page.insert_image(page.rect, filename=str(sources / "scan.png"))
    doc.save(sources / "scan.pdf")
hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources.iterdir()}
base = f"http://127.0.0.1:{args.port}"
with socket.socket() as probe:
    assert probe.connect_ex(("127.0.0.1", args.port)) != 0, "Test port is occupied"
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
process = subprocess.Popen([str(args.executable.resolve()), "--no-browser", "--port", str(args.port)],
                           env=os.environ | {"FORMAT_CONVERTER_DATA": str(work / "settings")},
                           creationflags=subprocess.CREATE_NO_WINDOW)
checks = []
signatures = {}


def request(path, body=None):
    payload = None if body is None else json.dumps(body).encode()
    response = opener.open(urllib.request.Request(base + "/api" + path, data=payload,
                           headers={"Content-Type": "application/json", "X-Format-Converter": "1"}), timeout=15)
    return json.load(response)


def run(name, tool, filenames, **parameters):
    body = {"tool": tool, "sources": [{"path": str(sources / f)} for f in filenames],
            "parameters": parameters, "preview": True}
    job = request("/jobs", body)
    deadline = time.monotonic() + 120
    while job["status"] in {"queued", "running"}:
        assert time.monotonic() < deadline, f"Timeout: {name}"
        request("/clients/heartbeat", {"id": "slim-smoke"})
        time.sleep(.15)
        job = request(f"/jobs/{job['id']}")
    assert job["status"] == "done", (name, job)
    artifacts = [a for task in job["tasks"] for a in task["outputs"]]
    blobs = [opener.open(base + a["url"]).read() for a in artifacts]
    commit = request(f"/jobs/{job['id']}/commit", body | {"preview": False,
                     "output_directory": str(output), "filename": name})
    paths = [Path(a["path"]) for task in commit["tasks"] for a in task["outputs"]]
    assert [p.read_bytes() for p in paths] == blobs, f"Preview/commit mismatch: {name}"
    signature = []
    for artifact, blob in zip(artifacts, blobs):
        suffix = Path(artifact["name"]).suffix.lower()
        if suffix == ".pdf":
            with fitz.open(stream=blob, filetype="pdf") as doc:
                if doc.needs_pass:
                    assert doc.authenticate("reader") == 2
                    assert not doc.permissions & fitz.PDF_PERM_PRINT
                signature.append({"pages": len(doc), "text": [p.get_text() for p in doc],
                                  "renders": [hashlib.sha256(p.get_pixmap().samples).hexdigest() for p in doc]})
        elif suffix == ".txt":
            signature.append(blob.decode("utf-8"))
        else:
            with Image.open(io.BytesIO(blob)) as result:
                result.load()
                signature.append({"size": result.size, "pixels": hashlib.sha256(result.convert("RGBA").tobytes()).hexdigest(),
                                  "ico_sizes": sorted(result.ico.sizes()) if suffix == ".ico" else []})
    signatures[name] = signature
    checks.append(name)
    print(f"PASS {name}", flush=True)
    return paths, signature


try:
    deadline = time.monotonic() + 45
    while True:
        try:
            request("/session", {})
            break
        except OSError:
            assert process.poll() is None and time.monotonic() < deadline, "Service startup failed"
            time.sleep(.2)
    request("/clients/heartbeat", {"id": "slim-smoke"})
    request("/roots", {"path": str(sources)})
    request("/roots", {"path": str(output)})
    assert opener.open(base).read().startswith(b"<!doctype html>")
    for fmt in ("PNG", "JPEG", "WEBP", "TIFF", "BMP", "ICO", "HEIF", "AVIF"):
        run(f"image-{fmt}", "image", ["alpha.png"], format=fmt)
    run("heif-decode", "image", ["source.heic"], format="PNG", width=160, rotation=90)
    run("tiff-all", "image", ["frames.tiff"], format="PNG")
    run("tiff-first", "image", ["frames.tiff"], format="PNG", frames="first")
    run("images-pdf", "images_pdf", ["frames.tiff"])
    run("render", "pdf_images", ["sample.pdf"], pages="3,1", dpi=96)
    for fmt in ("PNG", "JPEG"):
        run(f"extract-{fmt}", "pdf_images", ["sample.pdf"], extract_images=True, format=fmt)
    run("text", "pdf_text", ["sample.pdf"], pages="3,1")
    run("merge", "merge", ["sample.pdf", "sample.pdf"], pages="2,1")
    run("organize", "organize", ["sample.pdf"], pages="3,1", rotation=90)
    for mode in ("lossless", "lossy"):
        run(f"compress-{mode}", "compress", ["sample.pdf"], compression=mode)
    protected, _ = run("encrypt", "encrypt", ["sample.pdf"], opening_password="reader",
                       owner_password="owner", restrict=True, allow_print=False, allow_modify=True)
    # Outputs are inside an explicitly registered root; absolute paths stay local.
    run("protected-compress", "compress", [str(protected[0])], password="reader")
    run("decrypt", "decrypt", [str(protected[0])], password="owner")
    for language in ("eng", "chi_tra", "eng+chi_tra"):
        _, result = run(f"ocr-{language}", "ocr", ["scan.png"], ocr_language=language, ocr_output="txt")
        text = "".join(result[0].split())
        assert ("CONVERTER" in text if language == "eng" else "中文" in text), result
    _, result = run("ocr-searchable", "ocr", ["scan.pdf"], ocr_language="eng+chi_tra", ocr_output="pdf")
    assert "CONVERTER" in result[0]["text"][0]
    if args.text_pdf:
        (sources / "notes.txt").write_text("English 繁體中文測試\n\nSecond paragraph\n" + "longword" * 80, "utf-8")
        (sources / "notes.md").write_text('# Markdown TEST\n\n繁體中文測試 $E=mc^2$.\n\n$$\\frac{a}{b}$$\n\n'
            '```mermaid\nflowchart LR\n A[Start] --> B[Finish]\n```\n\n'
            '```mermaid\nsequenceDiagram\n Alice->>Bob: Hello\n```\n\n'
            '![ok](alpha.png) ![missing](missing.png)\n\nFINAL MARKER', "utf-8")
        run("plain-text-pdf", "text_pdf", ["notes.txt"])
        for engine in ("edge", "chrome", "firefox"):
            run(f"markdown-{engine}", "text_pdf", ["notes.md"], text_browser=engine)
        (sources / "bad.txt").write_bytes(b"\xff\xff")
        body = {"tool": "text_pdf", "sources": [{"path": str(sources / name)} for name in ("notes.txt", "bad.txt")], "preview": True}
        batch = request("/jobs", body)
        deadline = time.monotonic() + 60
        while batch["status"] in {"queued", "running"}:
            assert time.monotonic() < deadline
            time.sleep(.1)
            batch = request(f"/jobs/{batch['id']}")
        assert batch["status"] == "partial" and "TEXT_ENCODING_ERROR" in batch["tasks"][1]["error"]
        checks.append("mixed-text-batch-error")
        (sources / "cancel.md").write_text("```mermaid\nflowchart LR\n A-->B\n```\n\n" * 200, "utf-8")
        cancel = request("/jobs", {"tool": "text_pdf", "sources": [{"path": str(sources / "cancel.md")}], "preview": True})
        owned = []
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            from server.format_converter.browsers import browser_processes
            owned = browser_processes((work / "settings/temporary").glob("*/*/*/browser-profile-*"))
            if owned:
                break
            time.sleep(.1)
        assert owned, "Cancellation test did not reach a browser process"
        assert request(f"/jobs/{cancel['id']}/cancel", {})["status"] == "cancelled"
        _, alive = psutil.wait_procs(owned, timeout=10)
        assert not alive, "Cancelled browser children remain alive"
        checks.append("markdown-cancel-cleans-browser")
        # Keep the original fixture oracle separate from files created for this extension.
        assert hashes == {name: hashlib.sha256((sources / name).read_bytes()).hexdigest() for name in hashes}
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources.iterdir()}
    assert hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources.iterdir()}
    request("/clients/close", {"id": "slim-smoke"})
    process.wait(timeout=45)
    assert process.returncode == 0
    assert not any((work / "settings/temporary").iterdir())
    result = {"executable": str(args.executable.resolve()), "checks": checks, "source_hashes_unchanged": True,
              "normal_shutdown": True, "temporary_clean": True, "signatures": signatures}
    (work / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    print(f"PASS {len(checks)} frozen scenarios; shutdown and cleanup", flush=True)
finally:
    if process.poll() is None:
        for child in psutil.Process(process.pid).children(recursive=True):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        process.terminate()
        process.wait(timeout=10)
