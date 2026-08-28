#!/usr/bin/env python3
"""Contract tests for the browser-executed FPTR GitHub Pages Demo."""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
sys.path.insert(0, str(ROOT))

from tools import scheduler_validator  # noqa: E402


class BrowserDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "data" / "manifest.json").read_text(encoding="utf-8")
        )

    def test_frontend_executes_the_real_wasm_scheduler(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        github_demo = (REPOSITORY / "docs" / "demo" / "index.html").read_text(
            encoding="utf-8"
        )
        script = (ROOT / "app.js").read_text(encoding="utf-8")
        workflow = (
            REPOSITORY / ".github" / "workflows" / "pages.yml"
        ).read_text(encoding="utf-8")

        self.assertIn('src="runtime.js"', html)
        self.assertIn('src="wasm/fptr_solver.js"', html)
        self.assertIn('src="app.js"', html)
        self.assertIn('src="./wasm/fptr_baselines.js"', github_demo)
        self.assertIn('fetch(demoAssetUrl("data/manifest.json")', script)
        self.assertIn('const DEMO_BASE_URL', script)
        self.assertIn('ccall("fptr_run"', script)
        self.assertIn('"fptr_baseline_run"', script)
        self.assertNotIn("data/results.json", script)
        self.assertIn("bash space/build_wasm.sh", workflow)
        self.assertIn("node space/tests/smoke_wasm.js", workflow)
        self.assertIn("Deploy to GitHub Pages", workflow)
        self.assertFalse(
            (REPOSITORY / ".github" / "workflows" / "deploy-hf-space.yml").exists()
        )
        for readme in ("README.md", "README.zh-CN.md"):
            self.assertNotIn(
                "huggingface.co/spaces/",
                (REPOSITORY / readme).read_text(encoding="utf-8"),
            )
        self.assertNotIn(
            "wasm/fptr_solver.js", (ROOT / ".gitignore").read_text(encoding="utf-8")
        )
        self.assertNotIn(
            "wasm/fptr_solver.wasm", (ROOT / ".gitignore").read_text(encoding="utf-8")
        )
        self.assertIn(
            "space/wasm/fptr_solver.js",
            (REPOSITORY / ".gitignore").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "space/wasm/fptr_solver.wasm",
            (REPOSITORY / ".gitignore").read_text(encoding="utf-8"),
        )
        self.assertNotIn(
            "wasm/fptr_baselines.js", (ROOT / ".gitignore").read_text(encoding="utf-8")
        )
        self.assertNotIn(
            "wasm/fptr_baselines.wasm", (ROOT / ".gitignore").read_text(encoding="utf-8")
        )
        self.assertIn(
            "space/wasm/fptr_baselines.js",
            (REPOSITORY / ".gitignore").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "space/wasm/fptr_baselines.wasm",
            (REPOSITORY / ".gitignore").read_text(encoding="utf-8"),
        )

    def test_manifest_and_public_inputs_are_self_consistent(self) -> None:
        manifest = self.manifest
        self.assertEqual(manifest["schemaVersion"], 2)
        self.assertEqual(manifest["execution"], "browser-webassembly")
        self.assertEqual(len(manifest["scenarios"]), 5)
        self.assertEqual(len(manifest["budgets"]), 5)
        self.assertEqual(len(manifest["stages"]), 6)
        self.assertEqual(
            {stage["id"] for stage in manifest["stages"]},
            {"full", "remask", "cg", "global", "base", "beamfirst"},
        )

        for scenario in manifest["scenarios"]:
            path = ROOT / scenario["path"]
            self.assertTrue(path.is_file(), scenario["path"])
            text = path.read_text(encoding="utf-8")
            self.assertEqual(
                hashlib.sha256(text.encode("utf-8")).hexdigest(), scenario["sha256"]
            )
            case = scheduler_validator.parse_case_text(text, case_id=scenario["id"])
            dimensions = scenario["dimensions"]
            self.assertEqual(case.N, dimensions["users"])
            self.assertEqual(case.K, dimensions["resources"])
            self.assertEqual(case.P, dimensions["beams"])
            self.assertEqual(case.T, dimensions["subbands"])
            self.assertEqual(case.beam_max, dimensions["beamMax"])

    def test_wasm_build_is_bound_to_checked_in_cpp_core(self) -> None:
        build = (ROOT / "build_wasm.sh").read_text(encoding="utf-8")
        bridge = (ROOT / "src" / "wasm_api.cpp").read_text(encoding="utf-8")
        baseline_bridge = (ROOT / "src" / "external_wasm_api.cpp").read_text(
            encoding="utf-8"
        )
        self.assertIn('src/core.cpp', build)
        self.assertIn('src/wasm_api.cpp', build)
        self.assertIn("MODULARIZE=1", build)
        self.assertNotIn("SINGLE_FILE=1", build)
        self.assertIn("-fexceptions", build)
        self.assertIn('fptr_run', bridge)
        self.assertIn('src/external_wasm_api.cpp', build)
        self.assertIn('createFPTRBaselineModule', build)
        self.assertIn('fptr_baselines.js', build)
        self.assertIn('external_alns_baseline.cpp', baseline_bridge)
        self.assertIn('external_tabu_ga_baseline.cpp', baseline_bridge)
        self.assertIn('external_sa_ils_grasp.cpp', baseline_bridge)
        self.assertIn('fptr_baseline_run', baseline_bridge)
        self.assertEqual(
            (ROOT / "src" / "core.cpp").read_bytes(),
            (REPOSITORY / "src" / "core.cpp").read_bytes(),
        )
        self.assertEqual(
            (ROOT / "src" / "core.h").read_bytes(),
            (REPOSITORY / "src" / "core.h").read_bytes(),
        )

    def test_github_pages_is_a_readable_multipage_paper_companion(self) -> None:
        docs = REPOSITORY / "docs"
        home = (docs / "index.html").read_text(encoding="utf-8")
        method = (docs / "method" / "index.html").read_text(encoding="utf-8")
        evidence = (docs / "evidence" / "index.html").read_text(encoding="utf-8")
        demo = (docs / "demo" / "index.html").read_text(encoding="utf-8")
        css = (docs / "assets" / "site.css").read_text(encoding="utf-8")

        self.assertIn('<h1 data-i18n="paperTitle">FPTR Scheduler</h1>', home)
        self.assertIn("截止时间约束下的联合波束与资源调度", home)
        self.assertIn("保留可行解，隔离细化，验证后提交。", home)
        self.assertEqual(home.count('class="summary-card '), 3)
        self.assertNotIn('class="reading-grid"', home)
        for route in ("problem", "method", "evidence", "reproduce", "demo"):
            self.assertIn(f'href="./{route}/"', home)

        for cutoff in (
            '<mo>≤</mo><mn>45</mn>',
            '<mo>≤</mo><mn>84</mn>',
            '<mo>≤</mo><mn>87</mn>',
            '<mi>B</mi><mo>=</mo><mn>87</mn>',
            '<mi>D</mi><mo>=</mo><mn>100</mn>',
        ):
            self.assertIn(cutoff, method)
        self.assertIn("<h3>Pair</h3>", method)
        self.assertNotIn(
            '<img src="../images/Deadline_Aware_FPTR_Scheduler.png"', method
        )
        for rq in ("RQ1", "RQ2", "RQ3", "RQ4", "RQ5"):
            self.assertIn(rq, evidence)
        for panel in (
            "web_stage_gain.png",
            "web_scenario_gain.png",
            "web_budget_quality.png",
            "web_runtime_ecdf.png",
            "web_cg_stress.png",
            "web_optimality_gap.png",
        ):
            self.assertIn(panel, evidence)
            self.assertTrue((docs / "images" / panel).is_file(), panel)
            svg = panel.replace(".png", ".svg")
            self.assertNotIn(svg, evidence)
            self.assertFalse((docs / "images" / svg).exists(), svg)

        self.assertIn('class="advanced-controls"', demo)
        self.assertIn('id="results" class="results-section" aria-labelledby="resultTitle" hidden', demo)
        self.assertEqual(demo.count('id="deepAnalysis"'), 1)
        self.assertEqual(demo.count('role="tab"'), 4)
        self.assertNotIn('class="advanced-results"', demo)
        self.assertNotIn('class="advanced-detail"', demo)
        self.assertNotIn('class="step-number"', demo)
        self.assertIn('id="comparisonBars"', demo)
        self.assertIn('id="comparisonBody"', demo)
        self.assertIn('src="./wasm/fptr_baselines.js"', demo)
        self.assertEqual(demo.count('id="customInput"'), 1)
        self.assertEqual(demo.count('id="stageButtons"'), 1)
        self.assertIn('id="budgetSlider"', demo)
        self.assertIn('type="range"', demo)
        self.assertNotIn('id="budgetButtons"', demo)
        self.assertNotIn('id="runPrompt"', demo)
        for share_class in ("share-0", "share-1", "share-2", "share-3"):
            self.assertIn(f'class="{share_class}"', demo)

        self.assertIn("--text-body: 1rem", css)
        self.assertIn("min-height: 44px", css)
        self.assertIn(
            "https://rudykon.github.io/FPTR_Scheduler/demo/",
            (REPOSITORY / "README.md").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
