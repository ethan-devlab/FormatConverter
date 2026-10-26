# Format Converter

A local file conversion workspace for Windows, built by **Ethan DevLab**.
Convert PDF, images and text, preview the actual result, and manage files from
one browser-based workspace. Documents stay on your computer.

**Status:** `0.1.0-dev` developer preview. Windows x64 is the supported target.
macOS and Linux are not supported releases. Safari integration and further
Safari validation are pending.

## Features

| Area | Tools |
| --- | --- |
| PDF | Images to PDF, PDF to images or text, merge, organize/split/rotate, encrypt, decrypt and compress. |
| Images | PNG, JPEG, WebP, TIFF, BMP, ICO, HEIF and AVIF where the installed codec is available; resize, crop, rotate and metadata controls. |
| Text | TXT and formatted Markdown to PDF, with local images, KaTeX formulas and Mermaid diagrams. |
| OCR | Offline English, Traditional Chinese and mixed recognition; TXT or searchable PDF. |
| Workspace | Watched folder tree, drag-and-drop ordering, batch actions, parameter presets, cancellation and retry. |
| Preview | Actual temporary output, expanded viewer and per-file measured sizes for image conversion and PDF compression. |

The interface uses English by default and also supports Traditional Chinese.
Its responsive layout uses Fluent UI, warm neutral colors and OKLCH tokens.

## Run from source

Use **Windows x64**, Python **3.13**, Node.js **24.22.1**, pnpm **11.17.0** and uv.
The Node and pnpm versions are declared in `package.json`; Python dependencies
are locked in `uv.lock`.

```powershell
git clone https://github.com/ethan-devlab/FormatConverter.git
Set-Location FormatConverter
pnpm install --frozen-lockfile
uv sync --locked
.venv/Scripts/python.exe scripts/fetch-ocr-data.py
pnpm dev
```

Open **http://127.0.0.1:5173**. The frontend proxies requests to the loopback
service at port 8765. Stop the development process with Ctrl+C.
The OCR download is a setup step; downloaded data is hash-checked against the
pinned manifest. Conversion does not send documents to a remote service.

TXT conversion needs no external browser engine. Markdown PDF generation needs
an installed **Edge, Chrome or Firefox**. Select the engine in **Settings**;
leave **Browser executable** empty for detection or provide its executable path.
The selection survives refresh and restart. The app does not download browsers.

## Convert a file

1. Add a folder in **Files**, then drag files into the queue, or use **Add files**.
2. Select a tool, arrange the queue and set its parameters.
3. Choose **Preview** and inspect the generated output.
4. Choose **Convert**. One actual output opens **Save As** with a proposed name;
   multiple outputs open a destination folder dialog.

Queue removal does not delete source files. Explorer deletion requires
confirmation and uses the Recycle Bin. See the [user guide](docs/user-guide.md)
for shortcuts, PDF password roles, Markdown images, output conflicts and limits.

## Windows portable build

Build locally with:

```powershell
pnpm package:windows
```

The result is `release/FormatConverter-windows-x64.zip`. Extract it into a
writable folder and run `FormatConverter/FormatConverter.exe`. Keep `_internal`
beside the executable. Node, pnpm and Python are not required on the destination
computer; Markdown still needs a supported installed browser.

The executable is unsigned. This repository publishes source; it does not imply
that a downloadable binary release exists. See the [build guide](docs/development.md)
for verification and the separate native-dependency source requirements before
redistributing binaries.

## Privacy

The service binds to `127.0.0.1`. File uploads go to that local service.
Preferences, including registered folder paths and browser engine settings, are
stored under `%LOCALAPPDATA%/EthanDevLab/FormatConverter/`. Passwords, document
contents and job history are not saved as preferences. Temporary uploads and
previews are session-owned and cleaned at shutdown or on a later startup after
an abnormal exit. Saved outputs remain where you choose them.

## Documentation

- [User guide](docs/user-guide.md) — workflows, settings, shortcuts and limits.
- [Development and packaging](docs/development.md) — setup, checks and scripts.
- [Architecture](docs/architecture.md) — local service and processing contracts.
- [Decisions](docs/decisions.md) — maintained product and technical choices.
- [Validation status](docs/validation.md) — tested scope and remaining work.
- [Design system](DESIGN.md) — colors, typography and component rules.

## License and contact

Application source is **AGPL-3.0-only**. See [LICENSE](LICENSE) and
[third-party notices](THIRD_PARTY_NOTICES.md). Dependencies retain their own terms.

Built by **Ethan DevLab** · [hello@ethan-devlab.com](mailto:hello@ethan-devlab.com)

© 2026 Ethan DevLab. All rights reserved.
