# Development and packaging

## Environment

The supported development and packaging target is Windows x64. Use Python 3.13,
Node.js 24.22.1, pnpm 11.17.0 and uv. The exact JavaScript dependency resolution
is in pnpm-lock.yaml; Python resolution is in uv.lock. Do not update dependencies
as part of a routine build.

```powershell
pnpm install --frozen-lockfile
uv sync --locked
.venv/Scripts/python.exe scripts/fetch-ocr-data.py
pnpm dev
```

The frontend is at http://127.0.0.1:5173 and the service at port 8765. Use the
existing Python environment created by uv. The OCR fetcher verifies pinned
commit, length and SHA-256 before replacing English/Traditional Chinese data.
Markdown needs an installed Edge, Chrome or Firefox. Browser selection is a
user preference; there is no implicit engine fallback or browser download.

## Checks

```powershell
pnpm check
pnpm test:explorer
pnpm test:ico
pnpm test:feedback
pnpm test:navigation
uv run pytest -q --basetemp="$env:TEMP/fc-tests"
pnpm build
```

Use a fresh, short --basetemp directory for a new test run. Deep checkout-local
paths can exceed native browser path limits after profile files are added.
Tests generate synthetic
inputs; do not use private documents. Set FORMAT_CONVERTER_DATA to a dedicated
local directory when manually testing an isolated service. Test outputs,
preferences and downloaded OCR models must not enter Git.

Build the frontend before browser-engine smoke tests. This command runs installed
engines against synthetic Markdown and retains its output in a new work directory:

```powershell
.venv/Scripts/python.exe scripts/text-pdf-smoke.py --work tests/.work/text-engine-check
```

## Windows packaging

```powershell
pnpm package:windows
pnpm verify:delivery
```

The packager builds both frontend bundles, generates multi-size brand icons and
Windows version resources, and uses PyInstaller to bundle Python and native
libraries. The default compact profile excludes optional PDF layout models,
ONNX/NumPy and duplicate sources. WOFF2 fonts, OCR language packs, HEIF codecs
and Tcl/Tk dialogs remain included. No extra browser binary is bundled.

The delivery directory is release/FormatConverter and the archive is
release/FormatConverter-windows-x64.zip. The build creates checksums, dependency
inventories/notices and matching application source. Keep the complete _internal
folder beside the executable. Artifacts are ignored by Git.

pnpm finalize:delivery refreshes source, documents, notices and checksums around
an existing executable; it does not rebuild application code. Use it only when
those artifacts already correspond to that executable. After code changes, run
the full package command. Packaging verification compares current build bytes
and does not prove clean-machine behavior.

A built executable can be tested independently with synthetic fixtures:

```powershell
.venv/Scripts/python.exe scripts/slim-portable-smoke.py release/FormatConverter/FormatConverter.exe --port 8788 --work tests/.work/portable-check --text-pdf
```

Choose an unused port; do not stop an unknown process. Close the test client's
tabs and verify its session cleanup. The script name records its original
compact-build purpose; it now checks the default compact package too.

## Maintained scripts

| Script | Purpose |
| --- | --- |
| dev.mjs | Start frontend and local development service together. |
| fetch-ocr-data.py | Download and verify pinned OCR language data. |
| create-fixtures.py | Generate project-local synthetic files for manual checks. |
| package-windows.mjs, FormatConverter.spec, portable-entry.py | Build the Windows portable service. |
| windows-assets.py | Generate Windows icon and version resources. |
| finalize-delivery.mjs | Refresh package documents, source, notices and archives. |
| collect-notices.py | Collect installed dependency notices and inventories. |
| source-bundle.py | Create the maintained application source archive. |
| archive-portable.py | Archive the portable folder and calculate its checksum. |
| verify-delivery.py | Check versions, resources, inventories and package contents. |
| portable-smoke.py, slim-portable-smoke.py | Exercise a built local executable. |
| text-pdf-smoke.py | Exercise installed Markdown engines with synthetic files. |

Benchmark experiments and Safari GUI probes are not part of this source release.
Regression tests for maintained behavior remain under tests/.

## Binary redistribution

This source publication is not a binary release. Before distributing a portable,
provide the matching application source, applicable notices and corresponding
source/build material for bundled copyleft native dependencies. Generated
inventories and lockfiles do not by themselves satisfy every redistribution
requirement. See THIRD_PARTY_NOTICES.md. Developer ID/code signing, notarization,
clean Windows validation and macOS/Linux packages are separate work.
