import type { Job, Params, Task, Tool } from "./api.ts";

export function errorMessageKey(error: string): string | null {
  if (error.includes("TEXT_ENCODING_ERROR")) return "textDecodeError";
  if (error.includes("BROWSER_UNAVAILABLE")) return "browserUnavailable";
  if (error.includes("OWNER_PASSWORD_REQUIRED")) return "ownerRequired";
  if (error.includes("PASSWORD_REQUIRED_OR_INCORRECT")) return "passwordWrong";
  if (error.includes("SOURCE_CHANGED") || error.includes("PREVIEW_STALE")) return "sourceChanged";
  return null;
}

export function taskFailures(jobs: Job[]) {
  return jobs.flatMap((job) => job.tasks.filter((task) => !!task.error).map((task) => ({
    key: `${job.id}:${task.index}:${task.error}`, job, task,
  })));
}

export function usesQuality(tool: Tool, params: Params): boolean {
  return (tool === "compress" && params.compression === "lossy") ||
    (tool === "images_pdf" && !params.lossless) ||
    (["image", "pdf_images"].includes(tool) && ["JPEG", "WEBP", "HEIF", "AVIF"].includes(String(params.format)));
}

export function validQuality(value: unknown): boolean {
  return typeof value === "number" && Number.isInteger(value) && value >= 1 && value <= 100;
}

export function measuredSize(task: Task) {
  const outputs = task.outputs.filter((output) => !output.skipped);
  if (task.state !== "done" || !outputs.length || !task.source_sizes) return null;
  const input = task.source_sizes.reduce((sum, value) => sum + value, 0);
  const output = outputs.reduce((sum, value) => sum + value.size, 0);
  return { input, output, change: input > 0 ? (output - input) / input * 100 : null, outputs };
}

export function taskWarnings(jobs: Job[], dismissed: ReadonlySet<string> = new Set()) {
  return jobs.flatMap(job => job.tasks.flatMap(task => (task.warnings || []).map(message => ({
    key: JSON.stringify([job.id, task.index, message]), source: task.sources.join(", "), message,
  })))).filter(warning => !dismissed.has(warning.key));
}
