"""Render offline Markdown through a chosen installed browser."""
import base64
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import mimetypes
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin
from PIL import Image, ImageOps

from .browsers import BrowserPDF
from .config import BASE
from .files import fingerprint


def local_image(reference, source, roots, max_megapixels):
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc or not parsed.path or "\\" in reference:
        raise ValueError("Only relative local images are supported.")
    relative = Path(unquote(parsed.path))
    if relative.is_absolute():
        raise ValueError("Absolute image paths are not supported.")
    raw = Path(source).parent / relative
    if any(p.is_symlink() or p.is_junction() for p in (raw, *raw.parents)):
        raise ValueError("Linked image paths are not supported.")
    path = raw.resolve(strict=True)
    if not any(path.is_relative_to(Path(root)) for root in roots):
        raise ValueError("Image is outside the registered roots.")
    before = fingerprint(str(path))
    with Image.open(path) as image:
        if image.width * image.height > max_megapixels * 1_000_000:
            raise ValueError("Image pixel limit exceeded.")
        image = ImageOps.exif_transpose(image).convert("RGBA")
        data = io.BytesIO()
        image.save(data, format="PNG")
    if fingerprint(str(path)) != before:
        raise ValueError("Image changed during conversion.")
    return "data:image/png;base64," + base64.b64encode(data.getvalue()).decode("ascii"), (str(path), before)


def markdown_html(text, source, roots, max_megapixels=100):
    warnings, dependencies = [], {}
    parser = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"]).use(dollarmath_plugin)

    def image_rule(tokens, index, options, env):
        token = tokens[index]
        reference = token.attrGet("src") or ""
        alt = token.content or "Image"
        try:
            uri, dependency = local_image(reference, source, roots, max_megapixels)
            dependencies[dependency[0]] = dependency[1]
            return f'<img src="{uri}" alt="{escape(alt, quote=True)}">'
        except (OSError, ValueError, Image.DecompressionBombError):
            warnings.append("IMAGE_UNAVAILABLE: " + reference[:300])
            return '<span class="image-alt">[' + escape(alt) + ']</span>'

    parser.renderer.rules["image"] = image_rule
    return parser.render(text), list(dict.fromkeys(warnings)), dependencies


def print_geometry(p):
    width, height = {"A4": (210, 297), "Letter": (215.9, 279.4), "Custom": (p.page_width, p.page_height)}[p.page_size]
    if p.orientation == "landscape":
        width, height = max(width, height), min(width, height)
    if min(width, height) - 2 * p.margin < p.text_font_size * p.text_line_height * 25.4 / 72 * 2:
        raise ValueError("TEXT_LAYOUT_ERROR: Margins or font size leave insufficient text area.")
    return width, height


def render_markdown(text, source, p, work, roots):
    body, warnings, dependencies = markdown_html(text, source, roots, p.max_megapixels)
    width, height = print_geometry(p)
    assets = BASE / "dist"
    if not (assets / "markdown/render.js").is_file():
        raise ValueError("MARKDOWN_ASSETS_MISSING: Build the offline Markdown renderer first.")
    font_css = ""
    for css in (assets / "assets").glob("*.css"):
        font_css += "\n".join(re.findall(r"@font-face\s*\{[^}]*\}", css.read_text("utf-8")))
    nonce, token = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    font_css = font_css.replace("url(/assets/", f"url(/{token}/assets/")
    css = f"""@page {{ size:{width}mm {height}mm; margin:{p.margin}mm; }}
      * {{ box-sizing:border-box; }}
      html {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
      body {{ margin:0; font-family:{p.text_font},'Noto Sans TC'; font-size:{p.text_font_size}pt;
        line-height:{p.text_line_height}; color:{p.text_color}; background:{p.background}; overflow-wrap:break-word; }}
      pre {{ white-space:pre-wrap; overflow-wrap:break-word; padding:6pt; background:#eeeeee; }}
      code {{ font-family:monospace,'Noto Sans TC'; }}
      table {{ border-collapse:collapse; width:100%; }}
      td,th {{ border:0.5pt solid #888888; padding:4pt; overflow-wrap:anywhere; }}
      tr, img, .mermaid-output {{ break-inside:avoid; }}
      img, svg {{ max-width:100%; height:auto; }}
      blockquote {{ border-left:2pt solid #888888; padding-left:8pt; }}
      .katex-display {{ overflow-wrap:normal; }}
      h1,h2,h3,h4,h5,h6 {{ break-after:avoid; }}"""
    document = (f'<!doctype html><html><head><meta charset="utf-8"><title>Text to PDF</title>'
                f'<link rel="stylesheet" href="/{token}/markdown/render.css">'
                f'<style>{font_css}\n{css}</style></head><body>{body}'
                f'<script type="module" src="/{token}/markdown/render.js" nonce="{nonce}"></script></body></html>').encode()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            relative = unquote(urlsplit(self.path).path)
            prefix = f"/{token}/"
            if not relative.startswith(prefix):
                self.send_error(404)
                return
            relative = relative[len(prefix):]
            if relative == "index.html":
                data, kind = document, "text/html; charset=utf-8"
            else:
                path = (assets / relative).resolve()
                if not path.is_relative_to(assets.resolve()) or not path.is_file() or relative == "index.html":
                    self.send_error(404)
                    return
                data = path.read_bytes()
                kind = "text/javascript" if path.suffix == ".js" else mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", f"default-src 'none'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    browser = None
    try:
        browser = BrowserPDF(p.text_browser, p.text_browser_path, work)
        data, _ = browser.render(f"http://127.0.0.1:{server.server_port}/{token}/index.html", width, height)
        if not data.startswith(b"%PDF-"):
            raise ValueError("BROWSER_RENDER_ERROR: No valid PDF was returned.")
        return data, warnings, dependencies
    finally:
        if browser:
            browser.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
