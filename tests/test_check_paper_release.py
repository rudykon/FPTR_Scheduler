from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from tools import check_paper_release


class PaperReleaseGateUnitTests(unittest.TestCase):
    def test_latex_scanner_catches_each_release_blocker(self) -> None:
        text = "\n".join(
            (
                "! LaTeX Error: File `missing.sty' not found.",
                "LaTeX Warning: Citation `x' on page 1 undefined.",
                "LaTeX Warning: Reference `y' on page 1 undefined.",
                r"Overfull \hbox (1.0pt too wide)",
                "LaTeX Warning: Float too large for page by 2.0pt.",
            )
        )
        issues = check_paper_release.find_latex_issues(text)
        self.assertEqual(len(issues), 5)

    def test_latex_scanner_accepts_clean_summary(self) -> None:
        self.assertEqual(
            check_paper_release.find_latex_issues(
                "Output written on main.pdf (8 pages, 1000 bytes)."
            ),
            [],
        )

    def test_checksum_root_detects_tampering_and_unsafe_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="paper-release-checksum-") as temp:
            root = Path(temp)
            payload = root / "payload.txt"
            payload.write_text("sealed\n", encoding="utf-8")
            digest = hashlib.sha256(payload.read_bytes()).hexdigest()
            manifest = root / "CHECKSUMS.sha256"
            manifest.write_text(f"{digest}  payload.txt\n", encoding="utf-8")

            checked, errors = check_paper_release.verify_checksum_root(root)
            self.assertEqual(checked, 1)
            self.assertEqual(errors, [])

            payload.write_text("changed\n", encoding="utf-8")
            _, errors = check_paper_release.verify_checksum_root(root)
            self.assertIn("checksum mismatch", errors[0])

            manifest.write_text(f"{digest}  ../payload.txt\n", encoding="utf-8")
            _, errors = check_paper_release.verify_checksum_root(root)
            self.assertIn("unsafe path", errors[0])

    def test_stale_artifact_patterns_are_narrow(self) -> None:
        stale = ("main.tex.orig", "plot.tmp", "draft.bak", ".figure.svg.swp", "notes~")
        retained = ("main.aux", "main.fdb_latexmk", "figure.tiff", "temporary.md")
        self.assertTrue(all(check_paper_release.is_stale_artifact(Path(name)) for name in stale))
        self.assertTrue(
            all(not check_paper_release.is_stale_artifact(Path(name)) for name in retained)
        )


if __name__ == "__main__":
    unittest.main()
