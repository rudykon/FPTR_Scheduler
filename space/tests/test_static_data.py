#!/usr/bin/env python3
"""Contract tests for the browser-executed FPTR Static Space."""

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


class StaticSpaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "data" / "manifest.json").read_text(encoding="utf-8")
        )

    def test_frontend_executes_the_real_wasm_scheduler(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "app.js").read_text(encoding="utf-8")
        card = (ROOT / "README.md").read_text(encoding="utf-8")
        workflow = (
            REPOSITORY / ".github" / "workflows" / "deploy-hf-space.yml"
        ).read_text(encoding="utf-8")

        self.assertIn('src="runtime.js"', html)
        self.assertIn('src="wasm/fptr_solver.js"', html)
        self.assertIn('src="app.js"', html)
        self.assertIn('fetch("data/manifest.json"', script)
        self.assertIn('ccall("fptr_run"', script)
        self.assertNotIn("data/results.json", script)
        self.assertEqual(card.count("sdk: static"), 1)
        self.assertNotIn("sdk: docker", card)
        short_description = next(
            line.split(":", 1)[1].strip()
            for line in card.splitlines()
            if line.startswith("short_description:")
        )
        self.assertLessEqual(len(short_description), 60)
        self.assertIn("space_sdk: static", workflow)
        self.assertIn("space/build_wasm.sh", workflow)
        self.assertIn("space/tests/smoke_wasm.js", workflow)
        self.assertNotIn(
            "wasm/fptr_solver.js", (ROOT / ".gitignore").read_text(encoding="utf-8")
        )
        self.assertIn(
            "space/wasm/fptr_solver.js",
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
        self.assertIn('src/core.cpp', build)
        self.assertIn('src/wasm_api.cpp', build)
        self.assertIn("MODULARIZE=1", build)
        self.assertIn("SINGLE_FILE=1", build)
        self.assertIn("-fexceptions", build)
        self.assertIn('fptr_run', bridge)
        self.assertEqual(
            (ROOT / "src" / "core.cpp").read_bytes(),
            (REPOSITORY / "src" / "core.cpp").read_bytes(),
        )
        self.assertEqual(
            (ROOT / "src" / "core.h").read_bytes(),
            (REPOSITORY / "src" / "core.h").read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
