import test from "node:test";
import assert from "node:assert/strict";
import { WheelNavigation } from "../src/preview-navigation.ts";

test("wheel navigation accumulates small deltas and suppresses burst page jumps", () => {
  const wheel = new WheelNavigation();
  assert.equal(wheel.step(20,0,0),0);
  assert.equal(wheel.step(20,0,50),0);
  assert.equal(wheel.step(20,0,100),1);
  assert.equal(wheel.step(200,0,150),0);
  assert.equal(wheel.step(-120,0,600),-1);
});
test("wheel navigation resets old or reversed gestures and supports line/page units", () => {
  const wheel = new WheelNavigation();
  assert.equal(wheel.step(40,0,0),0);
  assert.equal(wheel.step(-40,0,20),0);
  assert.equal(wheel.step(20,0,400),0);
  assert.equal(wheel.step(4,1,450),1);
  assert.equal(wheel.step(-1,2,1000),-1);
});
