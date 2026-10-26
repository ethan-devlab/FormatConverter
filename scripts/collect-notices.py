import importlib.metadata as metadata
import json
import os
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
target = Path(sys.argv[1]) / "licenses"
target.mkdir(parents=True, exist_ok=True)
inventory = []
javascript_inventory = {}
for dist in metadata.distributions():
    name = dist.metadata["Name"]
    inventory.append({"name": name, "version": dist.version, "license": dist.metadata.get("License-Expression") or dist.metadata.get("License", "See bundled license"), "source": dist.metadata.get_all("Project-URL", [])})
    for file in dist.files or []:
        if any(word in file.name.lower() for word in ("license", "copying", "notice")):
            source = Path(dist.locate_file(file))
            if source.is_file():
                destination = target / "python" / name / str(file)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
for package in (root / "node_modules" / ".pnpm").iterdir():
    modules = package / "node_modules"
    if not modules.is_dir():
        continue
    candidates = []
    for entry in modules.iterdir():
        candidates.extend(entry.iterdir() if entry.name.startswith("@") and entry.is_dir() else [entry])
    for candidate in candidates:
        if not candidate.is_dir() or candidate.is_symlink() or candidate.is_junction():
            continue
        package_file = candidate / "package.json"
        if package_file.is_file():
            package_data = json.loads(package_file.read_text("utf-8"))
            key = (package_data.get("name", candidate.name), package_data.get("version", "unknown"))
            javascript_inventory[key] = {"name": key[0], "version": key[1],
                                         "license": package_data.get("license", "See collected license"),
                                         "repository": package_data.get("repository")}
        for directory, directories, files in os.walk(candidate, followlinks=False):
            directories[:] = [name for name in directories if name != "node_modules" and not Path(directory, name).is_symlink() and not Path(directory, name).is_junction()]
            for name in files:
                if name.lower().startswith(("license", "copying", "notice")):
                    source = Path(directory, name)
                    destination = target / "javascript" / modules.parent.name / source.relative_to(modules)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
(target / "python-inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), "utf-8")
(target / "javascript-inventory.json").write_text(json.dumps(sorted(javascript_inventory.values(), key=lambda item: (item["name"], item["version"])), ensure_ascii=False, indent=2), "utf-8")
(target / "inventory-scope.json").write_text(json.dumps({"scope": "Installed build environment; includes development tools and transitive packages. This is not a runtime-only SBOM or a legal compliance certification.", "python_count": len(inventory), "javascript_count": len(javascript_inventory)}, indent=2), "utf-8")
from pillow_heif import libheif_info
from PIL import features
import pymupdf
(target / "native-capabilities.json").write_text(json.dumps({"heif": libheif_info(), "pillow": {name: features.version(name) for name in features.get_supported()}, "pymupdf": pymupdf.version}, indent=2), "utf-8")
shutil.copyfile(root / "resources" / "tessdata" / "LICENSE", target / "tessdata-LICENSE")
