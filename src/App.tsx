import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Input,
  ProgressBar,
  Select,
  Spinner,
  Tab,
  TabList,
} from "@fluentui/react-components";
import {
  ChevronDownRegular,
  ChevronUpRegular,
  AddRegular,
  ArrowDownloadRegular,
  ArrowSyncRegular,
  DeleteRegular,
  DismissRegular,
  DocumentRegular,
  EyeRegular,
  FolderRegular,
  ImageRegular,
  LockClosedRegular,
  LockOpenRegular,
  MailRegular,
  PlayRegular,
  SaveRegular,
  ScanTextRegular,
  SettingsRegular,
  TextDescriptionRegular,
} from "@fluentui/react-icons";
import { useTranslation } from "react-i18next";
import i18n from "./i18n";
import {
  api,
  post,
  defaults,
  size,
  tools,
  type Artifact,
  type Bootstrap,
  type FileEntry,
  type Job,
  type Params,
  type Preferences,
  type QueueItem,
  type Root,
  type Tool,
} from "./api";
import { IconButton } from "./Controls";
import { FileTree, type FileEvents } from "./FileTree";
import { pathKey, uniqueEntries } from "./explorer";
import { Queue } from "./Queue";
import { ParameterFields } from "./Parameters";
import { Preview } from "./Preview";
import { parseIconSizes } from "./ico";
import { usesQuality, validQuality, errorMessageKey } from "./job-feedback";
import { JobFailures, JobWarnings, OutputSizes } from "./JobFeedback";

interface Inspection {
  name: string;
  encrypted?: boolean;
  readable?: boolean;
  owner?: boolean;
  can_decrypt?: boolean;
  pages?: number;
  error?: string;
}
interface Modal {
  kind: string;
  entries?: FileEntry[];
  folder?: string;
  item?: QueueItem;
  data?: Record<string, unknown>;
}
const toolIcons: Record<Tool, React.ReactElement> = {
  images_pdf: <ImageRegular />,
  text_pdf: <TextDescriptionRegular />,
  pdf_images: <DocumentRegular />,
  pdf_text: <TextDescriptionRegular />,
  merge: <DocumentRegular />,
  encrypt: <LockClosedRegular />,
  decrypt: <LockOpenRegular />,
  image: <ImageRegular />,
  organize: <DocumentRegular />,
  ocr: <ScanTextRegular />,
  compress: <DocumentRegular />,
};

export default function App() {
  const { t } = useTranslation();
  const [boot, setBoot] = useState<Bootstrap>();
  const [prefs, setPrefs] = useState<Preferences>();
  const [roots, setRoots] = useState<Root[]>([]);
  const [tool, setTool] = useState<Tool>("images_pdf");
  const [parameterSets, setParameterSets] = useState<
    Partial<Record<Tool, Params>>
  >({});
  const [items, setItems] = useState<QueueItem[]>([]);
  const [selected, setSelected] = useState(new Set<string>());
  const [outputFolder, setOutputFolder] = useState("");
  const [filename, setFilename] = useState("");
  const [naming, setNaming] = useState("{name}");
  const [collision, setCollision] = useState("rename");
  const [selectedFolder, setSelectedFolder] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{ key: string; count?: number } | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [current, setCurrent] = useState("");
  const [previewId, setPreviewId] = useState("");
  const [previewKey, setPreviewKey] = useState("");
  const [modal, setModal] = useState<Modal | null>(null);
  const [dialogText, setDialogText] = useState("");
  const [filePages, setFilePages] = useState("");
  const [filePassword, setFilePassword] = useState("");
  const [drawer, setDrawer] = useState(false);
  const [preset, setPreset] = useState("");
  const [events, setEvents] = useState<FileEvents>({ version: 0, events: [] });
  const upload = useRef<HTMLInputElement>(null);
  const [explorerWidth, setExplorerWidth] = useState(260);
  const [parameterWidth, setParameterWidth] = useState(360);
  const [inspection, setInspection] = useState<Inspection[]>([]);
  const [parametersOpen, setParametersOpen] = useState(false);
  const [settingsDraft, setSettingsDraft] = useState<Preferences>();
  const params: Params = tool === "text_pdf" ? { ...(parameterSets[tool] || defaults),
    text_browser: prefs?.text_browser || "edge",
    text_browser_path: prefs?.text_browser_path || "",
  } : (parameterSets[tool] || defaults);
  const setParams = (update: Params | ((old: Params) => Params)) =>
    setParameterSets((previous) => ({
      ...previous,
      [tool]:
        typeof update === "function"
          ? update(previous[tool] || defaults)
          : update,
    }));
  const onError = useCallback((e: unknown) => {
    setError(e instanceof Error ? e.message : String(e));
  }, []);
  const chosen = useMemo(
    () => items.filter((item) => selected.has(item.id)),
    [items, selected],
  );
  const sources = useMemo(
    () =>
      chosen.map((item) => ({
        path: item.path,
        pages: item.pages,
        password: item.password,
      })),
    [chosen],
  );
  const signature = JSON.stringify({ tool, parameters: params, sources });
  const previewJob = jobs.find((j) => j.id === previewId);
  const stale = !!previewId && previewKey !== signature;
  const currentJob = jobs.find((j) => j.id === current);
  const active = jobs.filter((j) => ["running", "queued"].includes(j.status));
  useEffect(() => {
    let mounted = true;
    void (async () => {
      await post("/session");
      const data = await api<Bootstrap>("/bootstrap");
      if (mounted) {
        setBoot(data);
        setPrefs(data.preferences);
        setExplorerWidth(data.preferences.explorer_width);
        setParameterWidth(data.preferences.parameter_width);
        setRoots(data.roots);
        await i18n.changeLanguage(data.preferences.language);
      }
    })().catch(onError);
    return () => {
      mounted = false;
    };
  }, [onError]);
  useEffect(() => {
    if (!boot) return;
    const id = crypto.randomUUID();
    const heartbeat = () =>
      void post("/clients/heartbeat", { id }).catch(() => {});
    heartbeat();
    const timer = setInterval(heartbeat, 5000);
    const close = () =>
      navigator.sendBeacon(
        "/api/clients/close",
        new Blob([JSON.stringify({ id })], { type: "application/json" }),
      );
    window.addEventListener("pagehide", close);
    return () => {
      clearInterval(timer);
      window.removeEventListener("pagehide", close);
    };
  }, [!!boot]);
  useEffect(() => {
    if (!boot) return;
    let mounted = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const data = await api<Job[]>("/jobs");
        if (mounted) setJobs(data);
      } catch (e) {
        if (mounted) onError(e);
      } finally {
        if (mounted) timer = setTimeout(poll, 700);
      }
    };
    void poll();
    return () => {
      mounted = false;
      clearTimeout(timer);
    };
  }, [!!boot, onError]);
  useEffect(() => {
    if (!boot) return;
    const source = new EventSource("/api/events/stream");
    source.onmessage = (event) => {
      const data = JSON.parse(event.data) as FileEvents;
      setEvents(data);
    };
    return () => source.close();
  }, [!!boot]);
  useEffect(() => {
    if (
      previewId &&
      (events.rescan ||
        events.events.some(
          (event) =>
            event.rescan || items.some((item) => item.path === event.path),
        ))
    )
      setPreviewKey("source-changed");
  }, [events]);
  useEffect(() => {
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);
  const savePreferences = async (values: Partial<Preferences>) => {
    try {
      const next = await api<Preferences>("/preferences", {
        method: "PUT",
        body: JSON.stringify(values),
      });
      setPrefs(next);
      if (values.language) await i18n.changeLanguage(next.language);
      return next;
    } catch (e) {
      onError(e);
    }
  };
  const addFiles = useCallback((entries: FileEntry[]) => {
    const added = entries.filter((entry) => !entry.directory && !entry.link);
    setItems((old) => {
      const paths = new Set(old.map((x) => pathKey(x.path)));
      const next = uniqueEntries(added)
        .filter((entry) => !paths.has(pathKey(entry.path)))
        .map((entry) => ({
          ...entry,
          id: crypto.randomUUID(),
          pages: "",
          password: "",
        }));
      setSelected((v) => new Set([...v, ...next.map((x) => x.id)]));
      return [...old, ...next];
    });
  }, []);
  const updateItems = (next: QueueItem[]) => {
    setItems(next);
    const ids = new Set(next.map((x) => x.id));
    setSelected((v) => new Set([...v].filter((id) => ids.has(id))));
  };
  const openModal = (next: Modal, text = "") => {
    setError("");
    setDialogText(text);
    if (next.kind === "settings") setSettingsDraft(prefs);
    setModal(next);
  };
  const addRootPath = async (path: string) => {
    const data = await post<Root[]>("/roots", { path });
    setRoots(data);
    return data;
  };
  const browseFolder = async (forOutput = false) => {
    setBusy(true);
    try {
      const result = await post<{ path: string }>("/pick-folder");
      if (result.path) {
        await addRootPath(result.path);
        if (forOutput) setOutputFolder(result.path);
      }
    } catch (e) {
      onError(e);
      openModal({ kind: forOutput ? "output-folder" : "add-root" });
    } finally {
      setBusy(false);
    }
  };
  const fileAction = async (
    action: string,
    entries: FileEntry[],
    folder: string,
  ) => {
    if (action === "output") {
      setOutputFolder(folder);
      return;
    }
    if (action === "rename") {
      openModal({ kind: "rename", entries }, entries[0]?.name || "");
      return;
    }
    if (action === "delete") {
      openModal({ kind: "delete", entries });
      return;
    }
    if (action === "properties") {
      try {
        const data = await post<Record<string, unknown>>("/files/properties", {
          path: entries[0]?.path,
        });
        openModal({ kind: "properties", data });
      } catch (e) {
        onError(e);
      }
      return;
    }
    try {
      const result = await post<{
        count?: number;
        results?: { ok: boolean; error?: string }[];
      }>("/files/operation", {
        action,
        paths: entries.map((e) => e.path),
        destination: folder,
      });
      if (result.results?.some((r) => !r.ok))
        onError(
          result.results
            .filter((r) => !r.ok)
            .map((r) => r.error)
            .join("\n"),
        );
      else if (action === "copy" || action === "cut")
        setNotice({
          key: action === "copy" ? "copied" : "cutReady",
          count: result.count,
        });
    } catch (e) {
      onError(e);
    }
  };
  const uploadFiles = async (files: FileList | File[]) => {
    if (!files.length) return;
    setBusy(true);
    const data = new FormData();
    Array.from(files).forEach((file) => data.append("files", file, file.name));
    try {
      addFiles(
        await api<FileEntry[]>("/uploads", { method: "POST", body: data }),
      );
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
      if (upload.current) upload.current.value = "";
    }
  };
  const dropFiles = (event: React.DragEvent) => {
    event.preventDefault();
    const local = event.dataTransfer.getData(
      "application/x-format-converter-files",
    );
    if (local) {
      try {
        addFiles(JSON.parse(local));
      } catch (e) {
        onError(e);
      }
    } else if (event.dataTransfer.files.length)
      void uploadFiles(event.dataTransfer.files);
  };
  const invalidIcoSizes = ["image", "pdf_images"].includes(tool) && params.format === "ICO" && !parseIconSizes(String(params.ico_sizes));
  const invalidQuality = usesQuality(tool, params) && !validQuality(params.quality);
  const submit = async (preview: boolean) => {
    if (invalidQuality) {
      setError(t("qualityInvalid"));
      return;
    }
    if (invalidIcoSizes) {
      setError(t("icoInvalid"));
      return;
    }
    if (!chosen.length) {
      setError(t("noSelected"));
      return;
    }
    const pdfOnly = [
      "pdf_images",
      "pdf_text",
      "merge",
      "encrypt",
      "decrypt",
      "organize",
      "compress",
    ].includes(tool);
    if (
      chosen.some((item) =>
        tool === "text_pdf" ? ![".txt", ".md", ".markdown", ".text"].includes(item.extension.toLowerCase()) : pdfOnly
          ? item.extension.toLowerCase() !== ".pdf"
          : tool !== "ocr" && item.extension.toLowerCase() === ".pdf",
      )
    ) {
      setError(t("incompatible"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = { tool, sources, parameters: params, output_directory: outputFolder,
        filename, naming, collision, preview: true };
      let result: Job;
      const remember = (job: Job) => {
        setCurrent(job.id);
        setJobs((old) => [job, ...old.filter((j) => j.id !== job.id)]);
      };
      if (!preview && previewJob && ["done", "partial", "queued", "running"].includes(previewJob.status) && !stale) {
        result = previewJob;
      } else {
        if (previewId) await api(`/jobs/${previewId}`, { method: "DELETE" });
        result = await post<Job>("/jobs", body);
        setPreviewId(result.id);
        setPreviewKey(signature);
        remember(result);
      }
      if (!preview) {
        setNotice({ key: "preparingOutput" });
        while (["queued", "running"].includes(result.status)) {
          await new Promise((resolve) => setTimeout(resolve, 400));
          result = await api<Job>(`/jobs/${result.id}`);
          remember(result);
        }
        setNotice(null);
        const outputs = result.tasks.flatMap((task) => task.outputs).filter((output) => !output.skipped);
        if (!outputs.length) return;
        const destination = await post<{ path: string; single: boolean }>(`/jobs/${result.id}/pick-output`, body);
        if (!destination.path) return;
        const split = Math.max(destination.path.lastIndexOf("/"), destination.path.lastIndexOf("\\"));
        const folder = destination.single ? destination.path.slice(0, split + 1) : destination.path;
        await addRootPath(folder);
        setOutputFolder(folder);
        result = await post<Job>(`/jobs/${result.id}/commit`, { ...body, preview: false,
          output_directory: folder,
          output_filename: destination.single ? destination.path.slice(split + 1) : "",
          collision: destination.single ? "overwrite" : collision });
        setPreviewId("");
        setPreviewKey("");
        setNotice(result.status === "done" ? { key: "jobSuccess" } : null);
      }
      remember(result);
    } catch (e) {
      setNotice(null);
      onError(e);
    } finally {
      setBusy(false);
    }
  };
  const runJobAction = async (
    job: Job,
    action: "cancel" | "retry" | "discard",
  ) => {
    try {
      if (action === "discard") {
        await api(`/jobs/${job.id}`, { method: "DELETE" });
        setJobs((old) => old.filter((j) => j.id !== job.id));
        if (previewId === job.id) setPreviewId("");
      } else {
        const result = await post<Job>(`/jobs/${job.id}/${action}`);
        setCurrent(result.id);
        setJobs((old) => [result, ...old.filter((j) => j.id !== result.id)]);
      }
    } catch (e) {
      onError(e);
    }
  };
  const applyDialog = async () => {
    if (!modal) return;
    try {
      if (modal.kind === "add-root" || modal.kind === "output-folder") {
        await addRootPath(dialogText);
        if (modal.kind === "output-folder") setOutputFolder(dialogText);
      }
      if (modal.kind === "rename" || modal.kind === "delete") {
        const result = await post<{
          results?: { ok: boolean; error?: string }[];
        }>("/files/operation", {
          action: modal.kind,
          paths: modal.entries?.map((e) => e.path),
          name: dialogText,
          confirmed: modal.kind === "delete",
        });
        if (result.results?.some((r) => !r.ok))
          throw new Error(
            result.results
              .filter((r) => !r.ok)
              .map((r) => r.error)
              .join("\n"),
          );
      }
      if (modal.kind === "file" && modal.item)
        setItems((old) =>
          old.map((item) =>
            item.id === modal.item!.id
              ? { ...item, pages: filePages, password: filePassword }
              : item,
          ),
        );
      if (modal.kind === "preset" && prefs) {
        if (!dialogText.trim()) throw new Error(t("nameRequired"));
        if (
          !(await savePreferences({
            presets: { ...prefs.presets, [dialogText.trim()]: params },
          }))
        )
          return;
        setPreset(dialogText);
      }
      if (
        modal.kind === "settings" &&
        settingsDraft &&
        !(await savePreferences(settingsDraft))
      )
        return;
      setModal(null);
    } catch (e) {
      onError(e);
    }
  };
  const sort = (mode: string) => {
    const collator = new Intl.Collator(i18n.language, {
      numeric: true,
      sensitivity: "base",
    });
    const next = [...items];
    if (mode === "nameAsc" || mode === "nameDesc")
      next.sort(
        (a, b) =>
          collator.compare(a.name, b.name) * (mode === "nameAsc" ? 1 : -1),
      );
    if (mode === "sizeAsc" || mode === "sizeDesc")
      next.sort((a, b) => (a.size - b.size) * (mode === "sizeAsc" ? 1 : -1));
    if (mode === "modified")
      next.sort((a, b) => (b.modified || 0) - (a.modified || 0));
    if (mode === "type")
      next.sort((a, b) => collator.compare(a.extension, b.extension));
    setItems(next);
  };
  const localizedError = error.includes("OWNER_PASSWORD_REQUIRED")
    ? t("ownerRequired")
    : error.includes("PASSWORD_REQUIRED_OR_INCORRECT")
      ? t("passwordWrong")
      : error.includes("SOURCE_CHANGED") || error.includes("PREVIEW_STALE")
        ? t("sourceChanged")
        : error;
  const tree = prefs && (
    <FileTree
      roots={roots}
      onRoots={setRoots}
      hidden={prefs.show_hidden}
      onHidden={() => void savePreferences({ show_hidden: !prefs.show_hidden })}
      onAdd={() => openModal({ kind: "add-root" })}
      onForget={(path) =>
        void api<Root[]>("/roots", {
          method: "DELETE",
          body: JSON.stringify({ path }),
        })
          .then(setRoots)
          .catch(onError)
      }
      onFiles={addFiles}
      onFolder={setSelectedFolder}
      onAction={(...args) => void fileAction(...args)}
      onError={onError}
      events={events}
    />
  );
  const actions = (
    <>
      <Button
        icon={<EyeRegular />}
        disabled={busy || !chosen.length || invalidIcoSizes || invalidQuality}
        onClick={() => void submit(true)}
      >
        {t("preview")}
      </Button>
      <Button
        appearance="primary"
        icon={<PlayRegular />}
        disabled={busy || !chosen.length || invalidIcoSizes || invalidQuality}
        onClick={() => void submit(false)}
      >
        {t("convert")}
        {chosen.length > 0 && ` (${chosen.length})`}
      </Button>
    </>
  );
  if (!boot || !prefs)
    return (
      <div className="startup">
        <img src="/favicon.svg" alt="" />
        <h1>Format Converter</h1>
        {error ? (
          <>
            <p role="alert">{t("connectError")}</p>
            <p>{error}</p>
            <Button onClick={() => location.reload()}>{t("retry")}</Button>
          </>
        ) : (
          <Spinner label={t("loading")} />
        )}
      </div>
    );
  const fileDialog = (
    <Dialog
      open={!!modal}
      onOpenChange={(_, data) => {
        if (!data.open) setModal(null);
      }}
    >
      <DialogSurface className={modal?.kind === "jobs" ? "jobs-dialog" : ""}>
        <DialogBody>
          <DialogTitle
            action={
              <IconButton
                label={t("close")}
                icon={<DismissRegular />}
                onClick={() => setModal(null)}
              />
            }
          >
            {t(
              modal?.kind === "add-root"
                ? "addFolder"
                : modal?.kind === "output-folder"
                  ? "chooseOutput"
                  : modal?.kind === "file"
                    ? "perFile"
                    : modal?.kind === "preset"
                      ? "savePreset"
                      : modal?.kind === "delete"
                        ? "recycle"
                        : modal?.kind || "settings",
            )}
          </DialogTitle>
          <DialogContent>
            {error && (
              <p role="alert" className="task-error">
                {localizedError}
              </p>
            )}
            {["add-root", "output-folder", "rename", "preset"].includes(
              modal?.kind || "",
            ) && (
              <div className="dialog-fields">
                <Field
                  label={t(
                    modal?.kind === "rename"
                      ? "newName"
                      : modal?.kind === "preset"
                        ? "presetName"
                        : "folderPath",
                  )}
                >
                  <Input
                    value={dialogText}
                    onChange={(_, data) => setDialogText(data.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") void applyDialog();
                    }}
                    autoFocus
                  />
                </Field>
                {["add-root", "output-folder"].includes(
                  modal?.kind || "",
                ) && (
                  <Button
                    icon={<FolderRegular />}
                    onClick={async () => {
                      try {
                        const result = await post<{ path: string }>(
                          "/pick-folder",
                        );
                        if (result.path) setDialogText(result.path);
                      } catch (e) {
                        onError(e);
                      }
                    }}
                  >
                    {t("browse")}
                  </Button>
                )}
              </div>
            )}
            {modal?.kind === "delete" && (
              <>
                <p>{t("recycleConfirm", { count: modal.entries?.length })}</p>
                <p className="help">{t("recycleNote")}</p>
              </>
            )}
            {modal?.kind === "inspection" && (
              <div className="job-list">
                {inspection.map((item, index) => (
                  <article key={index} className="job-card">
                    <h3>{item.name}</h3>
                    {item.error ? (
                      <p className="task-error">{item.error}</p>
                    ) : (
                      <>
                        <p>
                          {t(item.encrypted ? "protected" : "unprotected")}
                        </p>
                        <p>
                          {t(
                            item.readable
                              ? "credentialValid"
                              : "passwordWrong",
                          )}
                        </p>
                        {item.encrypted && (
                          <p>
                            {t(
                              item.owner
                                ? "ownerAuthenticated"
                                : "ownerNotAuthenticated",
                            )}
                          </p>
                        )}
                        <p>
                          {t(
                            item.can_decrypt ? "canDecrypt" : "ownerRequired",
                          )}
                        </p>
                        {item.pages && (
                          <p>{t("pageCount", { count: item.pages })}</p>
                        )}
                      </>
                    )}
                  </article>
                ))}
              </div>
            )}
            {modal?.kind === "properties" && (
              <dl className="properties">
                {Object.entries(modal.data || {}).map(([key, value]) => (
                  <div key={key}>
                    <dt>
                      {t(
                        (
                          {
                            size: "fileSize",
                            modified: "modifiedAt",
                            created: "created",
                            read_only: "readOnly",
                          } as Record<string, string>
                        )[key] || key,
                      )}
                    </dt>
                    <dd>
                      {typeof value === "boolean"
                        ? t(value ? "yes" : "no")
                        : key === "size"
                          ? size(Number(value))
                          : ["modified", "created"].includes(key)
                            ? new Date(Number(value) * 1000).toLocaleString(
                                i18n.language,
                              )
                            : String(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
            {modal?.kind === "file" && (
              <div className="dialog-fields">
                <p>{modal.item?.name}</p>
                <p className="help">{t("perFileHelp")}</p>
                <Field label={t("p.pages")} hint={t("pagesHelp")}>
                  <Input
                    value={filePages}
                    onChange={(_, data) => setFilePages(data.value)}
                  />
                </Field>
                <Field label={t("p.password")}>
                  <Input
                    type="password"
                    autoComplete="new-password"
                    value={filePassword}
                    onChange={(_, data) => setFilePassword(data.value)}
                  />
                </Field>
              </div>
            )}
            {modal?.kind === "settings" && settingsDraft && (
              <div className="dialog-fields">
                <Field label={t("language")}>
                  <Select
                    value={settingsDraft.language}
                    onChange={(e) =>
                      setSettingsDraft({
                        ...settingsDraft,
                        language: e.target.value,
                      })
                    }
                  >
                    <option value="en">English</option>
                    <option value="zh-TW">繁體中文</option>
                  </Select>
                </Field>
                <Field label={t("p.text_browser")} hint={t("textBrowserHelp")}>
                  <Select value={settingsDraft.text_browser}
                    onChange={(e) => setSettingsDraft({ ...settingsDraft, text_browser: e.target.value, text_browser_path: "" })}>
                    <option value="edge">Microsoft Edge</option>
                    <option value="chrome">Google Chrome</option>
                    <option value="firefox">Mozilla Firefox</option>
                    <option value="safari" disabled>Safari — {t("safariPending")}</option>
                  </Select>
                </Field>
                <Field label={t("p.text_browser_path")} hint={t("textBrowserPathHelp")}>
                  <Input value={settingsDraft.text_browser_path}
                    onChange={(_, d) => setSettingsDraft({ ...settingsDraft, text_browser_path: d.value })} />
                </Field>
                <Field label={t("workers")}>
                  <Input
                    type="number"
                    min={1}
                    max={16}
                    value={String(settingsDraft.workers)}
                    onChange={(_, d) =>
                      setSettingsDraft({
                        ...settingsDraft,
                        workers: Number(d.value),
                      })
                    }
                  />
                </Field>
                <Field label={t("memory")} hint={t("memoryHelp")}>
                  <Input
                    type="number"
                    min={256}
                    max={32768}
                    value={String(settingsDraft.memory_mb)}
                    onChange={(_, d) =>
                      setSettingsDraft({
                        ...settingsDraft,
                        memory_mb: Number(d.value),
                      })
                    }
                  />
                </Field>
                <Checkbox
                  label={t("darkCanvas")}
                  checked={settingsDraft.preview_dark}
                  onChange={(_, d) =>
                    setSettingsDraft({
                      ...settingsDraft,
                      preview_dark: !!d.checked,
                    })
                  }
                />
                <p className="help">{t("remember")}</p>
                <p className="help">{t("stopService")}</p>
                <p>
                  AGPL-3.0 · {t("version")} {boot.version}
                </p>
              </div>
            )}
            {modal?.kind === "jobs" && (
              <div className="job-list">
                {!jobs.length && <p>{t("noJobs")}</p>}
                {jobs.map((job) => (
                  <article className="job-card" key={job.id}>
                    <div className="job-title">
                      <h3>
                        {t(`tool.${job.tool}`)}
                        {job.preview && ` · ${t("preview")}`}
                      </h3>
                      <span>{t(job.status)}</span>
                    </div>
                    <ProgressBar
                      value={job.progress}
                      aria-label={t(job.status)}
                    />
                    {job.tasks.map((task) => (
                      <div className="task-result" key={task.index}>
                        <span>{task.sources.join(", ")}</span>
                        <small>{t(task.state)}</small>
                        {task.error && (
                          <p className="task-error">
                            {t(errorMessageKey(task.error) || "rawError", { defaultValue: task.error })}
                          </p>
                        )}
                        {task.outputs.map((out, index) => (
                          <div className="artifact" key={out.id || index}>
                            {out.skipped ? (
                              <span>
                                {out.name} · {t("skip")}
                              </span>
                            ) : (
                              <a href={`${out.url}?download=true`} download>
                                {out.name} · {size(out.size)}
                              </a>
                            )}
                          </div>
                        ))}
                      </div>
                    ))}
                    <div className="job-actions">
                      {["running", "queued"].includes(job.status) && (
                        <Button
                          size="small"
                          onClick={() => void runJobAction(job, "cancel")}
                        >
                          {t("cancel")}
                        </Button>
                      )}
                      {["partial", "failed", "cancelled"].includes(
                        job.status,
                      ) && (
                        <Button
                          size="small"
                          onClick={() => void runJobAction(job, "retry")}
                        >
                          {t("retry")}
                        </Button>
                      )}
                      <Button
                        size="small"
                        appearance="subtle"
                        onClick={() => void runJobAction(job, "discard")}
                      >
                        {t("discard")}
                      </Button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </DialogContent>
          {modal?.kind !== "inspection" &&
            modal?.kind !== "jobs" &&
            modal?.kind !== "properties" && (
              <DialogActions>
                <Button appearance="secondary" onClick={() => setModal(null)}>
                  {t("cancel")}
                </Button>
                <Button
                  appearance="primary"
                  onClick={() => void applyDialog()}
                >
                  {t(modal?.kind === "delete" ? "confirm" : "save")}
                </Button>
              </DialogActions>
            )}
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <img src="/favicon.svg" alt="" />
          <span>Format Converter</span>
        </div>
        <div className="header-tools">
          <Select
            size="small"
            aria-label={t("language")}
            value={prefs.language}
            onChange={(e) => void savePreferences({ language: e.target.value })}
          >
            <option value="en">EN</option>
            <option value="zh-TW">繁中</option>
          </Select>
          <Button
            appearance="subtle"
            className="jobs-button"
            onClick={() => openModal({ kind: "jobs" })}
          >
            {t("jobs")}
            {active.length > 0 && ` (${active.length})`}
          </Button>
          <IconButton
            label={t("settings")}
            icon={<SettingsRegular />}
            onClick={() => openModal({ kind: "settings" })}
          />
        </div>
      </header>
      <nav className="tool-tabs" aria-label={t("app")}>
        <TabList
          selectedValue={tool}
          onTabSelect={(_, data) => setTool(data.value as Tool)}
        >
          {tools.map((value) => (
            <Tab key={value} value={value} icon={toolIcons[value]}>
              {t(`tool.${value}`)}
            </Tab>
          ))}
        </TabList>
      </nav>
      {error && (
        <div className="message error" role="alert">
          <div>
            <strong>{t("error")}</strong>
            <span>{localizedError}</span>
          </div>
          <IconButton
            label={t("close")}
            icon={<DismissRegular />}
            onClick={() => setError("")}
          />
        </div>
      )}
      {notice && (
        <div className="message notice" role="status">
          <span>{t(notice.key, { count: notice.count })}</span>
          <IconButton
            label={t("close")}
            icon={<DismissRegular />}
            onClick={() => setNotice(null)}
          />
        </div>
      )}
      <JobFailures jobs={jobs} onJobs={() => openModal({ kind: "jobs" })} />
      <JobWarnings jobs={jobs} />
      <div className="mobile-folder">
        <Button icon={<FolderRegular />} onClick={() => setDrawer(true)}>
          {t("files")}
        </Button>
        <span title={selectedFolder}>{selectedFolder || t("noRoots")}</span>
      </div>
      <main
        className="workspace"
        style={
          {
            "--explorer-width": `${explorerWidth}px`,
            "--parameter-width": `${parameterWidth}px`,
          } as React.CSSProperties
        }
      >
        <aside className="explorer-pane">{tree}</aside>
        <ResizeHandle
          label={t("files")}
          value={explorerWidth}
          min={190}
          max={420}
          onChange={setExplorerWidth}
          onSave={(value) => void savePreferences({ explorer_width: value })}
        />
        <section
          className="queue-pane"
          onDragOver={(event) => event.preventDefault()}
          onDrop={dropFiles}
        >
          <div className="queue-heading">
            <div>
              <h1>{t(`tool.${tool}`)}</h1>
              <p>{t("emptyHelp")}</p>
            </div>
            <Button
              appearance="primary"
              icon={<AddRegular />}
              disabled={busy}
              onClick={() => upload.current?.click()}
            >
              {t("addFiles")}
            </Button>
          </div>
          <input
            ref={upload}
            type="file"
            multiple
            hidden
            accept={
              [
                "merge",
                "encrypt",
                "decrypt",
                "organize",
                "compress",
                "pdf_images",
                "pdf_text",
              ].includes(tool)
                ? ".pdf"
                : tool === "text_pdf" ? ".txt,.text,.md,.markdown" : tool === "ocr"
                  ? ".pdf,image/*,.heic,.heif"
                  : "image/*,.heic,.heif"
            }
            onChange={(event) =>
              event.target.files && void uploadFiles(event.target.files)
            }
          />
          <div className="queue-toolbar">
            <Checkbox
              label={t("selectAll")}
              checked={
                selected.size === items.length && items.length > 0
                  ? true
                  : selected.size
                    ? "mixed"
                    : false
              }
              onChange={(_, data) =>
                setSelected(
                  data.checked ? new Set(items.map((x) => x.id)) : new Set(),
                )
              }
            />
            <Select
              size="small"
              aria-label={t("sort")}
              value="manual"
              onChange={(event) => sort(event.target.value)}
            >
              <option value="manual">{t("sort")}</option>
              {[
                "nameAsc",
                "nameDesc",
                "sizeAsc",
                "sizeDesc",
                "modified",
                "type",
              ].map((mode) => (
                <option key={mode} value={mode}>
                  {t(mode)}
                </option>
              ))}
            </Select>
            <span className="toolbar-spacer" />
            <Button
              size="small"
              appearance="subtle"
              disabled={!selected.size}
              onClick={() =>
                updateItems(items.filter((x) => !selected.has(x.id)))
              }
            >
              {t("removeSelected")}
            </Button>
            <IconButton
              label={t("clearQueue")}
              icon={<DeleteRegular />}
              disabled={!items.length}
              onClick={() => updateItems([])}
            />
          </div>
          <button className="drop-zone" onClick={() => upload.current?.click()}>
            <ArrowDownloadRegular />
            {busy ? t("loading") : t("dropHint")}
          </button>
          <Queue
            items={items}
            selected={selected}
            onSelected={setSelected}
            onItems={updateItems}
            onOptions={(item) => {
              setFilePages(item.pages);
              setFilePassword(item.password);
              openModal({ kind: "file", item });
            }}
          />
          <OutputSizes key={currentJob?.id || "none"} job={currentJob?.tool === tool ? currentJob : undefined} stale={!!currentJob?.preview && stale} />
          <div className="queue-summary">
            <span>
              {t("selected", { count: chosen.length })} ·{" "}
              {size(chosen.reduce((sum, item) => sum + item.size, 0))}
            </span>
            {currentJob && (
              <button
                className="job-summary"
                onClick={() => openModal({ kind: "jobs" })}
              >
                {t(currentJob.status)} {Math.round(currentJob.progress * 100)}%
              </button>
            )}
          </div>
          {currentJob && ["running", "queued"].includes(currentJob.status) && (
            <ProgressBar
              value={currentJob.progress}
              aria-label={t("running")}
            />
          )}
        </section>
        <ResizeHandle
          label={t("parameters")}
          value={parameterWidth}
          min={300}
          max={520}
          reverse
          onChange={setParameterWidth}
          onSave={(value) => void savePreferences({ parameter_width: value })}
        />
        <aside className="parameter-pane">
          <div className="pane-heading">
            <h2>{t("parameters")}</h2>
            <span>{t("preset")}</span>
          </div>
          <Preview
            job={previewJob}
            stale={stale}
            dark={prefs.preview_dark}
            onDark={(value) => void savePreferences({ preview_dark: value })}
            onError={onError}
          />
          <Button
            className="parameter-toggle"
            appearance="subtle"
            icon={
              parametersOpen ? <ChevronUpRegular /> : <ChevronDownRegular />
            }
            aria-expanded={parametersOpen}
            onClick={() => setParametersOpen((v) => !v)}
          >
            {t("parameters")}
          </Button>
          <div
            className={`parameter-scroll ${parametersOpen ? "parameters-open" : "parameters-closed"}`}
          >
            <div className="preset-row">
              <Select
                aria-label={t("preset")}
                value={preset}
                onChange={(e) => {
                  const name = e.target.value;
                  setPreset(name);
                  if (name && prefs.presets[name])
                    setParams(
                      (old) => ({ ...old, ...prefs.presets[name] }) as Params,
                    );
                }}
              >
                <option value="">{t("defaultPreset")}</option>
                {Object.keys(prefs.presets).map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </Select>
              <IconButton
                label={t("savePreset")}
                icon={<SaveRegular />}
                onClick={() => openModal({ kind: "preset" })}
              />
              <IconButton
                label={t("deletePreset")}
                icon={<DeleteRegular />}
                disabled={!preset}
                onClick={() => {
                  const next = { ...prefs.presets };
                  delete next[preset];
                  void savePreferences({ presets: next });
                  setPreset("");
                }}
              />
            </div>
            {["encrypt", "decrypt"].includes(tool) && (
              <Button
                disabled={!chosen.length || busy}
                icon={<LockClosedRegular />}
                onClick={async () => {
                  setBusy(true);
                  try {
                    setInspection(
                      await post<Inspection[]>("/files/inspect-pdf", {
                        sources: sources.slice(0, 100).map((source) => ({
                          ...source,
                          password: source.password || params.password,
                        })),
                      }),
                    );
                    openModal({ kind: "inspection" });
                  } catch (e) {
                    onError(e);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {t("inspectProtection")}
              </Button>
            )}
            <ParameterFields
              tool={tool}
              value={params}
              onChange={(key, value) =>
                setParams((old) => ({ ...old, [key]: value }))
              }
              encoders={boot.capabilities.encoders}
            />
            <details className="output-settings" open>
              <summary>{t("output")}</summary>
              <div className="parameter-fields">
                <Field label={t("outputName")}>
                  <Input
                    value={filename}
                    onChange={(_, data) => setFilename(data.value)}
                    placeholder={
                      tool === "merge"
                        ? "merged.pdf"
                        : tool === "images_pdf"
                          ? "images.pdf"
                          : "{name}"
                    }
                  />
                </Field>
                <Field label={t("outputStartFolder")} hint={t("saveDialogHelp")}>
                  <div className="folder-input">
                    <Input
                      value={outputFolder}
                      onChange={(_, data) => setOutputFolder(data.value)}
                      placeholder={t("chooseOutput")}
                    />
                    <Button
                      icon={<FolderRegular />}
                      aria-label={t("browse")}
                      onClick={() => void browseFolder(true)}
                    />
                  </div>
                </Field>
                <Field label={t("naming")} hint={t("namingHelp")}>
                  <Input
                    value={naming}
                    onChange={(_, data) => setNaming(data.value)}
                  />
                </Field>
                <Field label={t("conflict")}>
                  <Select
                    value={collision}
                    onChange={(e) => setCollision(e.target.value)}
                  >
                    {["rename", "skip", "overwrite", "ask"].map((value) => (
                      <option value={value} key={value}>
                        {t(value === "rename" ? "renameConflict" : value)}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            </details>
          </div>
          <div className="parameter-actions">{actions}</div>
        </aside>
      </main>
      <footer className="app-footer">
        <span className="footer-status">
          {t("local")} · {t("workers")}: {prefs.workers}
        </span>
        <span>© 2026 Ethan DevLab. All rights reserved.</span>
        <span>Built by Ethan DevLab</span>
        <a
          href="mailto:hello@ethan-devlab.com"
          aria-label={t("mail")}
          title="hello@ethan-devlab.com"
        >
          <MailRegular />
        </a>
        <span>v{boot.version}</span>
      </footer>
      <div className="mobile-actions">{actions}</div>
      <Dialog open={drawer} onOpenChange={(_, data) => {
        if (!modal) setDrawer(data.open);
      }}>
        <DialogSurface className="file-drawer">
          <DialogBody>
            <DialogTitle
              action={
                <IconButton
                  label={t("close")}
                  icon={<DismissRegular />}
                  onClick={() => setDrawer(false)}
                />
              }
            >
              {t("files")}
            </DialogTitle>
            <DialogContent>{tree}</DialogContent>
          </DialogBody>
          {drawer && fileDialog}
        </DialogSurface>
      </Dialog>
      {!drawer && fileDialog}
    </div>
  );
}

function ResizeHandle({
  label,
  value,
  min,
  max,
  reverse = false,
  onChange,
  onSave,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  reverse?: boolean;
  onChange: (n: number) => void;
  onSave: (n: number) => void;
}) {
  const drag = useRef<{ x: number; value: number; next: number } | undefined>(
    undefined,
  );
  const clamp = (n: number) => Math.max(min, Math.min(max, n));
  return (
    <div
      role="separator"
      className="pane-resizer"
      tabIndex={0}
      aria-label={label}
      aria-orientation="vertical"
      aria-valuenow={value}
      aria-valuemin={min}
      aria-valuemax={max}
      onPointerDown={(e) => {
        drag.current = { x: e.clientX, value, next: value };
        e.currentTarget.setPointerCapture(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (drag.current) {
          const next = clamp(
            drag.current.value +
              (e.clientX - drag.current.x) * (reverse ? -1 : 1),
          );
          drag.current.next = next;
          onChange(next);
        }
      }}
      onPointerUp={() => {
        if (drag.current) onSave(drag.current.next);
        drag.current = undefined;
      }}
      onPointerCancel={() => {
        drag.current = undefined;
      }}
      onKeyDown={(e) => {
        if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
          e.preventDefault();
          const next =
            e.key === "Home"
              ? min
              : e.key === "End"
                ? max
                : clamp(
                    value +
                      (e.key === "ArrowRight" ? 10 : -10) * (reverse ? -1 : 1),
                  );
          onChange(next);
          onSave(next);
        }
      }}
    />
  );
}
