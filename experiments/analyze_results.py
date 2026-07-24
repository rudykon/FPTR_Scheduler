#!/usr/bin/env python3
"""Paired, scenario-stratified analysis for scheduler experiments.

Independent solver processes support external baseline and deployment
comparisons.  Causal cumulative ablation is analyzed separately from the stage
scores emitted inside each Full run, avoiding wall-clock jitter across processes.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence


METHODS = ("BeamFirst", "Base", "Global", "CG", "Remask", "Full")
INDEPENDENT_COMPARISONS = (
    ("Base", "BeamFirst"),
    ("Full", "BeamFirst"),
    ("Full", "Base"),
)
TRACE_STAGES = ("Base", "Global", "CG", "Remask", "Full")
TRACE_COMPARISONS = tuple(zip(TRACE_STAGES[1:], TRACE_STAGES[:-1]))


def percentile(values: Sequence[float], q: float) -> float:
    """Return the linearly interpolated q-th percentile."""

    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must lie in [0, 1]")
    ordered = sorted(float(value) for value in values)
    index = (len(ordered) - 1) * q
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def _mean_relative_gain(pairs: Iterable[tuple[float, float]]) -> float:
    gains = [(candidate - baseline) / baseline for candidate, baseline in pairs if baseline > 0.0]
    return statistics.fmean(gains) if gains else 0.0


def stratified_bootstrap_ci(
    pairs_by_scenario: Mapping[str, Sequence[tuple[float, float]]],
    *,
    seed: int = 20260722,
    samples: int = 5000,
) -> list[float]:
    """Bootstrap instances within each scenario and weight scenarios equally."""

    if samples < 1:
        raise ValueError("bootstrap samples must be positive")
    strata = [(name, list(pairs)) for name, pairs in sorted(pairs_by_scenario.items()) if pairs]
    if not strata:
        return [0.0, 0.0]
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(samples):
        scenario_means: list[float] = []
        for _name, pairs in strata:
            resampled = [pairs[rng.randrange(len(pairs))] for _ in range(len(pairs))]
            scenario_means.append(_mean_relative_gain(resampled))
        estimates.append(statistics.fmean(scenario_means))
    estimates.sort()
    return [percentile(estimates, 0.025), percentile(estimates, 0.975)]


def _comparison_payload(
    candidate_name: str,
    baseline_name: str,
    candidate: Mapping[tuple[str, int], float],
    baseline: Mapping[tuple[str, int], float],
    *,
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> dict[str, object]:
    common = sorted(candidate.keys() & baseline.keys())
    if not common:
        raise ValueError(f"no paired instances for {candidate_name} and {baseline_name}")
    if candidate.keys() != baseline.keys():
        raise ValueError(f"unpaired instances for {candidate_name} and {baseline_name}")

    absolute = [candidate[key] - baseline[key] for key in common]
    relative = [
        (candidate[key] - baseline[key]) / baseline[key]
        for key in common
        if baseline[key] > 0.0
    ]
    by_scenario: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for scenario, seed in common:
        by_scenario[scenario].append(
            (candidate[(scenario, seed)], baseline[(scenario, seed)])
        )
    scenario_relative = {
        scenario: _mean_relative_gain(pairs)
        for scenario, pairs in sorted(by_scenario.items())
    }
    return {
        "candidate": candidate_name,
        "baseline": baseline_name,
        "paired_instances": len(common),
        "relative_gain_instances": len(relative),
        "mean_relative_gain": statistics.fmean(relative) if relative else 0.0,
        "median_relative_gain": statistics.median(relative) if relative else 0.0,
        "mean_absolute_gain": statistics.fmean(absolute),
        "median_absolute_gain": statistics.median(absolute),
        "wins": sum(delta > 0.0 for delta in absolute),
        "ties": sum(delta == 0.0 for delta in absolute),
        "losses": sum(delta < 0.0 for delta in absolute),
        "scenario_mean_relative_gain": scenario_relative,
        "stratified_bootstrap_95_ci": stratified_bootstrap_ci(
            by_scenario,
            seed=bootstrap_seed,
            samples=bootstrap_samples,
        ),
    }


def analyze_rows(
    rows: Sequence[Mapping[str, str | int | float]],
    *,
    bootstrap_samples: int = 5000,
    bootstrap_seed: int = 20260722,
) -> dict[str, object]:
    """Analyze independent processes without treating stage differences as causal."""

    table: dict[str, dict[tuple[str, int], float]] = defaultdict(dict)
    for row in rows:
        method = str(row.get("method", row.get("variant", "")))
        if method not in METHODS:
            continue
        key = (str(row["scenario"]), int(row["seed"]))
        score = float(row.get("transmitted_median", row.get("transmitted", 0.0)))
        if key in table[method]:
            raise ValueError(f"duplicate aggregate row for {method} and {key}")
        table[method][key] = score

    missing_methods = [method for method in METHODS if method not in table]
    if missing_methods:
        raise ValueError(f"missing methods in aggregate input: {', '.join(missing_methods)}")

    comparisons: dict[str, object] = {}
    for comparison_index, (candidate_name, baseline_name) in enumerate(
        INDEPENDENT_COMPARISONS
    ):
        comparisons[f"{candidate_name}_vs_{baseline_name}"] = _comparison_payload(
            candidate_name,
            baseline_name,
            table[candidate_name],
            table[baseline_name],
            bootstrap_samples=bootstrap_samples,
            bootstrap_seed=bootstrap_seed + comparison_index * 1009,
        )

    return {
        "schema_version": 3,
        "analysis_role": (
            "independent-process external comparisons; intermediate-stage process "
            "differences are not interpreted as causal module effects"
        ),
        "unit_of_analysis": "instance-level median over repeated executions",
        "bootstrap": {
            "method": "resample instances within scenario; equal weight per scenario",
            "samples": bootstrap_samples,
            "seed": bootstrap_seed,
            "interval": "percentile 95%",
        },
        "comparisons": comparisons,
    }


def analyze_trace_rows(
    rows: Sequence[Mapping[str, str | int | float]],
    *,
    bootstrap_samples: int = 5000,
    bootstrap_seed: int = 20260722,
) -> dict[str, object]:
    """Analyze cumulative stages recorded within the same repeated Full runs."""

    grouped: dict[tuple[str, int, str], list[float]] = defaultdict(list)
    demands: dict[tuple[str, int], float] = {}
    seen: set[tuple[str, int, int, str]] = set()
    run_stage_scores: dict[tuple[str, int, int], dict[str, float]] = defaultdict(dict)
    run_trace_present: dict[tuple[str, int, int], dict[str, bool]] = defaultdict(dict)
    credit_eligible_runs: dict[tuple[str, int, int], bool] = {}

    for row in rows:
        stage = str(row["stage"])
        if stage not in TRACE_STAGES:
            continue
        scenario = str(row["scenario"])
        seed = int(row["seed"])
        repeat = int(row["repeat"])
        key = (scenario, seed)
        run_key = (scenario, seed, repeat)
        unique = (*run_key, stage)
        if unique in seen:
            raise ValueError(f"duplicate trace-ablation row for {unique}")
        seen.add(unique)
        score = float(row.get("credited_stage_score", row.get("score", 0.0)))
        grouped[(scenario, seed, stage)].append(score)
        run_stage_scores[run_key][stage] = score
        present_text = str(row.get("stage_trace_present", "")).lower()
        if present_text:
            trace_present = present_text in {"true", "1"}
        else:
            trace_present = str(row.get("observed_stage_score", "")) != ""
        run_trace_present[run_key][stage] = trace_present
        demands[key] = float(row["demand"])
        eligible_text = str(row.get("run_credit_eligible", "")).lower()
        eligible = eligible_text in {"true", "1"} if eligible_text else score > 0.0
        if run_key in credit_eligible_runs and credit_eligible_runs[run_key] != eligible:
            raise ValueError(f"inconsistent credit eligibility within Full run {run_key}")
        credit_eligible_runs[run_key] = eligible

    if not grouped:
        raise ValueError("trace ablation input is empty")

    table: dict[str, dict[tuple[str, int], float]] = {
        stage: {} for stage in TRACE_STAGES
    }
    all_instances = sorted({(scenario, seed) for scenario, seed, _stage in grouped})
    for key in all_instances:
        repeat_counts: set[int] = set()
        for stage in TRACE_STAGES:
            values = grouped.get((*key, stage), [])
            if not values:
                raise ValueError(f"missing trace stage {stage} for instance {key}")
            repeat_counts.add(len(values))
            table[stage][key] = statistics.median(values)
        if len(repeat_counts) != 1:
            raise ValueError(f"unequal trace repeat counts for instance {key}")

    nonmonotone_runs = 0
    incomplete_runs = 0
    for run_key, stage_scores in run_stage_scores.items():
        present = run_trace_present[run_key]
        if (
            set(stage_scores) != set(TRACE_STAGES)
            or set(present) != set(TRACE_STAGES)
            or not all(present.values())
        ):
            incomplete_runs += 1
            continue
        ordered = [stage_scores[stage] for stage in TRACE_STAGES]
        if any(ordered[index] < ordered[index - 1] for index in range(1, len(ordered))):
            nonmonotone_runs += 1

    stage_summary: dict[str, object] = {}
    for stage in TRACE_STAGES:
        scores = list(table[stage].values())
        satisfaction = [
            table[stage][key] / demands[key] for key in sorted(table[stage])
        ]
        stage_summary[stage] = {
            "instances": len(scores),
            "mean_instance_median_score": statistics.fmean(scores),
            "median_instance_median_score": statistics.median(scores),
            "mean_instance_median_satisfaction": statistics.fmean(satisfaction),
            "zero_credited_instances": sum(score == 0.0 for score in scores),
        }

    comparisons: dict[str, object] = {}
    for comparison_index, (candidate_name, baseline_name) in enumerate(
        TRACE_COMPARISONS
    ):
        comparisons[f"{candidate_name}_vs_{baseline_name}"] = _comparison_payload(
            candidate_name,
            baseline_name,
            table[candidate_name],
            table[baseline_name],
            bootstrap_samples=bootstrap_samples,
            bootstrap_seed=bootstrap_seed + comparison_index * 1009,
        )

    return {
        "schema_version": 1,
        "analysis_role": "causal cumulative ablation from stages inside the same Full run",
        "stages": list(TRACE_STAGES),
        "unit_of_analysis": (
            "instance-level median of credited within-run stage scores over repeated Full runs"
        ),
        "credit_rule": (
            "all stages receive zero credit when their parent Full run times out, "
            "is invalid, exits nonzero, or misses the external deadline"
        ),
        "run_diagnostics": {
            "full_runs": len(run_stage_scores),
            "credit_eligible_runs": sum(credit_eligible_runs.values()),
            "zero_credited_runs": sum(not value for value in credit_eligible_runs.values()),
            "incomplete_runs": incomplete_runs,
            "nonmonotone_credited_runs": nonmonotone_runs,
        },
        "bootstrap": {
            "method": "resample instances within scenario; equal weight per scenario",
            "samples": bootstrap_samples,
            "seed": bootstrap_seed,
            "interval": "percentile 95%",
        },
        "stage_summary": stage_summary,
        "comparisons": comparisons,
    }


def analyze_file(
    input_path: Path,
    output_path: Path,
    *,
    bootstrap_samples: int = 5000,
    bootstrap_seed: int = 20260722,
) -> dict[str, object]:
    with input_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = analyze_rows(
        rows,
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def analyze_trace_file(
    input_path: Path,
    output_path: Path,
    *,
    bootstrap_samples: int = 5000,
    bootstrap_seed: int = 20260722,
) -> dict[str, object]:
    with input_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = analyze_trace_rows(
        rows,
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("paper/results/synthetic_results.csv"),
        help="per-instance independent-process aggregate CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("paper/results/paired_analysis.json"),
    )
    parser.add_argument(
        "--trace-input",
        type=Path,
        help="optional within-Full-run trace_ablation_results.csv",
    )
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=Path("paper/results/trace_ablation_analysis.json"),
    )
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260722)
    args = parser.parse_args()

    independent = analyze_file(
        args.input,
        args.output,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
    )
    payload: dict[str, object] = {"independent": independent}
    if args.trace_input is not None:
        payload["trace_ablation"] = analyze_trace_file(
            args.trace_input,
            args.trace_output,
            bootstrap_samples=args.bootstrap_samples,
            bootstrap_seed=args.bootstrap_seed,
        )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
