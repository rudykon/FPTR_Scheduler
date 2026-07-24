#!/usr/bin/env python3
"""Apply the restrained reference style to an existing results SVG.

This dependency-free fallback is useful on release machines that do not have
Matplotlib installed.  The quantitative geometry is left untouched: only
typography, strokes, grid opacity, panel-label placement, and concise wording
are changed.  The normal data-to-figure path remains
``experiments/plot_paper_results.py``.
"""

from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path


SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
DC = "http://purl.org/dc/elements/1.1/"
CC = "http://creativecommons.org/ns#"

for prefix, uri in (("", SVG), ("xlink", XLINK), ("rdf", RDF), ("dc", DC), ("cc", CC)):
    ET.register_namespace(prefix, uri)


FONT_SIZE_MAP = {
    "6.1px": "5.25px",
    "6px": "4.8px",
    "6.2px": "5.55px",
    "7.4px": "6.45px",
}

STROKE_WIDTH_MAP = {
    "0.3": "0.24",
    "0.35": "0.30",
    "0.45": "0.34",
    "0.48": "0.36",
    "0.55": "0.42",
    "0.56": "0.42",
    "0.6": "0.45",
    "0.62": "0.46",
    "0.65": "0.46",
    "0.7": "0.50",
    "0.72": "0.52",
    "0.78": "0.56",
    "0.8": "0.56",
    "0.84": "0.64",
    "0.88": "0.68",
    "0.92": "0.68",
    "0.94": "0.68",
}

TEXT_MAP = {
    "n=150; fixed order": "n = 150; median of 5",
    "5-run median; losses=0": "fixed order; losses = 0",
    "Ordered stage gains": "Ordered stage gain",
    "Full gain by scenario": "Scenario-wise Full gain",
    "Budget trade-off; labels = wall p95": "Budget trade-off",
    "CG-size stress (coverage co-varies)": "CG-size stress",
    "Exact-suite gaps (11 core + 1 wider)": "Exact gaps (11 core + 1 wider)",
    "★ wider": "* wider",
    "◇ mean": "mean",
}

PANEL_LABEL_X = {
    "a": "18.70",
    "b": "207.35",
    "c": "18.70",
    "d": "194.10",
    "e": "18.70",
    "f": "194.10",
}


def parse_style(value: str) -> list[tuple[str, str]]:
    declarations: list[tuple[str, str]] = []
    for item in value.split(";"):
        item = item.strip()
        if not item or ":" not in item:
            continue
        name, setting = item.split(":", 1)
        declarations.append((name.strip(), setting.strip()))
    return declarations


def format_style(declarations: list[tuple[str, str]]) -> str:
    return "; ".join(f"{name}: {value}" for name, value in declarations)


def restyle(input_path: Path, output_path: Path) -> dict[str, object]:
    root = ET.parse(input_path).getroot()
    if not root.tag.endswith("svg"):
        raise ValueError(f"not an SVG root: {root.tag}")

    changed_fonts = 0
    changed_strokes = 0
    changed_text = 0
    visible_text = 0

    for element in root.iter():
        style_value = element.get("style")
        if style_value:
            declarations = parse_style(style_value)
            style = dict(declarations)
            rewritten: list[tuple[str, str]] = []
            for name, value in declarations:
                if name == "font-size" and value in FONT_SIZE_MAP:
                    value = FONT_SIZE_MAP[value]
                    changed_fonts += 1
                elif name == "stroke-width" and value in STROKE_WIDTH_MAP:
                    value = STROKE_WIDTH_MAP[value]
                    changed_strokes += 1
                elif (
                    name == "stroke-opacity"
                    and style.get("stroke", "").lower() == "#d0d0d0"
                    and value == "0.68"
                ):
                    value = "0.56"
                rewritten.append((name, value))
            element.set("style", format_style(rewritten))

        if element.tag.endswith("path"):
            path_data = element.get("d", "")
            style = element.get("style", "").lower()
            if "stroke: #2f2f2f" in style and "1.9" in path_data:
                path_data = re.sub(r"(?<![0-9.])-1\.9(?![0-9.])", "-1.45", path_data)
                path_data = re.sub(r"(?<![0-9.])1\.9(?![0-9.])", "1.45", path_data)
                element.set("d", path_data)

        if element.tag.endswith("text"):
            visible_text += 1
            content = "".join(element.itertext())
            if content in TEXT_MAP and len(element) == 0:
                element.text = TEXT_MAP[content]
                content = element.text
                changed_text += 1
            elif content.startswith("Δ+") and len(element) == 0:
                element.text = content[1:]
                content = element.text
                changed_text += 1
            if content in PANEL_LABEL_X and "font-weight: 700" in element.get("style", ""):
                element.set("x", PANEL_LABEL_X[content])

    axes_by_id = {
        element.get("id"): element
        for element in root.iter()
        if element.tag.endswith("g") and element.get("id")
    }
    note_style = (
        "font-size: 4.8px; font-family: 'Arial', 'DejaVu Sans', "
        "'Liberation Sans', sans-serif; fill: #707070"
    )
    note_specs = (
        ("axes_3", "restyle_note_c", "162.8", "127.6", "end", "labels: wall p95 (ms)"),
        ("axes_5", "restyle_note_e", "41.5", "223.6", "start", "coverage co-varies"),
    )
    for axes_id, note_id, x, y, anchor, content in note_specs:
        axes = axes_by_id.get(axes_id)
        if axes is None or any(child.get("id") == note_id for child in axes):
            continue
        group = ET.SubElement(axes, f"{{{SVG}}}g", {"id": note_id})
        text_element = ET.SubElement(
            group,
            f"{{{SVG}}}text",
            {
                "x": x,
                "y": y,
                "transform": f"rotate(-0 {x} {y})",
                "style": note_style + f"; text-anchor: {anchor}",
            },
        )
        text_element.text = content
        visible_text += 1

    root.set("data-pragmatic-style", "reference-v2")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space=" ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)

    reparsed = ET.parse(output_path).getroot()
    font_sizes = []
    for element in reparsed.iter():
        if not element.tag.endswith("text"):
            continue
        match = re.search(r"font-size:\s*([0-9.]+)px", element.get("style", ""))
        if match:
            font_sizes.append(float(match.group(1)))
    if visible_text < 100 or not font_sizes:
        raise RuntimeError("restyled SVG lost expected editable text nodes")
    if min(font_sizes) < 4.8 - 1e-9:
        raise RuntimeError(f"unexpected minimum font size: {min(font_sizes)}")
    return {
        "editable_text_nodes": visible_text,
        "minimum_font_px": min(font_sizes),
        "font_styles_changed": changed_fonts,
        "stroke_styles_changed": changed_strokes,
        "text_labels_changed": changed_text,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = restyle(args.input, args.output)
    print(" ".join(f"{key}={value}" for key, value in summary.items()))


if __name__ == "__main__":
    main()
