#!/usr/bin/env python3
"""Build reviewer-requested supplementary tables from sealed paper artifacts.

The script is read-only with respect to ``paper/results`` and ``paper/audit``.
It writes derived CSV tables, compact LaTeX row snippets, and a manifest under
``paper/supplement_data`` by default.  All calculations use the same method and
stage terminology as the manuscript.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
METHODS = ("BeamFirst", "Base", "Global", "CG", "Remask", "Full")
STAGES = ("Base", "Global", "CG", "Remask", "Full")
STAGE_DELTAS = (
    ("Global", "Base"),
    ("CG", "Global"),
    ("Remask", "CG"),
    ("Pair", "Remask"),
)
SCENARIOS = (
    "small-balanced",
    "medium-longtail",
    "medium-tight",
    "large-mixed",
    "large-nonadjacent",
)
REGIME_TARGETS = {
    "small-balanced": (0.45, 0.35, 0.10, 0.00),
    "medium-longtail": (0.32, 0.55, 0.15, 0.00),
    "medium-tight": (0.18, 0.65, 0.20, 0.00),
    "large-mixed": (0.22, 0.70, 0.15, 0.00),
    "large-nonadjacent": (0.16, 0.75, 0.30, 0.80),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path} contains no data rows")
    return rows


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        raise ValueError("percentile requires data")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def fmean(values: Iterable[float]) -> float:
    materialized = list(values)
    return statistics.fmean(materialized) if materialized else 0.0


def stratified_mean_relative(
    candidate: Mapping[tuple[str, int], float],
    baseline: Mapping[tuple[str, int], float],
) -> float:
    by_scenario: dict[str, list[float]] = defaultdict(list)
    if candidate.keys() != baseline.keys():
        raise ValueError("paired method tables have different instance keys")
    for key in sorted(candidate):
        scenario, _seed = key
        if baseline[key] > 0:
            by_scenario[scenario].append((candidate[key] - baseline[key]) / baseline[key])
    return fmean(fmean(values) for _scenario, values in sorted(by_scenario.items()))


def generator_regimes(
    case_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, object]]:
    """Summarize the predeclared main-regime targets and realized integers."""

    output: list[dict[str, object]] = []
    for scenario in SCENARIOS:
        rows = [
            row
            for row in case_rows
            if row["experiment"] == "heldout" and row["scenario"] == scenario
        ]
        if len(rows) != 30:
            raise ValueError(f"expected 30 held-out cases for {scenario}, found {len(rows)}")

        constant_fields = (
            "N",
            "K",
            "P",
            "T",
            "beam_max",
            "compatibility_groups",
            "max_group_size",
            "double_memberships",
            "nonadjacent_memberships",
        )
        constants: dict[str, int] = {}
        for field in constant_fields:
            values = {int(row[field]) for row in rows}
            if len(values) != 1:
                raise ValueError(f"{scenario} has nonconstant {field}: {sorted(values)}")
            constants[field] = values.pop()

        beam_ratio, cg_user_ratio, dual_ratio, nonadjacent_ratio = REGIME_TARGETS[scenario]
        cg_users = round(constants["N"] * cg_user_ratio)
        output.append(
            {
                "scenario": scenario,
                "instances": len(rows),
                "N": constants["N"],
                "K": constants["K"],
                "P": constants["P"],
                "T": constants["T"],
                "beam_ratio_target": beam_ratio,
                "beam_max": constants["beam_max"],
                "cg_user_ratio_target": cg_user_ratio,
                "cg_users": cg_users,
                "compatibility_groups": constants["compatibility_groups"],
                "max_group_size": constants["max_group_size"],
                "dual_resource_ratio_target": dual_ratio,
                "dual_resources": constants["double_memberships"],
                "nonadjacent_within_dual_target": nonadjacent_ratio,
                "nonadjacent_resources": constants["nonadjacent_memberships"],
            }
        )
    return output


def launch_counts(
    main_runs: Sequence[Mapping[str, str]],
    budget_runs: Sequence[Mapping[str, str]],
    stress_runs: Sequence[Mapping[str, str]],
    exact_runs: Sequence[Mapping[str, str]],
) -> list[dict[str, object]]:
    """Account for every formal independent process launch."""

    suites = (
        ("Main", main_runs),
        ("Budget sweep", budget_runs),
        ("CG stress", stress_runs),
        ("Exact calibration", exact_runs),
    )
    output: list[dict[str, object]] = []
    for suite, rows in suites:
        instances = len({row["instance_id"] for row in rows})
        conditions = len({(row["method"], row["budget_ms"]) for row in rows})
        repeats = sorted({int(row["repeat"]) for row in rows})
        if repeats != list(range(5)):
            raise ValueError(f"{suite} does not contain repeats 0--4: {repeats}")
        expected = instances * conditions * len(repeats)
        if len(rows) != expected:
            raise ValueError(
                f"{suite} launch accounting mismatch: {len(rows)} != {expected}"
            )
        output.append(
            {
                "suite": suite,
                "instances": instances,
                "conditions_per_instance": conditions,
                "repeats_per_condition": len(repeats),
                "launches": len(rows),
                "valid_outputs": sum(as_bool(row["valid"]) for row in rows),
                "deadline_misses_100ms": sum(
                    as_bool(row["deadline_miss"]) for row in rows
                ),
            }
        )
    output.append(
        {
            "suite": "Total",
            "instances": "--",
            "conditions_per_instance": "--",
            "repeats_per_condition": "--",
            "launches": sum(int(row["launches"]) for row in output),
            "valid_outputs": sum(int(row["valid_outputs"]) for row in output),
            "deadline_misses_100ms": sum(
                int(row["deadline_misses_100ms"]) for row in output
            ),
        }
    )
    if int(output[-1]["launches"]) != 8610:
        raise ValueError(f"expected 8,610 total launches, found {output[-1]['launches']}")
    return output


def budget_sweep(
    aggregate_rows: Sequence[Mapping[str, str]],
    run_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, object]]:
    """Summarize the four predeclared Full budget operating points."""

    budgets = (20, 40, 60, 87)
    medians: dict[int, dict[tuple[str, int], float]] = {
        budget: {} for budget in budgets
    }
    for row in aggregate_rows:
        budget = int(row["budget_ms"])
        if row["experiment"] != "budget" or row["method"] != "Full" or budget not in medians:
            continue
        medians[budget][(row["scenario"], int(row["seed"]))] = float(
            row["transmitted_median"]
        )
    if any(len(medians[budget]) != 150 for budget in budgets):
        raise ValueError("expected 150 aggregate budget instances at every operating point")

    times: dict[int, list[float]] = defaultdict(list)
    valid: dict[int, int] = defaultdict(int)
    misses: dict[int, int] = defaultdict(int)
    for row in run_rows:
        budget = int(row["budget_ms"])
        if row["method"] != "Full" or budget not in medians:
            continue
        times[budget].append(float(row["solver_wall_ms"]))
        valid[budget] += int(as_bool(row["valid"]))
        misses[budget] += int(as_bool(row["deadline_miss"]))

    output: list[dict[str, object]] = []
    for budget in budgets:
        values = times[budget]
        if len(values) != 750:
            raise ValueError(f"expected 750 runs at {budget} ms, found {len(values)}")
        output.append(
            {
                "budget_ms": budget,
                "instances": len(medians[budget]),
                "runs": len(values),
                "mean_instance_median_traffic": fmean(medians[budget].values()),
                "stratified_mean_relative_vs_20ms_percent": 100.0
                * stratified_mean_relative(medians[budget], medians[20]),
                "wall_p50_ms": percentile(values, 0.50),
                "wall_p95_ms": percentile(values, 0.95),
                "wall_worst_ms": max(values),
                "valid_outputs": valid[budget],
                "deadline_misses_100ms": misses[budget],
            }
        )
    return output


def cg_stress_table(
    aggregate_rows: Sequence[Mapping[str, str]],
    run_rows: Sequence[Mapping[str, str]],
    case_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, object]]:
    """Summarize the joint CG-size/coverage stress experiment."""

    case_by_scenario: dict[str, Mapping[str, str]] = {}
    for row in case_rows:
        if row["experiment"] != "stress":
            continue
        existing = case_by_scenario.get(row["scenario"])
        if existing is None:
            case_by_scenario[row["scenario"]] = row
        else:
            for field in ("N", "compatibility_groups", "max_group_size"):
                if existing[field] != row[field]:
                    raise ValueError(f"nonconstant stress field {field} in {row['scenario']}")

    output: list[dict[str, object]] = []
    for scenario, case in sorted(
        case_by_scenario.items(), key=lambda item: int(item[1]["max_group_size"])
    ):
        aggregate = [row for row in aggregate_rows if row["scenario"] == scenario]
        indexed = {
            (int(row["seed"]), row["method"]): float(row["transmitted_median"])
            for row in aggregate
        }
        seeds = sorted({int(row["seed"]) for row in aggregate})
        if len(seeds) != 10 or len(aggregate) != 30:
            raise ValueError(f"expected 10 cases and 3 methods for {scenario}")
        relative = [
            (indexed[(seed, "Full")] - indexed[(seed, "Base")])
            / indexed[(seed, "Base")]
            for seed in seeds
        ]
        full_runs = [
            row
            for row in run_rows
            if row["scenario"] == scenario and row["method"] == "Full"
        ]
        times = [float(row["solver_wall_ms"]) for row in full_runs]
        if len(times) != 50:
            raise ValueError(f"expected 50 Full runs for {scenario}, found {len(times)}")
        group_size = int(case["max_group_size"])
        group_count = int(case["compatibility_groups"])
        n_users = int(case["N"])
        output.append(
            {
                "scenario": scenario,
                "max_group_size": group_size,
                "cg_user_coverage_percent": 100.0 * group_size * group_count / n_users,
                "instances": len(seeds),
                "full_runs": len(full_runs),
                "base_mean_instance_median_traffic": fmean(
                    indexed[(seed, "Base")] for seed in seeds
                ),
                "cg_mean_instance_median_traffic": fmean(
                    indexed[(seed, "CG")] for seed in seeds
                ),
                "full_mean_instance_median_traffic": fmean(
                    indexed[(seed, "Full")] for seed in seeds
                ),
                "full_mean_relative_vs_base_percent": 100.0 * fmean(relative),
                "full_wall_p95_ms": percentile(times, 0.95),
                "full_wall_worst_ms": max(times),
                "full_valid_outputs": sum(as_bool(row["valid"]) for row in full_runs),
                "full_deadline_misses_100ms": sum(
                    as_bool(row["deadline_miss"]) for row in full_runs
                ),
            }
        )
    if [int(row["max_group_size"]) for row in output] != [2, 5, 10, 15, 20]:
        raise ValueError("unexpected CG stress sizes")
    return output


def method_quality_latency(
    aggregate_rows: Sequence[Mapping[str, str]],
    run_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, object]]:
    medians: dict[str, dict[tuple[str, int], float]] = {method: {} for method in METHODS}
    for row in aggregate_rows:
        if row["experiment"] != "main" or row["method"] not in medians:
            continue
        key = (row["scenario"], int(row["seed"]))
        medians[row["method"]][key] = float(row["transmitted_median"])
    if any(len(medians[method]) != 150 for method in METHODS):
        raise ValueError("expected 150 aggregate instances for every method")

    times: dict[str, list[float]] = defaultdict(list)
    valid: dict[str, int] = defaultdict(int)
    misses: dict[str, int] = defaultdict(int)
    for row in run_rows:
        method = row["method"]
        if method not in METHODS:
            continue
        times[method].append(float(row["solver_wall_ms"]))
        valid[method] += int(as_bool(row["valid"]))
        misses[method] += int(as_bool(row["deadline_miss"]))

    output: list[dict[str, object]] = []
    for method in METHODS:
        values = times[method]
        if len(values) != 750:
            raise ValueError(f"expected 750 main runs for {method}, found {len(values)}")
        output.append(
            {
                "method": method,
                "instances": len(medians[method]),
                "runs": len(values),
                "mean_instance_median_traffic": fmean(medians[method].values()),
                "stratified_mean_relative_vs_base_percent": 100.0
                * stratified_mean_relative(medians[method], medians["Base"]),
                "wall_p50_ms": percentile(values, 0.50),
                "wall_p95_ms": percentile(values, 0.95),
                "wall_p99_ms": percentile(values, 0.99),
                "wall_worst_ms": max(values),
                "valid_outputs": valid[method],
                "deadline_misses_100ms": misses[method],
            }
        )
    return output


def single_run_pairs(
    aggregate_rows: Sequence[Mapping[str, str]],
    run_rows: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    instance_median: dict[tuple[str, int, str], float] = {}
    full_ranges: list[float] = []
    full_relative_ranges: list[float] = []
    variable_instances = 0
    for row in aggregate_rows:
        if row["experiment"] != "main" or row["method"] not in METHODS:
            continue
        key = (row["scenario"], int(row["seed"]), row["method"])
        instance_median[key] = float(row["transmitted_median"])
        if row["method"] == "Full":
            score_range = float(row["transmitted_max"]) - float(row["transmitted_min"])
            full_ranges.append(score_range)
            denominator = float(row["transmitted_median"])
            full_relative_ranges.append(score_range / denominator if denominator > 0 else 0.0)
            variable_instances += int(score_range > 0)

    indexed: dict[tuple[str, int, int, str], Mapping[str, str]] = {}
    for row in run_rows:
        method = row["method"]
        if method not in METHODS:
            continue
        key = (row["scenario"], int(row["seed"]), int(row["repeat"]), method)
        if key in indexed:
            raise ValueError(f"duplicate main run key: {key}")
        indexed[key] = row

    detail: list[dict[str, object]] = []
    for scenario in SCENARIOS:
        seeds = sorted({seed for scen, seed, _repeat, method in indexed if scen == scenario and method == "Full"})
        for seed in seeds:
            for repeat in range(5):
                full = indexed[(scenario, seed, repeat, "Full")]
                base = indexed[(scenario, seed, repeat, "Base")]
                beam = indexed[(scenario, seed, repeat, "BeamFirst")]
                full_score = float(full["credited_transmitted"])
                base_score = float(base["credited_transmitted"])
                beam_score = float(beam["credited_transmitted"])
                median_score = instance_median[(scenario, seed, "Full")]
                detail.append(
                    {
                        "scenario": scenario,
                        "seed": seed,
                        "repeat": repeat,
                        "full_score": full_score,
                        "base_score": base_score,
                        "beamfirst_score": beam_score,
                        "full_vs_base_percent": 100.0 * (full_score - base_score) / base_score,
                        "full_vs_beamfirst_percent": 100.0 * (full_score - beam_score) / beam_score,
                        "full_vs_instance_median_percent": 100.0
                        * (full_score - median_score)
                        / median_score,
                        "full_wall_ms": float(full["solver_wall_ms"]),
                        "full_valid": as_bool(full["valid"]),
                        "full_deadline_miss": as_bool(full["deadline_miss"]),
                    }
                )
    if len(detail) != 750:
        raise ValueError(f"expected 750 paired Full runs, found {len(detail)}")

    summary: list[dict[str, object]] = []
    for comparator, field in (
        ("Base", "full_vs_base_percent"),
        ("BeamFirst", "full_vs_beamfirst_percent"),
    ):
        values = [float(row[field]) for row in detail]
        wins = sum(value > 1e-12 for value in values)
        losses = sum(value < -1e-12 for value in values)
        summary.append(
            {
                "comparison": f"Full_vs_{comparator}_single_run",
                "pairs": len(values),
                "wins": wins,
                "ties": len(values) - wins - losses,
                "losses": losses,
                "mean_relative_gain_percent": fmean(values),
                "p05_relative_gain_percent": percentile(values, 0.05),
                "p50_relative_gain_percent": percentile(values, 0.50),
                "p95_relative_gain_percent": percentile(values, 0.95),
                "minimum_relative_gain_percent": min(values),
                "maximum_relative_gain_percent": max(values),
            }
        )
    deviations = [float(row["full_vs_instance_median_percent"]) for row in detail]
    summary.append(
        {
            "comparison": "Full_run_vs_its_instance_median",
            "pairs": len(deviations),
            "wins": sum(value > 1e-12 for value in deviations),
            "ties": sum(abs(value) <= 1e-12 for value in deviations),
            "losses": sum(value < -1e-12 for value in deviations),
            "mean_relative_gain_percent": fmean(deviations),
            "p05_relative_gain_percent": percentile(deviations, 0.05),
            "p50_relative_gain_percent": percentile(deviations, 0.50),
            "p95_relative_gain_percent": percentile(deviations, 0.95),
            "minimum_relative_gain_percent": min(deviations),
            "maximum_relative_gain_percent": max(deviations),
        }
    )
    summary.append(
        {
            "comparison": "Full_within_instance_score_range",
            "pairs": len(full_ranges),
            "wins": variable_instances,
            "ties": len(full_ranges) - variable_instances,
            "losses": 0,
            "mean_relative_gain_percent": 100.0 * fmean(full_relative_ranges),
            "p05_relative_gain_percent": 100.0 * percentile(full_relative_ranges, 0.05),
            "p50_relative_gain_percent": 100.0 * percentile(full_relative_ranges, 0.50),
            "p95_relative_gain_percent": 100.0 * percentile(full_relative_ranges, 0.95),
            "minimum_relative_gain_percent": 100.0 * min(full_relative_ranges),
            "maximum_relative_gain_percent": 100.0 * max(full_relative_ranges),
        }
    )
    return detail, summary


def stage_acceptance(
    trace_rows: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    grouped: dict[tuple[str, int, str], list[float]] = defaultdict(list)
    run_scores: dict[tuple[str, int, int, str], float] = {}
    for row in trace_rows:
        stage = row["stage"]
        if stage in STAGES:
            run_key = (row["scenario"], int(row["seed"]), int(row["repeat"]), stage)
            if run_key in run_scores:
                raise ValueError(f"duplicate trace run key: {run_key}")
            run_scores[run_key] = float(row["credited_stage_score"])
            grouped[(row["scenario"], int(row["seed"]), stage)].append(
                float(row["credited_stage_score"])
            )

    medians: list[dict[str, object]] = []
    indexed: dict[tuple[str, int, str], float] = {}
    for key, values in sorted(grouped.items()):
        if len(values) != 5:
            raise ValueError(f"expected five trace repeats for {key}, found {len(values)}")
        indexed[key] = statistics.median(values)
        medians.append(
            {
                "scenario": key[0],
                "seed": key[1],
                "stage": key[2],
                "instance_median_score": indexed[key],
            }
        )

    summary: list[dict[str, object]] = []
    for scenario in (*SCENARIOS, "Overall"):
        seeds = sorted(
            {
                seed
                for scen, seed, stage in indexed
                if stage == "Base" and (scenario == "Overall" or scen == scenario)
            }
        )
        row: dict[str, object] = {"scenario": scenario, "instances": len(seeds)}
        for output_stage, previous_stage in STAGE_DELTAS:
            trace_stage = "Full" if output_stage == "Pair" else output_stage
            accepted = 0
            run_accepted = 0
            for seed in seeds:
                scen = next(
                    scen_name
                    for scen_name, seed_value, stage in indexed
                    if seed_value == seed
                    and stage == "Base"
                    and (scenario == "Overall" or scen_name == scenario)
                )
                accepted += int(
                    indexed[(scen, seed, trace_stage)]
                    > indexed[(scen, seed, previous_stage)]
                )
                for repeat in range(5):
                    run_accepted += int(
                        run_scores[(scen, seed, repeat, trace_stage)]
                        > run_scores[(scen, seed, repeat, previous_stage)]
                    )
            row[f"{output_stage}_improved"] = accepted
            row[f"{output_stage}_improved_percent"] = 100.0 * accepted / len(seeds)
            row[f"{output_stage}_run_improved"] = run_accepted
            row[f"{output_stage}_run_improved_percent"] = (
                100.0 * run_accepted / (5 * len(seeds))
            )
        summary.append(row)
    return medians, summary


def exact_case_table(
    exact_rows: Sequence[Mapping[str, str]],
    audit_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, object]]:
    scores: dict[tuple[str, int, str], Mapping[str, str]] = {}
    for row in exact_rows:
        key = (row["scenario"], int(row["seed"]), row["method"])
        scores[key] = row
    audits = {(row["scenario"], int(row["seed"])): row for row in audit_rows}
    output: list[dict[str, object]] = []
    cases = sorted(audits, key=lambda key: (key[1], key[0]))
    for scenario, seed in cases:
        beam = scores[(scenario, seed, "BeamFirst")]
        base = scores[(scenario, seed, "Base")]
        full = scores[(scenario, seed, "Full")]
        audit = audits[(scenario, seed)]
        if int(float(full["optimum"])) != int(audit["audited_optimum"]):
            raise ValueError(f"formal/audited optimum mismatch for {(scenario, seed)}")
        output.append(
            {
                "scenario": scenario,
                "seed": seed,
                "case_sha256": audit["case_sha256"],
                "optimum": int(audit["audited_optimum"]),
                "beamfirst_score": int(float(beam["transmitted_median"])),
                "base_score": int(float(base["transmitted_median"])),
                "full_score": int(float(full["transmitted_median"])),
                "full_gap_percent": 100.0 * float(full["relative_gap"]),
                "beam_plans": int(audit["beam_plans"]),
                "transition_attempts": int(audit["transition_attempts"]),
                "duplicates_collapsed": int(audit["duplicates_collapsed"]),
                "dominated_removed": int(audit["dominated_removed"]),
                "peak_frontier_states": int(audit["peak_frontier_states"]),
                "optimum_match": as_bool(audit["optimum_match"]),
            }
        )
    if len(output) != 12 or not all(bool(row["optimum_match"]) for row in output):
        raise ValueError("exact audit did not produce 12 matching cases")
    return output


def write_latex_rows(
    output: Path,
    tables: Mapping[str, Sequence[Mapping[str, object]]],
) -> None:
    methods = tables["method_quality_latency"]
    (output / "method_quality_latency_rows.tex").write_text(
        "".join(
            f"{row['method']} & {row['mean_instance_median_traffic']:.2f} & "
            f"{row['stratified_mean_relative_vs_base_percent']:+.2f} & "
            f"{row['wall_p50_ms']:.2f} & {row['wall_p95_ms']:.2f} & "
            f"{row['wall_worst_ms']:.2f} & "
            f"{row['deadline_misses_100ms']}/{row['runs']} \\\\\n"
            for row in methods
        ),
        encoding="utf-8",
    )

    single = {
        str(row["comparison"]): row for row in tables["single_run_summary"]
    }
    pair_labels = (
        ("Full_vs_Base_single_run", "Full vs Base"),
        ("Full_vs_BeamFirst_single_run", "Full vs BeamFirst"),
    )
    (output / "single_run_paired_rows.tex").write_text(
        "".join(
            f"{label} & {single[key]['pairs']} & "
            f"{single[key]['wins']}/{single[key]['ties']}/"
            f"{single[key]['losses']} & "
            f"{single[key]['mean_relative_gain_percent']:+.3f} & "
            f"{single[key]['p05_relative_gain_percent']:.3f} & "
            f"{single[key]['p50_relative_gain_percent']:.3f} & "
            f"{single[key]['p95_relative_gain_percent']:.3f} & "
            f"{single[key]['minimum_relative_gain_percent']:.3f} & "
            f"{single[key]['maximum_relative_gain_percent']:.3f} \\\\\n"
            for key, label in pair_labels
        ),
        encoding="utf-8",
    )

    deviation = single["Full_run_vs_its_instance_median"]
    (output / "full_run_deviation_row.tex").write_text(
        (
            f"{deviation['pairs']} & "
            f"{deviation['wins']}/{deviation['ties']}/"
            f"{deviation['losses']} & "
            f"{deviation['mean_relative_gain_percent']:+.3f} & "
            f"{deviation['p05_relative_gain_percent']:.3f} & "
            f"{deviation['p50_relative_gain_percent']:.3f} & "
            f"{deviation['p95_relative_gain_percent']:.3f} & "
            f"{deviation['minimum_relative_gain_percent']:.3f} & "
            f"{deviation['maximum_relative_gain_percent']:.3f} \\\\\n"
        ),
        encoding="utf-8",
    )

    score_range = single["Full_within_instance_score_range"]
    (output / "full_within_instance_range_row.tex").write_text(
        (
            f"{score_range['pairs']} & "
            f"{score_range['wins']}/{score_range['ties']} & "
            f"{score_range['mean_relative_gain_percent']:.3f} & "
            f"{score_range['p50_relative_gain_percent']:.3f} & "
            f"{score_range['p95_relative_gain_percent']:.3f} & "
            f"{score_range['maximum_relative_gain_percent']:.3f} \\\\\n"
        ),
        encoding="utf-8",
    )

    stages = tables["stage_acceptance"]
    (output / "stage_acceptance_rows.tex").write_text(
        "".join(
            f"{row['scenario']} & "
            f"{row['instances']}/{5 * int(row['instances'])} & "
            f"{row['Global_improved']}/{row['Global_run_improved']} & "
            f"{row['CG_improved']}/{row['CG_run_improved']} & "
            f"{row['Remask_improved']}/{row['Remask_run_improved']} & "
            f"{row['Pair_improved']}/{row['Pair_run_improved']} \\\\\n"
            for row in stages
        ),
        encoding="utf-8",
    )

    regimes = tables["generator_regimes"]
    (output / "generator_regime_rows.tex").write_text(
        "".join(
            f"\\texttt{{{row['scenario']}}} & "
            f"{row['N']}/{row['K']}/{row['P']}/{row['T']} & "
            f"{row['beam_max']} ({row['beam_ratio_target']:.2f}) & "
            f"{row['cg_users']} ({row['cg_user_ratio_target']:.2f}) & "
            f"{row['dual_resources']} ({row['dual_resource_ratio_target']:.2f}) & "
            f"{row['nonadjacent_resources']}/{row['dual_resources']} "
            f"({row['nonadjacent_within_dual_target']:.2f}) \\\\\n"
            for row in regimes
        ),
        encoding="utf-8",
    )

    launches = tables["launch_counts"]
    (output / "launch_count_rows.tex").write_text(
        "".join(
            f"{row['suite']} & {row['instances']} & "
            f"{row['conditions_per_instance']} & {row['repeats_per_condition']} & "
            f"{int(row['launches']):,} & {int(row['valid_outputs']):,} & "
            f"{row['deadline_misses_100ms']} \\\\\n"
            for row in launches
        ),
        encoding="utf-8",
    )

    budgets = tables["budget_sweep"]
    (output / "budget_sweep_rows.tex").write_text(
        "".join(
            f"{row['budget_ms']} & {row['mean_instance_median_traffic']:.2f} & "
            f"{row['stratified_mean_relative_vs_20ms_percent']:+.2f} & "
            f"{row['wall_p50_ms']:.2f} & {row['wall_p95_ms']:.2f} & "
            f"{row['wall_worst_ms']:.2f} & "
            f"{row['deadline_misses_100ms']}/{row['runs']} \\\\\n"
            for row in budgets
        ),
        encoding="utf-8",
    )

    stress = tables["cg_stress"]
    (output / "cg_stress_rows.tex").write_text(
        "".join(
            f"{row['max_group_size']} & {row['cg_user_coverage_percent']:.1f} & "
            f"{row['base_mean_instance_median_traffic']:.1f} & "
            f"{row['cg_mean_instance_median_traffic']:.1f} & "
            f"{row['full_mean_instance_median_traffic']:.1f} & "
            f"{row['full_mean_relative_vs_base_percent']:+.2f} & "
            f"{row['full_wall_p95_ms']:.2f} & {row['full_wall_worst_ms']:.2f} & "
            f"{row['full_deadline_misses_100ms']}/{row['full_runs']} \\\\\n"
            for row in stress
        ),
        encoding="utf-8",
    )

    for snippet_name in (
        "generator_regime_rows.tex",
        "launch_count_rows.tex",
        "budget_sweep_rows.tex",
        "cg_stress_rows.tex",
    ):
        snippet_path = output / snippet_name
        snippet_path.write_text(
            snippet_path.read_text(encoding="utf-8").rstrip("\n")
            + "\n\\bottomrule\n",
            encoding="utf-8",
        )

    exact = tables["exact_cases"]
    (output / "exact_case_rows.tex").write_text(
        "".join(
            f"{row['scenario']} & {row['seed']} & {row['optimum']} & "
            f"{row['beamfirst_score']} & {row['base_score']} & "
            f"{row['full_score']} & {row['full_gap_percent']:.2f} & "
            f"{row['beam_plans']} & {row['transition_attempts']} & "
            f"{row['duplicates_collapsed']} & {row['dominated_removed']} & "
            f"{row['peak_frontier_states']} \\\\\n"
            for row in exact
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=ROOT / "paper" / "results")
    parser.add_argument("--audit-dir", type=Path, default=ROOT / "paper" / "audit")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "paper" / "supplement_data")
    args = parser.parse_args()
    results_dir = args.results_dir.resolve()
    audit_dir = args.audit_dir.resolve()
    output_dir = args.output_dir.resolve()

    paths = {
        "aggregate": results_dir / "synthetic_results.csv",
        "runs": results_dir / "run_results.csv",
        "trace": results_dir / "trace_ablation_results.csv",
        "case_manifest": results_dir / "case_manifest.csv",
        "budget_aggregate": results_dir / "budget_results.csv",
        "budget_runs": results_dir / "budget_run_results.csv",
        "stress_aggregate": results_dir / "cg_stress_results.csv",
        "stress_runs": results_dir / "cg_stress_run_results.csv",
        "exact": results_dir / "exact_results.csv",
        "exact_runs": results_dir / "exact_run_results.csv",
        "exact_audit": audit_dir / "exact_suite_audit.csv",
    }
    rows = {name: read_csv(path) for name, path in paths.items()}
    regime_table = generator_regimes(rows["case_manifest"])
    launch_table = launch_counts(
        rows["runs"], rows["budget_runs"], rows["stress_runs"], rows["exact_runs"]
    )
    method_table = method_quality_latency(rows["aggregate"], rows["runs"])
    single_detail, single_summary = single_run_pairs(rows["aggregate"], rows["runs"])
    stage_medians, stage_summary = stage_acceptance(rows["trace"])
    budget_table = budget_sweep(rows["budget_aggregate"], rows["budget_runs"])
    stress_table = cg_stress_table(
        rows["stress_aggregate"], rows["stress_runs"], rows["case_manifest"]
    )
    exact_table = exact_case_table(rows["exact"], rows["exact_audit"])

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "generator_regimes.csv",
        tuple(regime_table[0]),
        regime_table,
    )
    write_csv(
        output_dir / "launch_counts.csv",
        tuple(launch_table[0]),
        launch_table,
    )
    write_csv(
        output_dir / "method_quality_latency.csv",
        tuple(method_table[0]),
        method_table,
    )
    write_csv(
        output_dir / "single_run_paired.csv",
        tuple(single_detail[0]),
        single_detail,
    )
    write_csv(
        output_dir / "single_run_stability_summary.csv",
        tuple(single_summary[0]),
        single_summary,
    )
    write_csv(
        output_dir / "stage_instance_medians.csv",
        tuple(stage_medians[0]),
        stage_medians,
    )
    write_csv(
        output_dir / "stage_acceptance_by_scenario.csv",
        tuple(stage_summary[0]),
        stage_summary,
    )
    write_csv(
        output_dir / "budget_sweep.csv",
        tuple(budget_table[0]),
        budget_table,
    )
    write_csv(
        output_dir / "cg_stress.csv",
        tuple(stress_table[0]),
        stress_table,
    )
    write_csv(
        output_dir / "exact_case_audit_table.csv",
        tuple(exact_table[0]),
        exact_table,
    )
    tables: dict[str, Sequence[Mapping[str, object]]] = {
        "generator_regimes": regime_table,
        "launch_counts": launch_table,
        "method_quality_latency": method_table,
        "single_run_summary": single_summary,
        "stage_acceptance": stage_summary,
        "budget_sweep": budget_table,
        "cg_stress": stress_table,
        "exact_cases": exact_table,
    }
    write_latex_rows(output_dir, tables)

    generated = sorted(
        path
        for path in output_dir.iterdir()
        if path.is_file()
        and path.name not in {"manifest.json", "CHECKSUMS.sha256"}
    )
    manifest = {
        "purpose": "Reviewer-requested P0--P3 supplementary evidence",
        "source_files": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for name, path in paths.items()
        },
        "derived_files": {
            path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in generated
            if path.name != "manifest.json"
        },
        "checks": {
            "generator_regimes": len(regime_table),
            "launch_accounting_rows": len(launch_table),
            "formal_launches": int(launch_table[-1]["launches"]),
            "method_rows": len(method_table),
            "single_run_pairs": len(single_detail),
            "single_run_summary_rows": len(single_summary),
            "trace_instance_stage_medians": len(stage_medians),
            "stage_scenario_rows": len(stage_summary),
            "budget_operating_points": len(budget_table),
            "cg_stress_settings": len(stress_table),
            "exact_cases": len(exact_table),
            "exact_optimum_matches": sum(bool(row["optimum_match"]) for row in exact_table),
        },
        "deadline_note": (
            "Zero observed misses is an empirical count. Under the rule-of-three "
            "approximation, 0/750 corresponds to an approximately 0.4% one-sided "
            "95% upper bound under an independent and identically distributed (i.i.d.) assumption."
        ),
        "artifact_erratum": (
            "Historical sealed fields named 'causal cumulative ablation' denote "
            "the fixed-order within-run trace from one Full execution. They do not "
            "identify standalone, order-invariant, or causal module effects."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    checksum_paths = [*generated, manifest_path]
    (output_dir / "CHECKSUMS.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in checksum_paths),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
