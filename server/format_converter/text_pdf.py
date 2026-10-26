"""Decode local text and paginate selectable text with the bundled MuPDF engine."""
import codecs
from html import escape
from pathlib import Path

import pymupdf as fitz

from .schemas import Parameters


def read_text(path: str, encoding: str) -> str:
    raw = Path(path).read_bytes()
    selected = encoding
    if encoding == "auto":
        if raw.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
            raise ValueError("TEXT_ENCODING_ERROR: UTF-32 is not supported.")
        selected = "utf-16" if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)) else "utf-8-sig"
    elif encoding == "utf-8":
        selected = "utf-8-sig"
    try:
        text = raw.decode(selected, errors="strict")
    except UnicodeError as exc:
        raise ValueError("TEXT_ENCODING_ERROR: Select the source file's encoding.") from exc
    if text.startswith("\ufeff"):
        text = text[1:]
    if "\x00" in text:
        raise ValueError("TEXT_ENCODING_ERROR: NUL characters found; check the selected encoding.")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def text_document(path: str, p: Parameters, progress):
    text = read_text(path, p.text_encoding).expandtabs(p.text_tab_width)
    mode = p.text_mode
    if mode == "auto":
        mode = "markdown" if Path(path).suffix.lower() in {".md", ".markdown"} else "plain"
    if mode == "markdown":
        raise ValueError("Markdown uses the selected browser engine.")
    else:
        body = '<div class="plain">' + escape(text) + '</div>'
    width, height = {"A4": (595.276, 841.89), "Letter": (612, 792),
                     "Custom": (p.page_width * 72 / 25.4, p.page_height * 72 / 25.4)}[p.page_size]
    if p.orientation == "landscape":
        width, height = max(width, height), min(width, height)
    margin = p.margin * 72 / 25.4
    if width - 2 * margin < p.text_font_size * 2 or height - 2 * margin < p.text_font_size * p.text_line_height * 2:
        raise ValueError("TEXT_LAYOUT_ERROR: Margins or font size leave insufficient text area.")
    css = f"""
        body {{ font-family:{p.text_font}; font-size:{p.text_font_size}pt;
               line-height:{p.text_line_height}; color:{p.text_color}; margin:0;
               overflow-wrap:break-word; }}
        .plain, pre {{ white-space:pre-wrap; overflow-wrap:break-word; margin:0; }}
        pre, code {{ font-family:monospace; }}
        p {{ margin:0 0 0.6em 0; }}
        table {{ border-collapse:collapse; width:100%; }}
        td, th {{ border:0.5pt solid #888888; padding:4pt; }}
        blockquote {{ border-left:2pt solid #888888; padding-left:8pt; }}
    """
    story = fitz.Story(html=body or "<div></div>", user_css=css, em=p.text_font_size)
    box = fitz.Rect(0, 0, width, height)
    content = fitz.Rect(margin, margin, width - margin, height - margin)

    def rectfn(index, filled):
        if index > 0 and fitz.Rect(filled).is_empty:
            raise ValueError("TEXT_LAYOUT_ERROR: Content cannot fit the selected page area.")
        progress.value = min(.9, .1 + index / (index + 10))
        return box, content, None

    doc = story.write_with_links(rectfn)
    for page in doc:
        page.draw_rect(page.rect, color=None,
                       fill=fitz.sRGB_to_pdf(int(p.background[1:], 16)), overlay=False)
    return doc
