#!/usr/bin/env python3
"""Convert the Matplotlib-style paper SVG subset to a vector PDF.

The converter intentionally supports only the primitives emitted by the
results figure: absolute M/L/C/Z paths, ``use`` references, rectangular clip
paths, and text with translate/rotate transforms.  It has no third-party
Python dependency and keeps the PDF free of raster images.
"""

from __future__ import annotations

import argparse
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Mapping


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
TOKEN_RE = re.compile(r"[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_number(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    match = NUMBER_RE.search(value)
    return float(match.group()) if match else default


def parse_style(value: str | None) -> dict[str, str]:
    style: dict[str, str] = {}
    for item in (value or "").split(";"):
        if ":" not in item:
            continue
        name, setting = item.split(":", 1)
        style[name.strip()] = setting.strip()
    return style


def parse_color(value: str | None) -> tuple[float, float, float] | None:
    if value is None:
        return None
    value = value.strip().lower()
    if value in {"none", "transparent"}:
        return None
    names = {"black": "#000000", "white": "#ffffff"}
    value = names.get(value, value)
    if re.fullmatch(r"#[0-9a-f]{3}", value):
        value = "#" + "".join(character * 2 for character in value[1:])
    if not re.fullmatch(r"#[0-9a-f]{6}", value):
        return (0.0, 0.0, 0.0)
    return tuple(int(value[index : index + 2], 16) / 255.0 for index in (1, 3, 5))


def blend_white(
    color: tuple[float, float, float], alpha: float
) -> tuple[float, float, float]:
    alpha = max(0.0, min(1.0, alpha))
    return tuple(alpha * component + (1.0 - alpha) for component in color)


def pdf_number(value: float) -> str:
    if abs(value) < 5e-8:
        value = 0.0
    return f"{value:.5f}".rstrip("0").rstrip(".") or "0"


def path_to_pdf(path_data: str, page_height: float, dx: float = 0.0, dy: float = 0.0) -> str:
    tokens = TOKEN_RE.findall(path_data)
    output: list[str] = []
    index = 0
    command = ""
    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            if command in {"z", "Z"}:
                output.append("h")
                command = ""
            continue
        if command == "M":
            x, y = float(tokens[index]) + dx, float(tokens[index + 1]) + dy
            output.append(f"{pdf_number(x)} {pdf_number(page_height - y)} m")
            index += 2
            command = "L"
        elif command == "L":
            x, y = float(tokens[index]) + dx, float(tokens[index + 1]) + dy
            output.append(f"{pdf_number(x)} {pdf_number(page_height - y)} l")
            index += 2
        elif command == "C":
            values = [float(tokens[index + offset]) for offset in range(6)]
            x1, y1, x2, y2, x3, y3 = values
            output.append(
                " ".join(
                    (
                        pdf_number(x1 + dx),
                        pdf_number(page_height - (y1 + dy)),
                        pdf_number(x2 + dx),
                        pdf_number(page_height - (y2 + dy)),
                        pdf_number(x3 + dx),
                        pdf_number(page_height - (y3 + dy)),
                        "c",
                    )
                )
            )
            index += 6
        else:
            raise ValueError(f"unsupported SVG path command {command!r}")
    return "\n".join(output)


def path_bounds(path_data: str) -> tuple[float, float, float, float]:
    tokens = TOKEN_RE.findall(path_data)
    coordinates: list[tuple[float, float]] = []
    index = 0
    command = ""
    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            continue
        if command in {"M", "L"}:
            coordinates.append((float(tokens[index]), float(tokens[index + 1])))
            index += 2
            if command == "M":
                command = "L"
        elif command == "C":
            for offset in (0, 2, 4):
                coordinates.append(
                    (float(tokens[index + offset]), float(tokens[index + offset + 1]))
                )
            index += 6
        elif command in {"z", "Z"}:
            command = ""
        else:
            raise ValueError(f"unsupported path command in clip path: {command!r}")
    xs = [point[0] for point in coordinates]
    ys = [point[1] for point in coordinates]
    return min(xs), min(ys), max(xs), max(ys)


def style_pdf_commands(style: Mapping[str, str]) -> tuple[list[str], bool, bool]:
    commands: list[str] = []
    fill = parse_color(style.get("fill"))
    stroke = parse_color(style.get("stroke"))
    opacity = parse_number(style.get("opacity"), 1.0)
    if fill is not None:
        fill_alpha = opacity * parse_number(style.get("fill-opacity"), 1.0)
        fill = blend_white(fill, fill_alpha)
        commands.append(" ".join(pdf_number(value) for value in fill) + " rg")
    if stroke is not None:
        stroke_alpha = opacity * parse_number(style.get("stroke-opacity"), 1.0)
        stroke = blend_white(stroke, stroke_alpha)
        commands.append(" ".join(pdf_number(value) for value in stroke) + " RG")
        commands.append(f"{pdf_number(parse_number(style.get('stroke-width'), 1.0))} w")
        dash = style.get("stroke-dasharray")
        if dash and dash != "none":
            values = [parse_number(item) for item in re.split(r"[ ,]+", dash.strip()) if item]
            commands.append("[" + " ".join(pdf_number(value) for value in values) + "] 0 d")
        else:
            commands.append("[] 0 d")
        commands.append("1 j" if style.get("stroke-linejoin") == "round" else "0 j")
        commands.append("1 J" if style.get("stroke-linecap") == "round" else "0 J")
    return commands, fill is not None, stroke is not None


def approximate_text_width(text: str, font_size: float, bold: bool) -> float:
    total = 0.0
    for character in text:
        if character == " ":
            factor = 0.278
        elif character in "ilI.,:;'!|":
            factor = 0.26
        elif character in "MW@%":
            factor = 0.84
        elif character in "mw":
            factor = 0.76
        elif character.isdigit():
            factor = 0.556
        elif character.isupper():
            factor = 0.66
        elif character in "-+/<>=()[]":
            factor = 0.48
        else:
            factor = 0.52
        total += factor
    return font_size * total * (1.02 if bold else 1.0)


def ascii_text(text: str) -> str:
    replacements = {
        "Δ": "",
        "★": "*",
        "◇": "<>",
        "–": "-",
        "—": "-",
        "−": "-",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text.encode("ascii", "ignore").decode("ascii")


def escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def parse_text_transform(element: ET.Element, page_height: float) -> tuple[float, float, float]:
    transform = element.get("transform", "").strip()
    x = parse_number(element.get("x"))
    y = parse_number(element.get("y"))
    angle = 0.0
    translate = re.search(
        r"translate\(\s*([-+0-9.eE]+)[ ,]+([-+0-9.eE]+)\s*\)", transform
    )
    if translate:
        x = float(translate.group(1))
        y = float(translate.group(2))
    rotate = re.search(r"rotate\(\s*([-+0-9.eE]+)", transform)
    if rotate:
        angle = -float(rotate.group(1))
    return x, page_height - y, angle


def text_to_pdf(element: ET.Element, page_height: float) -> str:
    raw_text = "".join(element.itertext())
    text = ascii_text(raw_text)
    style = parse_style(element.get("style"))
    font_size = parse_number(style.get("font-size"), 6.0)
    bold = style.get("font-weight") in {"bold", "700", "800", "900"}
    font_name = "F2" if bold else "F1"
    x, y, angle = parse_text_transform(element, page_height)
    anchor = style.get("text-anchor", "start")
    width = approximate_text_width(text, font_size, bold)
    offset = 0.0
    if anchor == "middle":
        offset = -0.5 * width
    elif anchor == "end":
        offset = -width
    color = parse_color(style.get("fill")) or (0.0, 0.0, 0.0)
    alpha = parse_number(style.get("opacity"), 1.0)
    color = blend_white(color, alpha)
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    matrix = " ".join(
        pdf_number(value) for value in (cosine, sine, -sine, cosine, x, y)
    )
    return "\n".join(
        (
            "BT",
            f"/{font_name} {pdf_number(font_size)} Tf",
            " ".join(pdf_number(value) for value in color) + " rg",
            f"{matrix} Tm",
            f"{pdf_number(offset)} 0 Td",
            f"({escape_pdf_text(text)}) Tj",
            "ET",
        )
    )


def clip_commands(
    clip_id: str | None,
    clips: Mapping[str, tuple[float, float, float, float]],
    page_height: float,
) -> list[str]:
    if not clip_id or clip_id not in clips:
        return []
    x0, y0, x1, y1 = clips[clip_id]
    return [
        "q",
        (
            f"{pdf_number(x0)} {pdf_number(page_height - y1)} "
            f"{pdf_number(x1 - x0)} {pdf_number(y1 - y0)} re W n"
        ),
    ]


def clip_id_from(value: str | None) -> str | None:
    if not value:
        return None
    match = re.fullmatch(r"url\(#([^)]+)\)", value.strip())
    return match.group(1) if match else None


def draw_path(
    path_data: str,
    style: Mapping[str, str],
    page_height: float,
    *,
    dx: float = 0.0,
    dy: float = 0.0,
    clip_id: str | None = None,
    clips: Mapping[str, tuple[float, float, float, float]],
) -> str:
    prefix = clip_commands(clip_id, clips, page_height)
    style_commands, has_fill, has_stroke = style_pdf_commands(style)
    paint = "B" if has_fill and has_stroke else "f" if has_fill else "S" if has_stroke else "n"
    commands = prefix + style_commands + [path_to_pdf(path_data, page_height, dx, dy), paint]
    if prefix:
        commands.append("Q")
    return "\n".join(commands)


def build_content(root: ET.Element, page_height: float, *, include_text: bool) -> str:
    path_defs = {
        element.get("id"): element
        for element in root.iter()
        if local_name(element.tag) == "path" and element.get("id")
    }
    clips: dict[str, tuple[float, float, float, float]] = {}
    for element in root.iter():
        if local_name(element.tag) != "clipPath" or not element.get("id"):
            continue
        path = next((child for child in element if local_name(child.tag) == "path"), None)
        if path is not None:
            clips[element.get("id", "")] = path_bounds(path.get("d", ""))

    content: list[str] = ["1 0 0 1 0 0 cm"]

    def walk(element: ET.Element, inherited_clip: str | None = None) -> None:
        name = local_name(element.tag)
        if name in {"metadata", "defs", "clipPath", "style"}:
            return
        current_clip = clip_id_from(element.get("clip-path")) or inherited_clip
        if name == "path" and element.get("d"):
            content.append(
                draw_path(
                    element.get("d", ""),
                    parse_style(element.get("style")),
                    page_height,
                    clip_id=current_clip,
                    clips=clips,
                )
            )
            return
        if name == "use":
            href = element.get(f"{{{XLINK_NS}}}href") or element.get("href")
            reference = path_defs.get(href[1:] if href and href.startswith("#") else "")
            if reference is not None:
                style = parse_style(reference.get("style"))
                style.update(parse_style(element.get("style")))
                content.append(
                    draw_path(
                        reference.get("d", ""),
                        style,
                        page_height,
                        dx=parse_number(element.get("x")),
                        dy=parse_number(element.get("y")),
                        clip_id=current_clip,
                        clips=clips,
                    )
                )
            return
        if name == "text":
            if include_text:
                content.append(text_to_pdf(element, page_height))
            return
        for child in element:
            walk(child, current_clip)

    walk(root)
    return "\n".join(content) + "\n"


def make_pdf(
    width: float, height: float, content: bytes, *, include_fonts: bool
) -> bytes:
    resources = (
        "/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> "
        if include_fonts
        else "/Resources << >> "
    )
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {pdf_number(width)} {pdf_number(height)}] "
            + resources
            + "/Contents 4 0 R >>"
        ).encode("ascii"),
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"endstream",
    ]
    if include_fonts:
        objects.extend(
            (
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
            )
        )
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def convert(
    input_path: Path, output_path: Path, *, include_text: bool = True
) -> dict[str, object]:
    root = ET.parse(input_path).getroot()
    width = parse_number(root.get("width"))
    height = parse_number(root.get("height"))
    view_box = [float(value) for value in (root.get("viewBox") or "").split()]
    if len(view_box) == 4:
        width, height = view_box[2], view_box[3]
    if width <= 0 or height <= 0:
        raise ValueError("SVG has no positive width and height")
    content = build_content(root, height, include_text=include_text).encode("latin-1")
    payload = make_pdf(width, height, content, include_fonts=include_text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(payload)
    if output_path.stat().st_size < 10_000:
        raise RuntimeError("generated PDF is unexpectedly small")
    return {
        "width_pt": width,
        "height_pt": height,
        "content_bytes": len(content),
        "pdf_bytes": len(payload),
        "text_included": include_text,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--omit-text", action="store_true")
    args = parser.parse_args()
    summary = convert(args.input, args.output, include_text=not args.omit_text)
    print(" ".join(f"{key}={value}" for key, value in summary.items()))


if __name__ == "__main__":
    main()
