"""Build Windows icon and version resources from the application sources."""
import io
import json
import re
from pathlib import Path

import pymupdf
from PIL import Image
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable,
    VarFileInfo, VarStruct, VSVersionInfo,
)

root = Path(__file__).resolve().parent.parent
target = root / "build/windows-assets"
target.mkdir(parents=True, exist_ok=True)
version = json.loads((root / "package.json").read_text("utf-8"))["version"]
match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-([\w.-]+))?", version)
if not match:
    raise ValueError(f"Unsupported Windows product version: {version}")
numbers = tuple(int(match[i]) for i in (1, 2, 3)) + (0,)
if any(number > 65535 for number in numbers):
    raise ValueError("Windows version components must not exceed 65535")

with pymupdf.open(root / "public/favicon.svg") as document:
    page = document[0]
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1024 / page.rect.width, 1024 / page.rect.height), alpha=True)
    with Image.open(io.BytesIO(pixmap.tobytes("png"))) as image:
        image.save(target / "FormatConverter.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])

# Tk 8.6 reads DIB icon frames itself; PNG-compressed ICO frames can fall
# back to shell extraction. Render each size directly for title bars and DPI scales.
with pymupdf.open(root / "public/favicon.svg") as document:
    page = document[0]
    frames = []
    for edge in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256):
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(edge / page.rect.width, edge / page.rect.height), alpha=True)
        with Image.open(io.BytesIO(pixmap.tobytes("png"))) as image:
            frames.append(image.convert("RGBA"))
    frames[-1].save(target / "FormatConverter-tk.ico", format="ICO", bitmap_format="bmp",
        sizes=[frame.size for frame in frames], append_images=frames[:-1])

fields = {
    "CompanyName": "Ethan DevLab",
    "FileDescription": "Format Converter",
    "FileVersion": version,
    "InternalName": "FormatConverter",
    "LegalCopyright": "© 2026 Ethan DevLab. All rights reserved.",
    "OriginalFilename": "FormatConverter.exe",
    "ProductName": "Format Converter",
    "ProductVersion": version,
}
resource = VSVersionInfo(
    ffi=FixedFileInfo(filevers=numbers, prodvers=numbers, mask=0x3F,
                      flags=0x02 if match[4] else 0, OS=0x40004,
                      fileType=0x1, subtype=0, date=(0, 0)),
    kids=[StringFileInfo([StringTable("040904B0", [StringStruct(key, value) for key, value in fields.items()])]),
          VarFileInfo([VarStruct("Translation", [1033, 1200])])],
)
(target / "version-info.txt").write_text(str(resource), encoding="utf-8")
print(f"Windows resources: {version}, numeric {'.'.join(map(str, numbers))}, seven icon sizes")
