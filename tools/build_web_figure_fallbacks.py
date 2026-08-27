#!/usr/bin/env python3
"""Create deterministic SVG fallbacks and a version manifest for web figures."""

from __future__ import annotations

import argparse
import hashlib
import json
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


def svg_text(name: str, title: str, width: int, height: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="{name}-title">\n'
        f'  <title id="{name}-title">{title}</title>\n'
        f'  <image width="{width}" height="{height}" href="{name}.png" xlink:href="{name}.png" />\n'
        '</svg>\n'
    )


def expected(images_dir: Path) -> tuple[dict[Path, str], dict[str, object]]:
    files: dict[Path, str] = {}
    records: dict[str, object] = {}
    for name, title in FIGURES:
        png = images_dir / f"{name}.png"
        width, height = png_size(png)
        svg = images_dir / f"{name}.svg"
        content = svg_text(name, title, width, height)
        files[svg] = content
        records[name] = {
            "png": f"../images/{png.name}",
            "png_sha256": sha256(png),
            "svg": f"../images/{svg.name}",
            "width": width,
            "height": height,
        }
    manifest = {
        "schema_version": 1,
        "profile": "web-fallback",
        "native_generator": "python3 experiments/plot_paper_results.py --profile web",
        "fallback_generator": "python3 tools/build_web_figure_fallbacks.py",
        "note": "The code-only release keeps audited PNG exports and deterministic SVG wrappers. Native web-profile plots are regenerated when the sealed result bundle is supplied.",
        "figures": records,
    }
    return files, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-dir", type=Path, default=Path("docs/images"))
    parser.add_argument("--manifest", type=Path, default=Path("docs/evidence/figure-manifest.json"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files, manifest = expected(args.images_dir)
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        mismatches = [
            str(path)
            for path, content in files.items()
            if not path.exists() or path.read_text(encoding="utf-8") != content
        ]
        if not args.manifest.exists() or args.manifest.read_text(encoding="utf-8") != manifest_text:
            mismatches.append(str(args.manifest))
        if mismatches:
            raise SystemExit("stale web figure artifacts: " + ", ".join(mismatches))
        return
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(manifest_text, encoding="utf-8")


if __name__ == "__main__":
    main()
