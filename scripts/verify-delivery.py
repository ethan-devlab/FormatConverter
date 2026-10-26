"""Check local preview versions, notices, resources, source and portable bytes."""
import ast
import argparse
import hashlib
import importlib.metadata
import json
import re
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import pefile
from packaging.version import Version
from packaging.utils import canonicalize_name

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
profiles = parser.add_mutually_exclusive_group()
profiles.add_argument("--slim", action="store_true")
profiles.add_argument("--slim2", action="store_true")
args = parser.parse_args()
delivery = root / ("release/slim2" if args.slim2 else "release/slim" if args.slim else "release")
folder = delivery / "FormatConverter"
checks = []


def check(condition, name):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


def digest(data):
    return hashlib.sha256(data).hexdigest()


package = json.loads((root / "package.json").read_text("utf-8"))
project = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))["project"]
tree = ast.parse((root / "server/format_converter/config.py").read_text("utf-8"))
server_version = next(ast.literal_eval(node.value) for node in tree.body
                      if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in node.targets))
check(package["version"] == server_version and Version(package["version"]) == Version(project["version"]), "Application versions agree")
check(package["license"] == project["license"] == "AGPL-3.0-only", "Application license declarations agree")
exe = folder / "FormatConverter.exe"
pe = pefile.PE(str(exe))
check(pe.FILE_HEADER.Machine == 0x8664, "Executable is Windows x64")
fields = {}
for block in pe.FileInfo:
    for info in block:
        for table in getattr(info, "StringTable", []):
            fields.update({k.decode(): v.decode("utf-8") for k, v in table.entries.items()})
check(fields.get("ProductVersion") == fields.get("FileVersion") == package["version"], "Executable version strings agree")
check(fields.get("CompanyName") == "Ethan DevLab" and fields.get("ProductName") == "Format Converter"
      and fields.get("LegalCopyright") == "© 2026 Ethan DevLab. All rights reserved.", "Executable branding metadata agrees")
check(any(entry.id == 14 for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries), "Executable contains an icon group")
frontend = root / ("build/slim2-web" if args.slim2 else "dist")
for source in frontend.rglob("*"):
    if source.is_file():
        check(source.read_bytes() == (folder / "_internal/dist" / source.relative_to(frontend)).read_bytes(),
              f"Built frontend matches: {source.relative_to(root)}")
manifest = json.loads((root / "resources/tessdata/manifest.json").read_text())
for name, expected in manifest["files"].items():
    for base in (root / "resources/tessdata", folder / "_internal/resources/tessdata"):
        data = (base / name).read_bytes()
        check(len(data) == expected["bytes"] and digest(data) == expected["sha256"], f"Pinned OCR data matches: {base.name}/{name}")
check((root / "resources/tessdata/manifest.json").read_bytes() == (folder / "_internal/resources/tessdata/manifest.json").read_bytes(), "OCR manifest included")
for source in [root / name for name in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "DESIGN.md")]:
    check(source.read_bytes() == (folder / source.name).read_bytes(), f"Top-level document matches: {source.name}")
for source in (root / "docs").rglob("*"):
    if source.is_file():
        check(source.read_bytes() == (folder / source.relative_to(root)).read_bytes(), f"Bundled document matches: {source.relative_to(root)}")
for target in re.findall(r"\]\(([^)]+)\)", (folder / "README.md").read_text("utf-8")):
    if ":" not in target:
        check((folder / target.split("#")[0]).exists(), f"Portable README link resolves: {target}")
python_inventory = json.loads((folder / "licenses/python-inventory.json").read_text("utf-8"))
javascript_inventory = json.loads((folder / "licenses/javascript-inventory.json").read_text("utf-8"))
python_versions = {canonicalize_name(row["name"]): row["version"] for row in python_inventory}
for name in ("fastapi", "uvicorn", "pymupdf", "pillow", "pillow-heif", "watchfiles", "psutil"):
    check(python_versions[name] == importlib.metadata.version(name), f"Python inventory version: {name}")
javascript_versions = {row["name"]: row["version"] for row in javascript_inventory}
for name in package["dependencies"]:
    actual = json.loads((root / "node_modules" / name / "package.json").read_text("utf-8"))
    check(javascript_versions.get(name) == actual["version"], f"JavaScript inventory version: {name}")
for name in ("inventory-scope.json", "native-capabilities.json", "tessdata-LICENSE"):
    check((folder / "licenses" / name).is_file(), f"Notice metadata included: {name}")
with ZipFile(folder / "application-source.zip") as archive:
    check(archive.testzip() is None, "Source ZIP CRC")
    for name in archive.namelist():
        parts = Path(name).parts
        check(not any(part in {".work", ".git", ".venv", "node_modules", ".codegraph", "__pycache__"} or part.startswith(".env") for part in parts)
              and not name.endswith(".traineddata"), f"Source exclusion: {name}")
        check(archive.read(name) == (root / name).read_bytes(), f"Source matches workspace: {name}")
    check("resources/tessdata/manifest.json" in archive.namelist(), "Source contains pinned OCR manifest")
for name in ("pymupdf/layout", "pymupdf/mupdf-devel", "numpy", "numpy.libs", "onnxruntime"):
    check(not (folder / "_internal" / name).exists(), f"Optional payload excluded: {name}")
if not args.slim:
    check(not list((folder / "_internal").rglob("*.py")), "No duplicate Python source payload")
    check(not list((folder / "_internal/dist").rglob("*.woff")), "No WOFF fallback payload")
target = delivery / "FormatConverter-windows-x64.zip"
zip_hash = digest(target.read_bytes())
check((delivery / "SHA256SUMS").read_text().strip() == f"{zip_hash}  {target.name}", "Portable checksum file agrees")
with ZipFile(target) as archive:
    check(archive.testzip() is None, "Portable ZIP CRC")
    expected = {"FormatConverter/" + path.relative_to(folder).as_posix(): path for path in folder.rglob("*") if path.is_file()}
    check(set(archive.namelist()) == set(expected), "Portable ZIP file inventory agrees")
    for name, path in expected.items():
        check(digest(archive.read(name)) == digest(path.read_bytes()), f"Portable entry matches: {name}")
report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "version": package["version"],
          "scope": "Local unsigned developer preview; not public-release legal approval or clean-machine validation",
          "checks_passed": len(checks), "python_packages": len(python_inventory), "javascript_packages": len(javascript_inventory),
          "portable_sha256": zip_hash, "executable_sha256": digest(exe.read_bytes()), "checks": checks}
(delivery / "delivery-verification.json").write_text(json.dumps(report, indent=2), "utf-8")
print(json.dumps({key: value for key, value in report.items() if key != "checks"}, indent=2))
