import type { FileEntry, Root } from "./api.ts";

// Windows paths are identities; a tree row is only one display occurrence.
export function pathKey(path: string) {
  return path.replaceAll("/", "\\").replace(/\\+$/, "").toLowerCase();
}

export function inside(path: string, folder: string) {
  const key = pathKey(path), root = pathKey(folder);
  return key === root || key.startsWith(`${root}\\`);
}

export function uniqueEntries(entries: FileEntry[]) {
  return [...new Map(entries.map((entry) => [pathKey(entry.path), entry])).values()];
}

export function selectedEntries(entries: FileEntry[], selected: Set<string>) {
  return uniqueEntries(entries).filter((entry) => !entry.link && selected.has(pathKey(entry.path)));
}

export function operationEntries(action: string, entries: FileEntry[]) {
  const unique = uniqueEntries(entries);
  if (!["copy", "cut", "delete"].includes(action)) return unique;
  const folders = new Set(unique.filter((entry) => entry.directory).map((entry) => pathKey(entry.path)));
  return unique.filter((entry) => {
    const key = pathKey(entry.path);
    for (let end = key.lastIndexOf("\\"); end > 0; end = key.lastIndexOf("\\", end - 1))
      if (folders.has(key.slice(0, end))) return false;
    return true;
  });
}

export function canAct(action: string, entries: FileEntry[], roots: Root[], folder: string) {
  if (action === "paste") return !entries.some((entry) => entry.link) && !!folder && roots.some((root) => root.available && inside(folder, root.path));
  const targets = operationEntries(action, entries);
  if (!targets.length || targets.some((entry) => entry.link)) return false;
  if (["rename", "properties"].includes(action) && targets.length !== 1) return false;
  return !["rename", "cut", "delete"].includes(action) ||
    !targets.some((entry) => roots.some((root) => inside(root.path, entry.path)));
}

/** Own one current response per directory; obsolete replies cannot reach the UI. */
export class DirectoryRequests<T> {
  private pending = new Map<string, AbortController>();

  busy(path: string) {
    return this.pending.has(pathKey(path));
  }

  async run(path: string, append: boolean, read: (signal: AbortSignal) => Promise<T>): Promise<T | undefined> {
    const key = pathKey(path);
    if (append && this.pending.has(key)) return;
    this.pending.get(key)?.abort();
    const controller = new AbortController();
    this.pending.set(key, controller);
    try {
      const result = await read(controller.signal);
      if (this.pending.get(key) === controller) return result;
    } catch (error) {
      if (this.pending.get(key) === controller && !controller.signal.aborted) throw error;
    } finally {
      if (this.pending.get(key) === controller) this.pending.delete(key);
    }
  }

  cancel(keep: (path: string) => boolean = () => false) {
    for (const [path, controller] of this.pending) {
      if (!keep(path)) {
        this.pending.delete(path);
        controller.abort();
      }
    }
  }
}
