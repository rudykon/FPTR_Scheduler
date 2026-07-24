#!/usr/bin/env python3
"""Draw the publication-ready architecture and safety invariant in Figure 1."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from PIL import Image


plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
plt.rcParams["svg.fonttype"] = "none"

FIGURE_WIDTH_IN = 4.80
FIGURE_HEIGHT_IN = 2.35
BODY_FONT_PT = 5.75
HEADER_FONT_PT = 6.6

COLORS = {
    "ink": "#263238",
    "line": "#51636D",
    "white": "#FFFFFF",
    "model_bg": "#F5F8FB",
    "model_fill": "#E8F1FA",
    "model_edge": "#4D789F",
    "base_bg": "#F8F6FC",
    "base_fill": "#EEEAF7",
    "base_edge": "#7161A4",
    "search_bg": "#FFF9F1",
    "search_fill": "#FFF0DE",
    "search_edge": "#B87528",
    "gate_fill": "#F9E7E4",
    "gate_edge": "#B65049",
    "safe_bg": "#F3FAF5",
    "safe_fill": "#E1F2E6",
    "safe_edge": "#378253",
    "deadline_fill": "#FFF4D9",
    "deadline_edge": "#B88326",
    "header": "#334D5C",
}


@dataclass(frozen=True)
class BoxRecord:
    patch: FancyBboxPatch
    texts: tuple[mpl.text.Text, ...]
    role: str


@dataclass(frozen=True)
class ArrowRecord:
    start: tuple[float, float]
    end: tuple[float, float]
    role: str


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.size": BODY_FONT_PT,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.facecolor": "white",
            "savefig.edgecolor": "white",
        }
    )


def add_region(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    facecolor: str,
    edgecolor: str,
    linewidth: float = 0.75,
) -> FancyBboxPatch:
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.006,rounding_size=0.016",
        linewidth=linewidth,
        facecolor=facecolor,
        edgecolor=edgecolor,
        transform=ax.transAxes,
        zorder=0,
    )
    ax.add_patch(patch)
    return patch


def add_section_header(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    label: str,
    *,
    color: str = COLORS["header"],
) -> mpl.text.Text:
    patch = FancyBboxPatch(
        (x, y),
        width,
        0.044,
        boxstyle="round,pad=0.005,rounding_size=0.012",
        linewidth=0,
        facecolor=color,
        transform=ax.transAxes,
        zorder=3,
    )
    ax.add_patch(patch)
    return ax.text(
        x + 0.012,
        y + 0.022,
        label,
        transform=ax.transAxes,
        ha="left",
        va="center",
        fontsize=HEADER_FONT_PT,
        fontweight="bold",
        color=COLORS["white"],
        zorder=4,
    )


def add_text_box(
    ax: plt.Axes,
    registry: list[BoxRecord],
    x: float,
    y: float,
    width: float,
    height: float,
    text: str,
    *,
    facecolor: str,
    edgecolor: str,
    role: str,
    fontsize: float = BODY_FONT_PT,
    weight: str = "normal",
    linewidth: float = 0.8,
    pad: float = 0.005,
    rounding: float = 0.014,
) -> FancyBboxPatch:
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle=f"round,pad={pad},rounding_size={rounding}",
        linewidth=linewidth,
        facecolor=facecolor,
        edgecolor=edgecolor,
        transform=ax.transAxes,
        zorder=2,
    )
    ax.add_patch(patch)
    artist = ax.text(
        x + width / 2,
        y + height / 2,
        text,
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight=weight,
        color=COLORS["ink"],
        linespacing=1.05,
        zorder=3,
    )
    registry.append(BoxRecord(patch, (artist,), role))
    return patch


def add_module_box(
    ax: plt.Axes,
    registry: list[BoxRecord],
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
    body: str,
    *,
    facecolor: str,
    edgecolor: str,
    role: str,
) -> FancyBboxPatch:
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.005,rounding_size=0.014",
        linewidth=0.85,
        facecolor=facecolor,
        edgecolor=edgecolor,
        transform=ax.transAxes,
        zorder=2,
    )
    ax.add_patch(patch)
    title_artist = ax.text(
        x + width / 2,
        y + height - 0.019,
        title,
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=HEADER_FONT_PT,
        fontweight="bold",
        color=edgecolor,
        zorder=3,
    )
    body_artist = ax.text(
        x + width / 2,
        y + height * 0.36,
        body,
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=BODY_FONT_PT,
        color=COLORS["ink"],
        linespacing=1.05,
        zorder=3,
    )
    registry.append(BoxRecord(patch, (title_artist, body_artist), role))
    return patch


def add_arrow(
    ax: plt.Axes,
    arrows: list[ArrowRecord],
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    role: str,
    color: str,
    linewidth: float = 0.9,
) -> None:
    arrow = FancyArrowPatch(
        start,
        end,
        transform=ax.transAxes,
        arrowstyle="-|>",
        mutation_scale=7.0,
        linewidth=linewidth,
        color=color,
        shrinkA=0,
        shrinkB=0,
        zorder=1,
    )
    ax.add_patch(arrow)
    arrows.append(ArrowRecord(start, end, role))


def boxes_intersect_segment(
    start: tuple[float, float],
    end: tuple[float, float],
    records: list[BoxRecord],
) -> list[str]:
    crossed: list[str] = []
    for record in records:
        x, y = record.patch.get_x(), record.patch.get_y()
        width, height = record.patch.get_width(), record.patch.get_height()
        for fraction in (index / 20 for index in range(2, 19)):
            px = start[0] + fraction * (end[0] - start[0])
            py = start[1] + fraction * (end[1] - start[1])
            if x + 0.002 < px < x + width - 0.002 and y + 0.002 < py < y + height - 0.002:
                crossed.append(record.role)
                break
    return crossed


def validate_layout(
    fig: plt.Figure,
    registry: list[BoxRecord],
    arrows: list[ArrowRecord],
) -> dict[str, object]:
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    figure_box = fig.bbox
    visible_text = [
        artist
        for artist in fig.findobj(match=mpl.text.Text)
        if artist.get_visible() and artist.get_text().strip()
    ]

    clipped: list[str] = []
    box_overflow: list[str] = []
    for artist in visible_text:
        box = artist.get_window_extent(renderer)
        if (
            box.x0 < figure_box.x0 - 0.5
            or box.y0 < figure_box.y0 - 0.5
            or box.x1 > figure_box.x1 + 0.5
            or box.y1 > figure_box.y1 + 0.5
        ):
            clipped.append(artist.get_text())

    for record in registry:
        patch_box = record.patch.get_window_extent(renderer)
        for artist in record.texts:
            text_box = artist.get_window_extent(renderer)
            inset = 0.5
            if (
                text_box.x0 < patch_box.x0 + inset
                or text_box.y0 < patch_box.y0 + inset
                or text_box.x1 > patch_box.x1 - inset
                or text_box.y1 > patch_box.y1 - inset
            ):
                box_overflow.append(record.role)

    text_overlaps: list[str] = []
    text_roles = {
        id(artist): record.role
        for record in registry
        for artist in record.texts
    }
    text_boxes = [(artist, artist.get_window_extent(renderer)) for artist in visible_text]
    for index, (left_artist, left_box) in enumerate(text_boxes):
        for right_artist, right_box in text_boxes[index + 1 :]:
            left_role = text_roles.get(id(left_artist))
            right_role = text_roles.get(id(right_artist))
            if left_role is not None and left_role == right_role:
                continue
            overlap_width = min(left_box.x1, right_box.x1) - max(left_box.x0, right_box.x0)
            overlap_height = min(left_box.y1, right_box.y1) - max(left_box.y0, right_box.y0)
            if overlap_width > 0.8 and overlap_height > 0.8:
                text_overlaps.append(
                    f"{left_artist.get_text()!r} / {right_artist.get_text()!r}"
                )

    arrow_crossings: list[str] = []
    for arrow in arrows:
        crossed = boxes_intersect_segment(arrow.start, arrow.end, registry)
        if crossed:
            arrow_crossings.append(f"{arrow.role}: {', '.join(sorted(set(crossed)))}")

    minimum_font = min(artist.get_fontsize() for artist in visible_text)
    all_text = "\n".join(artist.get_text() for artist in visible_text)
    required_phrases = (
        "Fallback",
        "feasible F*",
        "1  Global",
        "2  CG",
        "3  Remask",
        "4  Pair",
        "complete · timely",
        "Reject: keep F*",
        "final validation + serialization",
        "BeamFirst\nseparate",
        "Base + 1–4",
    )
    missing_phrases = [phrase for phrase in required_phrases if phrase not in all_text]

    numbered_stages = {
        "global resource selection": "1  Global",
        "compatibility-group sharing": "2  CG",
        "demand-driven remask": "3  Remask",
        "two-resource refill": "4  Pair",
    }
    numbering_issues: list[str] = []
    records_by_role = {record.role: record for record in registry}
    for role, expected_title in numbered_stages.items():
        record = records_by_role.get(role)
        if record is None:
            numbering_issues.append(f"missing stage box {role}")
            continue
        title = record.texts[0]
        if title.get_text() != expected_title:
            numbering_issues.append(
                f"{role} is labelled {title.get_text()!r}, expected {expected_title!r}"
            )
        if mpl.colors.to_hex(title.get_color()).lower() != COLORS["search_edge"].lower():
            numbering_issues.append(f"{role} number is not orange")

    expected_stage_arrows = (
        "fallback to Base incumbent",
        "Base incumbent to global stage",
        "global to CG stage",
        "CG to remask stage",
        "remask to pair stage",
        "pair stage to commit gate",
        "commit gate to validated output",
    )
    arrow_roles = [arrow.role for arrow in arrows]
    missing_stage_arrows = [
        role for role in expected_stage_arrows if role not in arrow_roles
    ]
    present_indices = [
        arrow_roles.index(role)
        for role in expected_stage_arrows
        if role in arrow_roles
    ]
    stage_arrow_order_valid = (
        not missing_stage_arrows and present_indices == sorted(present_indices)
    )

    issues: list[str] = []
    if clipped:
        issues.append("text outside canvas: " + ", ".join(repr(item) for item in clipped))
    if box_overflow:
        issues.append("text outside box: " + ", ".join(sorted(set(box_overflow))))
    if text_overlaps:
        issues.append("text overlap: " + "; ".join(text_overlaps))
    if arrow_crossings:
        issues.append("arrow crosses box: " + "; ".join(arrow_crossings))
    if minimum_font < BODY_FONT_PT - 1e-6:
        issues.append(f"minimum font is only {minimum_font:.2f} pt")
    if missing_phrases:
        issues.append("missing required terminology: " + ", ".join(missing_phrases))
    if numbering_issues:
        issues.append("stage numbering mismatch: " + "; ".join(numbering_issues))
    if missing_stage_arrows:
        issues.append(
            "missing stage arrows: " + ", ".join(missing_stage_arrows)
        )
    elif not stage_arrow_order_valid:
        issues.append("stage arrows are not registered in Base→Global→CG→Remask→Pair order")
    if issues:
        raise RuntimeError("Layout validation failed: " + " | ".join(issues))

    return {
        "visible_text_items": len(visible_text),
        "boxed_text_items": sum(len(record.texts) for record in registry),
        "minimum_font_pt": minimum_font,
        "text_out_of_canvas": 0,
        "text_out_of_box": 0,
        "text_overlap_pairs": 0,
        "arrow_box_crossings": 0,
        "required_terminology_present": True,
        "stage_sequence": ["Base", "Global", "CG", "Remask", "Pair"],
        "orange_numbering_consistent": True,
        "stage_arrows_consistent": True,
    }


def validate_exports(output: Path) -> dict[str, object]:
    svg_path = output.with_suffix(".svg")
    pdf_path = output.with_suffix(".pdf")
    tiff_path = output.with_suffix(".tiff")
    png_path = output.with_suffix(".png")
    for path in (svg_path, pdf_path, tiff_path, png_path):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"missing or empty export: {path}")

    root = ET.parse(svg_path).getroot()
    svg_text_nodes = sum(1 for element in root.iter() if element.tag.endswith("text"))
    if svg_text_nodes == 0:
        raise RuntimeError("SVG export does not contain editable text nodes")

    with Image.open(tiff_path) as image:
        tiff_pixels = image.size
        tiff_dpi = tuple(round(float(value), 2) for value in image.info.get("dpi", (0, 0)))
    with Image.open(png_path) as image:
        png_pixels = image.size

    expected_tiff = (round(FIGURE_WIDTH_IN * 600), round(FIGURE_HEIGHT_IN * 600))
    expected_png = (round(FIGURE_WIDTH_IN * 300), round(FIGURE_HEIGHT_IN * 300))
    if tiff_pixels != expected_tiff:
        raise RuntimeError(f"unexpected TIFF dimensions: {tiff_pixels} != {expected_tiff}")
    if png_pixels != expected_png:
        raise RuntimeError(f"unexpected PNG dimensions: {png_pixels} != {expected_png}")
    if min(tiff_dpi) < 599:
        raise RuntimeError(f"TIFF resolution is below 600 dpi: {tiff_dpi}")

    return {
        "svg_editable_text_nodes": svg_text_nodes,
        "pdf_bytes": pdf_path.stat().st_size,
        "tiff_pixels": list(tiff_pixels),
        "tiff_dpi": list(tiff_dpi),
        "png_preview_pixels": list(png_pixels),
    }


def _build_legacy_figure() -> tuple[plt.Figure, list[BoxRecord], list[ArrowRecord]]:
    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, FIGURE_HEIGHT_IN))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    registry: list[BoxRecord] = []
    arrows: list[ArrowRecord] = []

    add_region(
        ax, 0.018, 0.775, 0.964, 0.192,
        facecolor=COLORS["model_bg"], edgecolor=COLORS["model_edge"],
    )
    add_section_header(ax, 0.028, 0.932, 0.226, "MODEL CONTRACT")
    add_text_box(
        ax, registry, 0.033, 0.795, 0.190, 0.116,
        "Traffic / channel\nfinite buffers Bᵤ\nγᵤ; beam cᵤ,ₚ",
        facecolor=COLORS["model_fill"], edgecolor=COLORS["model_edge"],
        role="model traffic and channels",
    )
    add_text_box(
        ax, registry, 0.237, 0.795, 0.225, 0.116,
        "Resource geometry\nexplicit 1–2 subbands\nnorm. t₂ − t₁ + 1",
        facecolor=COLORS["model_fill"], edgecolor=COLORS["model_edge"],
        role="resource geometry",
    )
    add_text_box(
        ax, registry, 0.476, 0.795, 0.245, 0.116,
        "Sharing\nsingleton / subset of one\ncompatibility group\n(CG)",
        facecolor=COLORS["model_fill"], edgecolor=COLORS["model_edge"],
        role="compatibility sharing rule",
    )
    add_text_box(
        ax, registry, 0.735, 0.795, 0.232, 0.116,
        "Safety / objective\nlinked-band beams\nbudget L; Σᵤ min(Bᵤ,Dᵤ)",
        facecolor=COLORS["model_fill"], edgecolor=COLORS["model_edge"],
        role="model safety and objective",
    )

    add_region(
        ax, 0.018, 0.320, 0.462, 0.426,
        facecolor=COLORS["base_bg"], edgecolor=COLORS["base_edge"],
    )
    add_section_header(
        ax, 0.028, 0.707, 0.425, "A   BUILD A FEASIBLE INCUMBENT",
        color=COLORS["base_edge"],
    )
    add_module_box(
        ax, registry, 0.034, 0.557, 0.210, 0.130,
        "Beam plans",
        "raw · norm. · unique\ndemand · rate · peak\nbeam budget L",
        facecolor=COLORS["base_fill"], edgecolor=COLORS["base_edge"],
        role="diversified beam plans",
    )
    add_module_box(
        ax, registry, 0.274, 0.557, 0.190, 0.130,
        "Reusable rates",
        "q(zᵤ,ᵣ) lookup\nshare size × user\n× beam plan",
        facecolor=COLORS["base_fill"], edgecolor=COLORS["base_edge"],
        role="reusable rate table",
    )
    add_module_box(
        ax, registry, 0.034, 0.402, 0.430, 0.126,
        "Base: sequential allocation",
        "Per r: singletons + each CG\nfor each s, take top-s positive Δᵤ\ncommit best Gᵣ; update residuals",
        facecolor=COLORS["base_fill"], edgecolor=COLORS["base_edge"],
        role="base top-s allocation",
    )
    add_text_box(
        ax, registry, 0.138, 0.337, 0.326, 0.046,
        "validated Base incumbent F*",
        facecolor=COLORS["safe_fill"], edgecolor=COLORS["safe_edge"],
        role="validated sequential incumbent", weight="bold",
    )
    add_arrow(
        ax, arrows, (0.244, 0.622), (0.274, 0.622),
        role="beam plans to rates", color=COLORS["base_edge"],
    )
    add_arrow(
        ax, arrows, (0.369, 0.557), (0.369, 0.528),
        role="rates to sequential allocation", color=COLORS["base_edge"],
    )
    add_arrow(
        ax, arrows, (0.321, 0.402), (0.321, 0.383),
        role="allocation to sequential incumbent", color=COLORS["safe_edge"],
        linewidth=1.05,
    )

    add_region(
        ax, 0.500, 0.320, 0.482, 0.426,
        facecolor=COLORS["search_bg"], edgecolor=COLORS["search_edge"],
    )
    add_section_header(
        ax, 0.510, 0.707, 0.363, "B   CUMULATIVE IMPROVEMENT",
        color=COLORS["search_edge"],
    )
    add_text_box(
        ax, registry, 0.512, 0.641, 0.458, 0.057,
        "rebuild + validate each candidate\naccept iff legal and Fᶜ > F*",
        facecolor=COLORS["gate_fill"], edgecolor=COLORS["gate_edge"],
        role="candidate acceptance rule", weight="bold", pad=0.003, rounding=0.010,
    )
    add_module_box(
        ax, registry, 0.516, 0.508, 0.195, 0.126,
        "1  Global",
        "best (r,G) after\neach assignment\nupdate residuals",
        facecolor=COLORS["search_fill"], edgecolor=COLORS["search_edge"],
        role="global resource selection",
    )
    add_module_box(
        ax, registry, 0.741, 0.508, 0.225, 0.126,
        "2  CG-focused plans",
        "CG-weighted masks\nsame budget L\nglobal reallocate",
        facecolor=COLORS["search_fill"], edgecolor=COLORS["search_edge"],
        role="compatibility-group-focused plans",
    )
    add_module_box(
        ax, registry, 0.741, 0.337, 0.225, 0.126,
        "3  Remask",
        "scheduled-user remask\nretain bandwise counts\nthen rebuild allocation",
        facecolor=COLORS["search_fill"], edgecolor=COLORS["search_edge"],
        role="scheduled-user remask",
    )
    add_module_box(
        ax, registry, 0.516, 0.337, 0.215, 0.126,
        "4  Pair refill",
        "Two-resource refill\nrecompute residuals\nboth orders",
        facecolor=COLORS["search_fill"], edgecolor=COLORS["search_edge"],
        role="two-resource refill",
    )
    add_arrow(
        ax, arrows, (0.464, 0.360), (0.516, 0.571),
        role="sequential incumbent to global stage", color=COLORS["safe_edge"],
        linewidth=1.05,
    )
    add_arrow(
        ax, arrows, (0.711, 0.571), (0.741, 0.571),
        role="global to compatibility-group plans", color=COLORS["search_edge"],
    )
    add_arrow(
        ax, arrows, (0.854, 0.508), (0.854, 0.463),
        role="compatibility-group plans to remask", color=COLORS["search_edge"],
    )
    add_arrow(
        ax, arrows, (0.741, 0.400), (0.731, 0.400),
        role="remask to two-resource refill", color=COLORS["search_edge"],
    )

    add_text_box(
        ax, registry, 0.018, 0.244, 0.964, 0.057,
        "DEADLINE-AWARE CONTROL · cutoff-guarded loops · reserve validation / serialization tail",
        facecolor=COLORS["deadline_fill"], edgecolor=COLORS["deadline_edge"],
        role="deadline-aware control", weight="bold", pad=0.004, rounding=0.010,
    )

    add_region(
        ax, 0.018, 0.036, 0.964, 0.188,
        facecolor=COLORS["safe_bg"], edgecolor=COLORS["safe_edge"], linewidth=0.9,
    )
    add_section_header(
        ax, 0.028, 0.188, 0.284, "SAFETY INVARIANT", color=COLORS["safe_edge"],
    )
    ax.text(
        0.318, 0.210,
        "Discard expired/incomplete candidates; never overwrite F*.",
        transform=ax.transAxes, ha="left", va="center", fontsize=BODY_FONT_PT,
        color=COLORS["safe_edge"], zorder=3,
    )
    add_text_box(
        ax, registry, 0.035, 0.078, 0.175, 0.075,
        "feasible fallback\nempty allocation",
        facecolor=COLORS["safe_fill"], edgecolor=COLORS["safe_edge"],
        role="feasible fallback", weight="bold",
    )
    add_text_box(
        ax, registry, 0.235, 0.078, 0.215, 0.075,
        "validated\nsequential incumbent",
        facecolor=COLORS["safe_fill"], edgecolor=COLORS["safe_edge"],
        role="sequential safety state", weight="bold",
    )
    add_text_box(
        ax, registry, 0.486, 0.068, 0.268, 0.095,
        "validated F* retained\nthrough all stages",
        facecolor=COLORS["safe_fill"], edgecolor=COLORS["safe_edge"],
        role="retained validated incumbent", weight="bold",
    )
    add_text_box(
        ax, registry, 0.800, 0.078, 0.160, 0.075,
        "final validation\n+ serialize",
        facecolor=COLORS["safe_fill"], edgecolor=COLORS["safe_edge"],
        role="final validation and serialization", weight="bold",
    )
    add_arrow(
        ax, arrows, (0.210, 0.116), (0.235, 0.116),
        role="fallback to sequential safety state", color=COLORS["safe_edge"],
        linewidth=1.05,
    )
    add_arrow(
        ax, arrows, (0.450, 0.116), (0.486, 0.116),
        role="sequential to retained incumbent", color=COLORS["safe_edge"],
        linewidth=1.05,
    )
    add_arrow(
        ax, arrows, (0.754, 0.116), (0.800, 0.116),
        role="retained incumbent to output", color=COLORS["safe_edge"],
        linewidth=1.05,
    )



def build_simplified_figure() -> tuple[
    plt.Figure, list[BoxRecord], list[ArrowRecord]
]:
    """Draw a two-tier release path and cumulative configuration map."""
    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, FIGURE_HEIGHT_IN))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    registry: list[BoxRecord] = []
    arrows: list[ArrowRecord] = []

    add_region(
        ax,
        0.015,
        0.405,
        0.970,
        0.565,
        facecolor=COLORS["model_bg"],
        edgecolor=COLORS["model_edge"],
        linewidth=0.85,
    )
    add_section_header(
        ax,
        0.027,
        0.914,
        0.386,
        "FPTR RELEASE PATH",
        color=COLORS["header"],
    )

    main_boxes = (
        (
            0.025, 0.095, "Fallback", "empty",
            COLORS["safe_fill"], COLORS["safe_edge"], "feasible fallback",
        ),
        (
            0.134, 0.105, "Base", "feasible F*",
            COLORS["base_fill"], COLORS["base_edge"], "Base incumbent",
        ),
        (
            0.253, 0.105, "1  Global", "repricing",
            COLORS["search_fill"], COLORS["search_edge"], "global resource selection",
        ),
        (
            0.372, 0.085, "2  CG", "sharing",
            COLORS["search_fill"], COLORS["search_edge"], "compatibility-group sharing",
        ),
        (
            0.471, 0.110, "3  Remask", "repair",
            COLORS["search_fill"], COLORS["search_edge"], "demand-driven remask",
        ),
        (
            0.595, 0.100, "4  Pair", "ruin / refill",
            COLORS["search_fill"], COLORS["search_edge"], "two-resource refill",
        ),
        (
            0.709, 0.145, "Commit gate", "complete · timely\nvalid · better",
            COLORS["gate_fill"], COLORS["gate_edge"], "transactional commit gate",
        ),
        (
            0.868, 0.110, "Output", "validated\nF*",
            COLORS["safe_fill"], COLORS["safe_edge"], "validated output",
        ),
    )
    for x, width, title, body, fill, edge, role in main_boxes:
        add_module_box(
            ax,
            registry,
            x,
            0.615,
            width,
            0.205,
            title,
            body,
            facecolor=fill,
            edgecolor=edge,
            role=role,
        )

    main_arrows = (
        (
            (0.120, 0.718), (0.134, 0.718),
            "fallback to Base incumbent", COLORS["safe_edge"],
        ),
        (
            (0.239, 0.718), (0.253, 0.718),
            "Base incumbent to global stage", COLORS["base_edge"],
        ),
        (
            (0.358, 0.718), (0.372, 0.718),
            "global to CG stage", COLORS["search_edge"],
        ),
        (
            (0.457, 0.718), (0.471, 0.718),
            "CG to remask stage", COLORS["search_edge"],
        ),
        (
            (0.581, 0.718), (0.595, 0.718),
            "remask to pair stage", COLORS["search_edge"],
        ),
        (
            (0.695, 0.718), (0.709, 0.718),
            "pair stage to commit gate", COLORS["gate_edge"],
        ),
        (
            (0.854, 0.718), (0.868, 0.718),
            "commit gate to validated output", COLORS["safe_edge"],
        ),
    )
    for start, end, role, color in main_arrows:
        add_arrow(
            ax,
            arrows,
            start,
            end,
            role=role,
            color=color,
            linewidth=1.0,
        )

    add_text_box(
        ax,
        registry,
        0.027,
        0.465,
        0.946,
        0.075,
        (
            "Reject: keep F*   |   Commit: replace F*   |   "
            "final validation + serialization"
        ),
        facecolor=COLORS["deadline_fill"],
        edgecolor=COLORS["deadline_edge"],
        role="commit discard safety invariant",
        weight="bold",
        pad=0.003,
        rounding=0.010,
    )

    add_region(
        ax,
        0.015,
        0.045,
        0.970,
        0.330,
        facecolor=COLORS["safe_bg"],
        edgecolor=COLORS["safe_edge"],
        linewidth=0.85,
    )
    add_section_header(
        ax,
        0.027,
        0.326,
        0.560,
        "CUMULATIVE EVALUATION CONFIGURATIONS",
        color=COLORS["safe_edge"],
    )
    configuration_boxes = (
        (
            0.030, 0.145, "BeamFirst\nseparate",
            COLORS["model_fill"], COLORS["line"], "BeamFirst configuration",
        ),
        (
            0.215, 0.130, "Base\nfloor",
            COLORS["base_fill"], COLORS["base_edge"], "Base configuration",
        ),
        (
            0.365, 0.130, "Global\nBase + 1",
            COLORS["search_fill"], COLORS["search_edge"], "Global configuration",
        ),
        (
            0.515, 0.130, "CG\nBase + 1–2",
            COLORS["search_fill"], COLORS["search_edge"], "CG configuration",
        ),
        (
            0.665, 0.130, "Remask\nBase + 1–3",
            COLORS["search_fill"], COLORS["search_edge"], "Remask configuration",
        ),
        (
            0.815, 0.145, "Full\nBase + 1–4",
            COLORS["safe_fill"], COLORS["safe_edge"], "Full configuration",
        ),
    )
    for x, width, label, fill, edge, role in configuration_boxes:
        add_text_box(
            ax,
            registry,
            x,
            0.105,
            width,
            0.145,
            label,
            facecolor=fill,
            edgecolor=edge,
            role=role,
            weight="bold",
        )

    ax.plot(
        [0.195, 0.195],
        [0.092, 0.263],
        transform=ax.transAxes,
        color=COLORS["line"],
        linewidth=0.7,
        linestyle=(0, (2, 2)),
        zorder=1,
    )
    configuration_arrows = (
        ((0.345, 0.178), (0.365, 0.178), "Base to Global configuration"),
        ((0.495, 0.178), (0.515, 0.178), "Global to CG configuration"),
        ((0.645, 0.178), (0.665, 0.178), "CG to Remask configuration"),
        ((0.795, 0.178), (0.815, 0.178), "Remask to Full configuration"),
    )
    for start, end, role in configuration_arrows:
        add_arrow(
            ax,
            arrows,
            start,
            end,
            role=role,
            color=COLORS["safe_edge"],
            linewidth=0.85,
        )

    return fig, registry, arrows
    return fig, registry, arrows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("paper/figures/scheduler_pipeline"),
    )
    args = parser.parse_args()
    configure_style()

    fig, registry, arrows = build_simplified_figure()
    layout_qa = validate_layout(fig, registry, arrows)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(args.output.with_suffix(".svg"))
    fig.savefig(args.output.with_suffix(".pdf"))
    fig.savefig(args.output.with_suffix(".tiff"), dpi=600)
    fig.savefig(args.output.with_suffix(".png"), dpi=300)
    plt.close(fig)

    export_qa = validate_exports(args.output)
    qa = {
        "core_conclusion": (
            "FPTR keeps an empty fallback and feasible Base incumbent, applies four "
            "bounded refinement stages through one commit-or-discard gate, and "
            "releases only a validated incumbent."
        ),
        "figure_archetype": "two-tier release path and configuration map",
        "target": "LNCS full-width figure",
        "backend": "Python (matplotlib)",
        "width_in": FIGURE_WIDTH_IN,
        "height_in": FIGURE_HEIGHT_IN,
        "exports": ["svg", "pdf", "tiff", "png"],
        "vector_primary": True,
        "tiff_target_dpi": 600,
        "minimum_font_target_pt": BODY_FONT_PT,
        **layout_qa,
        **export_qa,
    }
    args.output.with_name(args.output.name + "_qa.json").write_text(
        json.dumps(qa, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
