import test from "node:test";
import assert from "node:assert/strict";
import { taskFailures, taskWarnings, measuredSize, validQuality, usesQuality } from "../src/job-feedback.ts";

test("mixed batch reports failed task while another task is still running", () => {
  const job: any = {id:"batch",tasks:[{index:0,state:"running",error:""},{index:1,state:"failed",sources:["locked.pdf"],error:"PASSWORD_REQUIRED_OR_INCORRECT"}]};
  assert.deepEqual(taskFailures([job]).map((f) => f.task.sources), [["locked.pdf"]]);
  assert.equal(taskFailures([job])[0].key, taskFailures([job])[0].key);
});

test("quality rejects typed out-of-range and fractional values only where used", () => {
  for (const value of [0,101,1000,NaN,1.5,"85"]) assert.equal(validQuality(value), false);
  for (const value of [1,85,100]) assert.equal(validQuality(value), true);
  assert.equal(usesQuality("compress", {compression:"lossy"}), true);
  assert.equal(usesQuality("compress", {compression:"lossless"}), false);
  assert.equal(usesQuality("image", {format:"PNG"}), false);
});

test("measured output sums all frames and skips skipped files; failures have no size", () => {
  const task: any = {state:"done", source_sizes:[1000], outputs:[{size:200},{size:300},{size:900,skipped:true}]};
  assert.equal(measuredSize(task)?.output,500);
  assert.equal(measuredSize(task)?.change,-50);
  assert.equal(measuredSize({...task,state:"failed"}),null);
  assert.equal(measuredSize({...task,source_sizes:[0]})?.change,null);
});


test("dismissed warnings stay hidden across polling but new work and new warnings remain visible", () => {
  const job: any = {id:"one",tasks:[{index:0,sources:["document.md"],warnings:["IMAGE_UNAVAILABLE: a.png"]}]};
  const first = taskWarnings([job]);
  const dismissed = new Set(first.map(warning => warning.key));
  assert.equal(taskWarnings([structuredClone(job)], dismissed).length, 0);
  const next = structuredClone(job);
  next.tasks[0].warnings.unshift("IMAGE_UNAVAILABLE: b.png");
  assert.deepEqual(taskWarnings([next], dismissed).map(warning => warning.message), ["IMAGE_UNAVAILABLE: b.png"]);
  assert.equal(taskWarnings([{...job, id:"two"}], dismissed).length, 1);
  assert.equal(job.tasks[0].warnings.length, 1);
});
