# Maintained decisions

This document consolidates the accepted product and implementation decisions.
It replaces conversational question numbers and superseded exploration proposals
with the current contracts.

## Platform and runtime

- Windows x64 first. Use a Vite/React/TypeScript/Fluent UI browser interface and
  a loopback-only Python/FastAPI service. This is a local web application, not
  an embedded-browser desktop shell.
- Use PyMuPDF for PDF, Pillow/pillow-heif for images, and spawned processes for
  bounded parallel conversion. Application source is AGPL-3.0-only.
- Offer development mode and a portable that includes the runtime. The accepted
  compact profile preserves functionality while excluding unused optional models
  and duplicate payload. Keep WOFF2 fonts and native dialogs.
- Do not install or bundle a browser. Windows Markdown engines are installed
  Edge, Chrome and Firefox. Safari must mean actual Safari; product support and
  further user validation remain pending. A WebKit substitute is not equivalent.

## Data and filesystem

- Persist preferences only: language, registered roots, worker limits, pane/view
  settings, parameter presets and Markdown engine/path. Do not persist document
  contents, credentials, inventories or job history as preferences.
- Permit session-scoped uploads, previews and caches. Normal exit cleans them;
  later startup reclaims marked abandoned sessions. Saved outputs remain.
- Browse only explicitly added roots. Use paged lazy listings, virtualization and
  filesystem invalidation. Reject linked path components and junction traversal.
- Overlapping tree occurrences share physical-path selection and actions. Deduplicate
  counts, drags and operations; omit selected descendants for copy/cut/recycle.
- Protect registered roots and their ancestors from rename/cut/recycle. Forgetting
  a root does not delete its files. Invisible items lose selection unless another
  occurrence remains visible. Showing them again does not reselect them.
- Queue removal affects the queue only. Disk deletion requires confirmation and
  uses the Recycle Bin; never fall back to permanent deletion.

## Conversion and output

- Preview is the real temporary conversion result. Source/parameter changes make
  it stale. Convert reuses valid bytes or prepares new temporary results first.
- Use Save As with a suggested name for one actual output; use a folder dialog
  for multiple outputs. Cancel creates no final files. Do not overwrite inputs.
- Default conflicts to a unique suffix. Also expose skip, explicit overwrite and
  failure policies. Reserve/publish destinations safely across concurrent jobs.
- Show failures in the workspace while independent items continue. Permit retry
  of failed/cancelled items and clearing records without deleting saved output.
- Show per-source measured size after Preview for image/PDF compression, with
  multi-output details. Do not automatically estimate size or time.
- ICO stores all selected square dimensions in one file. Preserve aspect ratio
  with transparent padding; permit upscaling. Quality is an integer from 1 to 100.

## PDF credentials

- Opening protection and operation restrictions are separate controls. Opening-only
  mode uses the opening password internally as owner credential with permissions
  allowed. Restrictions require a separate owner password; opening may stay empty.
- Reading accepts valid credentials within permissions. Removing owner restrictions
  requires owner authentication. Enforce policy in the service, not only the UI.
- Compression preserves encryption and permissions. Rewriting signed PDFs can
  invalidate signatures; permission flags do not guarantee tamper prevention.

## Text and Markdown

- One source produces one PDF. TXT preserves line/blank-line structure with long
  line wrapping and pagination; expose paper, typography, margins and colors.
- Auto decoding uses strict UTF-8 or a supported BOM. Provide explicit UTF-16 LE/BE
  and Big5. Fail invalid decoding instead of inserting replacement characters.
- Markdown supports common block/inline syntax, tables, strikethrough, KaTeX and
  Mermaid. Source HTML is text, not executable markup. No remote image fetches.
- Read local relative raster images only inside registered roots. Missing,
  unsupported or inaccessible images show alt text and per-file warnings.
  Track embedded-image changes before committing a preview.
- Formula, diagram or engine errors fail the affected task. Never silently switch
  engines. Engine/path settings persist separately from parameter presets.

## Interface and lifecycle

- Warm White and Clay, OKLCH tokens, Fluent controls, no gradients. Preserve the
  accepted design rules in DESIGN.md. English default, Traditional Chinese option.
- Horizontal tool tabs; Explorer, ordered queue and preview/parameters on desktop.
  Use a file drawer and reachable actions in narrow layouts. Icons need names
  and explanations; Preview and Convert retain labels.
- With Explorer focus, use standard clipboard shortcuts, Ctrl+A for loaded visible
  editable items, F2, Delete, F5 and Alt+Enter. Text fields retain editing behavior.
- Expanded Fit preview uses the wheel for PDF pages or successive images. Stop
  at PDF boundaries; after zoom, wheel scrolls the image. Text keeps normal scroll.
- Closing the last portable client finishes submitted work before shutdown and
  permits a reconnect grace period. Development mode is stopped explicitly.
