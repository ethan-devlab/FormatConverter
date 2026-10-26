import test from "node:test";
import assert from "node:assert/strict";
import { parseIconSizes } from "../src/ico.ts";

test("ICO size input normalizes unique edge lengths in pixel order", () => {
  assert.deepEqual(parseIconSizes(" 256,16,16,32 "), [16,32,256]);
  assert.deepEqual(parseIconSizes("1,255,256"), [1,255,256]);
});

test("ICO size input rejects empty selections, dimensions, fractions and out-of-range values", () => {
  for (const value of ["", " ", "16,", "16,,32", "0", "257", "16x16", "16.5", "-1", "１２", "1,".repeat(1100)]) {
    assert.equal(parseIconSizes(value), null, value);
  }
});
