import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent.parent
folder = root / "release/FormatConverter"
target = root / "release/FormatConverter-windows-x64.zip"
with ZipFile(target, "w", ZIP_DEFLATED, compresslevel=6) as archive:
    for source in folder.rglob("*"):
        if source.is_file() and not source.is_symlink():
            archive.write(source, source.relative_to(folder.parent).as_posix())
digest = hashlib.file_digest(target.open("rb"), "sha256").hexdigest()
(target.parent / "SHA256SUMS").write_text(f"{digest}  {target.name}\n", "ascii")
print(f"{target.name}: {target.stat().st_size} bytes\nSHA256 {digest}")
