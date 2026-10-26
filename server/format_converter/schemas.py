from __future__ import annotations

import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Tool = Literal["images_pdf", "text_pdf", "pdf_images", "pdf_text", "merge", "encrypt", "decrypt", "image", "organize", "ocr", "compress"]


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pages: str = ""
    page_size: Literal["A4", "Letter", "Original", "Custom"] = "A4"
    page_width: float = Field(210, gt=0, le=5000)
    page_height: float = Field(297, gt=0, le=5000)
    orientation: Literal["portrait", "landscape"] = "portrait"
    margin: float = Field(10, ge=0, le=1000)
    fit: Literal["contain", "cover", "stretch"] = "contain"
    background: str = Field("#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    dpi: int = Field(150, ge=36, le=1200)
    quality: int = Field(85, ge=1, le=100)
    format: Literal["PNG", "JPEG", "WEBP", "TIFF", "BMP", "ICO", "HEIF", "AVIF"] = "PNG"
    width: int = Field(0, ge=0, le=30000)
    height: int = Field(0, ge=0, le=30000)
    frames: Literal["all", "first"] = "all"
    preserve_dpi: bool = False
    keep_ratio: bool = True
    resample: Literal["lanczos", "bicubic", "nearest"] = "lanczos"
    crop: str = ""
    rotation: Literal[0, 90, 180, 270] = 0
    sharpen: bool = False
    optimize: bool = True
    lossless: bool = False
    metadata: Literal["keep", "remove"] = "keep"
    color_mode: Literal["RGB", "L"] = "RGB"
    text_layout: bool = True
    text_mode: Literal["auto", "plain", "markdown"] = "auto"
    text_encoding: Literal["auto", "utf-8", "utf-16-le", "utf-16-be", "big5"] = "auto"
    text_font: Literal["sans-serif", "serif", "monospace"] = "sans-serif"
    text_font_size: float = Field(12, ge=6, le=72)
    text_line_height: float = Field(1.5, ge=1, le=3)
    text_tab_width: int = Field(4, ge=1, le=16)
    text_color: str = Field("#28231f", pattern=r"^#[0-9a-fA-F]{6}$")
    text_browser: Literal["edge", "chrome", "firefox", "safari"] = "edge"
    text_browser_path: str = Field("", max_length=2048)
    page_separator: bool = True
    organize_mode: Literal["single", "split"] = "single"
    split_every: int = Field(1, ge=1, le=100000)
    extract_images: bool = False
    opening_password: str = Field("", max_length=40)
    owner_password: str = Field("", max_length=40)
    password: str = Field("", max_length=256)
    require_opening: bool = True
    restrict: bool = False
    allow_print: bool = True
    allow_copy: bool = True
    allow_annotate: bool = True
    allow_modify: bool = False
    allow_forms: bool = True
    allow_assemble: bool = False
    ocr_language: Literal["eng", "chi_tra", "eng+chi_tra"] = "eng"
    ocr_chinese_first: bool = True
    force_ocr: bool = False
    ocr_output: Literal["pdf", "txt"] = "pdf"
    compression: Literal["lossless", "lossy"] = "lossless"
    target_dpi: int = Field(150, ge=36, le=600)
    dpi_threshold: int = Field(225, ge=37, le=1200)
    ico_sizes: str = "16,24,32,48,64,128,256"
    title: str = Field("", max_length=300)
    author: str = Field("", max_length=300)
    max_megapixels: int = Field(100, ge=1, le=500)

    @model_validator(mode="after")
    def validate_ico_sizes(self):
        if self.format == "ICO":
            if len(self.ico_sizes) > 2048 or not re.fullmatch(r"\s*[0-9]{1,3}\s*(,\s*[0-9]{1,3}\s*)*", self.ico_sizes):
                raise ValueError("ICO sizes must be comma-separated integers from 1 to 256, such as 16,32,256.")
            sizes = {int(part.strip()) for part in self.ico_sizes.split(",")}
            if any(size < 1 or size > 256 for size in sizes):
                raise ValueError("ICO sizes must be between 1 and 256.")
            self.ico_sizes = ",".join(str(size) for size in sorted(sizes))
        return self


class Source(BaseModel):
    path: str
    pages: str = ""
    password: str = Field("", max_length=256)


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: Tool
    sources: list[Source] = Field(min_length=1, max_length=10000)
    parameters: Parameters = Field(default_factory=Parameters)
    output_directory: str = ""
    output_filename: str = Field("", max_length=180)
    filename: str = Field("", max_length=180)
    naming: str = "{name}"
    collision: Literal["rename", "skip", "overwrite", "ask"] = "rename"
    preview: bool = False

    @model_validator(mode="after")
    def validate_operation(self):
        p = self.parameters
        if self.tool == "text_pdf" and p.page_size == "Original":
            raise ValueError("Text to PDF requires a fixed or custom page size.")
        if self.tool == "encrypt":
            if not p.require_opening and not p.restrict:
                raise ValueError("Choose opening protection or permission restrictions.")
            if p.require_opening and not p.opening_password:
                raise ValueError("An opening password is required for opening protection.")
            if p.restrict and not p.owner_password:
                raise ValueError("An owner password is required for permission restrictions.")
            if p.restrict and p.require_opening and p.owner_password == p.opening_password:
                raise ValueError("Use a separate owner password for permission restrictions.")
        if self.tool == "compress" and p.compression == "lossy" and p.target_dpi >= p.dpi_threshold:
            raise ValueError("Target DPI must be less than the downsampling threshold.")
        if self.output_filename and ("/" in self.output_filename or "\\" in self.output_filename or self.output_filename in (".", "..")):
            raise ValueError("The output filename must be a filename, not a path.")
        if self.output_filename and self.preview:
            raise ValueError("An exact output filename requires a completed preview.")
        if self.filename and ("/" in self.filename or "\\" in self.filename or self.filename in (".", "..")):
            raise ValueError("The output filename must be a filename, not a path.")
        if not self.preview and not self.output_directory:
            raise ValueError("Choose an output folder.")
        return self
