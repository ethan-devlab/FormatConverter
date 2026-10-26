import test from "node:test";
import assert from "node:assert/strict";
import { DirectoryRequests, uniqueEntries, pathKey, selectedEntries, operationEntries, canAct } from "../src/explorer.ts";

const entry = (path: string, directory = false) => ({ path, name: path, directory, size: 0, extension: directory ? "" : ".txt" });
const root = { path: "C:\\root", name: "root", available: true };

test("X01 mirrored occurrences select and operate on one physical path", () => {
  const file = entry("C:\\root\\nested\\one.txt");
  const selected = selectedEntries([file, { ...file, path: "c:/ROOT/nested/one.txt" }], new Set([pathKey(file.path)]));
  assert.equal(selected.length, 1);
  assert.equal(operationEntries("delete", selected).length, 1);
  assert.equal(operationEntries("copy", selected).length, 1);
});

test("X02 parent and descendants produce one top-level operation in selection order", () => {
  const folder = entry("C:\\root\\folder", true), child = entry("C:\\root\\folder\\child.txt"), other = entry("C:\\root\\other.txt");
  for (const action of ["copy", "cut", "delete"])
    assert.deepEqual(operationEntries(action, [child, folder, other]), [folder, other]);
  assert.equal(operationEntries("copy", [folder, entry("C:\\root\\folder-two.txt")]).length, 2);
});

test("X03 visible selection survives one collapsed mirror but disappears after all are hidden", () => {
  const file = entry("C:\\root\\one.txt"), selected = new Set([pathKey(file.path)]);
  assert.equal(selectedEntries([file, file], selected).length, 1);
  assert.equal(selectedEntries([file], selected).length, 1);
  const remaining = new Set(selectedEntries([], selected).map((file) => pathKey(file.path)));
  assert.equal(selectedEntries([file], remaining).length, 0);
});

test("X04 a registered root or its ancestor is protected through every occurrence", () => {
  const nested = { path: "C:\\root\\folder\\nested", name: "nested", available: true };
  for (const action of ["rename", "cut", "delete"]) {
    assert.equal(canAct(action, [entry(nested.path, true)], [root, nested], root.path), false);
    assert.equal(canAct(action, [entry("C:\\root\\folder", true)], [root, nested], root.path), false);
    assert.equal(canAct(action, [entry("C:\\root\\folder", true)], [root], root.path), true);
  }
});

test("X05 commands follow target cardinality, availability and operation type", () => {
  const one = entry("C:\\root\\one.txt"), two = entry("C:\\root\\two.txt");
  for (const action of ["rename", "properties"]) {
    assert.equal(canAct(action, [], [root], root.path), false);
    assert.equal(canAct(action, [one, two], [root], root.path), false);
    assert.equal(canAct(action, [one, one], [root], root.path), true);
    assert.equal(canAct(action, [{ ...one, link: true }], [root], root.path), false);
  }
  assert.equal(canAct("copy", [one, two], [root], root.path), true);
  assert.equal(canAct("paste", [], [root], "C:\\outside"), false);
  assert.equal(canAct("paste", [], [{ ...root, available: false }], root.path), false);
  assert.equal(canAct("paste", [], [root], root.path), true);
  assert.equal(canAct("paste", [{ ...one, link: true }], [root], root.path), false);
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

test("X07 a late old directory reply cannot replace a newer refresh", async () => {
  const requests = new DirectoryRequests<string>();
  const old = deferred<string>(), current = deferred<string>();
  const first = requests.run("C:\\root", false, () => old.promise);
  const second = requests.run("C:\\root", false, () => current.promise);
  old.resolve("stale");
  assert.equal(await first, undefined);
  assert.equal(requests.busy("C:\\root"), true);
  current.resolve("fresh");
  assert.equal(await second, "fresh");
  assert.equal(requests.busy("C:\\root"), false);
});

test("X08 repeated Load more reads one page, once", async () => {
  const requests = new DirectoryRequests<string>();
  const page = deferred<string>();
  let reads = 0;
  const read = () => { reads++; return page.promise; };
  const first = requests.run("C:\\root", true, read);
  assert.equal(await requests.run("c:/ROOT", true, read), undefined);
  page.resolve("page 2");
  assert.equal(await first, "page 2");
  assert.equal(reads, 1);
});

test("X06 forgotten-root replies and errors cannot restore removed rows", async () => {
  const requests = new DirectoryRequests<string>();
  const page = deferred<string>();
  const first = requests.run("C:\\forgotten", false, () => page.promise);
  requests.cancel();
  page.resolve("removed rows");
  assert.equal(await first, undefined);
  assert.equal(requests.busy("C:\\forgotten"), false);
});

test("X08 refreshed pages contain each Windows path once", () => {
  const entries = ["C:\\root\\one.txt", "c:/ROOT/ONE.txt", "C:\\root\\two.txt"].map((path) =>
    ({ path, name: path, directory: false, size: 0, extension: ".txt" }));
  assert.equal(uniqueEntries(entries).length, 2);
});
