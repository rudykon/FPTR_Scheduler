"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const runtime = require("../runtime.js");
const spaceRoot = path.resolve(__dirname, "..");
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "fptr-runtime-"));
const binary = path.join(temporary, "scheduler");

try {
  const compile = spawnSync(
    "g++",
    ["-std=c++17", "-O2", path.join(spaceRoot, "src/scheduler.cpp"), path.join(spaceRoot, "src/core.cpp"), "-o", binary],
    { encoding: "utf8" }
  );
  assert.equal(compile.status, 0, compile.stderr);

  const input = fs.readFileSync(path.join(spaceRoot, "data/cases/small-balanced.in"), "utf8");
  const caseData = runtime.parseCaseText(input, "small-balanced");
  const expectedTrace = {
    beamfirst: ["beam_first", "final"], base: ["base", "final"],
    global: ["base", "global", "final"], cg: ["base", "global", "cg", "final"],
    remask: ["base", "global", "cg", "remask", "final"],
    full: ["base", "global", "cg", "remask", "pair", "final"]
  };
  let fullRun = null;

  for (const [stage, traceStages] of Object.entries(expectedTrace)) {
    const run = spawnSync(binary, ["--stage", stage, "--budget-ms", "87", "--trace"], {
      input, encoding: "utf8", timeout: 5000
    });
    assert.equal(run.status, 0, run.stderr);
    const result = runtime.validateRun(caseData, run.stdout, run.stderr, 87, 0);
    assert.equal(result.valid, true);
    assert.equal(result.trace.at(-1).score, result.score);
    assert.deepEqual(result.trace.map((entry) => entry.stage), traceStages);
    assert.ok(result.beamUsed <= caseData.beamMax);
    assert.equal(result.delivered.length, caseData.N);
    if (stage === "full") fullRun = { output: run.stdout, result };
  }

  assert.ok(fullRun);
  const externalTrace = `TRACE external=alns score=${fullRun.result.score} elapsed_ms=1.25e1 iterations=37 accepted=9\n`;
  const external = runtime.validateExternalRun(
    caseData, fullRun.output, externalTrace, 87, 13, "alns"
  );
  assert.equal(external.valid, true);
  assert.equal(external.score, fullRun.result.score);
  assert.equal(external.iterations, 37);
  assert.equal(external.accepted, 9);
  assert.throws(
    () => runtime.validateExternalRun(caseData, fullRun.output, externalTrace, 87, 13, "ga"),
    /expected ga/
  );

  const view = runtime.instanceView(caseData);
  assert.equal(view.users, 20);
  assert.equal(view.resources, 18);
  assert.throws(() => runtime.parseCaseText("1 2 3\n"), /header|line/i);
  process.stdout.write("Browser runtime validated against every native C++ stage.\n");
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}
