import test from "node:test";
import assert from "node:assert/strict";
import { explorerShortcut } from "../src/shortcuts.ts";

const key = (name: string, values = {}) => ({key:name,ctrlKey:false,metaKey:false,altKey:false,shiftKey:false,...values});
test("Explorer maps standard file shortcuts without taking browser shortcuts", () => {
  assert.equal(explorerShortcut(key("c",{ctrlKey:true})),"copy");
  assert.equal(explorerShortcut(key("X",{ctrlKey:true})),"cut");
  assert.equal(explorerShortcut(key("v",{metaKey:true})),"paste");
  assert.equal(explorerShortcut(key("a",{ctrlKey:true})),"selectAll");
  assert.equal(explorerShortcut(key("F2")),"rename");
  assert.equal(explorerShortcut(key("F5")),"refresh");
  assert.equal(explorerShortcut(key("Delete")),"delete");
  assert.equal(explorerShortcut(key("Enter",{altKey:true})),"properties");
  assert.equal(explorerShortcut(key("F5",{ctrlKey:true})),null);
  assert.equal(explorerShortcut(key("F10",{shiftKey:true})),null);
  assert.equal(explorerShortcut(key("v",{ctrlKey:true,shiftKey:true})),null);
});
