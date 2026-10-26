from multiprocessing import get_context
from pathlib import Path

import pymupdf as fitz
import pytest
from PIL import Image, ImageDraw, ImageFont

from server.format_converter.conversion import open_pdf, page_indices, run_conversion
from server.format_converter.schemas import JobRequest, Parameters
from server.format_converter.config import TESSDATA


def pdf(path, text="A sample document", pages=2):
    with fitz.open() as doc:
        for i in range(pages):
            doc.new_page().insert_text((50, 80), f"{text} {i + 1}", fontsize=20)
        doc.save(path)
    return str(path)


def run(tmp_path, tool, paths, **params):
    out = tmp_path / f"work-{len(list(tmp_path.iterdir()))}"
    out.mkdir()
    result = run_conversion(tool, [{"path": str(p)} for p in paths], Parameters(**params).model_dump(), str(out), str(TESSDATA), get_context("spawn").Value("d", 0))
    return [Path(item["path"]) for item in result["outputs"]]


def test_page_ranges_preserve_order_and_reject_invalid():
    assert page_indices("3,1-2,3-2", 3) == [2, 0, 1, 2, 1]
    for value in ["0", "4", "1,,2", "a", "1-999999999"]:
        with pytest.raises(ValueError):
            page_indices(value, 3)


def test_multiframe_tiff_and_original_dpi(tmp_path):
    source = tmp_path / "frames.tiff"
    first = Image.new("RGB", (40, 30), "red")
    second = Image.new("RGB", (40, 30), "yellow")
    first.save(source, save_all=True, append_images=[second], dpi=(300, 300))
    outputs = run(tmp_path, "image", [source], format="PNG", preserve_dpi=True)
    assert len(outputs) == 2
    with Image.open(outputs[1]) as image:
        assert image.getpixel((0, 0)) == (255, 255, 0)
        assert image.info["dpi"][0] == pytest.approx(300, abs=.1)
    output = run(tmp_path, "images_pdf", [source])[0]
    with fitz.open(output) as doc:
        assert doc.page_count == 2
    assert len(run(tmp_path, "image", [source], frames="first")) == 1


def test_split_pdf_uses_selected_order(tmp_path):
    source = pdf(tmp_path / "split.pdf", pages=3)
    outputs = run(tmp_path, "organize", [source], organize_mode="split", split_every=2, pages="3,1,2")
    assert len(outputs) == 2
    with fitz.open(outputs[0]) as doc:
        assert doc.page_count == 2
        assert "document 3" in doc[0].get_text()
        assert "document 1" in doc[1].get_text()
    with fitz.open(outputs[1]) as doc:
        assert doc.page_count == 1


@pytest.mark.parametrize("language", ["chi_tra", "eng+chi_tra"])
def test_traditional_chinese_ocr(tmp_path, language):
    font_path = Path("C:/Windows/Fonts/msjh.ttc")
    if not font_path.exists():
        pytest.skip("Traditional Chinese fixture font is unavailable")
    image = Image.new("RGB", (1200, 200), "white")
    ImageDraw.Draw(image).text((30, 30), "繁體中文測試", fill="black", font=ImageFont.truetype(str(font_path), 100))
    source = tmp_path / "traditional.png"
    image.save(source)
    output = run(tmp_path, "ocr", [source], ocr_language=language, ocr_output="txt")[0]
    text = "".join(output.read_text("utf-8").split())
    assert "中文" in text, text


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP", "TIFF", "BMP", "ICO", "HEIF", "AVIF"])
def test_available_image_encoders_round_trip(tmp_path, format):
    Image.init()
    if format not in Image.SAVE:
        pytest.skip(f"{format} encoder is unavailable")
    source = tmp_path / "source.png"
    Image.new("RGBA", (64, 64), (180, 90, 60, 180)).save(source)
    output = run(tmp_path, "image", [source], format=format)[0]
    with Image.open(output) as image:
        image.load()
        assert image.size == ((256, 256) if format == "ICO" else (64, 64))


@pytest.mark.parametrize("dimensions", [(8, 8), (512, 256), (256, 512)])
def test_ico_has_all_requested_square_sizes_and_transparency(tmp_path, dimensions):
    source = tmp_path / "icon-source.png"
    image = Image.new("RGBA", dimensions, (180, 90, 60, 128))
    image.save(source)
    output = run(tmp_path, "image", [source], format="ICO", ico_sizes="16,32,256")[0]
    with Image.open(output) as icon:
        assert icon.ico.sizes() == {(16, 16), (32, 32), (256, 256)}
        for edge in (16, 32, 256):
            frame = icon.ico.getimage((edge, edge)).convert("RGBA")
            assert frame.size == (edge, edge)
            assert frame.getpixel((edge // 2, edge // 2))[3] == pytest.approx(128, abs=2)
            if dimensions[0] != dimensions[1]:
                assert frame.getpixel((0, 0))[3] == 0


@pytest.mark.parametrize("sizes", ["", " ", "16,", "16,,32", "0", "257", "16x16", "16.5", "-1", "１２"])
def test_ico_rejects_invalid_sizes_before_conversion(sizes):
    with pytest.raises(ValueError, match="ICO sizes"):
        Parameters(format="ICO", ico_sizes=sizes)


def test_ico_normalizes_valid_size_selection():
    assert Parameters(format="ICO", ico_sizes=" 256,16,16, 32 ").ico_sizes == "16,32,256"


def test_pdf_page_can_render_to_all_requested_ico_sizes(tmp_path):
    source = pdf(tmp_path / "icon-page.pdf", pages=1)
    output = run(tmp_path, "pdf_images", [source], format="ICO", ico_sizes="16,32,256")[0]
    with Image.open(output) as icon:
        assert icon.ico.sizes() == {(16,16), (32,32), (256,256)}


def test_pdf_transforms_do_not_remove_owner_restrictions_with_user_credential(tmp_path):
    source = tmp_path / "restricted-transform.pdf"
    with fitz.open() as doc:
        doc.new_page().insert_text((50, 80), "Protected fixture")
        doc.save(source, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="reader",
                 permissions=fitz.PDF_PERM_MODIFY | fitz.PDF_PERM_ASSEMBLE | fitz.PDF_PERM_COPY)
    compressed = run(tmp_path, "compress", [source], password="reader")[0]
    with fitz.open(compressed) as doc:
        assert doc.needs_pass
        assert doc.authenticate("reader") == 2
        assert not doc.permissions & fitz.PDF_PERM_PRINT
    for tool in ("merge", "organize", "ocr"):
        with pytest.raises(ValueError, match="OWNER_PASSWORD_REQUIRED"):
            run(tmp_path, tool, [source], password="reader")
    assert "Protected fixture" in run(tmp_path, "pdf_text", [source], password="reader")[0].read_text("utf-8")


def test_merge_bookmarks_and_rotated_pages(tmp_path):
    source = tmp_path / "outline.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.new_page().set_rotation(90)
        doc[0].insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(10, 10, 100, 40), "page": 1})
        doc.set_metadata({"title": "Fixture title", "author": "Fixture author"})
        doc.set_toc([[1, "First", 1], [1, "Second", 2]])
        doc.save(source)
    output = run(tmp_path, "organize", [source], pages="2,1", rotation=90)[0]
    with fitz.open(output) as doc:
        assert [p.rotation for p in doc] == [180, 90]
        assert doc.get_toc() == [[1, "First", 2], [1, "Second", 1]]
        assert doc.metadata["title"] == "Fixture title"
        assert doc[1].get_links()[0]["page"] == 0


def test_text_output_is_not_appended_or_written_to_cwd(tmp_path, monkeypatch):
    source = pdf(tmp_path / "input.pdf")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    marker = cwd / "input.txt"
    marker.write_text("keep", "utf-8")
    monkeypatch.chdir(cwd)
    first = run(tmp_path, "pdf_text", [source], pages="2")
    second = run(tmp_path, "pdf_text", [source], pages="2")
    assert first[0].read_text("utf-8") == second[0].read_text("utf-8")
    assert "document 2" in first[0].read_text("utf-8")
    assert marker.read_text("utf-8") == "keep"


def test_text_vector_pdf_renders_complete_pages(tmp_path):
    source = pdf(tmp_path / "text.pdf")
    images = run(tmp_path, "pdf_images", [source], dpi=72)
    assert len(images) == 2
    with Image.open(images[0]) as image:
        assert image.width > 500
        assert image.convert("L").getextrema()[0] < 150


def test_embedded_images_have_distinct_names(tmp_path):
    source = tmp_path / "images.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        for i, color in enumerate(["red", "blue"]):
            path = tmp_path / f"{color}.png"
            Image.new("RGB", (40, 40), color).save(path)
            page.insert_image(fitz.Rect(20 + i * 60, 20, 60 + i * 60, 60), filename=path)
        doc.save(source)
    result = run(tmp_path, "pdf_images", [source], extract_images=True)
    assert len(result) == 2
    assert result[0] != result[1]
    assert result[0].read_bytes() != result[1].read_bytes()


@pytest.mark.parametrize("matte", [None, 0, 1])
@pytest.mark.parametrize("gray", [False, True])
@pytest.mark.parametrize("format", ["PNG", "JPEG"])
def test_embedded_mask_preserves_color_and_transparency(tmp_path, matte, gray, format):
    alpha = 128
    original = (180,) if gray else (180, 90, 30)
    stored = tuple(round(channel * alpha / 255 + matte * (255 - alpha)) for channel in original) if matte is not None else original
    image = Image.new("LA" if gray else "RGBA", (40, 30), (*stored, alpha))
    embedded = tmp_path / "masked.png"
    image.save(embedded)
    source = tmp_path / "masked.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        xref = page.insert_image(fitz.Rect(20,20,100,80), filename=embedded)
        if matte is not None:
            mask = page.get_images(full=True)[0][1]
            doc.xref_set_key(mask, "Matte", f"[{matte}]" if gray else f"[{matte} {matte} {matte}]")
        doc.save(source)
    if matte is not None:
        with fitz.open(source) as doc:
            assert fitz.Pixmap(doc, xref).alpha == 1
    output = run(tmp_path, "pdf_images", [source], extract_images=True, format=format, quality=100)[0]
    with Image.open(output) as extracted:
        assert extracted.size == (40,30)
        if format == "PNG":
            pixel = extracted.getpixel((20,15))
            assert pixel[-1] == pytest.approx(alpha, abs=1)
            assert pixel[:-1] == pytest.approx(original, abs=3)
        else:
            rgb = (original[0],)*3 if gray else original
            expected = tuple(round(value * alpha/255 + 255*(1-alpha/255)) for value in rgb)
            assert extracted.convert("RGB").getpixel((20,15)) == pytest.approx(expected, abs=3)


def test_password_modes_and_owner_policy(tmp_path):
    source = pdf(tmp_path / "plain.pdf")
    opening = run(tmp_path, "encrypt", [source], opening_password="opening")[0]
    assert fitz.open(opening).needs_pass
    decrypted = run(tmp_path, "decrypt", [opening], password="opening")[0]
    with fitz.open(decrypted) as doc:
        assert not doc.needs_pass and doc.page_count == 2
    restricted = run(tmp_path, "encrypt", [source], require_opening=False, restrict=True, owner_password="owner", allow_copy=False)[0]
    with fitz.open(restricted) as doc:
        assert not doc.needs_pass
    with pytest.raises(ValueError, match="OWNER_PASSWORD_REQUIRED"):
        run(tmp_path, "decrypt", [restricted])
    assert run(tmp_path, "decrypt", [restricted], password="owner")
    combined = run(tmp_path, "encrypt", [source], restrict=True, opening_password="reader", owner_password="owner", allow_copy=False)[0]
    with pytest.raises(ValueError, match="OWNER_PASSWORD_REQUIRED"):
        run(tmp_path, "decrypt", [combined], password="reader")
    with pytest.raises(ValueError, match="OWNER_PASSWORD_REQUIRED"):
        run(tmp_path, "pdf_text", [combined], password="reader")
    with pytest.raises(ValueError, match="PASSWORD_REQUIRED_OR_INCORRECT"):
        open_pdf(str(combined), "wrong", "decrypt")


def test_encryption_validation_does_not_require_both_fields():
    assert JobRequest(tool="encrypt", preview=True, sources=[{"path": "x"}], parameters={"opening_password": "open"})
    assert JobRequest(tool="encrypt", preview=True, sources=[{"path": "x"}], parameters={"require_opening": False, "restrict": True, "owner_password": "owner"})
    with pytest.raises(ValueError):
        JobRequest(tool="encrypt", preview=True, sources=[{"path": "x"}], parameters={"restrict": True, "opening_password": "same", "owner_password": "same"})


def test_heif_decode_resize_and_alpha_jpeg(tmp_path):
    source = tmp_path / "source.heic"
    Image.new("RGB", (120, 80), "#b45a3a").save(source, format="HEIF")
    outputs = run(tmp_path, "image", [source], format="PNG", width=60)
    with Image.open(outputs[0]) as image:
        assert image.size == (60, 40)
    rgba = tmp_path / "alpha.png"
    Image.new("RGBA", (20, 20), (255, 0, 0, 0)).save(rgba)
    result = run(tmp_path, "image", [rgba], format="JPEG", background="#ffffff")[0]
    with Image.open(result) as image:
        assert min(image.getpixel((0, 0))) > 245


def test_image_pdf_layout_and_organize(tmp_path):
    image = tmp_path / "image.png"
    Image.new("RGBA", (240, 320), (255, 0, 0, 128)).save(image)
    result = run(tmp_path, "images_pdf", [image, image], margin=15, lossless=True)[0]
    with fitz.open(result) as doc:
        assert doc.page_count == 2
        assert abs(doc[0].rect.width / doc[0].rect.height - 210 / 297) < 0.001
    source = pdf(tmp_path / "pages.pdf", pages=3)
    result = run(tmp_path, "organize", [source], pages="3,1", rotation=90)[0]
    with fitz.open(result) as doc:
        assert doc.page_count == 2
        assert "document 3" in doc[0].get_text()


def test_compression_keeps_selectable_text(tmp_path):
    source = pdf(tmp_path / "source.pdf")
    for mode in ("lossless", "lossy"):
        result = run(tmp_path, "compress", [source], compression=mode)[0]
        with fitz.open(result) as doc:
            assert doc.page_count == 2
            assert "sample" in doc[0].get_text()


def test_actual_english_ocr_text_and_searchable_pdf(tmp_path):
    source = tmp_path / "scan.png"
    image = Image.new("RGB", (1400, 400), "white")
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 64)
    ImageDraw.Draw(image).text((70, 100), "FORMAT CONVERTER TEST", font=font, fill="black")
    image.save(source)
    text = run(tmp_path, "ocr", [source], ocr_output="txt")[0].read_text("utf-8")
    assert "CONVERTER" in text.upper()
    result = run(tmp_path, "ocr", [source], ocr_output="pdf")[0]
    with fitz.open(result) as doc:
        assert "CONVERTER" in doc[0].get_text().upper()
