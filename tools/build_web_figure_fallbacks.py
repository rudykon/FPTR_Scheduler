#!/usr/bin/env python3
"""Audit web figures and describe the checked-in PNG fallback honestly."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

FIGURES = (
    ("web_stage_gain", "Ordered cumulative stage gain"),
    ("web_scenario_gain", "Scenario-wise Full gain"),
    ("web_budget_quality", "Budget and quality trade-off"),
    ("web_runtime_ecdf", "Runtime empirical cumulative distribution"),
    ("web_cg_stress", "Compatibility-group stress test"),
    ("web_optimality_gap", "Exact optimality gaps"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_size(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    if payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    return struct.unpack(">II", payload[16:24])


def validate_native_svg(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if re.search(r"<(?:[\w-]+:)?image\b", source, re.IGNORECASE):
        raise ValueError(f"{path} embeds a raster image")
    if not re.search(r"<(?:[\w-]+:)?(?:path|line|circle|text)\b", source, re.IGNORECASE):
        raise ValueError(f"{path} contains no native vector drawing elements")


def fallback_manifest(images_dir: Path) -> dict[str, object]:
    records: dict[str, object] = {}
    for name, _title in FIGURES:
        png = images_dir / f"{name}.png"
        width, height = png_size(png)
        records[name] = {
            "png": f"../images/{png.name}",
            "png_sha256": sha256(png),
            "width": width,
            "height": height,
        }
    return {
        "schema_version": 2,
        "profile": "audited-png-fallback",
        "native_generator": "python3 experiments/plot_paper_results.py --profile web",
        "fallback_auditor": "python3 tools/build_web_figure_fallbacks.py",
        "note": "The code-only release currently publishes audited legacy PNG exports, which may retain manuscript panel letters. The formal result bundle is required to regenerate panel-label-free, large-type web and mobile assets; no SVG is advertised until it can contain native vector paths and editable text.",
        "pending_artifacts": [
            "panel-label-free native web SVG/PNG",
            "mobile-specific large-type PNG",
        ],
        "figures": records,
    }


def check_native_bundle(images_dir: Path, manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("profile") != "web":
        raise ValueError("native SVG figures require the formal web-profile manifest")
    outputs = manifest.get("outputs", {})
    for name, _title in FIGURES:
        svg = images_dir / f"{name}.svg"
        png = images_dir / f"{name}.png"
        validate_native_svg(svg)
        record = outputs.get(name, {})
        if record.get("svg_sha256") != sha256(svg) or record.get("png_sha256") != sha256(png):
            raise ValueError(f"manifest hashes do not match {name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-dir", type=Path, default=Path("docs/images"))
    parser.add_argument("--manifest", type=Path, default=Path("docs/evidence/figure-manifest.json"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    svg_paths = [args.images_dir / f"{name}.svg" for name, _title in FIGURES]
    native_count = sum(path.is_file() for path in svg_paths)
    if native_count not in (0, len(svg_paths)):
        raise SystemExit("web figures mix PNG-only and SVG states")
    if native_count:
        try:
            check_native_bundle(args.images_dir, args.manifest)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise SystemExit(str(error)) from error
        return

    manifest = fallback_manifest(args.images_dir)
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if args.check and (
        not args.manifest.exists()
        or args.manifest.read_text(encoding="utf-8") != manifest_text
    ):
        raise SystemExit(f"stale web figure manifest: {args.manifest}")
    if args.check:
        return
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(manifest_text, encoding="utf-8")


if __name__ == "__main__":
    main()
