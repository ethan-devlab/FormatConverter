from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).parent
profile = os.environ.get("FORMAT_CONVERTER_SLIM", "2")
slim = profile in {"1", "2"}
frontend = root / os.environ.get("FORMAT_CONVERTER_FRONTEND", "dist")
datas = [(str(frontend), "dist"), (str(root / "resources"), "resources")]
datas.append((str(root / "build/windows-assets/FormatConverter-tk.ico"), "resources"))
binaries = []
hiddenimports = ["server.format_converter.api", "server.format_converter.picker", "tkinter", "tkinter.filedialog"]
for package in ("pymupdf", "pillow_heif", "watchfiles"):
    options = {}
    if profile == "2":
        # Executable modules are already in PYZ; these packages do not need source data.
        options["include_py_files"] = False
    if slim and package == "pymupdf":
        # The application uses PDF primitives, not the optional ONNX layout models.
        options.update(filter_submodules=lambda name: not name.startswith("pymupdf.layout"),
                       exclude_datas=["layout/**", "mupdf-devel/**"])
    data, binary, hidden = collect_all(package, **options)
    if slim and package == "pymupdf":
        binary = [item for item in binary if not item[1].startswith(("pymupdf/layout", "pymupdf\\layout"))]
    datas += data
    binaries += binary
    hiddenimports += hidden
a = Analysis([str(root / "scripts" / "portable-entry.py")], pathex=[str(root)],
             binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             excludes=["pymupdf.layout", "onnxruntime", "numpy"] if slim else [])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="FormatConverter",
          icon=str(root / "build/windows-assets/FormatConverter.ico"),
          version=str(root / "build/windows-assets/version-info.txt"),
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="FormatConverter")
