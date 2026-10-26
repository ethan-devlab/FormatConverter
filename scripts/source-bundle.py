"""Archive application source using repository-relative names."""
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent.parent
names = ("src", "server", "scripts", "public", "docs", "tests", "package.json", "pnpm-lock.yaml",
         "pyproject.toml", "uv.lock", "vite.config.ts", "vite.markdown.config.ts", "tsconfig.json", "index.html", "LICENSE",
         "README.md", "THIRD_PARTY_NOTICES.md", "DESIGN.md", ".python-version", ".npmrc",
         "resources/tessdata/LICENSE", "resources/tessdata/manifest.json", ".gitignore")
with ZipFile(sys.argv[1], "w", ZIP_DEFLATED) as archive:
    for name in names:
        path = root / name
        for source in path.rglob("*") if path.is_dir() else [path]:
            relative = source.relative_to(root)
            if source.is_file() and not source.is_symlink() and not any(p in {"__pycache__", ".work", ".pytest_cache"} for p in relative.parts):
                archive.write(source, relative.as_posix())
