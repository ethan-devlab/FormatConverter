import codecs
from multiprocessing import get_context
from pathlib import Path

import pymupdf as fitz
import pytest
from PIL import Image

from server.format_converter.conversion import run_conversion
from server.format_converter.markdown_pdf import markdown_html
from server.format_converter.text_pdf import read_text
from server.format_converter.config import TESSDATA


@pytest.mark.parametrize("exit_code", [0, 7])
def test_browser_launcher_handoff_waits_only_for_success(tmp_path, monkeypatch, exit_code):
    import io
    from types import SimpleNamespace
    from server.format_converter import browsers

    executable = tmp_path / "msedge.exe"
    executable.write_bytes(b"synthetic executable; never launched")
    attempts = []
    closed = []

    def endpoint(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("Synthetic endpoint not ready")
        return io.BytesIO(b'[{"type":"page","webSocketDebuggerUrl":"ws://127.0.0.1/synthetic"}]')

    monkeypatch.setattr(browsers.subprocess, "Popen", lambda *args, **kwargs: SimpleNamespace(poll=lambda: exit_code))
    monkeypatch.setattr(browsers.urllib.request, "urlopen", endpoint)
    monkeypatch.setattr(browsers.time, "sleep", lambda _: None)
    monkeypatch.setattr(browsers.websocket, "create_connection", lambda *args, **kwargs: SimpleNamespace(settimeout=lambda _: None))
    monkeypatch.setattr(browsers.BrowserPDF, "call", lambda *args, **kwargs: {})
    monkeypatch.setattr(browsers.BrowserPDF, "close", lambda self: closed.append(True))

    if exit_code == 0:
        browser = browsers.BrowserPDF("edge", str(executable), tmp_path)
        assert browser.ws is not None and len(attempts) == 2 and not closed
    else:
        with pytest.raises(ValueError, match="BROWSER_START_FAILED"):
            browsers.BrowserPDF("edge", str(executable), tmp_path)
        assert len(attempts) == 1 and closed == [True]


@pytest.mark.parametrize("codec,bom,setting", [("utf-8", b"", "auto"), ("utf-8", codecs.BOM_UTF8, "auto"),
    ("utf-16-le", codecs.BOM_UTF16_LE, "auto"), ("utf-16-be", codecs.BOM_UTF16_BE, "auto"),
    ("utf-16-le", b"", "utf-16-le"), ("utf-16-be", b"", "utf-16-be"), ("big5", b"", "big5")])
def test_strict_text_encodings(tmp_path, codec, bom, setting):
    source = tmp_path / "text.txt"
    source.write_bytes(bom + "English 繁體中文\r\nSecond".encode(codec))
    assert read_text(str(source), setting) == "English 繁體中文\nSecond"


def test_invalid_encoding_does_not_replace_bytes(tmp_path):
    source = tmp_path / "bad.txt"
    source.write_bytes(b"\xff\xff")
    with pytest.raises(ValueError, match="TEXT_ENCODING_ERROR"):
        read_text(str(source), "auto")


def test_plain_pdf_wraps_paginate_and_preserves_searchable_text(tmp_path):
    source = tmp_path / "long.txt"
    source.write_text("  Alpha    Beta\n\n繁體中文測試\n" + "longword" * 100 + "\n" + "MORE LINES\n" * 160 + "FINAL TOKEN", "utf-8")
    out = tmp_path / "out"
    out.mkdir()
    result = run_conversion("text_pdf", [{"path": str(source)}], {}, str(out), str(TESSDATA), get_context("spawn").Value("d", 0))
    with fitz.open(result["outputs"][0]["path"]) as doc:
        assert len(doc) > 1
        text = "".join(p.get_text() for p in doc)
        assert "繁體中文測試" in text and "Alpha    Beta" in text and "FINAL TOKEN" in text
        assert "longword" * 100 in "".join(text.split())
        assert all(word[2] < page.rect.width - 15 for page in doc for word in page.get_text("words"))


def test_blank_text_and_invalid_margins(tmp_path):
    source = tmp_path / "empty.txt"
    source.touch()
    for index, params in enumerate([{}, {"margin": 1000}]):
        out = tmp_path / str(index)
        out.mkdir()
        if params:
            with pytest.raises(ValueError, match="TEXT_LAYOUT_ERROR"):
                run_conversion("text_pdf", [{"path": str(source)}], params, str(out), str(TESSDATA), get_context("spawn").Value("d", 0))
        else:
            result = run_conversion("text_pdf", [{"path": str(source)}], params, str(out), str(TESSDATA), get_context("spawn").Value("d", 0))
            with fitz.open(result["outputs"][0]["path"]) as doc:
                assert len(doc) == 1


def test_markdown_images_and_html_are_scoped(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    Image.new("RGB", (40, 30), "red").save(root / "image.png")
    Image.new("RGB", (40, 30), "blue").save(tmp_path / "outside.png")
    text = '# Title\n\n**bold** ~~old~~ $x^2$\n\n![ok](image.png) ![missing](none.png) ![outside](../outside.png) ![remote](https://example.com/image.png)\n\n<script>alert(1)</script>\n\n|A|B|\n|-|-|\n|1|2|'
    html, warnings, dependencies = markdown_html(text, str(root / "doc.md"), [str(root)])
    assert "<h1>Title</h1>" in html and "<strong>bold</strong>" in html and "<s>old</s>" in html
    assert "<table>" in html and 'class="math inline"' in html
    assert "data:image/png;base64," in html
    assert "[missing]" in html and "[outside]" in html and "[remote]" in html
    assert len(warnings) == 3 and list(dependencies) == [str(root / "image.png")]
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_browser_ownership_requires_exact_isolated_profile(tmp_path, monkeypatch):
    from server.format_converter import browsers
    profile = tmp_path / "browser-profile-owned"

    class Process:
        def __init__(self, value):
            self.value = value
        def name(self):
            return "msedge.exe"
        def cmdline(self):
            return ["msedge.exe", "--user-data-dir=" + str(self.value)]

    own, other = Process(profile), Process(str(profile) + "-unrelated")
    monkeypatch.setattr(browsers.psutil, "process_iter", lambda: [own, other])
    assert browsers.browser_processes([profile]) == [own]
