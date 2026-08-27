#!/usr/bin/env python3
"""Contract tests for the generated FPTR Static Space dataset."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent


class StaticSpaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads((ROOT / "data" / "results.json").read_text(encoding="utf-8"))

    def test_frontend_contract(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "app.js").read_text(encoding="utf-8")
        card = (ROOT / "README.md").read_text(encoding="utf-8")
        workflow = (REPOSITORY / ".github" / "workflows" / "deploy-hf-space.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('src="app.js"', html)
        self.assertIn('href="styles.css"', html)
        self.assertIn('fetch("data/results.json"', script)
        self.assertEqual(card.count("sdk: static"), 1)
        self.assertNotIn("sdk: docker", card)
        short_description = next(
            line.split(":", 1)[1].strip()
            for line in card.splitlines()
            if line.startswith("short_description:")
        )
        self.assertLessEqual(len(short_description), 60)
        self.assertIn("space_sdk: static", workflow)

    def test_generated_snapshots_are_self_consistent(self) -> None:
        payload = self.payload
        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(len(payload["scenarios"]), 5)
        self.assertEqual(len(payload["budgets"]), 5)
        self.assertEqual(len(payload["stages"]), 6)

        stage_ids = {stage["id"] for stage in payload["stages"]}
        for scenario in payload["scenarios"]:
            instance = scenario["instance"]
            self.assertEqual(len(instance["requested"]), instance["users"])
            self.assertEqual(len(instance["resourceBands"]), instance["resources"])
            for budget in payload["budgets"]:
                results = scenario["results"][str(budget)]
                self.assertEqual(set(results), stage_ids)
                baseline_score = results["beamfirst"]["score"]
                for result in results.values():
                    self.assertTrue(result["valid"])
                    self.assertEqual(result["baselineScore"], baseline_score)
                    self.assertEqual(sum(result["delivered"]), result["score"])
                    self.assertEqual(len(result["delivered"]), instance["users"])
                    self.assertEqual(len(result["beams"]), instance["subbands"])
                    self.assertEqual(sum(len(beams) for beams in result["beams"]), result["beamUsed"])
                    self.assertLessEqual(result["beamUsed"], instance["beamMax"])
                    self.assertEqual(len(result["resourceUsers"]), instance["resources"])
                    self.assertEqual(len(result["userResources"]), instance["users"])
                    self.assertEqual(
                        sum(bool(users) for users in result["resourceUsers"]),
                        result["resourcesUsed"],
                    )
                    self.assertEqual(
                        sum(len(users) > 1 for users in result["resourceUsers"]),
                        result["sharedResources"],
                    )
                    scores = [entry["score"] for entry in result["trace"]]
                    self.assertEqual(scores[-1], result["score"])
                    self.assertEqual(scores, sorted(scores))

                    reconstructed = [[] for _ in range(instance["users"])]
                    for resource, users in enumerate(result["resourceUsers"], start=1):
                        for user in users:
                            reconstructed[user - 1].append(resource)
                    self.assertEqual(reconstructed, result["userResources"])


if __name__ == "__main__":
    unittest.main()
