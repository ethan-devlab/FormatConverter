# User guide

## Convert files

1. Add one or more folders in **Files**, or use **Add files** to upload files to
   this local service. Added root paths are remembered as preferences.
2. Double-click a tree file or drag it into the queue. Select items, use the drag
   handles to change their order, or use the sort menu. The X removes a queue
   entry. It does not delete the source.
3. Select a horizontal tool tab. Set common or advanced parameters. **File
   options** sets a password or page range for an individual source.
4. Choose **Preview** to generate the actual temporary result. Expand the viewer
   for page navigation, zoom, fit and a dark/light canvas. Changed parameters or
   source files invalidate the preview.
5. Choose **Convert**. The app reuses a valid preview or first prepares temporary
   results. One actual output opens a Save As dialog with a proposed filename;
   multiple outputs open a folder dialog. Cancel writes no final output and keeps
   the preview for another attempt. A confirmed single-file replacement uses the
   Save As overwrite confirmation. Temporary results are removed after saving.
6. Task errors appear in the workspace. Open **Jobs** for output links,
   cancellation, retry and job clearing. Clear job removes its record and
   temporary preview, not saved outputs.

Image Convert and Compress PDF show measured input/output sizes after Preview,
including per-source totals and expandable output details. Changed inputs or
parameters mark these results stale. These are actual results, not estimates.
ICO settings show every selected square size stored inside the same ICO file;
the viewer chooses which size to display. Non-square inputs use transparent
padding, and smaller sources can be enlarged.

The default collision rule adds `_01`, `_02`, and so on. Skip, explicit output
overwrite, and stop-on-conflict are available. Original input files cannot be
overwritten by a conversion. Windows output publication refuses existing targets. Other platforms are not validated.

The Explorer has refresh, hidden-file visibility, rename, copy, cut, paste and
properties. Physical deletion asks for confirmation and uses the Windows
Recycle Bin. A failed recycle operation does not fall back to permanent delete.
Linked folders and junctions are not traversed. Folder roots cannot be moved,
renamed or deleted through this workspace. This protection also applies when a
root appears below another root and to ancestors that contain registered roots.
Overlapping roots share one physical selection; confirmation counts and actions
use unique paths. Copy/cut/recycle omit descendants of selected folders.

With focus in Files, use Ctrl+C/X/V for copy/cut/paste, Ctrl+A for loaded visible
editable entries, F2 to rename, Delete for the recycle confirmation, F5 to
refresh Files, and Alt+Enter for properties. Inputs keep normal text shortcuts.
Protected root entries and their ancestors are excluded from Ctrl+A.

In expanded Preview at Fit, scroll down/up over the image to move forward/back.
PDF paging stops at the document boundary; image outputs move between images.
After changing zoom, the wheel scrolls the image. Text previews and the small
preview retain normal scrolling.
Items with no visible occurrence are deselected; showing them again does not
select them automatically. Rename and Properties require one unique item.

Name filtering searches direct children of expanded folders before pagination;
it does not perform a recursive disk search. Folders remain visible for browsing.
Refresh rechecks unavailable roots and restarts their native subscriptions.
Updates preserve the loaded page extent. Failed cut items remain available for
retry; changed sources require a new explicit Copy/Cut selection.

## Tools

| Tool | Controls and behavior |
| --- | --- |
| Text to PDF | TXT and formatted Markdown; strict encoding, page/typography controls, selectable text, KaTeX formulas, Mermaid and scoped local images. |
| Images to PDF | A4, Letter, source-sized or custom pages; fit/fill/stretch, margins, background, quality or lossless image encoding, multi-frame pages. |
| PDF to Images | Render complete pages, including text and vectors, or extract embedded images separately. Page ranges, DPI, rotation and output format. |
| PDF to Text | UTF-8 text, selected pages, reading-order sorting, separators and automatic OCR for pages without usable text. |
| Merge PDF | Ordered sources, per-source ranges and credentials, rotated pages, bookmarks and page content. |
| Encrypt PDF | AES-256 opening protection, operation restrictions, or both. Opening-only mode uses the same internal owner credential. Restriction mode requires a separate owner password. |
| Decrypt PDF | Check document protection and credential role first. A readable user credential does not authorize removing owner restrictions. |
| Image Convert | PNG, JPEG, WebP, TIFF, BMP, ICO, HEIF and AVIF when the installed encoder is available. Resize, crop, rotation, metadata, color, DPI and supported encoding controls. |
| Organize PDF | Page ranges and order such as `3,1-2,5-4`, duplicate or omit pages, extract a subset, split by page count and rotate. |
| OCR | Local English, Traditional Chinese or mixed recognition for PDF and images; mixed model order is adjustable; UTF-8 text or searchable PDF. |
| Compress PDF | Lossless structural optimization or lossy image recompression/downsampling. |

Text to PDF detects `.md` and `.markdown` as Markdown; `.txt` and `.text` are
plain text. Override the format if needed. Automatic decoding accepts UTF-8 or
BOM-marked UTF-16; choose Big5 or UTF-16 LE/BE explicitly for other files.
Invalid bytes fail the individual task instead of becoming replacement text.

TXT uses MuPDF and needs no browser. Markdown uses the selected installed Edge,
Chrome or Firefox with an isolated temporary profile. Browser executables can
be detected or supplied in Settings. No browser is downloaded and no engine
fallback is hidden. Safari is not a supported engine. macOS integration and user validation remain pending.
The packaged KaTeX and Mermaid resources work offline. Use `$...$` / `$$...$$`
for TeX and fenced `mermaid` blocks for diagrams. Unsupported formulas and
invalid diagrams fail the task. Mermaid configuration directives are not allowed.
Raw HTML is printed as text, not executed. KaTeX does not compile full LaTeX.

Relative local raster images must be readable inside an added folder. Missing,
linked, unsupported, outside-root and remote images use alt text and show
per-file warnings on the main screen. For local image references, add the
document's folder in Explorer: browser uploads do not expose sibling files on
your disk. Changing an embedded image invalidates its previous preview.
Different engines can produce different line breaks, page counts or font
metrics. Inspect large tables, long formulas and diagrams in Preview.

Compression preserves existing encryption and permission flags. Creating a new
unrestricted PDF through merge, page organization or searchable-PDF OCR requires
owner authentication for an encrypted source. Text extraction still follows the
source copy permission.

PDF permission flags depend on the reader. They are not a digital signature or
a guarantee against modification. Rewriting a signed PDF invalidates its
signature. The current page organizer uses page-range controls; it does not
provide a visual page-thumbnail editor. Multi-frame image conversion writes
separate still images; it does not preserve animation timing. Image OCR currently
uses the first frame. OCR accuracy depends on the input; no accuracy percentage
is promised. Lossless compression can produce a larger output. HDR/gain maps and
10/12-bit image fidelity have not been validated.

## Privacy and temporary data

Preferences are stored at
`%LOCALAPPDATA%/EthanDevLab/FormatConverter/preferences.json`. They contain the
language, root folder paths, worker limits, pane widths, preview appearance,
Markdown engine/path and parameter presets. Presets exclude credentials and document-specific fields.
Files, inventories, thumbnail caches and job history are not persisted there.

Uploads and previews use an application-owned session directory under
`%LOCALAPPDATA%/EthanDevLab/FormatConverter/temporary`. Normal shutdown removes
it. A later startup removes marked sessions whose original process is no longer
alive. Active sessions and unrelated directories are preserved. This cleanup is
ordinary file deletion, not secure erasure. Final outputs remain in the chosen
folder. The app bundles fonts and OCR language data for offline use and sends no
document data to an external service.

## Settings

Language, Markdown PDF engine and its optional executable path survive refresh
and restart. Choose the engine that generates the PDF independently of the
browser used to open the UI. Leave the executable path empty for automatic
detection; set it only for a nonstandard installation. Changing the engine
clears the path. Parameter presets do not replace engine preferences.

## Service lifecycle

Close all connected tabs to stop the portable service. Submitted work finishes
first. The service allows 30 seconds to reconnect; crashed browser connections
expire after approximately 180 seconds. Development mode runs until stopped.

## Known limits

Windows x64 is the supported target. Narrow desktop layouts have been checked;
physical mobile devices and clean Windows installations need separate tests.
The app is a developer preview. Keep backups and inspect important outputs.
