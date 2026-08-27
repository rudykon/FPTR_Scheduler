"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const runtime = require("../runtime.js");
const createFPTRModule = require("../wasm/fptr_solver.js");

(async () => {
  const input = fs.readFileSync(path.resolve(__dirname, "../data/cases/small-balanced.in"), "utf8");
  const caseData = runtime.parseCaseText(input, "wasm-smoke");
  const module = await createFPTRModule();
  const raw = module.ccall(
    "fptr_run", "string", ["string", "string", "number"], [input, "full", 87]
  );
  const payload = JSON.parse(raw);
  assert.equal(payload.ok, true, payload.error);
  const result = runtime.validateRun(caseData, payload.output, payload.trace, 87, 0);
  assert.equal(result.valid, true);
  assert.equal(result.trace.at(-1).stage, "final");
  assert.ok(result.score > 0);
  process.stdout.write(`WebAssembly smoke test passed with score ${result.score}.\n`);
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
