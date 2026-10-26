"""Create synthetic, project-local files for manual QA."""
from pathlib import Path
import json

import pymupdf as fitz
from PIL import Image, ImageDraw
from pillow_heif import register_heif_opener

register_heif_opener()
root = Path(__file__).resolve().parents[1] / "tests" / ".work" / "ui-fixtures"
root.mkdir(parents=True, exist_ok=True)
(root / "output").mkdir(exist_ok=True)
for name, color in [("cover.png", "#a34f37"), ("chart.png", "#c78b70"), ("notes.heic", "#e3c8b6")]:
    path = root / name
    if not path.exists():
        image = Image.new("RGB", (900, 1200), "#f8f6f2")
        draw = ImageDraw.Draw(image)
        draw.rectangle((80, 100, 820, 480), fill=color)
        draw.text((100, 540), "FORMAT CONVERTER - SYNTHETIC TEST FILE", fill="#28231f")
        image.save(path, format="HEIF" if path.suffix == ".heic" else "PNG")
path = root / "sample.pdf"
if not path.exists():
    with fitz.open() as doc:
        for index in range(3):
            page = doc.new_page()
            page.insert_text((60, 80), f"Format Converter test page {index + 1}", fontsize=24)
            page.draw_rect(fitz.Rect(60, 130, 500, 350), fill=(0.64, 0.31, 0.22))
        doc.set_toc([[1, "Cover", 1], [1, "Second page", 2]])
        doc.save(path)
(root / ".hidden-test.txt").write_text("Synthetic hidden-file fixture.", "utf-8")
(root / ".fixture-manifest.json").write_text(json.dumps({"application": "format-converter-qa", "synthetic": True}), "utf-8")
print(root)
