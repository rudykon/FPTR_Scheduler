"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const runtime = require("../runtime.js");
const createFPTRModule = require("../wasm/fptr_solver.js");
const createFPTRBaselineModule = require("../wasm/fptr_baselines.js");

(async () => {
  const input = fs.readFileSync(path.resolve(__dirname, "../data/cases/small-balanced.in"), "utf8");
  const caseData = runtime.parseCaseText(input, "wasm-smoke");
  const [module, baselineModule] = await Promise.all([
    createFPTRModule(), createFPTRBaselineModule()
  ]);
  const raw = module.ccall(
    "fptr_run", "string", ["string", "string", "number"], [input, "full", 87]
  );
  const payload = JSON.parse(raw);
  assert.equal(payload.ok, true, payload.error);
  const result = runtime.validateRun(caseData, payload.output, payload.trace, 87, 0);
  assert.equal(result.valid, true);
  assert.equal(result.trace.at(-1).stage, "final");
  assert.ok(result.score > 0);

  const methods = ["alns", "tabu", "ga", "sa", "ils", "grasp"];
  for (const method of methods) {
    const baselineRaw = baselineModule.ccall(
      "fptr_baseline_run", "string", ["string", "string", "number", "number"],
      [input, method, 20, 20260801]
    );
    const baselinePayload = JSON.parse(baselineRaw);
    assert.equal(baselinePayload.ok, true, baselinePayload.error);
    const baselineResult = runtime.validateExternalRun(
      caseData, baselinePayload.output, baselinePayload.trace, 20, 0, method
    );
    assert.equal(baselineResult.valid, true);
    assert.ok(baselineResult.score > 0);
    assert.equal(baselineResult.trace[0].stage, method);
  }
  process.stdout.write(
    `WebAssembly smoke test passed for FPTR and ${methods.length} external baselines.\n`
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
