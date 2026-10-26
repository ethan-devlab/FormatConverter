from pathlib import Path

from server.format_converter import picker


def test_save_dialog_prefills_name_extension_and_cancel_is_empty(monkeypatch):
    from tkinter import filedialog
    calls = []
    class Root:
        def destroy(self):
            calls.append("destroy")
    class Connection:
        def send(self, value):
            calls.append(value)
        def close(self):
            calls.append("close")
    monkeypatch.setattr(picker, "create_root", Root)
    def save(**options):
        assert options["initialfile"] == "report.v2.pdf"
        assert options["defaultextension"] == ".pdf"
        assert options["confirmoverwrite"] is True
        return ""
    monkeypatch.setattr(filedialog, "asksaveasfilename", save)
    picker._pick(Connection(), "report.v2.pdf", "C:/Output")
    assert calls == ["destroy", {"path": ""}, "close"]


def test_directory_dialog_is_used_for_multiple_outputs(monkeypatch):
    from tkinter import filedialog
    calls = []
    class Root:
        def destroy(self):
            pass
    class Connection:
        def send(self, value):
            calls.append(value)
        def close(self):
            pass
    monkeypatch.setattr(picker, "create_root", Root)
    monkeypatch.setattr(filedialog, "askdirectory", lambda **options: "C:/Output")
    picker._pick(Connection())
    assert calls == [{"path": "C:/Output"}]


def test_native_root_windows_dpi_context_and_restoration():
    import ctypes
    import os
    import pytest
    if os.name != "nt":
        pytest.skip("Windows native DPI integration")
    user32 = ctypes.WinDLL("user32")
    user32.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    user32.GetWindowDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.GetWindowDpiAwarenessContext.restype = ctypes.c_void_p
    user32.AreDpiAwarenessContextsEqual.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    previous = user32.GetThreadDpiAwarenessContext()
    with picker.native_root() as root:
        root.update_idletasks()
        assert user32.AreDpiAwarenessContextsEqual(user32.GetThreadDpiAwarenessContext(), ctypes.c_void_p(-4))
        assert user32.AreDpiAwarenessContextsEqual(user32.GetWindowDpiAwarenessContext(root.winfo_id()), ctypes.c_void_p(-4))
    assert user32.AreDpiAwarenessContextsEqual(user32.GetThreadDpiAwarenessContext(), previous)


def test_native_root_restores_dpi_when_creation_fails(monkeypatch):
    import ctypes
    import os
    import pytest
    if os.name != "nt":
        pytest.skip("Windows native DPI integration")
    user32 = ctypes.WinDLL("user32")
    user32.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    user32.AreDpiAwarenessContextsEqual.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    previous = user32.GetThreadDpiAwarenessContext()
    def fail():
        raise RuntimeError("test creation failure")
    monkeypatch.setattr(picker, "create_root", fail)
    with pytest.raises(RuntimeError, match="test creation failure"):
        with picker.native_root():
            pytest.fail("No root should be returned")
    assert user32.AreDpiAwarenessContextsEqual(user32.GetThreadDpiAwarenessContext(), previous)
