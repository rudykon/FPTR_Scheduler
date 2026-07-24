#!/usr/bin/env python3
"""Generate a XeLaTeX text overlay for a vector-only paper-figure PDF."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from experiments.svg_to_vector_pdf import (
        local_name,
        parse_color,
        parse_number,
        parse_style,
        parse_text_transform,
    )
except ModuleNotFoundError:
    from svg_to_vector_pdf import (  # type: ignore[no-redef]
        local_name,
        parse_color,
        parse_number,
        parse_style,
        parse_text_transform,
    )


def tex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "%": r"\%",
        "#": r"\#",
        "$": r"\$",
        "&": r"\&",
        "_": r"\_",
        "^": r"\textasciicircum{}",
        "~": r"\textasciitilde{}",
    }
    return "".join(replacements.get(character, character) for character in text)


def color_name(color: tuple[float, float, float]) -> str:
    return "c" + "".join(f"{round(component * 255):02x}" for component in color)


def generate_tex(svg_path: Path, base_pdf: Path, output_path: Path) -> dict[str, object]:
    root = ET.parse(svg_path).getroot()
    view_box = [float(value) for value in (root.get("viewBox") or "").split()]
    if len(view_box) == 4:
        width, height = view_box[2], view_box[3]
    else:
        width = parse_number(root.get("width"))
        height = parse_number(root.get("height"))
    if width <= 0 or height <= 0:
        raise ValueError("SVG has no positive dimensions")

    text_elements = [element for element in root.iter() if local_name(element.tag) == "text"]
    colors = {
        parse_color(parse_style(element.get("style")).get("fill")) or (0.0, 0.0, 0.0)
        for element in text_elements
    }
    color_definitions = [
        (
            f"\\definecolor{{{color_name(color)}}}{{RGB}}"
            f"{{{round(color[0] * 255)},{round(color[1] * 255)},{round(color[2] * 255)}}}"
        )
        for color in sorted(colors)
    ]

    nodes: list[str] = []
    anchor_map = {"start": "base west", "middle": "base", "end": "base east"}
    for element in text_elements:
        text = "".join(element.itertext())
        style = parse_style(element.get("style"))
        font_size = parse_number(style.get("font-size"), 6.0)
        leading = max(font_size * 1.18, font_size + 0.8)
        bold = style.get("font-weight") in {"bold", "700", "800", "900"}
        color = parse_color(style.get("fill")) or (0.0, 0.0, 0.0)
        x, y_pdf, angle = parse_text_transform(element, height)
        y = height - y_pdf
        anchor = anchor_map.get(style.get("text-anchor", "start"), "base west")
        font_commands = (
            f"\\fontsize{{{font_size:.3f}bp}}{{{leading:.3f}bp}}"
            "\\selectfont\\sffamily"
            + ("\\bfseries" if bold else "")
        )
        nodes.append(
            "\\node["
            f"anchor={anchor},inner sep=0pt,outer sep=0pt,"
            f"rotate={angle:.5f},text={color_name(color)},"
            f"font={{{font_commands}}}"
            "] at (["
            f"xshift={x:.5f}bp,yshift=-{y:.5f}bp"
            "]current page.north west) {"
            + tex_escape(text)
            + "};"
        )

    document = "\n".join(
        [
            r"\documentclass{article}",
            rf"\usepackage[paperwidth={width:.5f}bp,paperheight={height:.5f}bp,margin=0pt]{{geometry}}",
            r"\usepackage{fontspec}",
            r"\usepackage{xcolor}",
            r"\usepackage{graphicx}",
            r"\usepackage{tikz}",
            r"\setsansfont{Liberation Sans}",
            r"\pagestyle{empty}",
            *color_definitions,
            r"\begin{document}",
            r"\thispagestyle{empty}",
            r"\begin{tikzpicture}[remember picture,overlay]",
            (
                r"\node[anchor=north west,inner sep=0pt,outer sep=0pt] "
                r"at (current page.north west) {"
                rf"\includegraphics[width={width:.5f}bp,height={height:.5f}bp]"
                rf"{{\detokenize{{{base_pdf.resolve().as_posix()}}}}}"
                r"};"
            ),
            *nodes,
            r"\end{tikzpicture}",
            r"\null",
            r"\end{document}",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    if len(nodes) < 100:
        raise RuntimeError("overlay contains too few text nodes")
    return {
        "width_pt": width,
        "height_pt": height,
        "text_nodes": len(nodes),
        "colors": len(colors),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg", type=Path, required=True)
    parser.add_argument("--base-pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = generate_tex(args.svg, args.base_pdf, args.output)
    print(" ".join(f"{key}={value}" for key, value in summary.items()))


if __name__ == "__main__":
    main()
