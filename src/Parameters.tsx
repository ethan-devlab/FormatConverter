import {
  Checkbox,
  Field,
  Input,
  Select,
  Tooltip,
} from "@fluentui/react-components";
import { InfoRegular } from "@fluentui/react-icons";
import { useTranslation } from "react-i18next";
import type { Params, Tool } from "./api";
import { parseIconSizes, standardIconSizes } from "./ico";
import { validQuality } from "./job-feedback";

export function ParameterFields({
  tool,
  value,
  onChange,
  encoders,
}: {
  tool: Tool;
  value: Params;
  onChange: (key: string, v: string | number | boolean) => void;
  encoders: string[];
}) {
  const { t } = useTranslation();
  const field = (
    key: string,
    kind: "number" | "password" | "text" | "check" | string[],
    help?: string,
  ) => {
    const label = (
      <span className="field-label">
        {t(`p.${key}`)}
        {help && (
          <Tooltip content={t(help)} relationship="description">
            <span tabIndex={0} aria-label={t(help)}>
              <InfoRegular />
            </span>
          </Tooltip>
        )}
      </span>
    );
    if (kind === "check")
      return (
        <Checkbox
          key={key}
          label={label}
          checked={!!value[key]}
          onChange={(_, d) => onChange(key, !!d.checked)}
        />
      );
    return (
      <Field key={key} label={label}
        validationState={key === "quality" && !validQuality(value[key]) ? "error" : "none"}
        validationMessage={key === "quality" && !validQuality(value[key]) ? t("qualityInvalid") : undefined}>
        {Array.isArray(kind) ? (
          <Select
            value={String(value[key])}
            onChange={(e) =>
              onChange(
                key,
                key === "rotation" ? Number(e.target.value) : e.target.value,
              )
            }
          >
            {kind.map((option) => (
              <option key={option} value={option} disabled={key === "text_browser" && option === "safari"}>
                {t(`o.${option}`, { defaultValue: option })}
              </option>
            ))}
          </Select>
        ) : (
          <Input
            type={kind}
            value={String(value[key])}
            onChange={(_, d) =>
              onChange(key, kind === "number" ? Number(d.value) : d.value)
            }
            min={key === "quality" ? 1 : key === "text_font_size" ? 6 : ["text_line_height", "text_tab_width"].includes(key) ? 1 : kind === "number" ? 0 : undefined}
            max={key === "quality" ? 100 : key === "text_font_size" ? 72 : key === "text_line_height" ? 3 : key === "text_tab_width" ? 16 : undefined}
            step={key === "text_line_height" ? 0.1 : kind === "number" ? 1 : undefined}
            autoComplete={kind === "password" ? "new-password" : "off"}
          />
        )}
      </Field>
    );
  };
  const common = [];
  if (["pdf_images", "pdf_text", "merge", "organize", "ocr"].includes(tool))
    common.push(field("pages", "text", "pagesHelp"));
  if (tool === "images_pdf") {
    common.push(field("page_size", ["A4", "Letter", "Original", "Custom"]));
    if (value.page_size === "Custom")
      common.push(
        <div className="field-grid" key="page-dims">
          {field("page_width", "number")}
          {field("page_height", "number")}
        </div>,
      );
    common.push(
      field("orientation", ["portrait", "landscape"]),
      field("fit", ["contain", "cover", "stretch"]),
      field("margin", "number"),
      field("background", "text"),
      field("lossless", "check"),
    );
    if (!value.lossless) common.push(field("quality", "number"));
  }
  if (tool === "text_pdf") {
    common.push(field("text_mode", ["auto", "plain", "markdown"], "textPdfHelp"),
      field("text_encoding", ["auto", "utf-8", "utf-16-le", "utf-16-be", "big5"], "textEncodingHelp"),
      field("page_size", ["A4", "Letter", "Custom"]));
    if (value.page_size === "Custom") common.push(
      <div className="field-grid" key="text-page-size">{field("page_width", "number")}{field("page_height", "number")}</div>);
    common.push(field("orientation", ["portrait", "landscape"]), field("margin", "number"),
      field("text_font", ["sans-serif", "serif", "monospace"], "textFontHelp"),
      field("text_font_size", "number"), field("text_line_height", "number"), field("text_tab_width", "number"),
      field("text_color", "text"), field("background", "text"));

  }
  if (["pdf_images", "image"].includes(tool))
    common.push(
      field(
        "format",
        ["PNG", "JPEG", "WEBP", "TIFF", "BMP", "ICO", "HEIF", "AVIF"].filter(
          (f) => encoders.includes(f),
        ),
      ),
    );
  if (["image", "pdf_images"].includes(tool) && value.format === "ICO") {
    const sizes = parseIconSizes(String(value.ico_sizes));
    common.push(
      <div key="ico-sizes">
        <div className="ico-output-summary" role="status" aria-live="polite">
          <strong>{t("icoOutputDimensions")}</strong>
          {sizes ? (
            <>
              <p>{sizes.map((edge) => `${edge} × ${edge} px`).join(" · ")}</p>
              <span>{t("icoOutputContainer", { count: sizes.length })}</span>
            </>
          ) : <p>{t("icoInvalid")}</p>}
        </div>
        <fieldset className="ico-size-fieldset">
          <legend>{t("p.ico_sizes")}</legend>
          <div className="ico-size-options">
            {standardIconSizes.map((edge) => (
              <Checkbox key={edge} label={`${edge} × ${edge} px`}
                checked={sizes?.includes(edge) ?? false}
                onChange={(_, data) => {
                  const next = new Set(sizes ?? []);
                  if (data.checked) next.add(edge); else next.delete(edge);
                  onChange("ico_sizes", [...next].sort((a, b) => a - b).join(","));
                }} />
            ))}
          </div>
        </fieldset>
        <p className="help">{t("icoHelp")}</p>
        <details>
          <summary>{t("icoCustom")}</summary>
          <Field label={t("icoCustomLabel")} validationState={sizes ? "none" : "error"}>
            <Input value={String(value.ico_sizes)} placeholder="16,32,256"
              onChange={(_, data) => onChange("ico_sizes", data.value)} />
          </Field>
        </details>
        {!sizes && <p role="alert" className="help">{t("icoInvalid")}</p>}
      </div>,
    );
  }
  if (tool === "pdf_images")
    common.push(
      field("extract_images", "check"),
      field("dpi", "number"),
      field("rotation", ["0", "90", "180", "270"]),
    );
  if (["image", "images_pdf"].includes(tool))
    common.push(field("frames", ["all", "first"]));
  if (["image", "images_pdf"].includes(tool))
    common.push(
      <div className="field-grid" key="image-dims">
        {field("width", "number", "resizeHelp")}
        {field("height", "number", "resizeHelp")}
      </div>,
      field("keep_ratio", "check"),
      field("crop", "text", "cropHelp"),
      field("rotation", ["0", "90", "180", "270"]),
    );
  if (
    ["pdf_images", "image"].includes(tool) &&
    ["JPEG", "WEBP", "HEIF", "AVIF"].includes(String(value.format))
  )
    common.push(field("quality", "number"));
  if (
    [
      "pdf_text",
      "decrypt",
      "encrypt",
      "merge",
      "organize",
      "compress",
      "pdf_images",
      "ocr",
    ].includes(tool)
  )
    common.push(field("password", "password"));
  if (tool === "encrypt") {
    common.push(field("require_opening", "check"));
    if (value.require_opening)
      common.push(field("opening_password", "password"));
    common.push(field("restrict", "check"));
    if (value.restrict)
      common.push(
        field("owner_password", "password"),
        <p className="help" key="permissions">
          {t("permissionHint")}
        </p>,
        ...[
          "allow_print",
          "allow_copy",
          "allow_annotate",
          "allow_modify",
          "allow_forms",
          "allow_assemble",
        ].map((k) => field(k, "check")),
      );
  }
  if (["pdf_text", "ocr"].includes(tool))
    common.push(
      field("ocr_language", ["eng", "chi_tra", "eng+chi_tra"]),
      field("force_ocr", "check"),
      <p className="help" key="ocr">
        {t("ocrHint")}
      </p>,
    );
  if (tool === "ocr")
    common.push(field("ocr_output", ["pdf", "txt"]), field("dpi", "number"));
  if (tool === "pdf_text")
    common.push(
      field("text_layout", "check"),
      field("page_separator", "check"),
    );
  if (tool === "organize") {
    common.push(
      field("organize_mode", ["single", "split"]),
      field("rotation", ["0", "90", "180", "270"]),
    );
    if (value.organize_mode === "split")
      common.push(field("split_every", "number"));
  }
  if (tool === "compress") {
    common.push(
      field("compression", ["lossless", "lossy"]),
      <p className="help" key="compression-help">
        {t("compressHelp")}
      </p>,
    );
    if (value.compression === "lossy")
      common.push(
        field("quality", "number"),
        field("dpi_threshold", "number"),
        field("target_dpi", "number"),
      );
  }
  return (
    <>
      <div className="parameter-fields">{common}</div>
      <details className="advanced">
        <summary>{t("advanced")}</summary>
        <div className="parameter-fields">
          {tool !== "pdf_text" && field("metadata", ["keep", "remove"])}
          {[
            "images_pdf",
            "text_pdf",
            "merge",
            "organize",
            "encrypt",
            "decrypt",
            "compress",
            "ocr",
          ].includes(tool) && (
            <>
              {field("title", "text")}
              {field("author", "text")}
            </>
          )}
          {["image", "pdf_images", "images_pdf"].includes(tool) && (
            <>
              {field("color_mode", ["RGB", "L"])}
              {field("optimize", "check")}
              {["image", "images_pdf"].includes(tool) && (
                <>
                  {field("resample", ["lanczos", "bicubic", "nearest"])}
                  {field("sharpen", "check")}
                  {field("preserve_dpi", "check")}
                  {field("dpi", "number")}
                </>
              )}
              {["image", "pdf_images"].includes(tool) &&
                ["JPEG", "BMP"].includes(String(value.format)) &&
                field("background", "text")}
              {value.format === "WEBP" && field("lossless", "check")}
            </>
          )}
          {["ocr", "pdf_text"].includes(tool) &&
            value.ocr_language === "eng+chi_tra" &&
            field("ocr_chinese_first", "check", "ocrOrderHelp")}
          {tool === "pdf_text" && field("dpi", "number")}
          {["pdf_images", "images_pdf", "image", "ocr"].includes(tool) &&
            field("max_megapixels", "number")}
        </div>
      </details>
    </>
  );
}
