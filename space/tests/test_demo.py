from __future__ import annotations

import unittest

import app


class DemoSmokeTests(unittest.TestCase):
    def test_small_full_run_is_valid_and_downloadable(self) -> None:
        outputs = app.run_demo(
            "Small · balanced",
            20260801,
            87,
            "Full · all refinements",
            None,
        )
        self.assertEqual(len(outputs), 9)
        self.assertIn("PASS", outputs[0])
        self.assertGreater(len(outputs[5]), 2)
        self.assertEqual(len(outputs[6]), 20)
        self.assertTrue(str(outputs[7]).endswith(".zip"))

    def test_generator_is_deterministic(self) -> None:
        first = app.load_instance("Small · balanced", 7, None)[0]
        second = app.load_instance("Small · balanced", 7, None)[0]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
