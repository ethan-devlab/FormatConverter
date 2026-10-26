# Third-party components

Format Converter application source is AGPL-3.0-only. Dependencies retain their
own copyrights and license terms. The packaging script collects installed
Python and JavaScript license files into `licenses/`, including bundled native
library notices. Lockfiles record exact resolved versions.

`licenses/python-inventory.json` and `licenses/javascript-inventory.json` record
the installed build environment, including development and transitive packages.
They are not runtime-only SBOMs. `inventory-scope.json` states this boundary;
`native-capabilities.json` records codec versions reported by the installed
engines. These inventories do not replace missing native corresponding source.
Test-only web-vitals 6.2.3 uses Apache-2.0 and is installed in excluded test data;
its code is not bundled into the application or portable frontend.

| Component | License / source reference |
| --- | --- |
| PyMuPDF / MuPDF | AGPL-3.0 or commercial; this project uses the open-source option. https://github.com/pymupdf/PyMuPDF and https://mupdf.com/ |
| Pillow | HPND; bundled image libraries have separate notices. https://github.com/python-pillow/Pillow |
| pillow-heif | Python source BSD-3-Clause; the installed binary wheel includes copyleft libraries. https://github.com/bigcat88/pillow_heif |
| libheif 1.23.6 | LGPL-3.0; https://github.com/strukturag/libheif/tree/v1.23.6 |
| libde265 1.1.3 | LGPL-3.0; https://github.com/strukturag/libde265/tree/v1.1.3 |
| x265 4.3+1-e9b8812, as reported by the installed encoder | GPL-2.0-or-later in source headers; https://github.com/Multicorewareinc/x265/tree/4.3 is a base source reference, not proof of matching binary source. |
| Tesseract language data | Apache-2.0; https://github.com/tesseract-ocr/tessdata_fast |
| FastAPI, Uvicorn, React, Fluent UI, Vite and supporting packages | See collected package license files and lockfiles. |
| markdown-it-py, mdit-py-plugins and mdurl | MIT; Markdown and TeX syntax parsing. See collected notices and Python lockfile. |
| KaTeX and Mermaid | MIT; offline formula and diagram rendering. See collected notices and pnpm lockfile. |
| websocket-client | Apache-2.0; local CDP / WebDriver BiDi transport. See collected notices. |
| Bricolage Grotesque, Nunito Sans, Noto Sans TC | SIL Open Font License; self-hosted through Fontsource. |
| Python, Tcl/Tk, Microsoft/MinGW runtime components | See collected runtime and package notices. |

For a public binary release, provide matching application and native dependency
corresponding source, applicable build scripts and full notices alongside the
binary. A lockfile, a source link, or application-source ZIP alone does not
replace all copyleft distribution obligations. The local portable preview has
not been published and is not represented as a completed license audit.
