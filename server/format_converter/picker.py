from __future__ import annotations

import multiprocessing
import os
from contextlib import contextmanager
from pathlib import Path

from .config import BASE


def create_root():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.title("Format Converter")
    icon = BASE / "resources" / "FormatConverter-tk.ico"
    if not icon.is_file():
        icon = BASE / "build/windows-assets/FormatConverter-tk.ico"
    if os.name == "nt":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EthanDevLab.FormatConverter")
        root.iconbitmap(default=str(icon))
    root.attributes("-topmost", True)
    return root


@contextmanager
def native_root():
    # Set the creating thread before Tk creates any HWND. Common Windows dialogs
    # then scale per monitor without changing the service or worker process mode.
    previous = None
    user32 = None
    if os.name == "nt":
        import ctypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        previous = user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        if not previous:
            raise ctypes.WinError(ctypes.get_last_error())
    try:
        root = create_root()
        try:
            yield root
        finally:
            root.destroy()
    finally:
        if previous is not None:
            user32.SetThreadDpiAwarenessContext(previous)


def _pick(connection, filename="", directory=""):
    try:
        from tkinter import filedialog

        with native_root() as root:
            if filename:
                extension = Path(filename).suffix
                path = filedialog.asksaveasfilename(parent=root, title="Format Converter",
                    initialfile=filename, initialdir=directory or None, defaultextension=extension,
                    filetypes=[(extension.upper().lstrip(".") + " file", "*" + extension)], confirmoverwrite=True)
            else:
                path = filedialog.askdirectory(parent=root, title="Format Converter", initialdir=directory or None, mustexist=True)
        connection.send({"path": path})
    except Exception:
        connection.send({"error": "FOLDER_PICKER_UNAVAILABLE: Enter a folder path instead."})
    finally:
        connection.close()


def pick_folder(filename="", directory=""):
    # A spawned main thread owns Tk. Pipes preserve Unicode in a windowless build.
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_pick, args=(child, filename, directory), daemon=True)
    process.start()
    child.close()
    try:
        if not parent.poll(180):
            raise ValueError("FOLDER_PICKER_TIMEOUT: Enter a folder path instead.")
        result = parent.recv()
        if "error" in result:
            raise ValueError(result["error"])
        return result
    finally:
        parent.close()
        process.join(timeout=2)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
