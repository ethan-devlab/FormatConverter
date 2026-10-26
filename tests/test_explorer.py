"""Explorer acceptance rules at the filesystem boundary; all inputs are synthetic."""
import os
from pathlib import Path

import pytest

from server.format_converter import config, files


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path / "preferences")
    monkeypatch.setattr(files.FileWorkspace, "restart_watcher", lambda self: None)
    root = tmp_path / "root"
    root.mkdir()
    workspace = files.FileWorkspace()
    workspace.add_root(str(root))
    yield workspace, root
    workspace.close()


def test_x15_paste_uses_clipboard_not_stale_selection(workspace):
    workspace, root = workspace
    source = root / "source.txt"
    source.write_text("source")
    destination = root / "destination"
    destination.mkdir()
    workspace.operate("copy", [str(source)])
    result = workspace.operate("paste", [str(root / "gone.txt")], str(destination))
    assert result["results"][0]["ok"]
    assert (destination / source.name).read_text() == "source"


def test_x14_cut_retry_retains_only_failed_sources(workspace, monkeypatch):
    workspace, root = workspace
    sources = [root / "one.txt", root / "two.txt"]
    for source in sources:
        source.write_text(source.name)
    destination = root / "destination"
    destination.mkdir()
    workspace.operate("cut", [str(p) for p in sources])
    sources[1].write_text("changed source")
    result = workspace.operate("paste", [], str(destination))
    assert [r["ok"] for r in result["results"]] == [True, False]
    assert workspace.clipboard["paths"] == [sources[1]]
    # A changed source must still fail on retry instead of silently accepting it.
    again = workspace.operate("paste", [], str(destination))
    assert [r["ok"] for r in again["results"]] == [False]
    assert sources[1].exists()
    assert (destination / "one.txt").read_text() == "one.txt"


@pytest.mark.parametrize("name", ["CON.txt", "aux", "LPT1.pdf", "trailing.", "trailing ", "bad\x01name"])
def test_x16_invalid_windows_names_leave_source_unchanged(workspace, name):
    workspace, root = workspace
    source = root / "source.txt"
    source.write_text("original")
    with pytest.raises(ValueError):
        workspace.operate("rename", [str(source)], name=name)
    assert source.read_text() == "original"


@pytest.mark.skipif(os.name != "nt", reason="Windows case-only rename")
def test_x16_case_only_rename(workspace):
    workspace, root = workspace
    source = root / "lower.txt"
    source.write_text("original")
    workspace.operate("rename", [str(source)], name="LOWER.txt")
    assert "LOWER.txt" in {p.name for p in root.iterdir()}
    assert (root / "LOWER.txt").read_text() == "original"


def test_x17_copy_does_not_overwrite_a_competing_destination(workspace, monkeypatch):
    workspace, root = workspace
    source = root / "source.txt"
    source.write_text("source")
    destination = root / "destination"
    destination.mkdir()
    original_unique = files.unique_path

    def competing_target(folder, name):
        target = original_unique(folder, name)
        target.write_text("external writer")
        return target

    monkeypatch.setattr(files, "unique_path", competing_target)
    workspace.operate("copy", [str(source)])
    result = workspace.operate("paste", [], str(destination))
    assert not result["results"][0]["ok"]
    assert (destination / source.name).read_text() == "external writer"
    assert source.read_text() == "source"


def test_x18_event_during_scan_does_not_publish_stale_cache(workspace, monkeypatch):
    workspace, root = workspace
    (root / "one.txt").write_text("one")
    original_sorted = files.natsorted
    changed = False

    def event_during_scan(entries, **kwargs):
        nonlocal changed
        if not changed:
            changed = True
            (root / "two.txt").write_text("two")
            workspace.changed([str(root / "two.txt")])
        return original_sorted(entries, **kwargs)

    monkeypatch.setattr(files, "natsorted", event_during_scan)
    workspace.list_directory(str(root))
    result = workspace.list_directory(str(root))
    assert {e["name"] for e in result["entries"]} == {"one.txt", "two.txt"}


def test_x10_filter_finds_a_match_after_the_first_page(workspace):
    workspace, root = workspace
    for index in range(205):
        (root / f"item-{index:03}.txt").write_text("fixture")
    (root / "z-match.txt").write_text("match")
    result = workspace.list_directory(str(root), query="z-match")
    assert [e["name"] for e in result["entries"]] == ["z-match.txt"]
    assert not result["has_more"]


@pytest.mark.parametrize("action", ["rename", "cut", "delete"])
def test_x04_root_ancestor_is_protected(workspace, action):
    workspace, root = workspace
    parent = root / "parent"
    nested = parent / "nested"
    nested.mkdir(parents=True)
    workspace.add_root(str(nested))
    for source in [parent, nested]:
        with pytest.raises(ValueError, match="root"):
            workspace.operate(action, [str(source)], name="renamed", confirmed=True)
    assert nested.is_dir()
    workspace.remove_root(str(nested))
    if action == "rename":
        workspace.operate(action, [str(parent)], name="renamed")
        assert (root / "renamed" / "nested").is_dir()


@pytest.mark.parametrize("action", ["copy", "cut", "delete"])
def test_x01_x02_duplicates_and_selected_descendants_are_processed_once(workspace, monkeypatch, action):
    workspace, root = workspace
    parent = root / "parent"
    parent.mkdir()
    child = parent / "child.txt"
    child.write_text("fixture")
    recycled = []
    monkeypatch.setattr(files, "send2trash", lambda path: recycled.append(path))
    result = workspace.operate(action, [str(child), str(parent), str(child)], confirmed=True)
    if action == "delete":
        assert recycled == [str(parent)]
        assert len(result["results"]) == 1
    else:
        assert result["count"] == 1
        assert workspace.clipboard["paths"] == [parent]


def test_x04_cut_rechecks_roots_at_paste_time(workspace):
    workspace, root = workspace
    parent = root / "parent"
    parent.mkdir()
    destination = root / "destination"
    destination.mkdir()
    workspace.operate("cut", [str(parent)])
    workspace.add_root(str(parent))
    result = workspace.operate("paste", [], str(destination))
    assert not result["results"][0]["ok"]
    assert parent.is_dir() and not (destination / parent.name).exists()


def test_x19_watchers_use_minimal_recursive_roots(workspace):
    workspace, root = workspace
    nested = root / "nested"
    nested.mkdir()
    other = root.parent / "other"
    other.mkdir()
    workspace.add_root(str(nested))
    workspace.add_root(str(other))
    assert workspace.watch_roots() == [root, other]


def test_x13_missing_root_can_return_without_losing_its_preference(workspace):
    workspace, root = workspace
    renamed = root.with_name("renamed")
    root.rename(renamed)
    assert not workspace.root_list()[0]["available"]
    renamed.rename(root)
    assert workspace.root_list()[0]["available"]


def test_x17_cut_does_not_overwrite_competing_target(workspace, monkeypatch):
    workspace, root = workspace
    source = root / "source.txt"
    source.write_text("source")
    destination = root / "destination"
    destination.mkdir()
    def competing_target(folder, name):
        target = folder / name
        target.write_text("external writer")
        return target
    monkeypatch.setattr(files, "unique_path", competing_target)
    workspace.operate("cut", [str(source)])
    result = workspace.operate("paste", [], str(destination))
    assert not result["results"][0]["ok"]
    assert source.read_text() == "source"
    assert (destination / source.name).read_text() == "external writer"


def test_x21_cut_paste_in_same_folder_does_not_rename_source(workspace):
    workspace, root = workspace
    source = root / "source.txt"
    source.write_text("source")
    workspace.operate("cut", [str(source)])
    result = workspace.operate("paste", [], str(root))
    assert result["results"] == [{"path": str(source), "ok": True, "skipped": True}]
    assert source.read_text() == "source"
    assert {p.name for p in root.iterdir()} == {"source.txt"}
    assert workspace.clipboard is None


def test_x22_source_changes_during_copy_do_not_publish_output(workspace, monkeypatch):
    workspace, root = workspace
    source = root / "source.txt"
    source.write_text("source")
    destination = root / "destination"
    destination.mkdir()
    original_copy = files.shutil.copy2
    def copy_then_change(source_path, target, **kwargs):
        result = original_copy(source_path, target, **kwargs)
        Path(source_path).write_text("new source content")
        return result
    monkeypatch.setattr(files.shutil, "copy2", copy_then_change)
    workspace.operate("copy", [str(source)])
    result = workspace.operate("paste", [], str(destination))
    assert not result["results"][0]["ok"]
    assert "SOURCE_CHANGED" in result["results"][0]["error"]
    assert source.read_text() == "new source content"
    assert not list(destination.iterdir())


def test_x19_stopped_watcher_cannot_invalidate_the_next_generation(workspace, monkeypatch):
    import threading
    workspace, _ = workspace
    ready = threading.Event()
    def stopped_watch(*args, stop_event, **kwargs):
        ready.set()
        stop_event.wait(3)
        raise OSError("old watch ended")
        yield  # Keep the interface identical to the native event iterator.
    monkeypatch.setattr(files, "watch", stopped_watch)
    workspace._restart_watcher()
    assert ready.wait(1)
    workspace._restart_watcher()
    assert workspace.get_events(0) == {"version": 0, "rescan": False, "events": []}


@pytest.mark.skipif(os.name != "nt", reason="Windows no-overwrite cut path")
def test_x14_retry_moves_only_the_sources_that_previously_failed(workspace, monkeypatch):
    workspace, root = workspace
    sources = [root / "one.txt", root / "two.txt"]
    for source in sources:
        source.write_text(source.name)
    destination = root / "destination"
    destination.mkdir()
    original_rename = Path.rename
    fail = True
    def temporarily_denied(source, target):
        if source == sources[1] and fail:
            raise PermissionError("Synthetic temporary access failure")
        return original_rename(source, target)
    monkeypatch.setattr(Path, "rename", temporarily_denied)
    workspace.operate("cut", [str(p) for p in sources])
    assert [r["ok"] for r in workspace.operate("paste", [], str(destination))["results"]] == [True, False]
    fail = False
    result = workspace.operate("paste", [], str(destination))
    assert len(result["results"]) == 1 and result["results"][0]["ok"]
    assert {p.name for p in destination.iterdir()} == {"one.txt", "two.txt"}
    assert workspace.clipboard is None
