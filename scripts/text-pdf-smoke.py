"""Exercise installed Markdown engines with synthetic local documents."""
import argparse
import json
import sys
from multiprocessing import get_context
from pathlib import Path

import pymupdf as fitz
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.format_converter.conversion import run_conversion
from server.format_converter.config import TESSDATA
from server.format_converter.browsers import browser_paths

parser = argparse.ArgumentParser()
parser.add_argument("--work", type=Path, required=True)
args = parser.parse_args()
work = args.work.resolve()
work.mkdir(parents=True, exist_ok=False)
fixtures = work / "sources"
fixtures.mkdir()
Image.new("RGB", (320, 160), "#a34f37").save(fixtures / "picture.png")
Image.new("RGB", (20, 20), "red").save(work / "outside.png")
markdown = r"""# Markdown engine test

English and 繁體中文測試. **Bold**, *italic*, ~~removed~~ and [a link](https://example.com).

| Column A | Column B |
|---|---|
| Alpha | 中文 |

1. First item
2. Second item

> Quoted text

Inline formula $E=mc^2$.

$$
\frac{a+b}{c}=\sqrt{x}
$$

```mermaid
flowchart LR
  A[開始 Start] --> B[轉換 Convert]
```

```mermaid
sequenceDiagram
  Alice->>Bob: Hello
  Bob-->>Alice: Ready
```

![embedded image](picture.png)
![missing image](missing.png)
![outside image](../outside.png)
![remote image](https://example.com/private.png)

<script>window.BAD_SOURCE_HTML = true</script>

```python
print("Code block")
```

FINAL MARKER
"""
source = fixtures / "document.md"
source.write_text(markdown, "utf-8")
results = []
for engine, path in browser_paths().items():
    if not path:
        results.append({"engine": engine, "status": "unavailable"})
        continue
    out = work / engine
    out.mkdir()
    result = run_conversion("text_pdf", [{"path": str(source)}], {"text_browser": engine, "_allowed_roots": [str(fixtures)]},
                            str(out), str(TESSDATA), get_context("spawn").Value("d", 0))
    pdf = Path(result["outputs"][0]["path"])
    with fitz.open(pdf) as doc:
        text = "\n".join(p.get_text() for p in doc)
        assert "FINAL MARKER" in text and "繁體中文測試" in text, text
        assert "Alice" in text and "Bob" in text, text
        assert "missing image" in text and "outside image" in text and "remote image" in text
        assert len(result["warnings"]) == 3, result["warnings"]
        assert len(result["dependencies"]) == 1
        assert sum(len(p.get_images()) for p in doc) >= 1
        assert sum(len(p.get_drawings()) for p in doc) > 5
        assert all(abs(p.rect.width - 595.276) < 1 for p in doc)
        doc[0].get_pixmap(matrix=fitz.Matrix(1.2, 1.2)).save(str(out / "page-1.png"))
        results.append({"engine": engine, "status": "passed", "pages": len(doc), "pdf_bytes": pdf.stat().st_size,
                        "warnings": result["warnings"], "text": text})
    print(f"PASS {engine}", flush=True)
(work / "result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), "utf-8")
