"""Conversion workers. Native PDF objects never cross process boundaries."""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageCms, ImageFilter, ImageOps
from pillow_heif import register_heif_opener

from .schemas import Parameters
from .text_pdf import read_text, text_document
from .markdown_pdf import render_markdown

register_heif_opener()
EXTENSIONS = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "TIFF": ".tiff", "BMP": ".bmp", "ICO": ".ico", "HEIF": ".heic", "AVIF": ".avif"}


def page_indices(spec: str, count: int) -> list[int]:
    if not spec.strip():
        return list(range(count))
    result = []
    for part in spec.split(","):
        match = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*", part)
        if not match:
            raise ValueError("Use page numbers and ranges, such as 1,3-5.")
        a, b = int(match[1]), int(match[2] or match[1])
        if not (1 <= a <= count and 1 <= b <= count):
            raise ValueError(f"Page range is outside 1-{count}.")
        step = 1 if b >= a else -1
        result.extend(i - 1 for i in range(a, b + step, step))
        if len(result) > 100000:
            raise ValueError("Too many selected pages.")
    return result


def open_pdf(path: str, password: str, operation: str):
    doc = fitz.open(path)
    try:
        encrypted = bool(doc.needs_pass or (doc.metadata or {}).get("encryption"))
        auth = doc.authenticate(password)
        if not auth:
            raise ValueError("PASSWORD_REQUIRED_OR_INCORRECT")
        if encrypted and auth == 2:
            if operation in {"decrypt", "encrypt", "merge", "organize", "ocr_pdf"}:
                raise ValueError("OWNER_PASSWORD_REQUIRED")
            required = {"pdf_text": fitz.PDF_PERM_COPY, "extract": fitz.PDF_PERM_COPY,
                        "merge": fitz.PDF_PERM_ASSEMBLE, "organize": fitz.PDF_PERM_ASSEMBLE,
                        "compress": fitz.PDF_PERM_MODIFY, "ocr": fitz.PDF_PERM_COPY}.get(operation)
            if required and not doc.permissions & required:
                raise ValueError("OWNER_PASSWORD_REQUIRED")
        return doc
    except Exception:
        doc.close()
        raise


def image_data(path: str, p: Parameters, frame: int = 0) -> tuple[Image.Image, dict]:
    with Image.open(path) as source:
        source.seek(frame)
        if source.width * source.height > p.max_megapixels * 1_000_000:
            raise ValueError("IMAGE_PIXEL_LIMIT")
        meta = {k: source.info[k] for k in ("icc_profile", "dpi") if k in source.info}
        exif = source.getexif()
        exif.pop(274, None)
        if exif:
            meta["exif"] = exif.tobytes()
        image = ImageOps.exif_transpose(source).copy()
    if p.crop:
        try:
            x, y, w, h = map(int, p.crop.split(","))
        except ValueError:
            raise ValueError("Crop must use x,y,width,height.") from None
        if min(x, y) < 0 or min(w, h) <= 0 or x + w > image.width or y + h > image.height:
            raise ValueError("Crop is outside the source image.")
        image = image.crop((x, y, x + w, y + h))
    if p.rotation:
        image = image.rotate(-p.rotation, expand=True)
    method = {"lanczos": Image.Resampling.LANCZOS, "bicubic": Image.Resampling.BICUBIC, "nearest": Image.Resampling.NEAREST}[p.resample]
    if p.width or p.height:
        width = p.width or max(1, round(image.width * p.height / image.height))
        height = p.height or max(1, round(image.height * p.width / image.width))
        if width * height > p.max_megapixels * 1_000_000:
            raise ValueError("IMAGE_PIXEL_LIMIT")
        image = ImageOps.contain(image, (width, height), method) if p.keep_ratio else image.resize((width, height), method)
    if p.sharpen:
        image = image.filter(ImageFilter.SHARPEN)
    if p.color_mode == "L":
        image = image.convert("LA" if "A" in image.getbands() else "L")
    elif image.mode == "CMYK":
        if meta.get("icc_profile"):
            image = ImageCms.profileToProfile(image, ImageCms.ImageCmsProfile(io.BytesIO(meta["icc_profile"])), ImageCms.createProfile("sRGB"), outputMode="RGB")
            meta.pop("icc_profile", None)
        else:
            image = image.convert("RGB")
    return image, meta if p.metadata == "keep" else {}


def frame_indices(path: str, p: Parameters):
    with Image.open(path) as source:
        return range(getattr(source, "n_frames", 1) if p.frames == "all" else 1)


def flatten(image: Image.Image, color: str) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, color)
    background.alpha_composite(rgba)
    return background.convert("RGB")


def save_image(image: Image.Image, target: Path, p: Parameters, meta: dict | None = None):
    fmt = p.format
    if fmt not in Image.SAVE:
        Image.init()
    if fmt not in Image.SAVE:
        raise ValueError(f"ENCODER_UNAVAILABLE: {fmt}")
    options = dict(meta or {})
    if not p.preserve_dpi or "dpi" not in options:
        options["dpi"] = (p.dpi, p.dpi)
    if fmt in {"JPEG", "BMP"}:
        image = flatten(image, p.background)
    elif image.mode not in {"RGB", "RGBA", "L", "LA", "P"}:
        image = image.convert("RGBA")
    if fmt in {"JPEG", "WEBP", "HEIF", "AVIF"}:
        options["quality"] = p.quality
    if fmt in {"JPEG", "PNG"}:
        options["optimize"] = p.optimize
    if fmt == "WEBP":
        options["lossless"] = p.lossless
    if fmt == "TIFF":
        options["compression"] = "tiff_deflate" if p.optimize else "raw"
    if fmt == "ICO":
        sizes = [int(v.strip()) for v in p.ico_sizes.split(",")]
        if not sizes or any(v < 1 or v > 256 for v in sizes):
            raise ValueError("ICO sizes must be between 1 and 256.")
        frames = []
        rgba = image.convert("RGBA")
        try:
            for edge in sorted(set(sizes), reverse=True):
                fitted = ImageOps.contain(rgba, (edge, edge), Image.Resampling.LANCZOS)
                canvas = Image.new("RGBA", (edge, edge), (0, 0, 0, 0))
                canvas.alpha_composite(fitted, ((edge - fitted.width) // 2, (edge - fitted.height) // 2))
                fitted.close()
                frames.append(canvas)
            frames[0].save(target, format="ICO", sizes=[frame.size for frame in frames], append_images=frames[1:])
        finally:
            rgba.close()
            for frame in frames:
                frame.close()
        return
    image.save(target, format=fmt, **options)


def metadata(doc, p):
    if p.metadata == "remove":
        doc.set_metadata({})
        if doc.xref_xml_metadata():
            doc.del_xml_metadata()
    else:
        data = doc.metadata or {}
        if p.title:
            data["title"] = p.title
        if p.author:
            data["author"] = p.author
        doc.set_metadata(data)


def copy_metadata(source, destination, p):
    if p.metadata == "keep":
        destination.set_metadata(source.metadata)
        xml = source.get_xml_metadata()
        if xml:
            destination.set_xml_metadata(xml)


def render(page, p: Parameters):
    if page.rect.width * page.rect.height * (p.dpi / 72) ** 2 > p.max_megapixels * 1_000_000:
        raise ValueError("IMAGE_PIXEL_LIMIT")
    pix = page.get_pixmap(matrix=fitz.Matrix(p.dpi / 72, p.dpi / 72).prerotate(p.rotation), colorspace=fitz.csGRAY if p.color_mode == "L" else fitz.csRGB, alpha=False)
    pix.set_dpi(p.dpi, p.dpi)
    return pix


def run_conversion(tool: str, sources: list[dict], raw: dict, work: str, tessdata: str, progress):
    raw = dict(raw)
    allowed_roots = raw.pop("_allowed_roots", [])
    p = Parameters.model_validate(raw)
    language = "chi_tra+eng" if p.ocr_language == "eng+chi_tra" and p.ocr_chinese_first else p.ocr_language
    folder = Path(work)
    outputs: list[dict] = []
    preview: list[str] = []
    serial = 0
    warnings, dependencies = [], {}

    def target(name: str, suffix: str):
        nonlocal serial
        serial += 1
        result = folder / f"output-{serial:05d}{suffix}"
        outputs.append({"path": str(result), "name": name + suffix})
        return result

    def tick(value: float):
        progress.value = value

    if tool == "text_pdf":
        for index, src in enumerate(sources):
            markdown = p.text_mode == "markdown" or (p.text_mode == "auto" and Path(src["path"]).suffix.lower() in {".md", ".markdown"})
            if markdown:
                data, alerts, images = render_markdown(read_text(src["path"], p.text_encoding).expandtabs(p.text_tab_width),
                                                       src["path"], p, folder, allowed_roots)
                warnings.extend(alerts)
                dependencies.update(images)
                out = fitz.open(stream=data, filetype="pdf")
            else:
                out = text_document(src["path"], p, progress)
            with out:
                metadata(out, p)
                out.save(target(Path(src["path"]).stem, ".pdf"), deflate=True, garbage=3)
            tick((index + 1) / len(sources))
    elif tool == "images_pdf":
        with fitz.open() as out:
            frames = [(src, frame) for src in sources for frame in frame_indices(src["path"], p)]
            for n, (src, frame) in enumerate(frames):
                image, _ = image_data(src["path"], p, frame)
                image = flatten(image, p.background)
                if p.page_size == "Original":
                    w, h = image.width * 72 / p.dpi, image.height * 72 / p.dpi
                else:
                    w, h = {"A4": (595.276, 841.89), "Letter": (612, 792), "Custom": (p.page_width * 72 / 25.4, p.page_height * 72 / 25.4)}[p.page_size]
                    if p.orientation == "landscape":
                        w, h = max(w, h), min(w, h)
                margin = p.margin * 72 / 25.4
                if margin * 2 >= min(w, h):
                    raise ValueError("Margins leave no image area.")
                page = out.new_page(width=w, height=h)
                page.draw_rect(page.rect, color=None, fill=fitz.sRGB_to_pdf(int(p.background[1:], 16)))
                rect = fitz.Rect(margin, margin, w - margin, h - margin)
                if p.fit == "cover":
                    image = ImageOps.fit(image, (max(1, round(rect.width * p.dpi / 72)), max(1, round(rect.height * p.dpi / 72))), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                image.save(buf, format="PNG" if p.lossless else "JPEG", quality=p.quality, optimize=p.optimize)
                page.insert_image(rect, stream=buf.getvalue(), keep_proportion=p.fit != "stretch")
                image.close()
                tick((n + 1) / len(frames))
            metadata(out, p)
            out.save(target("images", ".pdf"), deflate=True, garbage=3)
    elif tool == "organize" and p.organize_mode == "split":
        src = sources[0]
        with open_pdf(src["path"], src.get("password") or p.password, tool) as doc:
            selected = page_indices(src.get("pages") or p.pages, doc.page_count)
            for start in range(0, len(selected), p.split_every):
                with fitz.open() as out:
                    copy_metadata(doc, out, p)
                    for index in selected[start:start + p.split_every]:
                        out.insert_pdf(doc, from_page=index, to_page=index, rotate=(doc[index].rotation + p.rotation) % 360, links=True, annots=True, widgets=True)
                    metadata(out, p)
                    out.save(target(f"{Path(src['path']).stem}_part{start // p.split_every + 1:04d}", ".pdf"), garbage=3, deflate=True)
                tick(min(1, (start + p.split_every) / len(selected)))
    elif tool in {"merge", "organize"}:
        with fitz.open() as out:
            outline = []
            for n, src in enumerate(sources):
                with open_pdf(src["path"], src.get("password") or p.password, tool) as doc:
                    selected = page_indices(src.get("pages") or p.pages, doc.page_count)
                    source_outline = doc.get_toc()
                    if n == 0:
                        copy_metadata(doc, out, p)
                    mapping = {}
                    for offset, index in enumerate(selected):
                        mapping.setdefault(index + 1, out.page_count + offset + 1)
                    doc.select(selected)
                    if p.rotation:
                        for page in doc:
                            page.set_rotation((page.rotation + p.rotation) % 360)
                    out.insert_pdf(doc, links=True, annots=True, widgets=True)
                    for level, title, page in source_outline:
                        if page in mapping:
                            level = min(level, (outline[-1][0] + 1) if outline else 1)
                            outline.append([level, title, mapping[page]])
                tick((n + 1) / len(sources))
            if not out.page_count:
                raise ValueError("No pages selected.")
            metadata(out, p)
            if outline:
                out.set_toc(outline)
            out.save(target("merged" if tool == "merge" else Path(sources[0]["path"]).stem + "_organized", ".pdf"), garbage=3, deflate=True)
    else:
        src = sources[0]
        path, name = src["path"], Path(src["path"]).stem
        password = src.get("password") or p.password
        if tool == "image":
            frames = frame_indices(path, p)
            for frame in frames:
                image, meta = image_data(path, p, frame)
                suffix = f"_f{frame + 1:04d}" if len(frames) > 1 else ""
                save_image(image, target(name + suffix, EXTENSIONS[p.format]), p, meta)
                image.close()
                tick((frame + 1) / len(frames))
        elif tool == "ocr" and Path(path).suffix.lower() != ".pdf":
            image, _ = image_data(path, p)
            buf = io.BytesIO()
            flatten(image, p.background).save(buf, format="PNG")
            pix = fitz.Pixmap(buf.getvalue())
            pix.set_dpi(p.dpi, p.dpi)
            data = pix.pdfocr_tobytes(language=language, tessdata=tessdata)
            with fitz.open(stream=data, filetype="pdf") as recognized:
                if p.ocr_output == "txt":
                    target(name, ".txt").write_text(recognized[0].get_text(), "utf-8")
                else:
                    metadata(recognized, p)
                    recognized.save(target(name + "_ocr", ".pdf"))
        else:
            operation = "extract" if tool == "pdf_images" and p.extract_images else "ocr_pdf" if tool == "ocr" and p.ocr_output == "pdf" else tool
            with open_pdf(path, password, operation) as doc:
                indices = page_indices(src.get("pages") or p.pages, doc.page_count)
                if tool == "pdf_images":
                    for n, index in enumerate(indices):
                        page = doc[index]
                        if p.extract_images:
                            for j, info in enumerate(page.get_images(full=True)):
                                pix = fitz.Pixmap(doc, info[0])
                                if pix.width * pix.height > p.max_megapixels * 1_000_000:
                                    raise ValueError("IMAGE_PIXEL_LIMIT")
                                if info[1]:
                                    # Matte decoding can already add alpha. Mask composition
                                    # requires color channels only, then applies the PDF mask.
                                    if pix.alpha:
                                        pix = fitz.Pixmap(pix, 0)
                                    pix = fitz.Pixmap(pix, fitz.Pixmap(doc, info[1]))
                                if pix.colorspace and pix.colorspace.n not in {1, 3}:
                                    pix = fitz.Pixmap(fitz.csRGB, pix)
                                if pix.alpha:
                                    # MuPDF stores premultiplied samples; Pillow expects
                                    # straight alpha when it writes PNG or composites JPEG.
                                    gray = pix.colorspace.n == 1
                                    image = Image.frombytes("La" if gray else "RGBa", (pix.width, pix.height), pix.samples).convert("LA" if gray else "RGBA")
                                else:
                                    image = pix.pil_image()
                                if p.rotation:
                                    image = image.rotate(-p.rotation, expand=True)
                                if p.color_mode == "L":
                                    image = image.convert("LA" if "A" in image.getbands() else "L")
                                save_image(image, target(f"{name}_p{index + 1:04d}_img{j + 1:03d}", EXTENSIONS[p.format]), p)
                                image.close()
                        else:
                            pix = render(page, p)
                            save_image(pix.pil_image(), target(f"{name}_p{index + 1:04d}", EXTENSIONS[p.format]), p)
                        tick((n + 1) / len(indices))
                elif tool == "pdf_text":
                    texts = []
                    for n, index in enumerate(indices):
                        text = doc[index].get_text("text", sort=p.text_layout)
                        if p.force_ocr or not text.strip():
                            tp = doc[index].get_textpage_ocr(language=language, dpi=p.dpi, full=p.force_ocr, tessdata=tessdata)
                            text = doc[index].get_text("text", textpage=tp, sort=p.text_layout)
                        texts.append(text)
                        tick((n + 1) / len(indices))
                    target(name, ".txt").write_text(("\n\f\n" if p.page_separator else "\n").join(texts), "utf-8")
                elif tool == "encrypt":
                    perm = fitz.PDF_PERM_ACCESSIBILITY
                    for key, flag in [("allow_print", fitz.PDF_PERM_PRINT), ("allow_copy", fitz.PDF_PERM_COPY), ("allow_annotate", fitz.PDF_PERM_ANNOTATE), ("allow_modify", fitz.PDF_PERM_MODIFY), ("allow_forms", fitz.PDF_PERM_FORM), ("allow_assemble", fitz.PDF_PERM_ASSEMBLE)]:
                        if not p.restrict or getattr(p, key):
                            perm |= flag
                    metadata(doc, p)
                    user = p.opening_password if p.require_opening else ""
                    owner = p.owner_password if p.restrict else user
                    doc.save(target(name + "_encrypted", ".pdf"), encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw=owner, user_pw=user, permissions=perm, garbage=3, deflate=True)
                elif tool == "decrypt":
                    metadata(doc, p)
                    doc.save(target(name + "_decrypted", ".pdf"), encryption=fitz.PDF_ENCRYPT_NONE, garbage=3, deflate=True)
                elif tool == "compress":
                    if p.compression == "lossy":
                        doc.rewrite_images(dpi_threshold=p.dpi_threshold, dpi_target=p.target_dpi, quality=p.quality)
                    metadata(doc, p)
                    doc.save(target(name + "_compressed", ".pdf"), garbage=4, deflate=True, use_objstms=1, encryption=fitz.PDF_ENCRYPT_KEEP)
                elif tool == "ocr":
                    texts = []
                    with fitz.open() as out:
                        copy_metadata(doc, out, p)
                        for n, index in enumerate(indices):
                            page = doc[index]
                            existing = page.get_text("text", sort=p.text_layout)
                            if existing.strip() and not p.force_ocr:
                                out.insert_pdf(doc, from_page=index, to_page=index)
                                texts.append(existing)
                            else:
                                data = render(page, p).pdfocr_tobytes(language=language, tessdata=tessdata)
                                with fitz.open(stream=data, filetype="pdf") as recognized:
                                    texts.append(recognized[0].get_text("text", sort=p.text_layout))
                                    out.insert_pdf(recognized)
                            tick((n + 1) / len(indices))
                        if p.ocr_output == "txt":
                            target(name, ".txt").write_text(("\n\f\n" if p.page_separator else "\n").join(texts), "utf-8")
                        else:
                            metadata(out, p)
                            out.save(target(name + "_ocr", ".pdf"), deflate=True, garbage=3)
    if not outputs:
        raise ValueError("NO_OUTPUT: No matching content was found.")
    for item in outputs:
        output = Path(item["path"])
        item["size"] = output.stat().st_size
        if output.suffix == ".pdf":
            with fitz.open(output) as doc:
                if doc.needs_pass:
                    doc.authenticate(p.owner_password or p.opening_password or p.password)
                item["pages"] = doc.page_count
                thumb = folder / f"preview-{len(preview):05d}.png"
                doc[0].get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False).save(thumb)
                preview.append(str(thumb))
        elif output.suffix != ".txt":
            with Image.open(output) as image:
                thumb = folder / f"preview-{len(preview):05d}.png"
                image.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
                image.save(thumb, format="PNG")
                preview.append(str(thumb))
    tick(1)
    return {"outputs": outputs, "previews": preview, "warnings": warnings, "dependencies": dependencies}


def worker_entry(tool, sources, parameters, directory, tessdata, progress):
    try:
        result = run_conversion(tool, sources, parameters, directory, tessdata, progress)
    except Exception as exc:
        result = {"error": str(exc)[:600], "error_type": type(exc).__name__}
    Path(directory, "result.json").write_text(json.dumps(result), "utf-8")
