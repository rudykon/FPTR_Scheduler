#!/usr/bin/env python3
"""Validate the checked-in paper release bundle without modifying it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PDF_SPECS = {
    "main.pdf": (1, 12),
    "main_zh.pdf": (1, 12),
}
LOG_NAMES = ("main.log", "main_zh.log")
CHECKSUM_DIRS = ("results", "audit", "supplement_data")
FIGURE_STEMS = (
    "results_quality_runtime",
    "results_stress_optimality",
)
RASTER_FIGURES = (
    "scenario_constraint_coupling.png",
    "FPTR release path.png",
)
FIGURE_EXTENSIONS = ("svg", "pdf", "tiff", "png")
STALE_SUFFIXES = (".orig", ".rej", ".tmp", ".temp", ".bak", ".swp", ".swo")

LATEX_ERROR_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"!\s*LaTeX Error",
        r"!\s*(?:Undefined control sequence|Emergency stop)",
        r"Fatal error occurred",
        r"(?:Citation|Reference).+undefined",
        r"There were undefined (?:references|citations)",
        r"Overfull \\[hv]box",
        r"Float too large",
    )
)


@dataclass(frozen=True)
class Check:
    passed: bool
    label: str
    detail: str


class Report:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def add(self, passed: bool, label: str, detail: str) -> None:
        self.checks.append(Check(passed, label, detail))

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if not check.passed]

    def print(self) -> None:
        for check in self.checks:
            status = "PASS" if check.passed else "FAIL"
            print(f"[{status}] {check.label}: {check.detail}")
        passed = len(self.checks) - len(self.failures)
        print(f"\nPaper release gate: {passed}/{len(self.checks)} checks passed.")
        if self.failures:
            print(f"Release blocked by {len(self.failures)} failed check(s).")
        else:
            print("Release bundle is ready.")


def pdf_page_count(path: Path) -> int:
    """Return a PDF page count, preferring Poppler and using a local fallback."""
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        completed = subprocess.run(
            [pdfinfo, str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if completed.returncode == 0:
            match = re.search(r"^Pages:\s*(\d+)\s*$", completed.stdout, re.MULTILINE)
            if match:
                return int(match.group(1))
        detail = completed.stderr.strip() or "no Pages field in pdfinfo output"
        raise ValueError(f"pdfinfo failed: {detail}")

    data = path.read_bytes()
    count = len(re.findall(rb"/Type\s*/Page(?!s)\b", data))
    if count < 1:
        raise ValueError("cannot determine page count (pdfinfo unavailable)")
    return count


def find_latex_issues(text: str) -> list[tuple[int, str]]:
    """Find release-blocking LaTeX diagnostics while preserving line context."""
    issues: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if any(pattern.search(line) for pattern in LATEX_ERROR_PATTERNS):
            issues.append((number, line.strip()))
    return issues


def is_stale_artifact(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith("~") or name.endswith(STALE_SUFFIXES)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum_root(directory: Path) -> tuple[int, list[str]]:
    """Verify a sha256sum-style manifest and reject paths outside its root."""
    manifest = directory / "CHECKSUMS.sha256"
    if not manifest.is_file():
        return 0, ["missing CHECKSUMS.sha256"]

    errors: list[str] = []
    checked = 0
    root = directory.resolve()
    for line_number, raw_line in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{64})[ \t]+\*?(.+?)", line)
        if not match:
            errors.append(f"line {line_number}: malformed checksum entry")
            continue

        expected, relative_text = match.groups()
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"line {line_number}: unsafe path {relative_text!r}")
            continue
        target = (directory / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            errors.append(f"line {line_number}: path escapes checksum root")
            continue
        if not target.is_file():
            errors.append(f"line {line_number}: missing {relative_text}")
            continue

        checked += 1
        actual = sha256_file(target)
        if actual.lower() != expected.lower():
            errors.append(f"line {line_number}: checksum mismatch for {relative_text}")

    if checked == 0 and not errors:
        errors.append("checksum manifest contains no file entries")
    return checked, errors


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("invalid PNG signature")
    if header[12:16] != b"IHDR":
        raise ValueError("PNG has no leading IHDR chunk")
    return struct.unpack(">II", header[16:24])


def _tiff_values(handle, endian: str, field_type: int, count: int, raw: bytes) -> list[float]:
    formats = {3: ("H", 2), 4: ("I", 4), 5: ("II", 8)}
    if field_type not in formats:
        return []
    format_code, item_size = formats[field_type]
    total_size = item_size * count
    if total_size <= 4:
        payload = raw[:total_size]
    else:
        offset = struct.unpack(endian + "I", raw)[0]
        position = handle.tell()
        handle.seek(offset)
        payload = handle.read(total_size)
        handle.seek(position)
    if len(payload) != total_size:
        raise ValueError("truncated TIFF tag value")

    values: list[float] = []
    for index in range(count):
        start = index * item_size
        if field_type == 5:
            numerator, denominator = struct.unpack(
                endian + format_code, payload[start : start + item_size]
            )
            values.append(numerator / denominator if denominator else 0.0)
        else:
            values.append(
                float(
                    struct.unpack(
                        endian + format_code, payload[start : start + item_size]
                    )[0]
                )
            )
    return values


def tiff_metadata(path: Path) -> tuple[tuple[int, int], tuple[float, float]]:
    """Read width, height and normalized DPI from a baseline TIFF IFD."""
    with path.open("rb") as handle:
        header = handle.read(8)
        if len(header) != 8 or header[:2] not in (b"II", b"MM"):
            raise ValueError("invalid TIFF byte-order marker")
        endian = "<" if header[:2] == b"II" else ">"
        if struct.unpack(endian + "H", header[2:4])[0] != 42:
            raise ValueError("invalid TIFF magic")
        handle.seek(struct.unpack(endian + "I", header[4:8])[0])
        count_raw = handle.read(2)
        if len(count_raw) != 2:
            raise ValueError("truncated TIFF IFD")
        entry_count = struct.unpack(endian + "H", count_raw)[0]
        tags: dict[int, list[float]] = {}
        for _ in range(entry_count):
            entry = handle.read(12)
            if len(entry) != 12:
                raise ValueError("truncated TIFF IFD entry")
            tag, field_type, count = struct.unpack(endian + "HHI", entry[:8])
            if tag in (256, 257, 282, 283, 296):
                tags[tag] = _tiff_values(handle, endian, field_type, count, entry[8:12])

    try:
        width = int(tags[256][0])
        height = int(tags[257][0])
    except (KeyError, IndexError) as exc:
        raise ValueError("TIFF is missing width or height") from exc
    unit = int(tags.get(296, [2])[0])
    x_resolution = tags.get(282, [0.0])[0]
    y_resolution = tags.get(283, [0.0])[0]
    if unit == 3:  # pixels per centimetre
        x_resolution *= 2.54
        y_resolution *= 2.54
    elif unit != 2:
        x_resolution = y_resolution = 0.0
    return (width, height), (x_resolution, y_resolution)


def svg_metadata(path: Path) -> tuple[int, int]:
    root = ET.parse(path).getroot()
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError("root element is not SVG")
    text_nodes = 0
    image_nodes = 0
    for element in root.iter():
        local_name = element.tag.rsplit("}", 1)[-1]
        text_nodes += local_name == "text"
        image_nodes += local_name == "image"
    return text_nodes, image_nodes


def pdf_raster_image_count(path: Path) -> int:
    """Count PDF raster objects with pdfimages, falling back to object markers."""
    pdfimages = shutil.which("pdfimages")
    if pdfimages:
        completed = subprocess.run(
            [pdfimages, "-list", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or "unknown pdfimages error"
            raise ValueError(f"pdfimages failed: {detail}")
        return sum(
            bool(re.match(r"^\s*\d+\s+\d+\s+", line))
            for line in completed.stdout.splitlines()
        )
    return len(re.findall(rb"/Subtype\s*/Image\b", path.read_bytes()))


def _zero_like(value: object) -> bool:
    return value == 0 or value == [] or value == {}


def check_pdfs(paper: Path, report: Report) -> None:
    for name, (minimum, maximum) in PDF_SPECS.items():
        path = paper / name
        if not path.is_file():
            report.add(False, f"PDF {name}", "missing")
            continue
        if path.stat().st_size == 0 or not path.read_bytes()[:5] == b"%PDF-":
            report.add(False, f"PDF {name}", "empty or invalid PDF signature")
            continue
        try:
            pages = pdf_page_count(path)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            report.add(False, f"PDF {name}", str(exc))
            continue
        passed = minimum <= pages <= maximum
        expected = f"{minimum}" if minimum == maximum else f"{minimum}--{maximum}"
        report.add(passed, f"PDF {name}", f"{pages} page(s); expected {expected}")


def check_logs(paper: Path, report: Report) -> None:
    for name in LOG_NAMES:
        path = paper / name
        if not path.is_file() or path.stat().st_size == 0:
            report.add(False, f"LaTeX log {name}", "missing or empty")
            continue
        issues = find_latex_issues(path.read_text(encoding="utf-8", errors="replace"))
        if issues:
            preview = "; ".join(f"L{number}: {line}" for number, line in issues[:3])
            if len(issues) > 3:
                preview += f"; +{len(issues) - 3} more"
            report.add(False, f"LaTeX log {name}", preview)
        else:
            report.add(True, f"LaTeX log {name}", "no critical diagnostics")


def check_checksums(paper: Path, report: Report) -> None:
    for name in CHECKSUM_DIRS:
        count, errors = verify_checksum_root(paper / name)
        if errors:
            report.add(False, f"Checksums paper/{name}", "; ".join(errors[:5]))
        else:
            report.add(True, f"Checksums paper/{name}", f"{count} file(s) verified")


def check_figure(stem: str, figures: Path, report: Report) -> None:
    paths = {extension: figures / f"{stem}.{extension}" for extension in FIGURE_EXTENSIONS}
    missing = [path.name for path in paths.values() if not path.is_file() or path.stat().st_size == 0]
    if missing:
        report.add(False, f"Figure {stem}", "missing/empty: " + ", ".join(missing))
        return

    errors: list[str] = []
    try:
        if paths["pdf"].read_bytes()[:5] != b"%PDF-":
            errors.append("invalid PDF signature")
        elif pdf_page_count(paths["pdf"]) != 1:
            errors.append("figure PDF is not one page")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        errors.append(f"PDF: {exc}")

    try:
        png_size = png_dimensions(paths["png"])
    except (OSError, ValueError, struct.error) as exc:
        errors.append(f"PNG: {exc}")
        png_size = (0, 0)
    try:
        tiff_size, tiff_dpi = tiff_metadata(paths["tiff"])
    except (OSError, ValueError, struct.error) as exc:
        errors.append(f"TIFF: {exc}")
        tiff_size, tiff_dpi = (0, 0), (0.0, 0.0)
    try:
        svg_text_nodes, svg_image_nodes = svg_metadata(paths["svg"])
        if svg_text_nodes < 1:
            errors.append("SVG contains no editable text nodes")
    except (OSError, ET.ParseError, ValueError) as exc:
        errors.append(f"SVG: {exc}")
        svg_text_nodes, svg_image_nodes = 0, 0

    qa_path = figures / f"{stem}_qa.json"
    try:
        qa = json.loads(qa_path.read_text(encoding="utf-8"))
        if not isinstance(qa, dict):
            raise ValueError("top-level QA value is not an object")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"QA JSON: {exc}")
        qa = {}

    expected_exports = set(FIGURE_EXTENSIONS)
    if set(qa.get("exports", [])) != expected_exports:
        errors.append("QA exports do not list SVG/PDF/TIFF/PNG exactly")
    if qa.get("vector_primary") is not True:
        errors.append("QA does not declare a vector primary")
    if qa.get("pdf_bytes") != paths["pdf"].stat().st_size:
        errors.append("QA PDF byte count does not match the artifact")
    if qa.get("svg_editable_text_nodes") != svg_text_nodes:
        errors.append("QA SVG text-node count does not match the artifact")
    if qa.get("png_preview_pixels") != list(png_size):
        errors.append("QA PNG dimensions do not match the artifact")
    if qa.get("tiff_pixels") != list(tiff_size):
        errors.append("QA TIFF dimensions do not match the artifact")

    target_dpi = float(qa.get("tiff_target_dpi", 0))
    qa_dpi = qa.get("tiff_dpi")
    if target_dpi < 600:
        errors.append("QA TIFF target is below 600 dpi")
    if not (
        isinstance(qa_dpi, list)
        and len(qa_dpi) == 2
        and all(abs(float(qa_dpi[i]) - tiff_dpi[i]) <= 0.5 for i in range(2))
        and all(value + 0.5 >= target_dpi for value in tiff_dpi)
    ):
        errors.append("TIFF DPI is missing, below target, or inconsistent with QA")

    minimum_font = float(qa.get("minimum_font_pt", 0))
    minimum_target = float(qa.get("minimum_font_target_pt", 0))
    if minimum_target <= 0 or minimum_font < minimum_target:
        errors.append("minimum font is below the QA target")

    zero_fields: Iterable[str]
    true_fields: Iterable[str]
    if stem.startswith("results_"):
        zero_fields = (
            "svg_embedded_image_nodes",
            "pdf_raster_images",
            "text_out_of_canvas",
            "cross_panel_text_overlaps",
            "legend_title_overlaps",
            "overlapping_annotation_pairs",
            "overlapping_tick_groups",
            "broken_axes",
            "pdf_unembedded_fonts",
        )
        true_fields = (
            "required_panel_context_present",
            "zero_or_reference_anchored_quantitative_axes",
        )
        if svg_image_nodes:
            errors.append(f"results SVG embeds {svg_image_nodes} raster image(s)")
        try:
            pdf_images = pdf_raster_image_count(paths["pdf"])
            if pdf_images:
                errors.append(f"results PDF embeds {pdf_images} raster image(s)")
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            errors.append(f"PDF vector audit: {exc}")
        if qa.get("svg_embedded_image_nodes") != svg_image_nodes:
            errors.append("QA SVG image-node count does not match the artifact")
        if int(qa.get("pdf_embedded_fonts", 0)) < 1:
            errors.append("QA reports no embedded PDF fonts")
    else:
        zero_fields = (
            "text_out_of_canvas",
            "text_out_of_box",
            "text_overlap_pairs",
            "arrow_box_crossings",
        )
        true_fields = (
            "required_terminology_present",
            "stage_arrows_consistent",
            "orange_numbering_consistent",
        )
        if qa.get("stage_sequence") != ["Base", "Global", "CG", "Remask", "Pair"]:
            errors.append("scheduler stage sequence is missing or inconsistent")

    for field in zero_fields:
        if field not in qa or not _zero_like(qa[field]):
            errors.append(f"QA field {field!r} is not zero/empty")
    for field in true_fields:
        if qa.get(field) is not True:
            errors.append(f"QA field {field!r} is not true")

    if errors:
        report.add(False, f"Figure {stem}", "; ".join(errors))
    else:
        vector_note = ", no raster objects" if stem.startswith("results_") else ""
        report.add(
            True,
            f"Figure {stem}",
            f"SVG/PDF/TIFF/PNG + QA valid; {tiff_size[0]}x{tiff_size[1]} @ "
            f"{tiff_dpi[0]:.0f} dpi{vector_note}",
        )


def check_raster_figure(name: str, figures: Path, report: Report) -> None:
    path = figures / name
    if not path.is_file() or path.stat().st_size == 0:
        report.add(False, f"Figure {name}", "missing or empty")
        return
    try:
        width, height = png_dimensions(path)
    except (OSError, ValueError, struct.error) as exc:
        report.add(False, f"Figure {name}", f"invalid PNG: {exc}")
        return
    passed = width >= 800 and height >= 500
    detail = f"valid PNG; {width}x{height} px (minimum 800x500)"
    report.add(passed, f"Figure {name}", detail)


def check_figures(paper: Path, report: Report) -> None:
    figures = paper / "figures"
    for name in RASTER_FIGURES:
        check_raster_figure(name, figures, report)
    for stem in FIGURE_STEMS:
        check_figure(stem, figures, report)


def check_stale_artifacts(paper: Path, report: Report) -> None:
    stale = sorted(
        path.relative_to(paper).as_posix()
        for path in paper.rglob("*")
        if path.is_file() and is_stale_artifact(path)
    )
    if stale:
        report.add(False, "Paper artifact hygiene", "stale files: " + ", ".join(stale))
    else:
        report.add(True, "Paper artifact hygiene", "no .orig/.rej/temp/editor backups")


def run(root: Path) -> Report:
    report = Report()
    paper = root.resolve() / "paper"
    if not paper.is_dir():
        report.add(False, "Paper directory", f"missing: {paper}")
        return report
    check_pdfs(paper, report)
    check_logs(paper, report)
    check_checksums(paper, report)
    check_figures(paper, report)
    check_stale_artifacts(paper, report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=default_root,
        help="repository root (default: inferred from this script)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run(args.root)
    report.print()
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
