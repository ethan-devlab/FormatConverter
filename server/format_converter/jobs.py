from __future__ import annotations

import json
import multiprocessing as mp
import os
import re
import shutil
import threading
import time
import uuid
from collections import deque
from pathlib import Path

import psutil

from .config import DATA, TESSDATA, read_preferences
from .conversion import worker_entry
from .files import fingerprint
from .schemas import JobRequest


def pool_worker(connection, progress):
    while True:
        try:
            task = connection.recv()
        except EOFError:
            return
        if task is None:
            return
        worker_entry(*task, progress)
        connection.send(True)
        task = None


def safe_filename(value: str):
    if not value or Path(value).name != value or any(c in value for c in '<>:"/\\|?*') or value != value.rstrip(" ."):
        raise ValueError("Invalid output filename.")
    if Path(value).stem.upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}:
        raise ValueError("Reserved output filename.")
    return value


class JobManager:
    def __init__(self, workspace):
        self.workspace = workspace
        self.lock = threading.RLock()
        self.context = mp.get_context("spawn")
        self.jobs = {}
        self.pending = deque()
        self.slots = []
        self.artifacts = {}
        self.closed = threading.Event()
        temp = DATA / "temporary"
        temp.mkdir(parents=True, exist_ok=True)
        for directory in temp.iterdir():
            if directory.is_dir() and not directory.is_symlink() and not directory.is_junction():
                try:
                    owner = json.loads((directory / "owner.json").read_text("utf-8"))
                    if owner.get("application") != "format-converter":
                        continue
                    try:
                        active = abs(psutil.Process(owner["pid"]).create_time() - owner["created"]) < 1
                    except psutil.Error:
                        active = False
                    if not active:
                        shutil.rmtree(directory)
                except (OSError, ValueError, KeyError):
                    pass
        self.session = temp / uuid.uuid4().hex
        self.session.mkdir()
        (self.session / "owner.json").write_text(json.dumps({"application": "format-converter", "pid": os.getpid(), "created": psutil.Process().create_time()}), "utf-8")
        self.thread = threading.Thread(target=self._run, daemon=True, name="conversion-scheduler")
        self.thread.start()

    def _new_slot(self):
        parent, child = self.context.Pipe()
        progress = self.context.Value("d", 0)
        process = self.context.Process(target=pool_worker, args=(child, progress), daemon=True)
        process.start()
        child.close()
        slot = {"process": process, "connection": parent, "progress": progress, "task": None}
        self.slots.append(slot)
        return slot

    def submit(self, request: JobRequest):
        with self.lock:
            if request.output_filename:
                raise ValueError("An exact output filename requires preview commit.")
            if len(self.jobs) >= 200:
                for key, old in list(self.jobs.items()):
                    if old["status"] in {"done", "failed", "cancelled", "partial"} and not old["request"].preview:
                        self.discard(key)
                        break
                else:
                    raise ValueError("Clear completed previews before creating more jobs.")
            for src in request.sources:
                src.path = str(self.workspace.resolve(src.path))
                if not Path(src.path).is_file():
                    raise ValueError("Conversion inputs must be files.")
            if not request.preview:
                folder = self.workspace.resolve(request.output_directory)
                if not folder.is_dir():
                    raise ValueError("Choose an output folder.")
            identity = uuid.uuid4().hex
            groups = [request.sources] if request.tool in {"images_pdf", "merge"} else [[src] for src in request.sources]
            tasks = []
            for index, group in enumerate(groups):
                work = self.session / identity / str(index)
                work.mkdir(parents=True)
                tasks.append({"index": index, "sources": [s.model_dump() for s in group],
                              "fingerprints": [fingerprint(s.path) for s in group], "directory": work,
                              "state": "queued", "progress": 0.0, "error": "", "outputs": [], "previews": []})
            job = {"id": identity, "request": request, "status": "queued", "tasks": tasks, "created": time.time()}
            self.jobs[identity] = job
            self.pending.extend((identity, task) for task in tasks)
            return self.public(identity)

    def _register(self, file_path: str, name: str, **data):
        identity = uuid.uuid4().hex
        self.artifacts[identity] = Path(file_path)
        return {"id": identity, "name": name, "size": Path(file_path).stat().st_size,
                "url": f"/api/artifacts/{identity}", **data}

    def _check_sources(self, task):
        for src, expected in zip(task["sources"], task["fingerprints"]):
            self.workspace.resolve(src["path"])
            if fingerprint(src["path"]) != expected:
                raise ValueError("SOURCE_CHANGED")
        for path, expected in task.get("dependencies", {}).items():
            self.workspace.resolve(path)
            if fingerprint(path) != tuple(expected):
                raise ValueError("SOURCE_CHANGED: A Markdown image changed.")

    def _publish(self, output, request, index):
        folder = self.workspace.resolve(request.output_directory)
        original = Path(output["name"])
        if request.output_filename:
            name = request.output_filename
        elif request.filename:
            name = Path(request.filename).stem + original.suffix
        else:
            name = request.naming.format(name=original.stem, index=index + 1, tool=request.tool) + original.suffix
        safe_filename(name)
        target = folder / name
        for src in request.sources:
            if target.exists() and Path(src.path).exists() and os.path.samefile(src.path, target):
                if request.collision == "overwrite":
                    raise ValueError("SOURCE_OVERWRITE_NOT_ALLOWED")
        stage = folder / f".formatconverter-{uuid.uuid4().hex}.tmp"
        try:
            shutil.copyfile(output["path"], stage)
            with stage.open("rb+") as handle:
                os.fsync(handle.fileno())
            if request.collision == "overwrite":
                os.replace(stage, target)
            else:
                suffix = 0
                while True:
                    try:
                        # Windows rename refuses existing targets and also works on
                        # removable filesystems without hard-link support.
                        if os.name == "nt":
                            os.rename(stage, target)
                        else:
                            os.link(stage, target)
                        break
                    except FileExistsError:
                        if request.collision == "skip":
                            return {"name": name, "skipped": True}
                        if request.collision == "ask":
                            raise FileExistsError("OUTPUT_EXISTS: Choose rename, skip, or overwrite and retry.")
                        suffix += 1
                        target = folder / f"{Path(name).stem}_{suffix:02d}{Path(name).suffix}"
            return self._register(str(target), target.name, path=str(target), pages=output.get("pages"))
        finally:
            stage.unlink(missing_ok=True)

    def _finish_task(self, job, task):
        self._check_sources(task)
        result = json.loads((task["directory"] / "result.json").read_text("utf-8"))
        if result.get("error"):
            raise ValueError(result["error"])
        task["warnings"] = result.get("warnings", [])
        task["dependencies"] = result.get("dependencies", {})
        self._check_sources(task)
        task["raw_outputs"] = result["outputs"]
        task["previews"] = [self._register(p, "preview.png", preview=True) for p in result["previews"]]
        if job["request"].preview:
            task["outputs"] = [self._register(o["path"], o["name"], pages=o.get("pages"), temporary=True) for o in result["outputs"]]
        else:
            task["outputs"] = [self._publish(o, job["request"], task["index"]) for o in result["outputs"]]
        task["state"] = "done"
        task["progress"] = 1.0

    def _status(self, job):
        states = [task["state"] for task in job["tasks"]]
        if any(s == "running" for s in states):
            job["status"] = "running"
        elif any(s == "queued" for s in states):
            job["status"] = "queued"
        elif all(s == "cancelled" for s in states):
            job["status"] = "cancelled"
        elif all(s == "done" for s in states):
            job["status"] = "done"
        elif any(s == "done" for s in states):
            job["status"] = "partial"
        else:
            job["status"] = "failed"
        if job["status"] in {"done", "partial", "failed", "cancelled"} and not job["request"].preview:
            self._discard_temporary(job)

    def _run(self):
        while not self.closed.wait(0.1):
            with self.lock:
                for slot in list(self.slots):
                    task_info = slot["task"]
                    if not task_info:
                        if not slot["process"].is_alive():
                            slot["connection"].close()
                            slot["process"].join(timeout=0)
                            self.slots.remove(slot)
                        continue
                    job, task = task_info
                    task["progress"] = slot["progress"].value
                    if slot["connection"].poll() or not slot["process"].is_alive():
                        try:
                            if not slot["process"].is_alive():
                                raise RuntimeError("WORKER_STOPPED")
                            slot["connection"].recv()
                            self._finish_task(job, task)
                        except Exception as exc:
                            task["state"], task["error"] = "failed", str(exc)[:600]
                        slot["task"] = None
                        self._status(job)
                prefs = read_preferences()
                limit = prefs["workers"]
                while self.pending:
                    job_id, task = self.pending[0]
                    job = self.jobs[job_id]
                    if task["state"] != "queued":
                        self.pending.popleft()
                        continue
                    running = sum(s["task"] is not None for s in self.slots)
                    if running >= limit:
                        break
                    rss = 0
                    for slot in self.slots:
                        try:
                            rss += psutil.Process(slot["process"].pid).memory_info().rss
                        except psutil.Error:
                            pass
                    if running and rss > prefs["memory_mb"] * 1024**2:
                        break
                    slot = next((s for s in self.slots if s["task"] is None and s["process"].is_alive()), None)
                    if slot is None:
                        slot = self._new_slot()
                    self.pending.popleft()
                    try:
                        self._check_sources(task)
                        slot["progress"].value = 0
                        slot["task"] = (job, task)
                        parameters = job["request"].parameters.model_dump()
                        if job["request"].tool == "text_pdf":
                            with self.workspace.lock:
                                parameters["_allowed_roots"] = [str(p) for p in self.workspace.roots + self.workspace.temporary_roots]
                        slot["connection"].send((job["request"].tool, task["sources"], parameters, str(task["directory"]), str(TESSDATA)))
                        task["state"] = job["status"] = "running"
                    except Exception as exc:
                        task["state"], task["error"] = "failed", str(exc)[:600]
                        slot["task"] = None
                        self._status(job)

    def public(self, identity):
        with self.lock:
            job = self.jobs[identity]
            return {"id": identity, "tool": job["request"].tool, "preview": job["request"].preview,
                    "status": job["status"], "created": job["created"],
                    "progress": sum(t["progress"] for t in job["tasks"]) / len(job["tasks"]),
                    "tasks": [{"index": t["index"], "sources": [Path(s["path"]).name for s in t["sources"]],
                               "source_sizes": [value[2] for value in t["fingerprints"]],
                               "state": t["state"], "progress": t["progress"], "error": t["error"], "warnings": t.get("warnings", []),
                               "outputs": t["outputs"], "previews": t["previews"]} for t in job["tasks"]]}

    def cancel(self, identity):
        with self.lock:
            job = self.jobs[identity]
            for slot in list(self.slots):
                if slot["task"] and slot["task"][0] is job:
                    from .browsers import terminate_tree, terminate_browser_work
                    terminate_browser_work(slot["task"][1]["directory"])
                    terminate_tree(slot["process"].pid)
                    slot["process"].join(timeout=5)
                    slot["connection"].close()
                    self.slots.remove(slot)
            for task in job["tasks"]:
                if task["state"] in {"queued", "running"}:
                    task["state"], task["error"] = "cancelled", ""
                    shutil.rmtree(task["directory"], ignore_errors=True)
            self._status(job)
            return self.public(identity)

    def commit(self, identity, request: JobRequest):
        with self.lock:
            job = self.jobs[identity]
            if not job["request"].preview or job["status"] not in {"done", "partial"}:
                raise ValueError("No completed preview is available.")
            old = job["request"]
            if request.tool != old.tool or request.parameters != old.parameters or request.sources != old.sources:
                raise ValueError("PREVIEW_STALE")
            if request.output_filename:
                outputs = [o for task in job["tasks"] if task["state"] == "done" for o in task["raw_outputs"]]
                if len(outputs) != 1:
                    raise ValueError("An exact output filename requires one output.")
                if Path(request.output_filename).suffix.lower() != Path(outputs[0]["name"]).suffix.lower():
                    raise ValueError("Keep the output file extension.")
            for task in job["tasks"]:
                if task["state"] == "done":
                    self._check_sources(task)
            for task in job["tasks"]:
                if task["state"] == "done":
                    task["outputs"] = [self._publish(o, request, task["index"]) for o in task["raw_outputs"]]
            job["request"] = request
            self._discard_temporary(job)
            return self.public(identity)

    def _discard_temporary(self, job):
        directory = self.session / job["id"]
        for key, path in list(self.artifacts.items()):
            if path.is_relative_to(directory):
                self.artifacts.pop(key)
        for task in job["tasks"]:
            task["previews"] = []
        shutil.rmtree(directory, ignore_errors=True)

    def discard(self, identity):
        with self.lock:
            self.cancel(identity)
            job = self.jobs[identity]
            self._discard_temporary(job)
            for task in job["tasks"]:
                for artifact in task["outputs"]:
                    self.artifacts.pop(artifact.get("id"), None)
            self.pending = deque((key, task) for key, task in self.pending if key != identity)
            self.jobs.pop(identity)

    def retry(self, identity):
        with self.lock:
            job = self.jobs[identity]
            request = job["request"].model_copy(deep=True)
            request.sources = [type(request.sources[0]).model_validate(src) for task in job["tasks"] if task["state"] in {"failed", "cancelled"} for src in task["sources"]]
            if not request.sources:
                raise ValueError("No failed items to retry.")
            return self.submit(request)

    def busy(self):
        with self.lock:
            return any(j["status"] in {"running", "queued"} for j in self.jobs.values())

    def close(self):
        self.closed.set()
        self.thread.join(timeout=5)
        for slot in self.slots:
            from .browsers import terminate_tree, terminate_browser_work
            if slot["task"]:
                terminate_browser_work(slot["task"][1]["directory"])
            terminate_tree(slot["process"].pid)
            slot["process"].join(timeout=5)
            slot["connection"].close()
        shutil.rmtree(self.session, ignore_errors=True)
