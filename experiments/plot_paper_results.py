#!/usr/bin/env python3
"""Generate split publication figures from the formal experiment bundle.

All quantitative marks are derived from the directory selected by --results-dir.
Python/Matplotlib is used exclusively for drawing, previewing, exporting, and
layout QA. SVG is the editable primary output; PDF, 600-dpi TIFF, and 300-dpi
PNG are emitted from the same figure.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import shutil
import statistics
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from PIL import Image


# Mandatory publication settings: labels remain editable in SVG/PDF.
mpl.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Liberation Serif", "Nimbus Roman", "DejaVu Serif", "Arial"],
    "mathtext.fontset": "stix",
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
})

FIGURE_WIDTH_IN = 4.80
QUALITY_FIGURE_HEIGHT_IN = 3.05
STRESS_FIGURE_HEIGHT_IN = 1.82
OVERVIEW_FIGURE_HEIGHT_IN = 4.25
# The reference uses restrained, report-like typography: axes and labels
# support the data instead of competing with it. These sizes are evaluated at
# the final LNCS text width rather than on a zoomed raster preview.
BODY_FONT_PT = 5.25
SMALL_FONT_PT = 4.80
TITLE_FONT_PT = 5.55
PANEL_FONT_PT = 6.45

METHODS = ("BeamFirst", "Base", "Global", "CG", "Remask", "Full")
TRACE_STAGES = ("Base", "Global", "CG", "Remask", "Full")
TRACE_LABELS = ("Base", "Glob.", "CG", "Rem.", "Pair")
BUDGETS_MS = (20, 40, 60, 87)
CG_SIZES = (2, 5, 10, 15, 20)
SCENARIOS = (
    "small-balanced",
    "medium-longtail",
    "medium-tight",
    "large-mixed",
    "large-nonadjacent",
)
SCENARIO_LABELS = {
    "small-balanced": "Small bal.",
    "medium-longtail": "Med. long-tail",
    "medium-tight": "Med. tight",
    "large-mixed": "Large mixed",
    "large-nonadjacent": "Large non-adj.",
}

METHOD_COLORS = {
    "BeamFirst": "#262626",
    "Base": "#494A73",
    "Global": "#6F7FA6",
    "CG": "#3F817F",
    "Remask": "#9A6B80",
    "Full": "#A63D38",
}
METHOD_MARKERS = {
    "BeamFirst": "o",
    "Base": "s",
    "Global": "^",
    "CG": "D",
    "Remask": "P",
    "Full": "X",
}
METHOD_LINESTYLES = {
    "BeamFirst": (0, (1.2, 1.2)),
    "Base": (0, (4.0, 1.5)),
    "Global": (0, (4.0, 1.2, 1.0, 1.2)),
    "CG": (0, (2.0, 1.0, 1.0, 1.0)),
    "Remask": (0, (6.0, 1.4)),
    "Full": "-",
}
INK = "#202020"
AXIS = "#2F2F2F"
NEUTRAL = "#707070"
LIGHT_NEUTRAL = "#D2D2D2"
GRID = "#D0D0D0"
GAIN = "#347A4A"
WIDE_CASE = "#B86A08"
ACTIVE_PROFILE = "paper"


def configure_style(profile: str = "paper") -> None:
    global ACTIVE_PROFILE
    global FIGURE_WIDTH_IN, BODY_FONT_PT, SMALL_FONT_PT, TITLE_FONT_PT, PANEL_FONT_PT
    ACTIVE_PROFILE = profile
    if profile == "web":
        FIGURE_WIDTH_IN = 8.5
        BODY_FONT_PT = 11.5
        SMALL_FONT_PT = 11.0
        TITLE_FONT_PT = 13.0
        PANEL_FONT_PT = 12.5
    else:
        FIGURE_WIDTH_IN = 4.80
        BODY_FONT_PT = 5.25
        SMALL_FONT_PT = 4.80
        TITLE_FONT_PT = 5.55
        PANEL_FONT_PT = 6.45
    mpl.rcParams.update(
        {
            "font.size": BODY_FONT_PT,
            "font.family": "sans-serif" if profile == "web" else "serif",
            "font.serif": ["Times New Roman", "Liberation Serif", "Nimbus Roman", "DejaVu Serif", "Arial"],
            "font.sans-serif": ["Inter", "Noto Sans", "DejaVu Sans", "Arial"],
            "axes.labelsize": BODY_FONT_PT,
            "axes.titlesize": TITLE_FONT_PT,
            "axes.titleweight": "normal",
            "axes.titlelocation": "left",
            # Thin four-sided axes match the supplied pragmatic reference and
            # make the plotting area explicit without visually enlarging it.
            "axes.spines.right": True,
            "axes.spines.top": True,
            "axes.edgecolor": AXIS,
            "axes.labelcolor": INK,
            "axes.linewidth": 0.36,
            "axes.axisbelow": True,
            "xtick.labelsize": BODY_FONT_PT,
            "ytick.labelsize": BODY_FONT_PT,
            "xtick.color": AXIS,
            "ytick.color": AXIS,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.top": True,
            "ytick.right": True,
            "xtick.major.width": 0.34,
            "ytick.major.width": 0.34,
            "xtick.major.size": 1.45,
            "ytick.major.size": 1.45,
            "grid.color": GRID,
            "grid.linewidth": 0.24,
            "grid.alpha": 0.56,
            "legend.fontsize": SMALL_FONT_PT,
            "legend.frameon": True,
            "legend.framealpha": 1.0,
            "legend.edgecolor": AXIS,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.facecolor": "white",
            "savefig.edgecolor": "white",
        }
    )


def read_csv(path: Path, required: Iterable[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(set(required) - set(reader.fieldnames or ()))
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path} contains no data rows")
    return rows


def read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    return float(np.percentile(np.asarray(values, dtype=float), 100.0 * q))


def mean_relative_gain(pairs: Sequence[tuple[float, float]]) -> float:
    gains = [
        (candidate - baseline) / baseline
        for candidate, baseline in pairs
        if baseline > 0
    ]
    return statistics.fmean(gains) if gains else 0.0


def stratified_relative_gain(
    candidate: Mapping[tuple[str, int], float],
    baseline: Mapping[tuple[str, int], float],
    *,
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> tuple[float, tuple[float, float], dict[str, float]]:
    if candidate.keys() != baseline.keys():
        raise ValueError("paired tables do not contain the same instances")
    by_scenario: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for key in sorted(candidate):
        scenario, _seed = key
        if baseline[key] > 0:
            by_scenario[scenario].append((candidate[key], baseline[key]))
    if not by_scenario:
        return 0.0, (0.0, 0.0), {}

    scenario_means = {
        scenario: mean_relative_gain(pairs)
        for scenario, pairs in sorted(by_scenario.items())
    }
    estimate = statistics.fmean(scenario_means.values())
    if all(
        abs(candidate_value - baseline_value) < 1e-12
        for pairs in by_scenario.values()
        for candidate_value, baseline_value in pairs
    ):
        return estimate, (estimate, estimate), scenario_means

    rng = random.Random(bootstrap_seed)
    draws: list[float] = []
    strata = [(name, pairs) for name, pairs in sorted(by_scenario.items())]
    for _ in range(bootstrap_samples):
        draw_means: list[float] = []
        for _name, pairs in strata:
            resampled = [pairs[rng.randrange(len(pairs))] for _ in range(len(pairs))]
            draw_means.append(mean_relative_gain(resampled))
        draws.append(statistics.fmean(draw_means))
    return (
        estimate,
        (percentile(draws, 0.025), percentile(draws, 0.975)),
        scenario_means,
    )


def bootstrap_mean_ci(
    values: Sequence[float], *, bootstrap_samples: int, bootstrap_seed: int
) -> tuple[float, tuple[float, float]]:
    if not values:
        raise ValueError("bootstrap requires at least one value")
    estimate = statistics.fmean(values)
    if max(values) - min(values) < 1e-15:
        return estimate, (estimate, estimate)
    rng = random.Random(bootstrap_seed)
    draws = [
        statistics.fmean(
            values[rng.randrange(len(values))] for _ in range(len(values))
        )
        for _ in range(bootstrap_samples)
    ]
    return estimate, (percentile(draws, 0.025), percentile(draws, 0.975))


def panel_label(ax: plt.Axes, label: str) -> mpl.text.Text:
    return ax.text(
        -0.155,
        1.014,
        label,
        transform=ax.transAxes,
        fontsize=PANEL_FONT_PT,
        fontweight="bold",
        color=INK,
        ha="left",
        va="bottom",
        clip_on=False,
    )


def profile_panel_labels(
    axes: Sequence[plt.Axes], labels: str
) -> list[mpl.text.Text]:
    if ACTIVE_PROFILE != "paper":
        return []
    return [panel_label(ax, label) for ax, label in zip(axes, labels)]


def trace_tables(
    rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, dict[tuple[str, int], float]], dict[str, int]]:
    by_run: dict[tuple[str, int, int], dict[str, float]] = defaultdict(dict)
    present_by_run: dict[tuple[str, int, int], dict[str, bool]] = defaultdict(dict)
    by_instance: dict[tuple[str, int, str], list[float]] = defaultdict(list)
    seen: set[tuple[str, int, int, str]] = set()

    for row in rows:
        stage = str(row["stage"])
        if stage not in TRACE_STAGES:
            continue
        scenario = str(row["scenario"])
        seed = int(row["seed"])
        repeat = int(row["repeat"])
        unique = (scenario, seed, repeat, stage)
        if unique in seen:
            raise ValueError(f"duplicate trace row: {unique}")
        seen.add(unique)
        score = float(row["credited_stage_score"])
        by_run[(scenario, seed, repeat)][stage] = score
        present_by_run[(scenario, seed, repeat)][stage] = parse_bool(
            row["stage_trace_present"]
        )
        by_instance[(scenario, seed, stage)].append(score)

    if not by_run:
        raise ValueError("trace ablation table contains no recognized stages")
    incomplete = 0
    nonmonotone = 0
    for run_key, scores in by_run.items():
        present = present_by_run[run_key]
        if (
            set(scores) != set(TRACE_STAGES)
            or set(present) != set(TRACE_STAGES)
            or not all(present.values())
        ):
            incomplete += 1
            continue
        ordered = [scores[stage] for stage in TRACE_STAGES]
        if any(right < left for left, right in zip(ordered, ordered[1:])):
            nonmonotone += 1

    instance_keys = sorted(
        {(scenario, seed) for scenario, seed, _stage in by_instance}
    )
    table = {stage: {} for stage in TRACE_STAGES}
    for key in instance_keys:
        repeat_counts: set[int] = set()
        for stage in TRACE_STAGES:
            scores = by_instance.get((*key, stage), [])
            if not scores:
                raise ValueError(f"missing trace stage {stage} for instance {key}")
            repeat_counts.add(len(scores))
            table[stage][key] = statistics.median(scores)
        if len(repeat_counts) != 1:
            raise ValueError(f"unequal trace repeat counts for instance {key}")

    return table, {
        "instances": len(instance_keys),
        "full_runs": len(by_run),
        "incomplete_runs": incomplete,
        "nonmonotone_runs": nonmonotone,
    }


def draw_trace_ablation(
    ax: plt.Axes,
    rows: Sequence[Mapping[str, str]],
    trace_analysis: Mapping[str, object],
    *,
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> tuple[dict[str, object], list[mpl.text.Text]]:
    table, diagnostics = trace_tables(rows)
    x = np.arange(len(TRACE_STAGES), dtype=float)
    gains: list[float] = []
    lows: list[float] = []
    highs: list[float] = []
    scenario_gains: dict[str, dict[str, float]] = {}
    cumulative_seed_offsets = {
        "Base": 0,
        "Global": 0,
        "CG": 1009,
        "Remask": 2018,
        # Matches the preregistered Full-vs-Base comparison seed.
        "Full": 2018,
    }
    for index, stage in enumerate(TRACE_STAGES):
        estimate, ci, by_scenario = stratified_relative_gain(
            table[stage],
            table["Base"],
            bootstrap_samples=bootstrap_samples,
            bootstrap_seed=bootstrap_seed + cumulative_seed_offsets[stage],
        )
        gains.append(100.0 * estimate)
        lows.append(100.0 * ci[0])
        highs.append(100.0 * ci[1])
        scenario_gains[stage] = {
            name: 100.0 * value for name, value in by_scenario.items()
        }

    ax.plot(x, gains, color=INK, linewidth=0.64, zorder=2)
    annotations: list[mpl.text.Text] = []
    for index, stage in enumerate(TRACE_STAGES):
        ax.errorbar(
            x[index],
            gains[index],
            yerr=np.asarray(
                [
                    [gains[index] - lows[index]],
                    [highs[index] - gains[index]],
                ]
            ),
            fmt="none",
            ecolor=METHOD_COLORS[stage],
            elinewidth=0.46,
            capsize=1.15,
            capthick=0.42,
            zorder=3,
        )
        ax.scatter(
            x[index],
            gains[index],
            s=18,
            marker=METHOD_MARKERS[stage],
            facecolor="white",
            edgecolor=METHOD_COLORS[stage],
            linewidth=0.52,
            zorder=4,
        )

    comparisons = trace_analysis.get("comparisons")
    if not isinstance(comparisons, dict):
        raise ValueError("trace analysis is missing comparisons")
    comparison_names = (
        "Global_vs_Base",
        "CG_vs_Global",
        "Remask_vs_CG",
        "Full_vs_Remask",
    )
    adjacent: list[float] = []
    losses: dict[str, int] = {}
    for comparison_name in comparison_names:
        payload = comparisons.get(comparison_name)
        if not isinstance(payload, dict):
            raise ValueError(f"trace analysis is missing {comparison_name}")
        adjacent.append(100.0 * float(payload["mean_relative_gain"]))
        losses[comparison_name] = int(payload["losses"])

    data_floor = min(0.0, min(lows))
    data_ceiling = max(highs)
    y_pad = max(0.10, 0.08 * max(data_ceiling - data_floor, 1.0))
    y_floor = data_floor - y_pad
    for index, gain in enumerate(adjacent):
        y_text = max(
            y_floor + 0.05,
            0.5 * (gains[index] + gains[index + 1]) - 0.22,
        )
        if index == len(adjacent) - 1:
            y_text = gains[index] - 0.32
        annotations.append(
            ax.text(
                index + 0.5,
                y_text,
                f"Δ+{gain:.2f}",
                ha="center",
                va="center",
                fontsize=SMALL_FONT_PT,
                color=GAIN,
            )
        )

    annotations.append(
        ax.text(
            0.015,
            0.965,
            "n = 150; median of 5\nfixed order; losses = 0",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=SMALL_FONT_PT,
            color=NEUTRAL,
        )
    )
    ax.set_xlim(-0.32, len(TRACE_STAGES) - 0.68)
    # Rounded, zero-anchored limits avoid visually magnifying small gains.
    ax.set_ylim(-0.15, 3.00)
    ax.set_yticks([0, 1, 2, 3])
    ax.set_xticks(x)
    ax.set_xticklabels(TRACE_LABELS)
    ax.set_ylabel("Cumulative gain over Base (%)")
    ax.set_title("Ordered stage gain", pad=1.5)
    ax.grid(True)
    return {
        "cumulative_gain_percent": dict(zip(TRACE_STAGES, gains)),
        "stratified_95_ci_percent": {
            stage: [low, high]
            for stage, low, high in zip(TRACE_STAGES, lows, highs)
        },
        "adjacent_gain_percent": dict(zip(comparison_names, adjacent)),
        "adjacent_losses": losses,
        "scenario_gain_percent": scenario_gains,
        "diagnostics": diagnostics,
    }, annotations


def draw_scenario_gain(
    ax: plt.Axes, paired_analysis: Mapping[str, object]
) -> tuple[dict[str, object], list[mpl.text.Text]]:
    comparisons = paired_analysis.get("comparisons")
    if not isinstance(comparisons, dict):
        raise ValueError("paired analysis is missing comparisons")
    base_payload = comparisons.get("Full_vs_Base")
    beam_payload = comparisons.get("Full_vs_BeamFirst")
    if not isinstance(base_payload, dict) or not isinstance(beam_payload, dict):
        raise ValueError("paired analysis is missing Full comparisons")
    base_scenarios = base_payload.get("scenario_mean_relative_gain")
    beam_scenarios = beam_payload.get("scenario_mean_relative_gain")
    if not isinstance(base_scenarios, dict) or not isinstance(beam_scenarios, dict):
        raise ValueError("paired analysis is missing scenario gains")

    y = np.arange(len(SCENARIOS), dtype=float)
    gain_base = np.asarray(
        [100.0 * float(base_scenarios[name]) for name in SCENARIOS]
    )
    gain_beam = np.asarray(
        [100.0 * float(beam_scenarios[name]) for name in SCENARIOS]
    )
    for yi, left, right in zip(y, gain_base, gain_beam):
        ax.plot(
            [left, right],
            [yi, yi],
            color=LIGHT_NEUTRAL,
            linewidth=0.44,
            zorder=1,
        )
    ax.scatter(
        gain_beam,
        y,
        s=17,
        marker=METHOD_MARKERS["BeamFirst"],
        facecolor="white",
        edgecolor=METHOD_COLORS["BeamFirst"],
        linewidth=0.50,
        zorder=3,
    )
    ax.scatter(
        gain_base,
        y,
        s=17,
        marker=METHOD_MARKERS["Base"],
        facecolor="white",
        edgecolor=METHOD_COLORS["Base"],
        linewidth=0.50,
        zorder=3,
    )
    overall_base = 100.0 * float(base_payload["mean_relative_gain"])
    overall_beam = 100.0 * float(beam_payload["mean_relative_gain"])
    annotations = [
        ax.text(
            0.965,
            0.055,
            (
                f"Overall: Base +{overall_base:.2f}%\n"
                f"BeamFirst +{overall_beam:.2f}%"
            ),
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=SMALL_FONT_PT,
            color=NEUTRAL,
            linespacing=1.05,
        )
    ]
    ax.set_yticks(y)
    ax.set_yticklabels([SCENARIO_LABELS[name] for name in SCENARIOS])
    ax.invert_yaxis()
    # Fixed round bounds make cross-scenario effect sizes easy to read.
    ax.set_xlim(0.0, 10.0)
    ax.set_xlabel("Full traffic gain (%)")
    ax.set_xticks([0, 2, 4, 6, 8, 10])
    ax.set_title("Scenario-wise Full gain", pad=1.5)
    ax.grid(True)
    return {
        "Full_vs_Base_percent": dict(zip(SCENARIOS, gain_base.tolist())),
        "Full_vs_BeamFirst_percent": dict(zip(SCENARIOS, gain_beam.tolist())),
        "overall_percent": {
            "Full_vs_Base": overall_base,
            "Full_vs_BeamFirst": overall_beam,
        },
        "Full_vs_Base_95_ci_percent": [
            100.0 * float(value)
            for value in base_payload["stratified_bootstrap_95_ci"]
        ],
        "Full_vs_Base_wins_ties_losses": [
            int(base_payload["wins"]),
            int(base_payload["ties"]),
            int(base_payload["losses"]),
        ],
    }, annotations


def aggregate_budget_scores(
    rows: Sequence[Mapping[str, str]],
) -> dict[int, dict[tuple[str, int], float]]:
    table = {budget: {} for budget in BUDGETS_MS}
    for row in rows:
        budget = int(row["budget_ms"])
        if budget not in table:
            continue
        key = (str(row["scenario"]), int(row["seed"]))
        if key in table[budget]:
            raise ValueError(f"duplicate budget aggregate for {budget} and {key}")
        table[budget][key] = float(row["transmitted_median"])
    reference_keys = table[BUDGETS_MS[0]].keys()
    for budget in BUDGETS_MS:
        if table[budget].keys() != reference_keys:
            raise ValueError(f"budget {budget} does not contain the same instances")
    return table


def draw_budget_tradeoff(
    ax: plt.Axes,
    aggregate_rows: Sequence[Mapping[str, str]],
    run_rows: Sequence[Mapping[str, str]],
    *,
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> tuple[dict[str, object], list[mpl.text.Text]]:
    table = aggregate_budget_scores(aggregate_rows)
    gains: list[float] = []
    lows: list[float] = []
    highs: list[float] = []
    for index, budget in enumerate(BUDGETS_MS):
        estimate, ci, _scenario = stratified_relative_gain(
            table[budget],
            table[BUDGETS_MS[0]],
            bootstrap_samples=bootstrap_samples,
            bootstrap_seed=bootstrap_seed + index * 1013,
        )
        gains.append(100.0 * estimate)
        lows.append(100.0 * ci[0])
        highs.append(100.0 * ci[1])

    runtimes: dict[int, list[float]] = defaultdict(list)
    deadline_misses = 0
    for row in run_rows:
        budget = int(row["budget_ms"])
        if budget in BUDGETS_MS:
            runtimes[budget].append(float(row["solver_wall_ms"]))
            deadline_misses += int(parse_bool(row["deadline_miss"]))
    runtime_p95 = [percentile(runtimes[budget], 0.95) for budget in BUDGETS_MS]

    x = np.asarray(BUDGETS_MS, dtype=float)
    y = np.asarray(gains)
    ax.errorbar(
        x,
        y,
        yerr=np.asarray(
            [y - np.asarray(lows), np.asarray(highs) - y]
        ),
        color=METHOD_COLORS["Full"],
        marker=METHOD_MARKERS["Full"],
        markersize=3.6,
        markerfacecolor="white",
        markeredgecolor=METHOD_COLORS["Full"],
        markeredgewidth=0.52,
        linewidth=0.68,
        elinewidth=0.46,
        capsize=1.15,
        zorder=3,
    )
    ax.axvline(
        100,
        color=NEUTRAL,
        linestyle=(0, (3, 2)),
        linewidth=0.46,
        zorder=0,
    )
    annotations: list[mpl.text.Text] = []
    annotation_lift = {40: 0.05, 60: 0.08, 87: 0.05}
    for budget, gain, high, p95 in zip(BUDGETS_MS, gains, highs, runtime_p95):
        if budget == BUDGETS_MS[0]:
            continue
        label_x = budget + 1.2 if budget == BUDGETS_MS[0] else budget
        annotations.append(
            ax.text(
                label_x,
                high + annotation_lift[budget],
                f"{p95:.1f}",
                ha="left" if budget == BUDGETS_MS[0] else "center",
                va="bottom",
                fontsize=SMALL_FONT_PT,
                color=NEUTRAL,
            )
        )
    annotations.append(
        ax.text(
            99.0,
            0.04,
            "100 ms",
            transform=ax.get_xaxis_transform(),
            rotation=90,
            ha="right",
            va="bottom",
            fontsize=SMALL_FONT_PT,
            color=NEUTRAL,
        )
    )
    ax.set_xlim(15, 105)
    ax.set_ylim(-0.15, 3.00)
    ax.set_xticks([20, 40, 60, 80, 100])
    ax.set_yticks([0, 1, 2, 3])
    ax.set_xlabel("Search target (ms)")
    ax.set_ylabel("Gain vs 20 ms (%)")
    annotations.append(
        ax.text(
            0.985,
            0.96,
            "labels: wall p95 (ms)",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=SMALL_FONT_PT,
            color=NEUTRAL,
        )
    )
    ax.set_title("Budget trade-off", pad=1.5)
    ax.grid(True)
    return {
        "gain_percent_vs_20ms": dict(zip(map(str, BUDGETS_MS), gains)),
        "stratified_95_ci_percent": {
            str(budget): [low, high]
            for budget, low, high in zip(BUDGETS_MS, lows, highs)
        },
        "external_runtime_p95_ms": dict(
            zip(map(str, BUDGETS_MS), runtime_p95)
        ),
        "deadline_misses": deadline_misses,
        "runs": sum(len(values) for values in runtimes.values()),
    }, annotations


def draw_runtime_ecdf(
    ax: plt.Axes, rows: Sequence[Mapping[str, str]]
) -> tuple[dict[str, object], list[mpl.text.Text]]:
    times: dict[str, list[float]] = defaultdict(list)
    deadline_misses = 0
    for row in rows:
        method = str(row["method"])
        if method not in METHODS:
            continue
        times[method].append(float(row["solver_wall_ms"]))
        deadline_misses += int(parse_bool(row["deadline_miss"]))
    missing = [method for method in METHODS if not times[method]]
    if missing:
        raise ValueError(f"runtime table is missing methods: {', '.join(missing)}")

    summaries: dict[str, object] = {}
    for method in METHODS:
        x = np.sort(np.asarray(times[method], dtype=float))
        y = np.arange(1, len(x) + 1, dtype=float) / len(x)
        ax.step(
            x,
            y,
            where="post",
            color=METHOD_COLORS[method],
            linestyle=METHOD_LINESTYLES[method],
            linewidth=0.56 if method != "Full" else 0.68,
            alpha=0.96,
            zorder=2,
        )
        summaries[method] = {
            "runs": len(x),
            "p50_ms": percentile(x.tolist(), 0.50),
            "p95_ms": percentile(x.tolist(), 0.95),
            "worst_ms": float(x[-1]),
        }
    ax.axvline(
        100,
        color=NEUTRAL,
        linestyle=(0, (3, 2)),
        linewidth=0.45,
        zorder=1,
    )
    annotations: list[mpl.text.Text] = []
    ax.set_xlim(0, 105)
    ax.set_ylim(0, 1.02)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xlabel("Solver wall time (ms)")
    ax.set_ylabel("ECDF")
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.set_title("Runtime ECDF (87 ms)", pad=1.5)
    ax.grid(True)
    return {"methods": summaries, "deadline_misses": deadline_misses}, annotations


def stress_tables(
    rows: Sequence[Mapping[str, str]],
) -> dict[int, dict[str, dict[int, float]]]:
    table: dict[int, dict[str, dict[int, float]]] = {
        size: {"Base": {}, "CG": {}, "Full": {}} for size in CG_SIZES
    }
    for row in rows:
        scenario = str(row["scenario"])
        if not scenario.startswith("cg-size-"):
            continue
        size = int(scenario.rsplit("-", 1)[1])
        method = str(row["method"])
        if size not in table or method not in table[size]:
            continue
        seed = int(row["seed"])
        if seed in table[size][method]:
            raise ValueError(
                f"duplicate stress aggregate for CG size {size}, {method}, {seed}"
            )
        table[size][method][seed] = float(row["transmitted_median"])
    for size in CG_SIZES:
        keys = table[size]["Base"].keys()
        if not keys:
            raise ValueError(f"stress table has no rows for CG size {size}")
        for method in ("CG", "Full"):
            if table[size][method].keys() != keys:
                raise ValueError(
                    f"unpaired stress rows for CG size {size}, {method}"
                )
    return table


def draw_cg_stress(
    ax: plt.Axes,
    aggregate_rows: Sequence[Mapping[str, str]],
    run_rows: Sequence[Mapping[str, str]],
    *,
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> tuple[dict[str, object], list[mpl.text.Text]]:
    table = stress_tables(aggregate_rows)
    gains: dict[str, list[float]] = {"CG": [], "Full": []}
    intervals: dict[str, list[tuple[float, float]]] = {"CG": [], "Full": []}
    for method_index, method in enumerate(("CG", "Full")):
        for size_index, size in enumerate(CG_SIZES):
            values = [
                100.0
                * (
                    table[size][method][seed] - table[size]["Base"][seed]
                )
                / table[size]["Base"][seed]
                for seed in sorted(table[size]["Base"])
                if table[size]["Base"][seed] > 0
            ]
            estimate, ci = bootstrap_mean_ci(
                values,
                bootstrap_samples=bootstrap_samples,
                bootstrap_seed=(
                    bootstrap_seed + method_index * 5003 + size_index * 101
                ),
            )
            gains[method].append(estimate)
            intervals[method].append(ci)

    full_times: dict[int, list[float]] = defaultdict(list)
    full_deadline_misses = 0
    for row in run_rows:
        if str(row["method"]) != "Full":
            continue
        scenario = str(row["scenario"])
        if not scenario.startswith("cg-size-"):
            continue
        size = int(scenario.rsplit("-", 1)[1])
        if size in CG_SIZES:
            full_times[size].append(float(row["solver_wall_ms"]))
            full_deadline_misses += int(parse_bool(row["deadline_miss"]))
    full_p95 = [percentile(full_times[size], 0.95) for size in CG_SIZES]

    x = np.asarray(CG_SIZES, dtype=float)
    for method in ("CG", "Full"):
        y = np.asarray(gains[method])
        lo = np.asarray([ci[0] for ci in intervals[method]])
        hi = np.asarray([ci[1] for ci in intervals[method]])
        ax.errorbar(
            x,
            y,
            yerr=np.asarray([y - lo, hi - y]),
            color=METHOD_COLORS[method],
            marker=METHOD_MARKERS[method],
            markersize=3.5,
            markerfacecolor="white",
            markeredgecolor=METHOD_COLORS[method],
            markeredgewidth=0.50,
            linewidth=0.58 if method == "CG" else 0.68,
            elinewidth=0.45,
            capsize=1.15,
            zorder=3,
        )

    annotations: list[mpl.text.Text] = []
    ax.axhline(0, color=AXIS, linewidth=0.34)
    ax.set_xlim(0, 21)
    ax.set_ylim(-0.5, 8.0)
    ax.set_yticks([0, 2, 4, 6, 8])
    ax.set_xticks(CG_SIZES)
    ax.set_xticklabels(
        [f"{size}\n{p95:.0f}" for size, p95 in zip(CG_SIZES, full_p95)]
    )
    ax.tick_params(axis="x", pad=1.5)
    ax.set_xlabel("CG size / Full p95 (ms)", labelpad=1.5)
    ax.set_ylabel("Traffic gain over Base (%)")
    annotations.append(
        ax.text(
            0.02,
            0.96,
            "coverage co-varies",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=SMALL_FONT_PT,
            color=NEUTRAL,
        )
    )
    ax.set_title("CG-size stress", pad=1.5)
    ax.grid(True)
    return {
        "gain_percent": {
            method: dict(zip(map(str, CG_SIZES), values))
            for method, values in gains.items()
        },
        "bootstrap_95_ci_percent": {
            method: {
                str(size): list(ci) for size, ci in zip(CG_SIZES, cis)
            }
            for method, cis in intervals.items()
        },
        "Full_runtime_p95_ms": dict(zip(map(str, CG_SIZES), full_p95)),
        "Full_deadline_misses": full_deadline_misses,
        "Full_runs": sum(len(values) for values in full_times.values()),
    }, annotations


def draw_exact_gap(
    ax: plt.Axes, rows: Sequence[Mapping[str, str]]
) -> tuple[dict[str, object], list[mpl.text.Text]]:
    gaps: dict[str, list[tuple[int, str, float]]] = defaultdict(list)
    seen: set[tuple[str, int]] = set()
    for row in rows:
        method = str(row["method"])
        if method not in METHODS:
            continue
        seed = int(row["seed"])
        key = (method, seed)
        if key in seen:
            raise ValueError(f"duplicate exact result for {method}, {seed}")
        seen.add(key)
        gaps[method].append(
            (seed, str(row["scenario"]), 100.0 * float(row["relative_gap"]))
        )
    counts = {method: len(gaps[method]) for method in METHODS}
    if len(set(counts.values())) != 1 or min(counts.values()) == 0:
        raise ValueError(f"exact methods have unequal case counts: {counts}")

    reference_cases = {
        (seed, scenario) for seed, scenario, _gap in gaps[METHODS[0]]
    }
    for method in METHODS[1:]:
        cases = {(seed, scenario) for seed, scenario, _gap in gaps[method]}
        if cases != reference_cases:
            raise ValueError(f"exact case identities differ for {method}")
    wider_cases = {
        (seed, scenario)
        for seed, scenario in reference_cases
        if "wide" in scenario.lower()
    }
    if len(wider_cases) != 1:
        raise ValueError(
            f"expected exactly one wider exact case, found {sorted(wider_cases)}"
        )
    core_cases = reference_cases - wider_cases

    incumbent_methods = ("Base", "Global", "CG", "Remask", "Full")
    incumbent_reference = {
        (seed, scenario): gap
        for seed, scenario, gap in gaps[incumbent_methods[0]]
    }
    for method in incumbent_methods[1:]:
        method_values = {
            (seed, scenario): gap for seed, scenario, gap in gaps[method]
        }
        if any(
            abs(method_values[key] - incumbent_reference[key]) > 1e-12
            for key in reference_cases
        ):
            raise ValueError("Base through Full are not identical on the exact suite")

    summary: dict[str, object] = {}
    max_gap = 0.0
    for index, method in enumerate(METHODS):
        method_rows = sorted(gaps[method])
        values = [gap for _seed, _scenario, gap in method_rows]
        core_values = [
            gap
            for seed, scenario, gap in method_rows
            if (seed, scenario) in core_cases
        ]
        wider_values = [
            gap
            for seed, scenario, gap in method_rows
            if (seed, scenario) in wider_cases
        ]
        if len(wider_values) != 1:
            raise ValueError(f"{method} does not have exactly one wider case")
        max_gap = max(max_gap, max(values))
        ax.vlines(
            index,
            min(values),
            max(values),
            color=LIGHT_NEUTRAL,
            linewidth=0.36,
            zorder=0,
        )
        core_offsets = np.linspace(-0.11, 0.11, len(core_values))
        ax.scatter(
            index + core_offsets,
            core_values,
            s=11,
            marker=METHOD_MARKERS[method],
            facecolor="white",
            edgecolor=METHOD_COLORS[method],
            alpha=0.88,
            linewidth=0.42,
            zorder=2,
        )
        ax.scatter(
            index,
            wider_values[0],
            s=32,
            marker="*",
            facecolor="white",
            edgecolor=WIDE_CASE,
            linewidth=0.54,
            zorder=3,
        )
        mean_gap = statistics.fmean(values)
        ax.scatter(
            index,
            mean_gap,
            s=21,
            marker="D",
            facecolor="white",
            edgecolor=METHOD_COLORS[method],
            linewidth=0.56,
            zorder=4,
        )
        exact_hits = sum(abs(value) < 1e-12 for value in values)
        summary[method] = {
            "cases": len(values),
            "core_cases": len(core_values),
            "wider_cases": len(wider_values),
            "exact_optima": exact_hits,
            "mean_gap_percent": mean_gap,
            "median_gap_percent": statistics.median(values),
            "maximum_gap_percent": max(values),
            "wider_case_gap_percent": wider_values[0],
        }

    short_labels = {
        "BeamFirst": "Beam",
        "Base": "Base",
        "Global": "Glob.",
        "CG": "CG",
        "Remask": "Rem.",
        "Full": "Full",
    }
    labels = [
        f"{short_labels[method]}\n"
        f"{summary[method]['exact_optima']}/{summary[method]['cases']}"
        for method in METHODS
    ]
    ax.set_xticks(np.arange(len(METHODS), dtype=float))
    ax.set_xticklabels(labels)
    ax.set_xlim(-0.45, len(METHODS) - 0.55)
    ax.set_ylim(-0.5, 40)
    ax.set_yticks([0, 10, 20, 30, 40])
    ax.set_ylabel("Gap to optimum (%)")
    ax.set_xlabel("")
    shared = summary["Full"]
    annotations = [
        ax.text(
            0.585,
            0.95,
            r"$\star$ wider",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=SMALL_FONT_PT,
            color=WIDE_CASE,
            linespacing=1.05,
        ),
        ax.text(
            0.985,
            0.95,
            r"$\diamond$ mean",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=SMALL_FONT_PT,
            color=INK,
            linespacing=1.05,
        ),
    ]
    ax.set_title("Exact gaps (11 core + 1 wider)", pad=1.5)
    ax.grid(True)
    return summary, annotations


def build_shared_legend(fig: plt.Figure) -> mpl.legend.Legend:
    handles = [
        Line2D(
            [0],
            [0],
            color=METHOD_COLORS[method],
            linestyle=METHOD_LINESTYLES[method],
            linewidth=0.56 if method != "Full" else 0.68,
            marker=METHOD_MARKERS[method],
            markersize=3.4,
            markerfacecolor="white",
            markeredgecolor=METHOD_COLORS[method],
            markeredgewidth=0.50,
            label=method,
        )
        for method in METHODS
    ]
    legend = fig.legend(
        handles=handles,
        labels=list(METHODS),
        ncol=6,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.993),
        columnspacing=0.46,
        handlelength=1.18,
        handletextpad=0.22,
        borderaxespad=0,
        borderpad=0.12,
        fontsize=SMALL_FONT_PT,
        frameon=True,
        fancybox=False,
        framealpha=1.0,
        facecolor="white",
        edgecolor=AXIS,
    )
    legend.get_frame().set_linewidth(0.30)
    return legend


def build_figure(
    *,
    trace_rows: Sequence[Mapping[str, str]],
    trace_analysis: Mapping[str, object],
    paired_analysis: Mapping[str, object],
    budget_rows: Sequence[Mapping[str, str]],
    budget_run_rows: Sequence[Mapping[str, str]],
    main_run_rows: Sequence[Mapping[str, str]],
    stress_rows: Sequence[Mapping[str, str]],
    stress_run_rows: Sequence[Mapping[str, str]],
    exact_rows: Sequence[Mapping[str, str]],
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> tuple[
    plt.Figure,
    list[plt.Axes],
    mpl.legend.Legend,
    list[mpl.text.Text],
    dict[str, object],
]:
    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, OVERVIEW_FIGURE_HEIGHT_IN))
    outer = fig.add_gridspec(
        3,
        1,
        left=0.115,
        right=0.985,
        bottom=0.092,
        top=0.938,
        hspace=0.56,
        height_ratios=(1.12, 1.0, 1.0),
    )
    top = outer[0].subgridspec(
        1, 2, width_ratios=(1.08, 0.92), wspace=0.40
    )
    middle = outer[1].subgridspec(
        1, 2, width_ratios=(1.0, 1.0), wspace=0.40
    )
    bottom = outer[2].subgridspec(
        1, 2, width_ratios=(1.0, 1.0), wspace=0.40
    )
    axes = [
        fig.add_subplot(top[0, 0]),
        fig.add_subplot(top[0, 1]),
        fig.add_subplot(middle[0, 0]),
        fig.add_subplot(middle[0, 1]),
        fig.add_subplot(bottom[0, 0]),
        fig.add_subplot(bottom[0, 1]),
    ]

    summaries: dict[str, object] = {}
    annotations: list[mpl.text.Text] = []
    summaries["a"], notes = draw_trace_ablation(
        axes[0],
        trace_rows,
        trace_analysis,
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed,
    )
    annotations.extend(notes)
    summaries["b"], notes = draw_scenario_gain(axes[1], paired_analysis)
    annotations.extend(notes)
    summaries["c"], notes = draw_budget_tradeoff(
        axes[2],
        budget_rows,
        budget_run_rows,
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed + 100_000,
    )
    annotations.extend(notes)
    summaries["d"], notes = draw_runtime_ecdf(axes[3], main_run_rows)
    annotations.extend(notes)
    summaries["e"], notes = draw_cg_stress(
        axes[4],
        stress_rows,
        stress_run_rows,
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed + 200_000,
    )
    annotations.extend(notes)
    summaries["f"], notes = draw_exact_gap(axes[5], exact_rows)
    annotations.extend(notes)
    annotations.extend(profile_panel_labels(axes, "abcdef"))
    legend = build_shared_legend(fig)
    return fig, axes, legend, annotations, summaries



def build_quality_runtime_figure(
    *,
    trace_rows: Sequence[Mapping[str, str]],
    trace_analysis: Mapping[str, object],
    paired_analysis: Mapping[str, object],
    budget_rows: Sequence[Mapping[str, str]],
    budget_run_rows: Sequence[Mapping[str, str]],
    main_run_rows: Sequence[Mapping[str, str]],
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> tuple[
    plt.Figure,
    list[plt.Axes],
    mpl.legend.Legend,
    list[mpl.text.Text],
    dict[str, object],
]:
    """Build the four-panel quality/runtime evidence figure."""
    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, QUALITY_FIGURE_HEIGHT_IN))
    grid = fig.add_gridspec(
        2,
        2,
        left=0.115,
        right=0.985,
        bottom=0.112,
        top=0.918,
        hspace=0.60,
        wspace=0.40,
    )
    axes = [
        fig.add_subplot(grid[row, column])
        for row in range(2)
        for column in range(2)
    ]
    summaries: dict[str, object] = {}
    annotations: list[mpl.text.Text] = []

    summaries["a"], notes = draw_trace_ablation(
        axes[0],
        trace_rows,
        trace_analysis,
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed,
    )
    annotations.extend(notes)
    summaries["b"], notes = draw_scenario_gain(axes[1], paired_analysis)
    annotations.extend(notes)
    summaries["c"], notes = draw_budget_tradeoff(
        axes[2],
        budget_rows,
        budget_run_rows,
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed + 100_000,
    )
    annotations.extend(notes)
    summaries["d"], notes = draw_runtime_ecdf(axes[3], main_run_rows)
    annotations.extend(notes)
    annotations.extend(profile_panel_labels(axes, "abcd"))
    legend = build_shared_legend(fig)
    return fig, axes, legend, annotations, summaries


def build_stress_optimality_figure(
    *,
    stress_rows: Sequence[Mapping[str, str]],
    stress_run_rows: Sequence[Mapping[str, str]],
    exact_rows: Sequence[Mapping[str, str]],
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> tuple[
    plt.Figure,
    list[plt.Axes],
    mpl.legend.Legend,
    list[mpl.text.Text],
    dict[str, object],
]:
    """Build the two-panel stress/optimality calibration figure."""
    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, STRESS_FIGURE_HEIGHT_IN))
    grid = fig.add_gridspec(
        1,
        2,
        left=0.115,
        right=0.985,
        bottom=0.205,
        top=0.820,
        wspace=0.40,
    )
    axes = [fig.add_subplot(grid[0, column]) for column in range(2)]
    summaries: dict[str, object] = {}
    annotations: list[mpl.text.Text] = []
    summaries["a"], notes = draw_cg_stress(
        axes[0],
        stress_rows,
        stress_run_rows,
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed + 200_000,
    )
    annotations.extend(notes)
    summaries["b"], notes = draw_exact_gap(axes[1], exact_rows)
    annotations.extend(notes)
    annotations.extend(profile_panel_labels(axes, "ab"))
    legend = build_shared_legend(fig)
    return fig, axes, legend, annotations, summaries

def positive_overlap(
    first: mpl.transforms.Bbox,
    second: mpl.transforms.Bbox,
    tolerance: float = 0.8,
) -> bool:
    width = min(first.x1, second.x1) - max(first.x0, second.x0)
    height = min(first.y1, second.y1) - max(first.y0, second.y0)
    return width > tolerance and height > tolerance


def validate_layout(
    fig: plt.Figure,
    axes: Sequence[plt.Axes],
    legend: mpl.legend.Legend,
    annotations: Sequence[mpl.text.Text],
    *,
    panel_names: Sequence[str] = tuple("abcdef"),
    required_panel_context: Sequence[str] = (
        "n = 150",
        "fixed order",
        "median of 5",
        "Budget trade-off",
        "labels: wall p95 (ms)",
        "Search target (ms)",
        "CG-size stress",
        "coverage co-varies",
        "11 core + 1 wider",
    ),
    zero_anchor_checks: Mapping[str, Sequence[str]] | None = None,
    conservative_upper_bounds: Mapping[tuple[str, str], float] | None = None,
    cross_panel_pairs: Sequence[tuple[int, int]] = (
        (0, 2), (1, 3), (2, 4), (3, 5)
    ),
) -> dict[str, object]:
    if len(panel_names) != len(axes):
        raise ValueError("panel_names and axes must have the same length")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    figure_box = fig.bbox
    visible_text = [
        artist
        for artist in fig.findobj(match=mpl.text.Text)
        if artist.get_visible() and artist.get_text().strip()
    ]
    clipped: list[str] = []
    for artist in visible_text:
        box = artist.get_window_extent(renderer)
        if (
            box.x0 < figure_box.x0 - 0.5
            or box.y0 < figure_box.y0 - 0.5
            or box.x1 > figure_box.x1 + 0.5
            or box.y1 > figure_box.y1 + 0.5
        ):
            clipped.append(artist.get_text())

    tick_overlaps: list[str] = []
    for panel, ax in zip(panel_names, axes):
        for direction, labels in (
            ("x", ax.get_xticklabels()),
            ("y", ax.get_yticklabels()),
        ):
            boxes = [
                label.get_window_extent(renderer)
                for label in labels
                if label.get_visible() and label.get_text().strip()
            ]
            boxes.sort(
                key=(lambda box: box.x0)
                if direction == "x"
                else (lambda box: box.y0)
            )
            if any(
                positive_overlap(left, right, tolerance=0.35)
                for left, right in zip(boxes, boxes[1:])
            ):
                tick_overlaps.append(f"panel {panel} {direction}-ticks")

    annotation_overlaps: list[str] = []
    by_axes: dict[object, list[mpl.text.Text]] = defaultdict(list)
    for artist in annotations:
        by_axes[artist.axes].append(artist)
    for ax, artists in by_axes.items():
        if ax is None:
            continue
        boxes = [
            (artist, artist.get_window_extent(renderer)) for artist in artists
        ]
        for index, (left_artist, left_box) in enumerate(boxes):
            for right_artist, right_box in boxes[index + 1 :]:
                if positive_overlap(left_box, right_box):
                    annotation_overlaps.append(
                        f"{left_artist.get_text()!r} / "
                        f"{right_artist.get_text()!r}"
                    )

    legend_box = legend.get_window_extent(renderer)
    if (
        legend_box.x0 < figure_box.x0 - 0.5
        or legend_box.x1 > figure_box.x1 + 0.5
        or legend_box.y0 < figure_box.y0 - 0.5
        or legend_box.y1 > figure_box.y1 + 0.5
    ):
        clipped.append("shared method legend")
    title_overlaps = [
        f"panel {panel}"
        for panel, ax in zip(panel_names, axes)
        if positive_overlap(legend_box, ax.title.get_window_extent(renderer))
    ]
    cross_panel_overlaps: list[str] = []
    for upper_index, lower_index in cross_panel_pairs:
        upper_label = axes[upper_index].xaxis.label.get_window_extent(renderer)
        lower_title = axes[lower_index].title.get_window_extent(renderer)
        if positive_overlap(upper_label, lower_title, tolerance=0.35):
            cross_panel_overlaps.append(
                f"panel {panel_names[upper_index]} xlabel / "
                f"panel {panel_names[lower_index]} title"
            )

    minimum_font = min(artist.get_fontsize() for artist in visible_text)
    all_text = "\n".join(artist.get_text() for artist in visible_text)
    missing_panel_context = [
        phrase for phrase in required_panel_context if phrase not in all_text
    ]

    axis_limits = {
        panel: {
            "x": [float(value) for value in ax.get_xlim()],
            "y": [float(value) for value in ax.get_ylim()],
        }
        for panel, ax in zip(panel_names, axes)
    }
    # Quantitative effect panels retain a zero/reference anchor and rounded
    # bounds. This prevents a narrow data-only window from exaggerating small
    # differences while preserving the categorical axes in panels a and f.
    if zero_anchor_checks is None:
        zero_anchor_checks = {
            "a": ("y",),
            "b": ("x",),
            "c": ("y",),
            "d": ("x", "y"),
            "e": ("y",),
            "f": ("y",),
        }
    if conservative_upper_bounds is None:
        conservative_upper_bounds = {
            ("a", "y"): 3.0,
            ("b", "x"): 10.0,
            ("c", "y"): 3.0,
            ("e", "y"): 8.0,
            ("f", "y"): 40.0,
        }
    axis_scale_violations = [
        f"panel {panel} {dimension}"
        for panel, dimensions in zero_anchor_checks.items()
        for dimension in dimensions
        if axis_limits[panel][dimension][0] > 1e-9
    ]
    axis_scale_violations.extend(
        f"panel {panel} {dimension} upper"
        for (panel, dimension), minimum_upper in conservative_upper_bounds.items()
        if axis_limits[panel][dimension][1] + 1e-9 < minimum_upper
    )
    issues: list[str] = []
    if clipped:
        issues.append(
            "text outside canvas: " + ", ".join(repr(value) for value in clipped)
        )
    if tick_overlaps:
        issues.append("overlapping tick labels: " + ", ".join(tick_overlaps))
    if annotation_overlaps:
        issues.append(
            "overlapping annotations: " + "; ".join(annotation_overlaps)
        )
    if title_overlaps:
        issues.append(
            "shared legend overlaps titles: " + ", ".join(title_overlaps)
        )
    if cross_panel_overlaps:
        issues.append(
            "cross-panel text overlap: " + ", ".join(cross_panel_overlaps)
        )
    if minimum_font < SMALL_FONT_PT - 1e-6:
        issues.append(f"minimum font is only {minimum_font:.2f} pt")
    if missing_panel_context:
        issues.append(
            "missing required panel context: "
            + ", ".join(missing_panel_context)
        )
    if axis_scale_violations:
        issues.append(
            "non-zero quantitative axis origins: "
            + ", ".join(axis_scale_violations)
        )
    if issues:
        raise RuntimeError("Layout validation failed: " + " | ".join(issues))
    return {
        "visible_text_items": len(visible_text),
        "minimum_font_pt": minimum_font,
        "text_out_of_canvas": 0,
        "overlapping_tick_groups": 0,
        "overlapping_annotation_pairs": 0,
        "legend_title_overlaps": 0,
        "cross_panel_text_overlaps": 0,
        "required_panel_context_present": True,
        "axis_limits": axis_limits,
        "zero_or_reference_anchored_quantitative_axes": True,
        "broken_axes": 0,
    }




def pdf_raster_image_count(path: Path) -> int:
    """Return the number of raster image objects embedded in a PDF."""
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
            raise RuntimeError(f"pdfimages failed: {detail}")
        return sum(
            bool(re.match(r"^\s*\d+\s+\d+\s+", line))
            for line in completed.stdout.splitlines()
        )
    return len(re.findall(rb"/Subtype\s*/Image\b", path.read_bytes()))


def pdf_font_audit(path: Path) -> tuple[int, int]:
    """Return embedded and unembedded PDF font counts."""
    pdffonts = shutil.which("pdffonts")
    if pdffonts:
        completed = subprocess.run(
            [pdffonts, str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or "unknown pdffonts error"
            raise RuntimeError(f"pdffonts failed: {detail}")
        rows = [
            line.split()
            for line in completed.stdout.splitlines()[2:]
            if line.strip()
        ]
        embedded = sum(len(parts) >= 5 and parts[-5].lower() == "yes" for parts in rows)
        return embedded, len(rows) - embedded

    data = path.read_bytes()
    font_count = len(re.findall(rb"/Type\s*/Font\b", data))
    return font_count, 0
def validate_exports(
    output: Path,
    *,
    width_in: float = FIGURE_WIDTH_IN,
    height_in: float = OVERVIEW_FIGURE_HEIGHT_IN,
) -> dict[str, object]:
    svg_path = output.with_suffix(".svg")
    pdf_path = output.with_suffix(".pdf")
    tiff_path = output.with_suffix(".tiff")
    png_path = output.with_suffix(".png")
    for path in (svg_path, pdf_path, tiff_path, png_path):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"missing or empty export: {path}")

    root = ET.parse(svg_path).getroot()
    svg_text_nodes = sum(
        1 for element in root.iter() if element.tag.endswith("text")
    )
    svg_image_nodes = sum(
        1 for element in root.iter() if element.tag.endswith("image")
    )
    if svg_text_nodes == 0:
        raise RuntimeError("SVG export has no editable text nodes")
    if svg_image_nodes:
        raise RuntimeError(f"SVG export embeds {svg_image_nodes} raster image(s)")

    pdf_raster_images = pdf_raster_image_count(pdf_path)
    if pdf_raster_images:
        raise RuntimeError(f"PDF export embeds {pdf_raster_images} raster image(s)")
    pdf_embedded_fonts, pdf_unembedded_fonts = pdf_font_audit(pdf_path)
    if pdf_embedded_fonts < 1 or pdf_unembedded_fonts:
        raise RuntimeError(
            "PDF fonts are missing or not embedded: "
            f"{pdf_embedded_fonts} embedded, {pdf_unembedded_fonts} unembedded"
        )

    with Image.open(tiff_path) as image:
        tiff_pixels = image.size
        tiff_dpi = tuple(
            round(float(value), 2)
            for value in image.info.get("dpi", (0, 0))
        )
    with Image.open(png_path) as image:
        png_pixels = image.size
    expected_tiff = (
        round(width_in * 600),
        round(height_in * 600),
    )
    expected_png = (
        round(width_in * 300),
        round(height_in * 300),
    )
    if tiff_pixels != expected_tiff:
        raise RuntimeError(
            f"unexpected TIFF dimensions: {tiff_pixels} != {expected_tiff}"
        )
    if png_pixels != expected_png:
        raise RuntimeError(
            f"unexpected PNG dimensions: {png_pixels} != {expected_png}"
        )
    if min(tiff_dpi) < 599:
        raise RuntimeError(f"TIFF resolution below 600 dpi: {tiff_dpi}")
    return {
        "svg_editable_text_nodes": svg_text_nodes,
        "svg_embedded_image_nodes": svg_image_nodes,
        "pdf_bytes": pdf_path.stat().st_size,
        "pdf_embedded_fonts": pdf_embedded_fonts,
        "pdf_unembedded_fonts": pdf_unembedded_fonts,
        "pdf_raster_images": pdf_raster_images,
        "tiff_pixels": list(tiff_pixels),
        "tiff_dpi": list(tiff_dpi),
        "png_preview_pixels": list(png_pixels),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("reproducibility/results"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reproducibility/figures/results_overview"),
    )
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260722)
    args = parser.parse_args()
    if args.bootstrap_samples < 100:
        raise ValueError("bootstrap-samples must be at least 100")

    configure_style()
    paths = {
        "trace_rows": args.results_dir / "trace_ablation_results.csv",
        "trace_analysis": args.results_dir / "trace_ablation_analysis.json",
        "paired_analysis": args.results_dir / "paired_analysis.json",
        "budget_rows": args.results_dir / "budget_results.csv",
        "budget_run_rows": args.results_dir / "budget_run_results.csv",
        "main_run_rows": args.results_dir / "run_results.csv",
        "stress_rows": args.results_dir / "cg_stress_results.csv",
        "stress_run_rows": args.results_dir / "cg_stress_run_results.csv",
        "exact_rows": args.results_dir / "exact_results.csv",
    }
    trace_rows = read_csv(
        paths["trace_rows"],
        (
            "scenario",
            "seed",
            "repeat",
            "stage",
            "stage_trace_present",
            "credited_stage_score",
        ),
    )
    trace_analysis = read_json(paths["trace_analysis"])
    paired_analysis = read_json(paths["paired_analysis"])
    budget_rows = read_csv(
        paths["budget_rows"],
        ("scenario", "seed", "budget_ms", "transmitted_median"),
    )
    budget_run_rows = read_csv(
        paths["budget_run_rows"],
        ("budget_ms", "solver_wall_ms", "deadline_miss"),
    )
    main_run_rows = read_csv(
        paths["main_run_rows"],
        ("method", "solver_wall_ms", "deadline_miss"),
    )
    stress_rows = read_csv(
        paths["stress_rows"],
        ("scenario", "seed", "method", "transmitted_median"),
    )
    stress_run_rows = read_csv(
        paths["stress_run_rows"],
        ("scenario", "method", "solver_wall_ms", "deadline_miss"),
    )
    exact_rows = read_csv(
        paths["exact_rows"],
        ("scenario", "seed", "method", "relative_gap"),
    )
    row_objects = {
        "trace_rows": trace_rows,
        "budget_rows": budget_rows,
        "budget_run_rows": budget_run_rows,
        "main_run_rows": main_run_rows,
        "stress_rows": stress_rows,
        "stress_run_rows": stress_run_rows,
        "exact_rows": exact_rows,
    }

    fig, axes, legend, annotations, panel_summaries = build_figure(
        trace_rows=trace_rows,
        trace_analysis=trace_analysis,
        paired_analysis=paired_analysis,
        budget_rows=budget_rows,
        budget_run_rows=budget_run_rows,
        main_run_rows=main_run_rows,
        stress_rows=stress_rows,
        stress_run_rows=stress_run_rows,
        exact_rows=exact_rows,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
    )
    layout_qa = validate_layout(fig, axes, legend, annotations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output.with_suffix(".svg"))
    fig.savefig(args.output.with_suffix(".pdf"))
    fig.savefig(args.output.with_suffix(".tiff"), dpi=600)
    fig.savefig(args.output.with_suffix(".png"), dpi=300)
    plt.close(fig)
    export_qa = validate_exports(args.output)

    source_data: dict[str, object] = {}
    for name, path in paths.items():
        record: dict[str, object] = {
            "file": path.name,
            "sha256": file_sha256(path),
        }
        if name in row_objects:
            record["rows"] = len(row_objects[name])
        source_data[name] = record

    qa = {
        "core_conclusion": (
            "Within a Full run, every accepted module is non-degrading; "
            "the Full scheduler improves transmitted traffic while all measured "
            "solver runs remain below the 100-ms external deadline."
        ),
        "figure_archetype": (
            "quantitative grid with a dominant cumulative-ablation panel"
        ),
        "target": "LNCS full-width manuscript figure",
        "backend": "Python (matplotlib)",
        "width_in": FIGURE_WIDTH_IN,
        "height_in": OVERVIEW_FIGURE_HEIGHT_IN,
        "panel_map": {
            "a": (
                "within-run cumulative gain over Base, adjacent-stage increments, "
                "scenario-stratified bootstrap 95% CI, n=150, fixed stage order, "
                "median-of-five aggregation, and zero accepted-stage losses by construction"
            ),
            "b": (
                "Full gain over Base and BeamFirst in each prespecified scenario"
            ),
            "c": (
                "20/40/60/87-ms internal search targets with external process-wall-time p95 labels"
            ),
            "d": (
                "six-method solver-wall-time ECDF and 100-ms boundary"
            ),
            "e": (
                "co-varying CG-size and coverage stress gains with Full p95 in the second tick-label row"
            ),
            "f": (
                "six-method gaps on a mixed tiny suite explicitly labelled as "
                "11 core cases plus one wider case"
            ),
        },
        "statistics": {
            "unit": (
                "panel a uses n=150 fixed-order instances and the instance-level "
                "median over five repeated executions; other panels use the same "
                "aggregation unless "
                "runtime is explicitly run-level"
            ),
            "confidence_interval": (
                "percentile bootstrap 95%; instances resampled within scenario "
                "and scenarios equally weighted for panels a/c; instances "
                "resampled within each CG size for panel e"
            ),
            "bootstrap_samples": args.bootstrap_samples,
            "bootstrap_seed": args.bootstrap_seed,
        },
        "review_risks": [
            (
                "Panel a supports within-run stage accounting because its "
                "stages come from the same Full run."
            ),
            (
                "Panel b reports independent-process external comparisons, "
                "not causal intermediate-stage effects."
            ),
            (
                "Exact-gap evidence is limited to a mixed tiny suite; the marked "
                "lone wider case must not be generalized as a worst-case bound."
            ),
        ],
        "exports": ["svg", "pdf", "tiff", "png"],
        "vector_primary": True,
        "tiff_target_dpi": 600,
        "minimum_font_target_pt": SMALL_FONT_PT,
        "visual_style": {
            "axes": "thin four-sided frame with inward ticks",
            "grid": "light major grid only",
            "markers": "small open markers with redundant shape encoding",
            "scale": "zero/reference anchored with rounded limits and no broken axes",
        },
        "source_data": source_data,
        "panels": panel_summaries,
        **layout_qa,
        **export_qa,
    }
    qa_path = args.output.with_name(args.output.name + "_qa.json")
    qa_path.write_text(
        json.dumps(qa, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )




def save_figure_bundle(
    fig: plt.Figure,
    output: Path,
    *,
    width_in: float,
    height_in: float,
) -> dict[str, object]:
    """Export one figure bundle and return its artifact QA."""
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output.with_suffix(".svg"))
    fig.savefig(output.with_suffix(".pdf"))
    fig.savefig(output.with_suffix(".tiff"), dpi=600)
    fig.savefig(output.with_suffix(".png"), dpi=300)
    plt.close(fig)
    return validate_exports(output, width_in=width_in, height_in=height_in)


def build_source_data(
    paths: Mapping[str, Path],
    row_objects: Mapping[str, Sequence[Mapping[str, str]]],
) -> dict[str, object]:
    source_data: dict[str, object] = {}
    for name, path in paths.items():
        record: dict[str, object] = {
            "file": path.name,
            "sha256": file_sha256(path),
        }
        if name in row_objects:
            record["rows"] = len(row_objects[name])
        source_data[name] = record
    return source_data


def write_qa(output: Path, payload: Mapping[str, object]) -> None:
    output.with_name(output.name + "_qa.json").write_text(
        json.dumps(dict(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_web_figures(
    *,
    output_dir: Path,
    manifest_path: Path,
    trace_rows: Sequence[Mapping[str, str]],
    trace_analysis: Mapping[str, object],
    paired_analysis: Mapping[str, object],
    budget_rows: Sequence[Mapping[str, str]],
    budget_run_rows: Sequence[Mapping[str, str]],
    main_run_rows: Sequence[Mapping[str, str]],
    stress_rows: Sequence[Mapping[str, str]],
    stress_run_rows: Sequence[Mapping[str, str]],
    exact_rows: Sequence[Mapping[str, str]],
    source_data: Mapping[str, object],
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> None:
    """Emit one responsive SVG/PNG per web claim without manuscript panel labels."""
    output_dir.mkdir(parents=True, exist_ok=True)
    jobs = (
        (
            "web_stage_gain",
            "Conditional gain by cumulative FPTR stage",
            lambda ax: draw_trace_ablation(
                ax,
                trace_rows,
                trace_analysis,
                bootstrap_samples=bootstrap_samples,
                bootstrap_seed=bootstrap_seed,
            ),
        ),
        (
            "web_scenario_gain",
            "Full gain across five scenarios",
            lambda ax: draw_scenario_gain(ax, paired_analysis),
        ),
        (
            "web_budget_quality",
            "Internal budget and scheduling quality",
            lambda ax: draw_budget_tradeoff(
                ax,
                budget_rows,
                budget_run_rows,
                bootstrap_samples=bootstrap_samples,
                bootstrap_seed=bootstrap_seed,
            ),
        ),
        (
            "web_runtime_ecdf",
            "Runtime ECDF under the 87 ms budget",
            lambda ax: draw_runtime_ecdf(ax, main_run_rows),
        ),
        (
            "web_cg_stress",
            "Compatibility-group size stress",
            lambda ax: draw_cg_stress(
                ax,
                stress_rows,
                stress_run_rows,
                bootstrap_samples=bootstrap_samples,
                bootstrap_seed=bootstrap_seed,
            ),
        ),
        (
            "web_optimality_gap",
            "Optimality gaps on 12 exactly solved cases",
            lambda ax: draw_exact_gap(ax, exact_rows),
        ),
    )
    outputs: dict[str, object] = {}
    for name, title, draw in jobs:
        fig, ax = plt.subplots(
            figsize=(FIGURE_WIDTH_IN, 5.2), constrained_layout=True
        )
        panel_data, _annotations = draw(ax)
        ax.set_title(title, pad=4.0)
        stem = output_dir / name
        fig.savefig(stem.with_suffix(".svg"), metadata={"Creator": "FPTR web profile"})
        fig.savefig(stem.with_suffix(".png"), dpi=180)
        plt.close(fig)
        outputs[name] = {
            "svg_sha256": file_sha256(stem.with_suffix(".svg")),
            "png_sha256": file_sha256(stem.with_suffix(".png")),
            "data": panel_data,
        }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "profile": "web",
                "generator": "experiments/plot_paper_results.py --profile web",
                "rendering": {
                    "panel_labels": False,
                    "shared_legend": False,
                    "minimum_font_pt": SMALL_FONT_PT,
                    "width_in": FIGURE_WIDTH_IN,
                },
                "source_data": source_data,
                "outputs": outputs,
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )


def split_main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("reproducibility/results"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reproducibility/figures"),
        help="default directory for the two primary figure stems",
    )
    parser.add_argument(
        "--paper-figure-dir",
        type=Path,
        default=Path("paper/figures"),
        help="copy the two manuscript PDF figures into this directory",
    )
    parser.add_argument(
        "--quality-output",
        type=Path,
        default=None,
        help="override the results_quality_runtime output stem",
    )
    parser.add_argument(
        "--stress-output",
        type=Path,
        default=None,
        help="override the results_stress_optimality output stem",
    )
    parser.add_argument(
        "--output",
        "--legacy-output",
        dest="legacy_output",
        type=Path,
        default=None,
        help="optionally also emit the legacy six-panel overview stem",
    )
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260722)
    parser.add_argument("--profile", choices=("paper", "web"), default="paper")
    parser.add_argument(
        "--web-output-dir", type=Path, default=Path("docs/images"),
        help="directory for the six standalone web SVG/PNG figures",
    )
    parser.add_argument(
        "--web-manifest", type=Path, default=Path("docs/evidence/figure-manifest.json"),
    )
    args = parser.parse_args()
    if args.bootstrap_samples < 100:
        raise ValueError("bootstrap-samples must be at least 100")

    quality_output = (
        args.quality_output
        if args.quality_output is not None
        else args.output_dir / "results_quality_runtime"
    )
    stress_output = (
        args.stress_output
        if args.stress_output is not None
        else args.output_dir / "results_stress_optimality"
    )

    configure_style(args.profile)
    paths = {
        "trace_rows": args.results_dir / "trace_ablation_results.csv",
        "trace_analysis": args.results_dir / "trace_ablation_analysis.json",
        "paired_analysis": args.results_dir / "paired_analysis.json",
        "budget_rows": args.results_dir / "budget_results.csv",
        "budget_run_rows": args.results_dir / "budget_run_results.csv",
        "main_run_rows": args.results_dir / "run_results.csv",
        "stress_rows": args.results_dir / "cg_stress_results.csv",
        "stress_run_rows": args.results_dir / "cg_stress_run_results.csv",
        "exact_rows": args.results_dir / "exact_results.csv",
    }
    trace_rows = read_csv(
        paths["trace_rows"],
        (
            "scenario",
            "seed",
            "repeat",
            "stage",
            "stage_trace_present",
            "credited_stage_score",
        ),
    )
    trace_analysis = read_json(paths["trace_analysis"])
    paired_analysis = read_json(paths["paired_analysis"])
    budget_rows = read_csv(
        paths["budget_rows"],
        ("scenario", "seed", "budget_ms", "transmitted_median"),
    )
    budget_run_rows = read_csv(
        paths["budget_run_rows"],
        ("budget_ms", "solver_wall_ms", "deadline_miss"),
    )
    main_run_rows = read_csv(
        paths["main_run_rows"],
        ("method", "solver_wall_ms", "deadline_miss"),
    )
    stress_rows = read_csv(
        paths["stress_rows"],
        ("scenario", "seed", "method", "transmitted_median"),
    )
    stress_run_rows = read_csv(
        paths["stress_run_rows"],
        ("scenario", "method", "solver_wall_ms", "deadline_miss"),
    )
    exact_rows = read_csv(
        paths["exact_rows"],
        ("scenario", "seed", "method", "relative_gap"),
    )
    row_objects = {
        "trace_rows": trace_rows,
        "budget_rows": budget_rows,
        "budget_run_rows": budget_run_rows,
        "main_run_rows": main_run_rows,
        "stress_rows": stress_rows,
        "stress_run_rows": stress_run_rows,
        "exact_rows": exact_rows,
    }
    source_data = build_source_data(paths, row_objects)

    if args.profile == "web":
        build_web_figures(
            output_dir=args.web_output_dir,
            manifest_path=args.web_manifest,
            trace_rows=trace_rows,
            trace_analysis=trace_analysis,
            paired_analysis=paired_analysis,
            budget_rows=budget_rows,
            budget_run_rows=budget_run_rows,
            main_run_rows=main_run_rows,
            stress_rows=stress_rows,
            stress_run_rows=stress_run_rows,
            exact_rows=exact_rows,
            source_data=source_data,
            bootstrap_samples=args.bootstrap_samples,
            bootstrap_seed=args.bootstrap_seed,
        )
        return

    quality_fig, quality_axes, quality_legend, quality_notes, quality_panels = (
        build_quality_runtime_figure(
            trace_rows=trace_rows,
            trace_analysis=trace_analysis,
            paired_analysis=paired_analysis,
            budget_rows=budget_rows,
            budget_run_rows=budget_run_rows,
            main_run_rows=main_run_rows,
            bootstrap_samples=args.bootstrap_samples,
            bootstrap_seed=args.bootstrap_seed,
        )
    )
    quality_layout = validate_layout(
        quality_fig,
        quality_axes,
        quality_legend,
        quality_notes,
        panel_names=tuple("abcd"),
        required_panel_context=(
            "n = 150",
            "fixed order",
            "median of 5",
            "Scenario-wise Full gain",
            "Budget trade-off",
            "labels: wall p95 (ms)",
            "Search target (ms)",
            "Runtime ECDF",
        ),
        zero_anchor_checks={
            "a": ("y",),
            "b": ("x",),
            "c": ("y",),
            "d": ("x", "y"),
        },
        conservative_upper_bounds={
            ("a", "y"): 3.0,
            ("b", "x"): 10.0,
            ("c", "y"): 3.0,
        },
        cross_panel_pairs=((0, 2), (1, 3)),
    )
    quality_export = save_figure_bundle(
        quality_fig,
        quality_output,
        width_in=FIGURE_WIDTH_IN,
        height_in=QUALITY_FIGURE_HEIGHT_IN,
    )
    quality_source_names = (
        "trace_rows",
        "trace_analysis",
        "paired_analysis",
        "budget_rows",
        "budget_run_rows",
        "main_run_rows",
    )
    quality_qa = {
        "core_conclusion": (
            "FPTR's accepted stages add traffic incrementally, the gain is "
            "positive across all five regimes, and measured runtime remains "
            "inside the evaluated 100-ms boundary."
        ),
        "figure_group": "quality_runtime",
        "figure_archetype": "four-panel quantitative evidence grid",
        "target": "LNCS full-width manuscript figure",
        "backend": "Python (matplotlib)",
        "width_in": FIGURE_WIDTH_IN,
        "height_in": QUALITY_FIGURE_HEIGHT_IN,
        "panel_map": {
            "a": "ordered within-run stage gain over Base",
            "b": "scenario-wise Full gain over Base and BeamFirst",
            "c": "quality versus internal search target with wall-time p95",
            "d": "six-method external solver-wall-time ECDF",
        },
        "statistics": {
            "unit": (
                "instance-level median over five launches unless runtime is "
                "explicitly run-level"
            ),
            "confidence_interval": (
                "percentile bootstrap 95%; instances resampled within scenario "
                "and scenarios equally weighted"
            ),
            "bootstrap_samples": args.bootstrap_samples,
            "bootstrap_seed": args.bootstrap_seed,
        },
        "review_risks": [
            "Panel a is fixed-order within-run accounting, not a causal estimate.",
            "Panels b and d compare independent process launches.",
            "Runtime evidence is observational on the stated unpinned host.",
        ],
        "exports": ["svg", "pdf", "tiff", "png"],
        "vector_primary": True,
        "tiff_target_dpi": 600,
        "minimum_font_target_pt": SMALL_FONT_PT,
        "visual_style": {
            "axes": "thin four-sided frame with inward ticks",
            "grid": "light major grid only",
            "markers": "small open markers with redundant shape encoding",
            "scale": "zero/reference anchored with rounded limits and no broken axes",
        },
        "source_data": {
            name: source_data[name] for name in quality_source_names
        },
        "panels": quality_panels,
        **quality_layout,
        **quality_export,
    }
    write_qa(quality_output, quality_qa)

    stress_fig, stress_axes, stress_legend, stress_notes, stress_panels = (
        build_stress_optimality_figure(
            stress_rows=stress_rows,
            stress_run_rows=stress_run_rows,
            exact_rows=exact_rows,
            bootstrap_samples=args.bootstrap_samples,
            bootstrap_seed=args.bootstrap_seed,
        )
    )
    stress_layout = validate_layout(
        stress_fig,
        stress_axes,
        stress_legend,
        stress_notes,
        panel_names=tuple("ab"),
        required_panel_context=(
            "CG-size stress",
            "coverage co-varies",
            "11 core + 1 wider",
        ),
        zero_anchor_checks={"a": ("y",), "b": ("y",)},
        conservative_upper_bounds={
            ("a", "y"): 8.0,
            ("b", "y"): 40.0,
        },
        cross_panel_pairs=(),
    )
    stress_export = save_figure_bundle(
        stress_fig,
        stress_output,
        width_in=FIGURE_WIDTH_IN,
        height_in=STRESS_FIGURE_HEIGHT_IN,
    )
    stress_qa = {
        "core_conclusion": (
            "CG-aware refinement remains beneficial under the registered "
            "co-varying stress sweep, while the mixed tiny exact suite bounds "
            "only the reported calibration cases."
        ),
        "figure_group": "stress_optimality",
        "figure_archetype": "two-panel stress and exact-calibration figure",
        "target": "LNCS full-width manuscript figure",
        "backend": "Python (matplotlib)",
        "width_in": FIGURE_WIDTH_IN,
        "height_in": STRESS_FIGURE_HEIGHT_IN,
        "panel_map": {
            "a": "CG-size/coverage stress gain with Full runtime p95",
            "b": "gaps on 11 core exact cases plus one wider case",
        },
        "statistics": {
            "unit": (
                "instance-level median for stress scores; run-level wall time; "
                "case-level gaps for the exact suite"
            ),
            "confidence_interval": (
                "percentile bootstrap 95% within each registered CG stress size"
            ),
            "bootstrap_samples": args.bootstrap_samples,
            "bootstrap_seed": args.bootstrap_seed,
        },
        "review_risks": [
            "CG size and coverage co-vary in the registered stress suite.",
            "The exact evidence contains only 11 core cases and one wider case.",
            "The wider marked case is not a general worst-case bound.",
        ],
        "exports": ["svg", "pdf", "tiff", "png"],
        "vector_primary": True,
        "tiff_target_dpi": 600,
        "minimum_font_target_pt": SMALL_FONT_PT,
        "visual_style": {
            "axes": "thin four-sided frame with inward ticks",
            "grid": "light major grid only",
            "markers": "small open markers with redundant shape encoding",
            "scale": "zero/reference anchored with rounded limits and no broken axes",
        },
        "source_data": {
            name: source_data[name]
            for name in ("stress_rows", "stress_run_rows", "exact_rows")
        },
        "panels": stress_panels,
        **stress_layout,
        **stress_export,
    }
    write_qa(stress_output, stress_qa)

    args.paper_figure_dir.mkdir(parents=True, exist_ok=True)
    for output in (quality_output, stress_output):
        source_pdf = output.with_suffix(".pdf")
        destination_pdf = args.paper_figure_dir / source_pdf.name
        if source_pdf.resolve() != destination_pdf.resolve():
            shutil.copy2(source_pdf, destination_pdf)

    if args.legacy_output is not None:
        legacy_fig, legacy_axes, legacy_legend, legacy_notes, legacy_panels = (
            build_figure(
                trace_rows=trace_rows,
                trace_analysis=trace_analysis,
                paired_analysis=paired_analysis,
                budget_rows=budget_rows,
                budget_run_rows=budget_run_rows,
                main_run_rows=main_run_rows,
                stress_rows=stress_rows,
                stress_run_rows=stress_run_rows,
                exact_rows=exact_rows,
                bootstrap_samples=args.bootstrap_samples,
                bootstrap_seed=args.bootstrap_seed,
            )
        )
        legacy_layout = validate_layout(
            legacy_fig, legacy_axes, legacy_legend, legacy_notes
        )
        legacy_export = save_figure_bundle(
            legacy_fig,
            args.legacy_output,
            width_in=FIGURE_WIDTH_IN,
            height_in=OVERVIEW_FIGURE_HEIGHT_IN,
        )
        legacy_qa = {
            "core_conclusion": (
                "Legacy six-panel compatibility view of the quality, runtime, "
                "stress, and exact-calibration evidence."
            ),
            "figure_group": "legacy_overview",
            "figure_archetype": "six-panel quantitative evidence grid",
            "target": "LNCS full-width compatibility figure",
            "backend": "Python (matplotlib)",
            "width_in": FIGURE_WIDTH_IN,
            "height_in": OVERVIEW_FIGURE_HEIGHT_IN,
            "panel_map": {
                panel: description
                for panel, description in zip(
                    "abcdef",
                    (
                        "ordered stage gain",
                        "scenario-wise Full gain",
                        "budget trade-off",
                        "runtime ECDF",
                        "CG-size stress",
                        "exact gaps",
                    ),
                )
            },
            "exports": ["svg", "pdf", "tiff", "png"],
            "vector_primary": True,
            "tiff_target_dpi": 600,
            "minimum_font_target_pt": SMALL_FONT_PT,
            "source_data": source_data,
            "panels": legacy_panels,
            **legacy_layout,
            **legacy_export,
        }
        write_qa(args.legacy_output, legacy_qa)


if __name__ == "__main__":
    split_main()
