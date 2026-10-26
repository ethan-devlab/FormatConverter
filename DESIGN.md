# Format Converter design system: Warm White and Clay

The selected Warm White and Clay direction was developed with Stitch and
implemented as semantic Fluent UI tokens. This file describes the maintained
application design; exploratory screens and local review captures are not part
of the source distribution.

## 1. Visual Theme and Atmosphere

A calm local file-conversion workspace. Clean working surfaces, clear separators,
restrained accents and a compact Explorer tree. No gradients, decorative hero,
marketing cards, glass effects or saturated blue, green or purple accents.

## 2. Color Palette and Roles

OKLCH is the implementation source of truth. Hex values are sRGB equivalents for
Stitch interoperability, not a separate palette.

| Role | OKLCH | sRGB equivalent |
| --- | --- | --- |
| canvas | oklch(0.9736 0.0057 84.57) | #f8f6f2 |
| surface | oklch(1.0000 0.0000 89.88) | #ffffff |
| text | oklch(0.2603 0.0105 61.00) | #28231f |
| muted | oklch(0.5048 0.0208 59.16) | #6e6259 |
| border | oklch(0.8764 0.0134 71.31) | #dcd5cd |
| primary | oklch(0.5273 0.1174 36.81) | #a34f37 |

Use the primary accent for the main action, selected tab indicator, keyboard
focus and restrained selection cues. Use text/icons as well as color for state.
Verify accessible contrast in implementation; these proposals do not establish
measured accessibility compliance.

## 3. Typography Rules

English brand and headings: Bricolage Grotesque. English body and controls: Nunito Sans.
Traditional Chinese: Noto Sans TC. Bundle selected fonts for offline use. Body and controls: 14px. Secondary metadata: 12px.
Section headings: 16px semibold. App title: 20px semibold. No all-caps headings.
Use a readable system fallback while bundled fonts load; do not depend
on a remote font request for normal offline operation.

## 4. Component Styling

Use Fluent UI controls with semantic theme tokens. Buttons and inputs have 8px
corners; major panes have subtle 12px corners. Avoid pill-shaped action groups.
Reserve shadows for menus, dialogs and overlays. Icons use Fluent line icons,
20px for actions. Icon-only controls need tooltips and accessible names.
Keep Preview and Convert labeled. Queue removal uses an X and says Remove from
queue; physical file deletion uses a trash icon and confirmation.

## 5. Layout Principles

Desktop: header, horizontal tool tabs, resizable Explorer pane on the left,
ordered conversion queue in the center, and an accessible parameter area.
Tabs cover Text to PDF, Images to PDF, PDF to Images, PDF to Text, Merge PDF, Encrypt PDF,
Decrypt PDF, Image Convert, Organize PDF, OCR, and Compress PDF.
Allow horizontal scrolling when tabs do not fit, keeping labels and focus visible.
Explorer and queue toolbars expose selection, sort and bulk actions.
The queue includes drag handles, names, types, sizes, status and remove controls.
Preview shows the generated result and is clearly associated with its parameters.
Show typical parameters first; keep advanced effective parameters reachable.
Use a 4px spacing base, 8-12px control gaps, and 16-24px pane padding.
Narrow screens: Explorer becomes a drawer, parameters become a sheet or stacked
section, tabs remain horizontally reachable, and preview uses the available width.

Footer contains exactly: © 2026 Ethan DevLab. All rights reserved.
Also include Built by Ethan DevLab, an email icon linked to hello@ethan-devlab.com,
and the real application version from package metadata. Mockups may use an
explicitly marked placeholder version; do not imply a published release.

English is the default UI language. Include an EN / 繁中 language selector.
Use only synthetic filenames and document thumbnails in generated designs.



## Implementation mappings

`src/styles.css` owns OKLCH semantic surface, text, border and accent values.
`src/main.tsx` maps the matching clay ramp into Fluent brand variants. Components
use Fluent UI React and Fluent icons; no generated Material icon runtime or
screenshot background is used. Self-hosted fonts work offline.

Desktop preview remains above an independent parameter scroller. Explorer and
parameter widths can be changed with pointer or keyboard separators on wide
screens. Narrow layouts use a folder drawer and a collapsible parameter region,
with labeled Preview/Convert actions docked below the content. Expanded previews
have separate zoom/fit and page-navigation rows, and both counters use nowrap.
The actual output aspect ratio is preserved.

Normal/hover/selected/focus/disabled/loading/error states use text and accessible
names. X actions remove queue entries; recycle actions confirm disk changes.
Native file and conversion errors appear in a readable banner or dialog. Motion
respects `prefers-reduced-motion`. Full screen-reader certification is not claimed.
