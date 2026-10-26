"""Use installed browsers through their local CDP or WebDriver BiDi endpoints."""
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request

import psutil
import websocket


def browser_paths():
    candidates = {
        "edge": [Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
                 Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe"],
        "chrome": [Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
                   Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe"],
        "firefox": [Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Mozilla Firefox/firefox.exe",
                    Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Mozilla Firefox/firefox.exe"],
    }
    return {name: next((str(p) for p in paths if p.is_file()), "") for name, paths in candidates.items()}


def terminate_tree(pid):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for process in reversed(children):
            try:
                process.terminate()
            except psutil.Error:
                pass
        psutil.wait_procs(children, timeout=3)
        if parent.is_running():
            parent.terminate()
            parent.wait(timeout=5)
    except psutil.Error:
        pass


def browser_processes(profiles):
    profiles = {os.path.normcase(str(Path(p).resolve())) for p in profiles}
    found = []
    for process in psutil.process_iter():
        try:
            if process.name().lower() not in {"msedge.exe", "chrome.exe", "firefox.exe"}:
                continue
            args = process.cmdline()
            values = [arg.split("=", 1)[1] for arg in args if arg.startswith("--user-data-dir=")]
            values += [args[index + 1] for index, arg in enumerate(args[:-1]) if arg in {"--profile", "-profile"}]
            if any(os.path.normcase(str(Path(value).resolve())) in profiles for value in values):
                found.append(process)
        except (psutil.Error, OSError):
            pass
    return found


def terminate_browser_work(work):
    # A browser may relaunch outside the worker tree. Match only exact unique
    # profile arguments owned by this task, never names or shared user profiles.
    profiles = list(Path(work).glob("browser-profile-*"))
    for process in browser_processes(profiles):
        terminate_tree(process.pid)


class BrowserPDF:
    def __init__(self, engine, override, work):
        if engine == "safari":
            raise ValueError("BROWSER_UNAVAILABLE: Safari requires later macOS validation.")
        path = override or browser_paths().get(engine, "")
        expected = {"edge": "msedge.exe", "chrome": "chrome.exe", "firefox": "firefox.exe"}[engine]
        if not path or not Path(path).is_file() or Path(path).name.lower() != expected:
            raise ValueError(f"BROWSER_UNAVAILABLE: Configure an installed {engine} executable.")
        self.engine, self.process, self.ws, self.serial = engine, None, None, 0
        self.work = Path(work)
        profile = Path(tempfile.mkdtemp(prefix="browser-profile-", dir=self.work))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        if engine == "firefox":
            (profile / "user.js").write_text('user_pref("browser.shell.checkDefaultBrowser", false);\n'
                'user_pref("datareporting.policy.dataSubmissionEnabled", false);\n'
                'user_pref("toolkit.telemetry.enabled", false);\n', "utf-8")
            command = [path, "--headless", "--no-remote", "--profile", str(profile), "--remote-debugging-port", str(port), "about:blank"]
        else:
            command = [path, "--headless=new", "--no-first-run", "--no-default-browser-check",
                       "--disable-extensions", "--disable-background-networking", "--disable-sync",
                       f"--user-data-dir={profile}", f"--remote-debugging-port={port}",
                       "--remote-debugging-address=127.0.0.1", "about:blank"]
        self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            deadline = time.monotonic() + 25
            while True:
                try:
                    if engine == "firefox":
                        endpoint = f"ws://127.0.0.1:{port}/session"
                    else:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1) as response:
                            pages = json.load(response)
                        endpoint = next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page")
                    self.ws = websocket.create_connection(endpoint, timeout=5, suppress_origin=True)
                    self.ws.settimeout(60)
                    break
                except (OSError, StopIteration, websocket.WebSocketException):
                    # A successful launcher can hand off to another process with
                    # this task's profile before its local endpoint is ready.
                    if self.process.poll() not in (None, 0) or time.monotonic() > deadline:
                        raise ValueError("BROWSER_START_FAILED: Check the browser path and local policies.")
                    time.sleep(.1)
            if engine == "firefox":
                self.call("session.new", {"capabilities": {}})
                self.context = self.call("browsingContext.create", {"type": "tab"})["context"]
            else:
                self.call("Page.enable")
        except Exception:
            self.close()
            raise

    def call(self, method, params=None):
        self.serial += 1
        identity = self.serial
        self.ws.send(json.dumps({"id": identity, "method": method, "params": params or {}}))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            response = json.loads(self.ws.recv())
            if response.get("id") != identity:
                continue
            if "error" in response:
                raise ValueError(f"BROWSER_RENDER_ERROR: {response.get('message') or response['error']}")
            return response.get("result", {})
        raise ValueError("BROWSER_RENDER_TIMEOUT")

    def evaluate(self, expression):
        if self.engine == "firefox":
            result = self.call("script.evaluate", {"expression": expression, "target": {"context": self.context}, "awaitPromise": True})
            if result.get("type") == "exception":
                raise ValueError("BROWSER_RENDER_ERROR: JavaScript evaluation failed.")
            # JSON strings avoid protocol-specific nested object serialization.
            return json.loads(result["result"].get("value", "null"))
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        if result.get("exceptionDetails"):
            raise ValueError("BROWSER_RENDER_ERROR: JavaScript evaluation failed.")
        return json.loads(result.get("result", {}).get("value", "null"))

    def render(self, url, width, height):
        if self.engine == "firefox":
            self.call("browsingContext.navigate", {"context": self.context, "url": url, "wait": "complete"})
        else:
            self.call("Page.navigate", {"url": url})
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            state = self.evaluate("JSON.stringify(window.__FC_STATUS || null)")
            if state and state.get("ready"):
                break
            if state and state.get("error"):
                raise ValueError("MARKDOWN_RENDER_ERROR: " + state["error"])
            time.sleep(.1)
        else:
            raise ValueError("MARKDOWN_RENDER_TIMEOUT: Formula or diagram rendering did not finish.")
        if self.engine == "firefox":
            result = self.call("browsingContext.print", {"context": self.context, "background": True,
                "page": {"width": width / 10, "height": height / 10},
                "margin": {"top": 0, "bottom": 0, "left": 0, "right": 0}, "shrinkToFit": False})
        else:
            result = self.call("Page.printToPDF", {"printBackground": True, "preferCSSPageSize": True,
                "paperWidth": width / 25.4, "paperHeight": height / 25.4,
                "marginTop": 0, "marginBottom": 0, "marginLeft": 0, "marginRight": 0})
        return base64.b64decode(result["data"]), state

    def close(self):
        if self.ws:
            self.ws.close()
        if self.process:
            terminate_browser_work(self.work)
            terminate_tree(self.process.pid)
