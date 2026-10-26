import { useEffect, useRef, useState } from "react";
import {
  Button,
  Dialog,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Select,
  Spinner,
} from "@fluentui/react-components";
import {
  AddRegular,
  ArrowExpandRegular,
  ChevronLeftRegular,
  ChevronRightRegular,
  DismissRegular,
  DocumentRegular,
  EyeRegular,
  SubtractRegular,
  WeatherMoonRegular,
  WeatherSunnyRegular,
} from "@fluentui/react-icons";
import { useTranslation } from "react-i18next";
import { api, post, type Job, type Artifact } from "./api";
import { IconButton } from "./Controls";
import { WheelNavigation } from "./preview-navigation";

export function Preview({
  job,
  stale,
  dark,
  onDark,
  onError,
}: {
  job?: Job;
  stale: boolean;
  dark: boolean;
  onDark: (dark: boolean) => void;
  onError: (e: unknown) => void;
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [index, setIndex] = useState(0);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [rendered, setRendered] = useState("");
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [truncated, setTruncated] = useState(false);
  const request = useRef(0);
  const children = useRef<string[]>([]);
  const largeCanvas = useRef<HTMLDivElement>(null);
  const wheelNavigation = useRef(new WheelNavigation());
  const wheelHandler = useRef<(event: WheelEvent) => void>(() => {});
  const outputs =
    job?.tasks.flatMap((task) => task.outputs).filter((o) => !o.skipped) || [];
  const thumbs = job?.tasks.flatMap((task) => task.previews) || [];
  const output: Artifact | undefined = outputs[index];
  const pageCount = output?.pages || 1;
  const image = rendered || thumbs[index]?.url || "";
  const clean = () => {
    request.current++;
    for (const id of children.current)
      void api(`/jobs/${id}`, { method: "DELETE" }).catch(() => {});
    children.current = [];
  };
  useEffect(() => {
    clean();
    setIndex(0);
    setPage(1);
    setRendered("");
    setZoom(1);
    setBusy(false);
    return clean;
  }, [job?.id]);
  useEffect(() => {
    if (!output?.name.endsWith(".txt")) {
      setText("");
      return;
    }
    void api<{ text: string; truncated: boolean }>(
      `/artifacts/${output.id}/text`,
    )
      .then((data) => {
        setText(data.text);
        setTruncated(data.truncated);
      })
      .catch(onError);
  }, [output?.id, onError]);
  const selectOutput = (next: number) => {
    clean();
    setIndex(next);
    setPage(1);
    setRendered("");
    setZoom(1);
    setBusy(false);
  };
  const changePage = async (next: number) => {
    if (!output || busy || stale || next < 1 || next > pageCount) return;
    clean();
    const version = request.current;
    setPage(next);
    setRendered("");
    if (next === 1) return;
    setBusy(true);
    try {
      let child = await post<Job>("/preview-page", {
        artifact: output.id,
        page: next,
      });
      children.current.push(child.id);
      while (["queued", "running"].includes(child.status)) {
        await new Promise((resolve) => setTimeout(resolve, 250));
        if (version !== request.current) return;
        child = await api<Job>(`/jobs/${child.id}`);
      }
      if (version !== request.current) return;
      const artifact = child.tasks.flatMap((task) => task.outputs)[0];
      if (!artifact)
        throw new Error(
          child.tasks.find((task) => task.error)?.error || t("previewFailed"),
        );
      setRendered(artifact.url);
    } catch (e) {
      onError(e);
    } finally {
      if (version === request.current) setBusy(false);
    }
  };
  const pdfOutput = !!output?.name.toLowerCase().endsWith(".pdf");
  const imageOutput = !!output && /\.(png|jpe?g|webp|heic|heif|bmp|tiff?|avif|ico)$/i.test(output.name);
  const canPrevious = pdfOutput ? page > 1 : imageOutput && index > 0;
  const canNext = pdfOutput ? page < pageCount : imageOutput && index < outputs.length - 1;
  const navigate = (direction: number) => {
    if (busy || stale || (direction < 0 ? !canPrevious : !canNext)) return;
    if (pdfOutput) void changePage(page + direction);
    else if (imageOutput) selectOutput(index + direction);
  };
  wheelHandler.current = (event) => {
    if (!expanded || zoom !== 1 || busy || stale || (!pdfOutput && !imageOutput) ||
      (pdfOutput ? pageCount <= 1 : outputs.length <= 1) ||
      event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
    event.preventDefault();
    event.stopPropagation();
    const direction = wheelNavigation.current.step(event.deltaY, event.deltaMode, event.timeStamp);
    if (direction) navigate(direction);
  };
  useEffect(() => {
    wheelNavigation.current = new WheelNavigation();
  }, [job?.id, expanded, zoom]);
  useEffect(() => {
    const canvas = largeCanvas.current;
    if (!expanded || !canvas) return;
    const handler = (event: WheelEvent) => wheelHandler.current(event);
    canvas.addEventListener("wheel", handler, { passive: false });
    return () => canvas.removeEventListener("wheel", handler);
  }, [expanded]);
  const pager = (
    <div className="page-controls">
      <IconButton
        label={t("previous")}
        icon={<ChevronLeftRegular />}
        disabled={!canPrevious || busy || stale}
        onClick={() => navigate(-1)}
      />
      <span className="page-counter">
        {imageOutput ? index + 1 : page} / {imageOutput ? outputs.length : pageCount}
      </span>
      <IconButton
        label={t("next")}
        icon={<ChevronRightRegular />}
        disabled={!canNext || busy || stale}
        onClick={() => navigate(1)}
      />
    </div>
  );
  const content = (large = false) => (
    <div
      ref={large ? largeCanvas : undefined}
      className={`preview-canvas ${large ? "large" : ""} ${large && dark ? "dark" : ""}`}
    >
      {busy ||
      (["queued", "running"].includes(job?.status || "") && !output) ? (
        <Spinner size="small" label={t("running")} />
      ) : text ? (
        <pre className="text-preview">
          {text}
          {truncated && `\n… ${t("truncated")}`}
        </pre>
      ) : image ? (
        <img
          src={image}
          alt={t("outputPreview")}
          style={
            large
              ? {
                  width: `${zoom * 100}%`,
                  maxWidth: zoom === 1 ? "100%" : "none",
                  maxHeight: zoom === 1 ? "100%" : "none",
                }
              : undefined
          }
        />
      ) : (
        <div className="preview-placeholder">
          <DocumentRegular />
          <p>
            {t(
              job && ["failed", "partial"].includes(job.status)
                ? "previewFailed"
                : "noPreview",
            )}
          </p>
        </div>
      )}
    </div>
  );
  return (
    <>
      <section className="preview-panel" aria-label={t("outputPreview")}>
        <div className="preview-header">
          <h2>
            <EyeRegular />
            {t("outputPreview")}
          </h2>
          <IconButton
            label={t("expand")}
            icon={<ArrowExpandRegular />}
            disabled={!output}
            onClick={() => setExpanded(true)}
          />
        </div>
        {outputs.length > 1 && (
          <Select
            aria-label={t("source")}
            value={String(index)}
            onChange={(e) => selectOutput(Number(e.target.value))}
          >
            {outputs.map((o, i) => (
              <option value={i} key={o.id}>
                {o.name}
              </option>
            ))}
          </Select>
        )}
        {content()}
        <div className="preview-bottom">
          {output ? (
            <>
              {pager}
              <span className="preview-kind">{t("previewTemporary")}</span>
            </>
          ) : (
            <span />
          )}
        </div>
        {stale && (
          <div role="status" className="stale-preview">
            {t("previewStale")}
          </div>
        )}
      </section>
      <Dialog
        open={expanded}
        onOpenChange={(_, data) => setExpanded(data.open)}
      >
        <DialogSurface className="expanded-preview">
          <DialogBody>
            <DialogTitle
              action={
                <IconButton
                  label={t("close")}
                  icon={<DismissRegular />}
                  onClick={() => setExpanded(false)}
                />
              }
            >
              {t("outputPreview")}
            </DialogTitle>
            <DialogContent className="expanded-content">
              {content(true)}
              <p className="preview-wheel-hint">{t("previewWheelHelp")}</p>
              <div className="expanded-controls">
                <div className="zoom-controls">
                  <IconButton
                    label={t("zoomOut")}
                    icon={<SubtractRegular />}
                    onClick={() => setZoom((v) => Math.max(0.25, v - 0.25))}
                  />
                  <span className="page-counter">
                    {Math.round(zoom * 100)}%
                  </span>
                  <IconButton
                    label={t("zoomIn")}
                    icon={<AddRegular />}
                    onClick={() => setZoom((v) => Math.min(4, v + 0.25))}
                  />
                  <Button
                    appearance="subtle"
                    size="small"
                    onClick={() => setZoom(1)}
                  >
                    {t("fit")}
                  </Button>
                  <IconButton
                    label={t(dark ? "lightCanvas" : "darkCanvas")}
                    icon={
                      dark ? <WeatherSunnyRegular /> : <WeatherMoonRegular />
                    }
                    onClick={() => onDark(!dark)}
                  />
                </div>
                {pager}
              </div>
            </DialogContent>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </>
  );
}
