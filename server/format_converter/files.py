from __future__ import annotations

import os
import errno
import shutil
import tempfile
import threading
import time
from collections import OrderedDict, deque
from pathlib import Path

from natsort import natsorted
from send2trash import send2trash
from watchfiles import watch

from .config import read_preferences, write_preferences


def fingerprint(path: str) -> tuple[int, int, int, int]:
    stat = Path(path).stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def unique_path(folder: Path, name: str) -> Path:
    stem, suffix = Path(name).stem, Path(name).suffix
    target, index = folder / name, 1
    while target.exists():
        target = folder / f"{stem}_{index:02d}{suffix}"
        index += 1
    return target


def validate_name(name: str):
    reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    reserved.update(f"{prefix}{digit}" for prefix in ("COM", "LPT") for digit in "123456789¹²³")
    if (not name or name in {".", ".."} or name.endswith((".", " "))
            or any(ord(c) < 32 or c in '<>:"/\\|?*' for c in name)
            or name.split(".", 1)[0].rstrip(" ").upper() in reserved):
        raise ValueError("Use a valid Windows filename without reserved names or trailing dots/spaces.")


def copy_checked(source, target):
    before = fingerprint(str(source))
    result = shutil.copy2(source, target)
    if fingerprint(str(source)) != before:
        raise ValueError("SOURCE_CHANGED")
    return result


def publish_copy(source: Path, target: Path, expected):
    # Stage in the destination filesystem. Windows rename refuses an existing
    # target, including one created after unique_path chose the output name.
    with tempfile.TemporaryDirectory(prefix=".formatconverter-", dir=target.parent) as staging:
        staged = Path(staging) / source.name
        if source.is_dir():
            shutil.copytree(source, staged, copy_function=copy_checked)
        else:
            copy_checked(source, staged)
        if fingerprint(str(source)) != expected:
            raise ValueError("SOURCE_CHANGED")
        if os.name == "nt":
            staged.rename(target)
        elif staged.is_file():
            os.link(staged, target)
        else:
            # Non-Windows directory moves need an exclusive destination claim.
            target.mkdir()
            shutil.copytree(staged, target, dirs_exist_ok=True)


class FileWorkspace:
    def __init__(self):
        self.lock = threading.RLock()
        self.operation_lock = threading.Lock()
        self.watcher_lock = threading.Lock()
        self.roots: list[Path] = []
        self.temporary_roots: list[Path] = []
        for value in read_preferences().get("roots", []):
            # Revalidate the saved spelling before following any filesystem link.
            path = Path(os.path.abspath(value))
            if path not in self.roots:
                self.roots.append(path)
        self.cache = OrderedDict()
        self.events = deque(maxlen=1024)
        self.version = 0
        self.stop = threading.Event()
        self.watcher = None
        self.clipboard: dict | None = None
        self.restart_watcher()

    def resolve(self, value: str, *, exists: bool = True) -> Path:
        raw = Path(os.path.abspath(value))
        for component in (raw, *raw.parents):
            if component.is_symlink() or component.is_junction():
                raise PermissionError("LINKED_PATH_NOT_ALLOWED")
        path = Path(value).resolve(strict=exists)
        with self.lock:
            if not any(path == root or path.is_relative_to(root) for root in self.roots + self.temporary_roots):
                raise PermissionError("PATH_OUTSIDE_ROOTS")
        return path

    def root_list(self):
        with self.lock:
            roots = list(self.roots)
        return [{"path": str(p), "name": p.name or str(p), "available": self.available(p)} for p in roots]

    @staticmethod
    def available(path):
        try:
            if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
                return False
            with os.scandir(path):
                return True
        except OSError:
            return False

    def add_root(self, value: str):
        raw = Path(os.path.abspath(value))
        if any(p.is_symlink() or p.is_junction() for p in (raw, *raw.parents)):
            raise PermissionError("LINKED_PATH_NOT_ALLOWED")
        path = Path(value).resolve(strict=True)
        if not path.is_dir():
            raise ValueError("Choose a folder.")
        with self.operation_lock, self.lock:
            if path not in self.roots:
                self.roots.append(path)
                write_preferences({"roots": [str(p) for p in self.roots]})
        self.restart_watcher()
        return self.root_list()

    def remove_root(self, value: str):
        with self.operation_lock, self.lock:
            removed = Path(os.path.abspath(value))
            self.roots = [p for p in self.roots if p != removed]
            self.cache.clear()
            write_preferences({"roots": [str(p) for p in self.roots]})
        self.restart_watcher()
        return self.root_list()

    def changed(self, paths):
        with self.lock:
            for value in paths:
                parent = str(Path(value).parent)
                self.cache.pop(os.path.normcase(parent), None)
                for key in list(self.cache):
                    if Path(key).is_relative_to(Path(value)):
                        self.cache.pop(key, None)
                self.version += 1
                self.events.append({"version": self.version, "parent": parent, "path": str(value)})

    def restart_watcher(self):
        with self.watcher_lock:
            self._restart_watcher()

    def watch_roots(self):
        with self.lock:
            roots = [p for p in self.roots if self.available(p)]
        return [p for p in roots if not any(p != other and p.is_relative_to(other) for other in roots)]

    def _restart_watcher(self):
        self.stop.set()
        if self.watcher:
            self.watcher.join(timeout=3)
        self.stop = threading.Event()
        roots = [str(p) for p in self.watch_roots()]
        if not roots:
            return
        stop = self.stop

        def run():
            try:
                for changes in watch(*roots, stop_event=stop, debounce=200, step=50, recursive=True, ignore_permission_denied=True):
                    if stop.is_set():
                        break
                    self.changed([path for _, path in changes if not Path(path).name.startswith(".formatconverter-")])
            except OSError:
                with self.lock:
                    if not stop.is_set():
                        self.cache.clear()
                        self.version += 1
                        self.events.append({"version": self.version, "rescan": True})

        self.watcher = threading.Thread(target=run, daemon=True, name="directory-events")
        self.watcher.start()

    def list_directory(self, value: str, hidden=False, offset=0, limit=200, refresh=False, query=""):
        path = self.resolve(value)
        if not path.is_dir():
            raise ValueError("Choose a folder.")
        key = os.path.normcase(str(path))
        with self.lock:
            cached = self.cache.get(key)
            scan_version = self.version
            if cached:
                self.cache.move_to_end(key)
        if refresh or not cached or time.monotonic() - cached[0] > 30:
            entries = []
            with os.scandir(path) as scan:
                for item in scan:
                    try:
                        stat = item.stat(follow_symlinks=False)
                        link = item.is_symlink() or Path(item.path).is_junction()
                        entries.append({"path": item.path, "name": item.name, "directory": item.is_dir(follow_symlinks=False),
                                        "size": stat.st_size, "modified": stat.st_mtime,
                                        "hidden": item.name.startswith(".") or bool(getattr(stat, "st_file_attributes", 0) & 2),
                                        "link": link, "extension": Path(item.name).suffix.lower()})
                    except OSError:
                        continue
            entries = natsorted(entries, key=lambda e: (not e["directory"], e["name"].casefold()))
            with self.lock:
                if self.version == scan_version:
                    self.cache[key] = (time.monotonic(), entries)
                    self.cache.move_to_end(key)
                    while len(self.cache) > 64 or sum(len(v[1]) for v in self.cache.values()) > 100000:
                        self.cache.popitem(last=False)
        else:
            entries = cached[1]
        query = query.casefold().strip()
        visible = [entry for entry in entries if (hidden or not entry["hidden"])
                   and (not query or entry["directory"] or query in entry["name"].casefold())]
        return {"entries": visible[offset:offset + limit], "total": len(visible), "offset": offset,
                "has_more": offset + limit < len(visible), "version": scan_version}

    def get_events(self, after: int):
        with self.lock:
            missed = bool(self.events and after < self.events[0]["version"] - 1)
            return {"version": self.version, "rescan": missed,
                    "events": [e for e in self.events if e["version"] > after]}

    def properties(self, value: str):
        path = self.resolve(value)
        stat = path.stat()
        info = {"name": path.name, "path": str(path), "directory": path.is_dir(), "size": stat.st_size,
                "modified": stat.st_mtime, "created": getattr(stat, "st_birthtime", stat.st_ctime), "read_only": not os.access(path, os.W_OK)}
        if path.is_dir():
            info.pop("size")
        return info

    def operate(self, action: str, values: list[str], destination="", name="", confirmed=False):
        # Serialize clipboard and destination allocation without blocking directory reads.
        with self.operation_lock:
            return self._operate(action, values, destination, name, confirmed)

    def _operate(self, action: str, values: list[str], destination="", name="", confirmed=False):
        paths = list(dict.fromkeys(self.resolve(v) for v in values)) if action != "paste" else []
        if action != "paste" and not paths:
            raise ValueError("Select at least one item.")
        if action in {"copy", "cut", "delete"}:
            selected = set(paths)
            paths = [p for p in paths if not any(parent in selected for parent in p.parents)]
        if self.protected(paths) and action in {"rename", "delete", "cut"}:
            raise ValueError("Remove a root from the workspace instead of deleting or moving it.")
        if action in {"copy", "cut"}:
            self.clipboard = {"action": action, "paths": paths, "fingerprints": [fingerprint(str(p)) for p in paths]}
            return {"count": len(paths)}
        if action == "rename":
            if len(paths) != 1:
                raise ValueError("Use one file and a valid new filename.")
            validate_name(name)
            target = paths[0].parent / name
            self.resolve(str(target), exists=False)
            if str(target) == str(paths[0]):
                return {"paths": [str(target)]}
            if target.exists() and target != paths[0]:
                raise FileExistsError("A file with that name already exists.")
            paths[0].rename(target)
            self.changed([str(paths[0]), str(target)])
            return {"paths": [str(target)]}
        if action == "delete":
            if not confirmed:
                raise ValueError("Confirm recycle-bin deletion first.")
            results = []
            for path in paths:
                try:
                    send2trash(str(path))
                    results.append({"path": str(path), "ok": True})
                except OSError as exc:
                    results.append({"path": str(path), "ok": False, "error": str(exc)})
            self.changed([str(p) for p in paths])
            return {"results": results}
        if action == "paste":
            folder = self.resolve(destination)
            if not folder.is_dir() or not self.clipboard:
                raise ValueError("Choose a destination folder and copy or cut files first.")
            results = []
            clipboard = self.clipboard
            failed_paths, failed_fingerprints = [], []
            for source, expected in zip(clipboard["paths"], clipboard["fingerprints"]):
                try:
                    self.resolve(str(source))
                    if clipboard["action"] == "cut" and self.protected([source]):
                        raise ValueError("Remove a root from the workspace instead of deleting or moving it.")
                    if fingerprint(str(source)) != expected:
                        raise ValueError("SOURCE_CHANGED")
                    if clipboard["action"] == "cut" and folder == source.parent:
                        results.append({"path": str(source), "ok": True, "skipped": True})
                        continue
                    if folder == source or folder.is_relative_to(source):
                        raise ValueError("Cannot paste a folder inside itself.")
                    if source.is_dir():
                        for directory, dirs, files in os.walk(source, followlinks=False):
                            for child in dirs + files:
                                candidate = Path(directory, child)
                                if candidate.is_symlink() or candidate.is_junction():
                                    raise ValueError("Copying folders with links is not supported.")
                    target = unique_path(folder, source.name)
                    if clipboard["action"] == "cut":
                        try:
                            if os.name == "nt":
                                source.rename(target)
                            else:
                                raise OSError(errno.EXDEV, "Use exclusive copy publication")
                        except OSError as exc:
                            if exc.errno != errno.EXDEV and getattr(exc, "winerror", None) != 17:
                                raise
                            publish_copy(source, target, expected)
                            if source.is_dir():
                                shutil.rmtree(source)
                            else:
                                source.unlink()
                    else:
                        publish_copy(source, target, expected)
                    results.append({"path": str(target), "ok": True})
                except (OSError, ValueError) as exc:
                    results.append({"path": str(source), "ok": False, "error": str(exc)})
                    failed_paths.append(source)
                    failed_fingerprints.append(expected)
            if clipboard["action"] == "cut":
                self.clipboard = {"action": "cut", "paths": failed_paths, "fingerprints": failed_fingerprints} if failed_paths else None
            self.changed([str(folder / "changed"), *[str(p) for p in clipboard["paths"]]])
            return {"results": results}
        raise ValueError("Unsupported file operation.")

    def protected(self, paths):
        with self.lock:
            return any(root.is_relative_to(path) for root in self.roots for path in paths)

    def close(self):
        self.stop.set()
        if self.watcher:
            self.watcher.join(timeout=3)
