"""Fetch the two official tessdata_fast language packs for offline OCR."""
from pathlib import Path
from urllib.request import urlopen
import hashlib
import json

folder = Path(__file__).resolve().parent.parent / "resources/tessdata"
folder.mkdir(parents=True, exist_ok=True)
manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
for name, expected in manifest["files"].items():
    with urlopen(f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{manifest['revision']}/{name}", timeout=60) as response:
        data = response.read()
    if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
        raise ValueError(f"OCR data integrity check failed: {name}")
    (folder / name).write_bytes(data)
    print(f"Saved {name}: {len(data)} bytes")
