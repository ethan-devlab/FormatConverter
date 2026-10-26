export type Tool =
  | "images_pdf"
  | "text_pdf"
  | "pdf_images"
  | "pdf_text"
  | "merge"
  | "encrypt"
  | "decrypt"
  | "image"
  | "organize"
  | "ocr"
  | "compress";
export interface FileEntry {
  path: string;
  name: string;
  directory: boolean;
  size: number;
  modified?: number;
  extension: string;
  hidden?: boolean;
  link?: boolean;
  temporary?: boolean;
}
export interface QueueItem extends FileEntry {
  id: string;
  pages: string;
  password: string;
}
export interface Root {
  path: string;
  name: string;
  available: boolean;
}
export interface Artifact {
  id: string;
  name: string;
  size: number;
  url: string;
  pages?: number;
  path?: string;
  skipped?: boolean;
  temporary?: boolean;
}
export interface Task {
  index: number;
  sources: string[];
  source_sizes?: number[];
  state: string;
  progress: number;
  error: string;
  warnings?: string[];
  outputs: Artifact[];
  previews: Artifact[];
}
export interface Job {
  id: string;
  tool: Tool;
  preview: boolean;
  status: string;
  progress: number;
  created: number;
  tasks: Task[];
}
export interface Preferences {
  text_browser: string;
  text_browser_path: string;
  explorer_width: number;
  parameter_width: number;
  language: string;
  roots: string[];
  show_hidden: boolean;
  workers: number;
  memory_mb: number;
  preview_dark: boolean;
  presets: Record<string, Record<string, unknown>>;
}
export type Params = Record<string, string | number | boolean>;
export interface Bootstrap {
  version: string;
  preferences: Preferences;
  roots: Root[];
  capabilities: {
    encoders: string[];
    ocr_languages: string[];
    pdf_engine: string;
  };
}
export const tools: Tool[] = [
  "images_pdf",
  "text_pdf",
  "pdf_images",
  "pdf_text",
  "merge",
  "encrypt",
  "decrypt",
  "image",
  "organize",
  "ocr",
  "compress",
];
export const defaults: Params = {
  pages: "",
  page_size: "A4",
  page_width: 210,
  page_height: 297,
  orientation: "portrait",
  margin: 10,
  fit: "contain",
  background: "#ffffff",
  dpi: 150,
  quality: 85,
  format: "PNG",
  width: 0,
  height: 0,
  frames: "all",
  preserve_dpi: false,
  keep_ratio: true,
  resample: "lanczos",
  crop: "",
  rotation: 0,
  sharpen: false,
  optimize: true,
  lossless: false,
  metadata: "keep",
  color_mode: "RGB",
  organize_mode: "single",
  split_every: 1,
  text_layout: true,
  text_mode: "auto",
  text_encoding: "auto",
  text_font: "sans-serif",
  text_font_size: 12,
  text_line_height: 1.5,
  text_tab_width: 4,
  text_color: "#28231f",
  text_browser: "edge",
  text_browser_path: "",
  page_separator: true,
  extract_images: false,
  opening_password: "",
  owner_password: "",
  password: "",
  require_opening: true,
  restrict: false,
  allow_print: true,
  allow_copy: true,
  allow_annotate: true,
  allow_modify: false,
  allow_forms: true,
  allow_assemble: false,
  ocr_language: "eng",
  ocr_chinese_first: true,
  force_ocr: false,
  ocr_output: "pdf",
  compression: "lossless",
  target_dpi: 150,
  dpi_threshold: 225,
  ico_sizes: "16,24,32,48,64,128,256",
  title: "",
  author: "",
  max_megapixels: 100,
};

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}
export async function api<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Format-Converter", "1");
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    const detail = Array.isArray(data.detail)
      ? data.detail.map((x: { msg: string }) => x.msg).join("\n")
      : data.detail;
    throw new ApiError(String(detail || response.statusText), response.status);
  }
  return response.json();
}
export const post = <T = unknown>(path: string, body: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export function size(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  const unit = Math.min(3, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** unit).toLocaleString(undefined, { maximumFractionDigits: 1 })} ${["B", "KB", "MB", "GB"][unit]}`;
}
