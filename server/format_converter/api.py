from __future__ import annotations

import asyncio
import hmac
import io
import mimetypes
import os
import secrets
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pymupdf
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from PIL import Image, ImageOps
from pydantic import BaseModel, Field
from pillow_heif import register_heif_opener, libheif_info

from .config import BASE, DATA, TESSDATA, VERSION, read_preferences, write_preferences
from .files import FileWorkspace
from .jobs import JobManager, safe_filename
from .schemas import JobRequest, Source
from .inspection import inspect_documents
from .picker import pick_folder as native_pick_folder

register_heif_opener()


class PathBody(BaseModel):
    path: str


class InspectionBody(BaseModel):
    sources: list[Source] = Field(min_length=1, max_length=100)


class FileOperation(BaseModel):
    action: str
    paths: list[str] = Field(default_factory=list, max_length=10000)
    destination: str = ""
    name: str = ""
    confirmed: bool = False


def create_app(dev=False):
    session = secrets.token_urlsafe(32)
    workspace = FileWorkspace()
    manager = JobManager(workspace)
    clients = {}
    state_lock = threading.RLock()

    def session_cookie(request: Request):
        # Cookies share a host across ports; distinct names prevent one local
        # instance from replacing another instance's session credential.
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        return f"fc_session_{port}"

    @asynccontextmanager
    async def lifespan(app):
        yield
        manager.close()
        workspace.close()

    app = FastAPI(title="Format Converter", version=VERSION, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.manager, app.state.workspace = manager, workspace
    app.state.clients, app.state.started, app.state.had_clients = clients, time.monotonic(), False
    app.state.last_close = time.monotonic()
    uploads = manager.session / "uploads"
    uploads.mkdir()
    workspace.temporary_roots = [manager.session]

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        host = request.url.hostname
        if host not in {"127.0.0.1", "localhost", "testserver"} or (host == "testserver" and not os.environ.get("PYTEST_CURRENT_TEST")):
            return JSONResponse({"detail": "HOST_NOT_ALLOWED"}, 403)
        origin = request.headers.get("origin")
        allowed = {f"{request.url.scheme}://{request.headers.get('host')}"}
        if dev:
            allowed.add("http://127.0.0.1:5173")
        if origin and origin not in allowed:
            return JSONResponse({"detail": "ORIGIN_NOT_ALLOWED"}, 403)
        if request.url.path.startswith("/api/") and request.url.path not in {"/api/session", "/api/health"}:
            if not hmac.compare_digest(request.cookies.get(session_cookie(request), ""), session):
                return JSONResponse({"detail": "SESSION_REQUIRED"}, 401)
            if request.method not in {"GET", "HEAD"} and request.url.path != "/api/clients/close" and request.headers.get("x-format-converter") != "1":
                return JSONResponse({"detail": "REQUEST_HEADER_REQUIRED"}, 403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        return response

    @app.exception_handler(PermissionError)
    async def permission_error(request, exc):
        return JSONResponse({"detail": str(exc)}, 403)

    @app.exception_handler(FileNotFoundError)
    async def missing_error(request, exc):
        return JSONResponse({"detail": "FILE_NOT_FOUND"}, 404)

    @app.exception_handler(ValueError)
    @app.exception_handler(OSError)
    async def operation_error(request, exc):
        return JSONResponse({"detail": str(exc)[:600]}, 400)

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": VERSION}

    @app.post("/api/session")
    def start_session(request: Request):
        if request.headers.get("x-format-converter") != "1":
            raise HTTPException(403, "REQUEST_HEADER_REQUIRED")
        response = JSONResponse({"version": VERSION})
        response.set_cookie(session_cookie(request), session, httponly=True, samesite="strict")
        return response

    @app.get("/api/bootstrap")
    def bootstrap():
        Image.init()
        return {"version": VERSION, "preferences": read_preferences(), "roots": workspace.root_list(),
                "capabilities": {"encoders": sorted(Image.SAVE), "heif": libheif_info(),
                                 "ocr_languages": [p.stem for p in TESSDATA.glob("*.traineddata")],
                                 "pdf_engine": pymupdf.version[0]}}

    @app.put("/api/preferences")
    def preferences(values: dict):
        # Root changes go through root validation and watcher management.
        return write_preferences({k: v for k, v in values.items() if k != "roots"})

    @app.post("/api/roots")
    def add_root(body: PathBody):
        return workspace.add_root(body.path)

    @app.get("/api/roots")
    def roots(refresh: bool = False):
        if refresh:
            workspace.restart_watcher()
        return workspace.root_list()

    @app.delete("/api/roots")
    def remove_root(body: PathBody):
        return workspace.remove_root(body.path)

    @app.post("/api/pick-folder")
    def pick_folder():
        return native_pick_folder()

    @app.post("/api/jobs/{identity}/pick-output")
    def pick_output(identity: str, body: JobRequest):
        with manager.lock:
            job = manager.jobs.get(identity)
            if not job or not job["request"].preview or job["status"] not in {"done", "partial"}:
                raise ValueError("No completed preview is available.")
            outputs = [(task, o) for task in job["tasks"] if task["state"] == "done" for o in task["raw_outputs"]]
            if not outputs:
                raise ValueError("No successful output is available.")
            name = ""
            if len(outputs) == 1:
                task, output = outputs[0]
                original = Path(output["name"])
                name = (Path(body.filename).stem if body.filename else body.naming.format(
                    name=original.stem, index=task["index"] + 1, tool=body.tool)) + original.suffix
                safe_filename(name)
        result = native_pick_folder(name, body.output_directory)
        return {**result, "single": len(outputs) == 1}

    @app.get("/api/directory")
    def directory(path: str, hidden: bool = False, offset: int = 0, limit: int = 200, refresh: bool = False, query: str = ""):
        return workspace.list_directory(path, hidden, max(0, offset), max(1, min(1000, limit)), refresh, query)

    @app.get("/api/events")
    def events(after: int = 0):
        return workspace.get_events(after)

    @app.get("/api/events/stream")
    async def event_stream(request: Request, after: int = 0):
        async def generate():
            import json
            version = after
            last = time.monotonic()
            while not await request.is_disconnected():
                data = workspace.get_events(version)
                if data["version"] != version:
                    version = data["version"]
                    yield "data: " + json.dumps(data) + "\n\n"
                    last = time.monotonic()
                elif time.monotonic() - last > 10:
                    yield ": heartbeat\n\n"
                    last = time.monotonic()
                await asyncio.sleep(0.25)
        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.post("/api/files/operation")
    def operate(body: FileOperation):
        return workspace.operate(body.action, body.paths, body.destination, body.name, body.confirmed)

    @app.post("/api/files/properties")
    def properties(body: PathBody):
        return workspace.properties(body.path)

    @app.post("/api/files/inspect-pdf")
    def inspect_pdf(body: InspectionBody):
        sources = []
        for source in body.sources:
            path = workspace.resolve(source.path)
            sources.append({"path": str(path), "name": path.name, "password": source.password})
        return inspect_documents(sources)

    @app.post("/api/thumbnail")
    def thumbnail(body: PathBody):
        path = workspace.resolve(body.path)
        with Image.open(path) as source:
            if source.width * source.height > 100_000_000:
                raise ValueError("IMAGE_PIXEL_LIMIT")
            source.draft("RGB", (128, 128))
            image = ImageOps.exif_transpose(source)
            image.thumbnail((96, 96))
            buffer = io.BytesIO()
            image.convert("RGBA").save(buffer, "PNG")
        return Response(buffer.getvalue(), media_type="image/png")

    @app.post("/api/uploads")
    async def upload(files: list[UploadFile] = File()):
        result = []
        for file in files:
            original = safe_filename(Path(file.filename or "file").name)
            folder = uploads / uuid.uuid4().hex
            folder.mkdir()
            path = folder / original
            try:
                with path.open("xb") as handle:
                    while block := await file.read(1024 * 1024):
                        handle.write(block)
                result.append({"path": str(path), "name": original, "size": path.stat().st_size,
                               "directory": False, "extension": path.suffix.lower(), "temporary": True})
            except Exception:
                path.unlink(missing_ok=True)
                raise
            finally:
                await file.close()
        return result

    @app.post("/api/jobs")
    def submit(body: JobRequest):
        return manager.submit(body)

    @app.get("/api/jobs")
    def jobs():
        with manager.lock:
            return [manager.public(key) for key in reversed(manager.jobs) if not manager.jobs[key].get("internal")]

    @app.get("/api/jobs/{identity}")
    def job(identity: str):
        if identity not in manager.jobs:
            raise HTTPException(404, "JOB_NOT_FOUND")
        return manager.public(identity)

    @app.post("/api/jobs/{identity}/cancel")
    def cancel(identity: str):
        if identity not in manager.jobs:
            raise HTTPException(404, "JOB_NOT_FOUND")
        return manager.cancel(identity)

    @app.post("/api/jobs/{identity}/retry")
    def retry(identity: str):
        if identity not in manager.jobs:
            raise HTTPException(404, "JOB_NOT_FOUND")
        return manager.retry(identity)

    @app.post("/api/jobs/{identity}/commit")
    def commit(identity: str, body: JobRequest):
        if identity not in manager.jobs:
            raise HTTPException(404, "JOB_NOT_FOUND")
        return manager.commit(identity, body)

    @app.delete("/api/jobs/{identity}")
    def discard(identity: str):
        if identity in manager.jobs:
            manager.discard(identity)
        return {"ok": True}

    @app.get("/api/artifacts/{identity}")
    def artifact(identity: str, download: bool = False):
        path = manager.artifacts.get(identity)
        if not path or not path.is_file():
            raise HTTPException(404, "ARTIFACT_NOT_FOUND")
        media = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return FileResponse(path, media_type=media, filename=path.name if download else None)

    @app.get("/api/artifacts/{identity}/text")
    def text_artifact(identity: str):
        path = manager.artifacts.get(identity)
        if not path or not path.is_file() or path.suffix != ".txt":
            raise HTTPException(404, "ARTIFACT_NOT_FOUND")
        with path.open(encoding="utf-8") as handle:
            text = handle.read(100001)
        return {"text": text[:100000], "truncated": len(text) > 100000}

    @app.post("/api/preview-page")
    def preview_page(values: dict):
        artifact_id, page = str(values.get("artifact", "")), int(values.get("page", 1))
        with manager.lock:
            path = manager.artifacts.get(artifact_id)
            if not path or path.suffix != ".pdf":
                raise HTTPException(404, "ARTIFACT_NOT_FOUND")
            parent = next((j for j in manager.jobs.values() if any(o.get("id") == artifact_id for task in j["tasks"] for o in task["outputs"])), None)
            if not parent:
                raise HTTPException(404, "JOB_NOT_FOUND")
            p = parent["request"].parameters
            password = p.owner_password or p.opening_password or p.password
            body = JobRequest(tool="pdf_images", preview=True, sources=[{"path": str(path), "password": password}],
                              parameters={"pages": str(page), "dpi": 120, "format": "PNG"})
            result = manager.submit(body)
            manager.jobs[result["id"]]["internal"] = True
            return result

    @app.post("/api/clients/heartbeat")
    def heartbeat(values: dict):
        identity = str(values.get("id", ""))[:80]
        if not identity:
            raise ValueError("A client ID is required.")
        with state_lock:
            clients[identity] = time.monotonic()
            app.state.had_clients = True
        return {"busy": manager.busy()}

    @app.post("/api/clients/close")
    async def close_client(request: Request):
        values = await request.json()
        with state_lock:
            clients.pop(str(values.get("id", "")), None)
            app.state.last_close = time.monotonic()
        return {"ok": True}

    @app.get("/{resource:path}")
    def frontend(resource: str):
        dist = BASE / "dist"
        target = (dist / resource).resolve()
        if not target.is_relative_to(dist.resolve()):
            raise HTTPException(403, "PATH_OUTSIDE_ROOTS")
        if not target.is_file():
            target = dist / "index.html"
        if not target.is_file():
            return JSONResponse({"detail": "Frontend not built. Run pnpm build, or use pnpm dev."}, 503)
        return FileResponse(target)

    return app
