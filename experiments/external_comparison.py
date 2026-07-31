#!/usr/bin/env python3
"""Fair external-baseline comparison for the FPTR scheduler.

The experiment reuses the paper's case generator and reference validator, but
keeps its outputs separate from reproducibility/results and paper/.  The
external baseline is the independent C++ ALNS implementation in
src/external_alns_baseline.cpp.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments import paper_experiments as protocol  # noqa: E402
from tools import scheduler_validator  # noqa: E402


MAIN_METHODS = (
    "BeamFirst", "Base", "Full", "ALNS", "Tabu", "GA", "SA", "ILS", "GRASP"
)
BUDGET_METHODS = ("Full", "ALNS", "Tabu", "GA", "SA", "ILS", "GRASP")
EXTERNAL_METHODS = ("ALNS", "Tabu", "GA", "SA", "ILS", "GRASP")
STAGE_ARGUMENT = {
    "BeamFirst": "beamfirst",
    "Base": "base",
    "Full": "full",
}
EXTERNAL_ARGUMENT = {
    "Tabu": "tabu",
    "GA": "ga",
    "SA": "sa",
    "ILS": "ils",
    "GRASP": "grasp",
}


def stable_seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_csv_list(text: str, cast=str) -> tuple:
    values = tuple(cast(token.strip()) for token in text.split(",") if token.strip())
    if not values:
        raise argparse.ArgumentTypeError("expected a non-empty comma-separated list")
    return values


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def compile_binaries(build_dir: Path, compiler: str) -> tuple[Path, dict[str, Path]]:
    scheduler = build_dir / "scheduler_reference"
    external_sources = {
        "ALNS": ROOT / "src" / "external_alns_baseline.cpp",
        "Tabu": ROOT / "src" / "external_tabu_ga_baseline.cpp",
        "GA": ROOT / "src" / "external_tabu_ga_baseline.cpp",
        "SA": ROOT / "src" / "external_sa_ils_grasp.cpp",
        "ILS": ROOT / "src" / "external_sa_ils_grasp.cpp",
        "GRASP": ROOT / "src" / "external_sa_ils_grasp.cpp",
    }
    binary_names = {
        "ALNS": "external_alns",
        "Tabu": "external_tabu_ga",
        "GA": "external_tabu_ga",
        "SA": "external_sa_ils_grasp",
        "ILS": "external_sa_ils_grasp",
        "GRASP": "external_sa_ils_grasp",
    }
    external_binaries = {
        method: build_dir / binary_names[method] for method in external_sources
    }
    commands = [
        (
            scheduler,
            [
                compiler,
                "-std=c++17",
                "-O2",
                str(ROOT / "src" / "scheduler.cpp"),
                str(ROOT / "src" / "core.cpp"),
                "-o",
                str(scheduler),
            ],
        )
    ]
    seen_outputs = {output for output, _ in commands}
    for method, source in external_sources.items():
        output = external_binaries[method]
        if output in seen_outputs:
            continue
        commands.append(
            (
                output,
                [
                    compiler,
                    "-std=c++17",
                    "-O2",
                    str(source),
                    "-o",
                    str(output),
                ],
            )
        )
        seen_outputs.add(output)
    for output, command in commands:
        result = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"compilation failed for {output.name}: "
                + " ".join(result.stderr.split())[:2000]
            )
    return scheduler, external_binaries

def parse_trace(stderr: str) -> list[dict[str, object]]:
    traces: list[dict[str, object]] = []
    for line in stderr.splitlines():
        tokens = dict(
            token.split("=", 1)
            for token in line.strip().split()
            if "=" in token
        )
        if not line.startswith("TRACE") or "elapsed_ms" not in tokens:
            continue
        try:
            traces.append(
                {
                    "score": int(tokens["score"]),
                    "elapsed_ms": float(tokens["elapsed_ms"]),
                    "deadline_hit": tokens.get("deadline_hit", "0") == "1",
                    "external": tokens.get("external") == "alns",
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return traces


def run_one(
    scheduler: Path,
    external: Mapping[str, Path],
    bundle: protocol.CaseBundle,
    *,
    suite: str,
    method: str,
    budget_ms: int,
    repeat: int,
    execution_order: int,
    deadline_ms: float,
    timeout_ms: int,
) -> dict[str, object]:
    if method in EXTERNAL_METHODS:
        seed = stable_seed("external", method, suite, bundle.instance_id, budget_ms, repeat)
        command = [str(external[method])]
        if method != "ALNS":
            command.extend(["--method", EXTERNAL_ARGUMENT[method]])
        command.extend(
            [
                "--budget-ms",
                str(budget_ms),
                "--seed",
                str(seed),
                "--trace",
            ]
        )
        seed_value: int | None = seed
    else:
        command = [
            str(scheduler),
            "--stage",
            STAGE_ARGUMENT[method],
            "--budget-ms",
            str(budget_ms),
            "--trace",
        ]
        seed_value = None

    started = time.perf_counter()
    stdout = ""
    stderr = ""
    timed_out = False
    returncode = -1
    try:
        process = subprocess.run(
            command,
            input=bundle.text,
            text=True,
            capture_output=True,
            timeout=timeout_ms / 1000.0,
            check=False,
            cwd=ROOT,
        )
        stdout = process.stdout
        stderr = process.stderr
        returncode = process.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        if isinstance(exc.stdout, bytes):
            stdout = exc.stdout.decode(errors="replace")
        else:
            stdout = exc.stdout or ""
        if isinstance(exc.stderr, bytes):
            stderr = exc.stderr.decode(errors="replace")
        else:
            stderr = exc.stderr or ""
    wall_ms = (time.perf_counter() - started) * 1000.0

    traces = parse_trace(stderr)
    algorithm_ms = max(
        (float(trace["elapsed_ms"]) for trace in traces), default=None
    )
    observed = 0
    beams = 0
    line_count = 0
    valid = False
    error = ""
    if timed_out:
        error = f"timeout after {timeout_ms} ms"
    elif returncode != 0:
        error = f"return code {returncode}: {' '.join(stderr.split())[:320]}"
    else:
        try:
            scored = scheduler_validator.validate_and_score(bundle.case, stdout)
            observed = scored.transmitted
            beams = scored.beam_used
            line_count = scored.line_count
            valid = True
        except Exception as exc:  # noqa: BLE001 - preserve validator diagnostics
            error = f"{type(exc).__name__}: {' '.join(str(exc).split())[:320]}"

    deadline_miss = timed_out or wall_ms > deadline_ms
    credited = observed if valid and not deadline_miss else 0
    trace_score_consistent = None
    if traces and valid:
        trace_score_consistent = int(traces[-1]["score"]) == observed

    return {
        "suite": suite,
        "scenario": bundle.scenario.name,
        "seed": bundle.seed,
        "instance_id": bundle.instance_id,
        "case_sha256": bundle.case_sha256,
        "method": method,
        "budget_ms": budget_ms,
        "repeat": repeat,
        "execution_order": execution_order,
        "seed_arg": seed_value,
        "observed_transmitted": observed,
        "credited_transmitted": credited,
        "demand": bundle.demand,
        "satisfaction": credited / bundle.demand if bundle.demand else 0.0,
        "solver_wall_ms": wall_ms,
        "algorithm_ms": algorithm_ms,
        "beams": beams,
        "line_count": line_count,
        "valid": valid,
        "deadline_miss": deadline_miss,
        "timeout": timed_out,
        "returncode": returncode,
        "trace_score_consistent": trace_score_consistent,
        "trace_count": len(traces),
        "error": error,
    }


def method_order(methods: Sequence[str], suite: str, instance_id: str, repeat: int) -> list[str]:
    ordered = list(methods)
    random.Random(stable_seed("method-order", suite, instance_id, repeat)).shuffle(ordered)
    return ordered


def condition_order(
    methods: Sequence[str], budgets: Sequence[int], suite: str, instance_id: str, repeat: int
) -> list[tuple[str, int]]:
    conditions = [(method, budget) for method in methods for budget in budgets]
    random.Random(stable_seed("condition-order", suite, instance_id, repeat)).shuffle(conditions)
    return conditions


def run_main(
    scheduler: Path,
    external: Mapping[str, Path],
    bundles: Sequence[protocol.CaseBundle],
    *,
    methods: Sequence[str],
    repeats: int,
    budget_ms: int,
    deadline_ms: float,
    timeout_ms: int,
    quiet: bool,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for index, bundle in enumerate(bundles, start=1):
        for repeat in range(repeats):
            for order, method in enumerate(method_order(methods, "main", bundle.instance_id, repeat)):
                records.append(
                    run_one(
                        scheduler,
                        external,
                        bundle,
                        suite="main",
                        method=method,
                        budget_ms=budget_ms,
                        repeat=repeat,
                        execution_order=order,
                        deadline_ms=deadline_ms,
                        timeout_ms=timeout_ms,
                    )
                )
        if not quiet:
            print(f"[main {index}/{len(bundles)}] {bundle.instance_id}", file=sys.stderr)
    return records


def run_budget(
    scheduler: Path,
    external: Mapping[str, Path],
    bundles: Sequence[protocol.CaseBundle],
    *,
    methods: Sequence[str],
    budgets: Sequence[int],
    repeats: int,
    deadline_ms: float,
    timeout_ms: int,
    quiet: bool,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for index, bundle in enumerate(bundles, start=1):
        for repeat in range(repeats):
            for order, (method, budget) in enumerate(
                condition_order(methods, budgets, "budget", bundle.instance_id, repeat)
            ):
                records.append(
                    run_one(
                        scheduler,
                        external,
                        bundle,
                        suite="budget",
                        method=method,
                        budget_ms=budget,
                        repeat=repeat,
                        execution_order=order,
                        deadline_ms=deadline_ms,
                        timeout_ms=timeout_ms,
                    )
                )
        if not quiet:
            print(f"[budget {index}/{len(bundles)}] {bundle.instance_id}", file=sys.stderr)
    return records


def run_exact(
    scheduler: Path,
    external: Mapping[str, Path],
    bundles: Sequence[protocol.CaseBundle],
    *,
    methods: Sequence[str],
    repeats: int,
    budget_ms: int,
    deadline_ms: float,
    timeout_ms: int,
    quiet: bool,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    records: list[dict[str, object]] = []
    optima: dict[str, int] = {}
    for index, bundle in enumerate(bundles, start=1):
        optimum = protocol.exact_optimum(bundle.case)
        optima[bundle.instance_id] = optimum
        for repeat in range(repeats):
            for order, method in enumerate(method_order(methods, "exact", bundle.instance_id, repeat)):
                records.append(
                    run_one(
                        scheduler,
                        external,
                        bundle,
                        suite="exact",
                        method=method,
                        budget_ms=budget_ms,
                        repeat=repeat,
                        execution_order=order,
                        deadline_ms=deadline_ms,
                        timeout_ms=timeout_ms,
                    )
                )
        if not quiet:
            print(
                f"[exact {index}/{len(bundles)}] {bundle.instance_id} optimum={optimum}",
                file=sys.stderr,
            )
    return records, optima


def aggregate(records: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for record in records:
        key = (
            record["suite"],
            record["scenario"],
            record["seed"],
            record["instance_id"],
            record["case_sha256"],
            record["method"],
            record["budget_ms"],
        )
        grouped[key].append(record)

    rows: list[dict[str, object]] = []
    for key, rows_for_key in sorted(grouped.items(), key=lambda item: str(item[0])):
        wall = [float(row["solver_wall_ms"]) for row in rows_for_key]
        algorithm = [
            float(row["algorithm_ms"])
            for row in rows_for_key
            if row["algorithm_ms"] is not None
        ]
        credited = [int(row["credited_transmitted"]) for row in rows_for_key]
        observed = [int(row["observed_transmitted"]) for row in rows_for_key]
        valid = [bool(row["valid"]) for row in rows_for_key]
        misses = [bool(row["deadline_miss"]) for row in rows_for_key]
        credited_median = statistics.median(credited)
        row = {
            "suite": key[0],
            "scenario": key[1],
            "seed": key[2],
            "instance_id": key[3],
            "case_sha256": key[4],
            "method": key[5],
            "budget_ms": key[6],
            "repeats": len(rows_for_key),
            "demand": rows_for_key[0]["demand"],
            "observed_median": statistics.median(observed),
            "credited_median": credited_median,
            "observed_min": min(observed),
            "observed_max": max(observed),
            "credited_min": min(credited),
            "credited_max": max(credited),
            "score_range": max(credited) - min(credited),
            "satisfaction": credited_median / float(rows_for_key[0]["demand"]),
            "wall_p50_ms": percentile(wall, 0.50),
            "wall_p95_ms": percentile(wall, 0.95),
            "wall_worst_ms": max(wall),
            "algorithm_p50_ms": percentile(algorithm, 0.50) if algorithm else None,
            "valid_rate": statistics.fmean(1.0 if value else 0.0 for value in valid),
            "deadline_miss_rate": statistics.fmean(1.0 if value else 0.0 for value in misses),
            "deadline_misses": sum(1 for value in misses if value),
        }
        rows.append(row)
    return rows


def stratified_bootstrap(
    values: Mapping[str, Sequence[float]], samples: int, seed: int
) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    distributions: list[float] = []
    for _ in range(samples):
        scenario_means = []
        for scenario in sorted(values):
            group = list(values[scenario])
            draws = [group[rng.randrange(len(group))] for _ in group]
            scenario_means.append(statistics.fmean(draws))
        distributions.append(statistics.fmean(scenario_means))
    return percentile(distributions, 0.025), percentile(distributions, 0.975)


def paired_comparison(
    aggregates: Sequence[Mapping[str, object]],
    *,
    candidate: str,
    baseline: str,
    budget_ms: int,
    samples: int,
    seed: int,
) -> dict[str, object]:
    lookup = {
        (row["suite"], row["instance_id"], row["method"], row["budget_ms"]): row
        for row in aggregates
    }
    gains_by_scenario: dict[str, list[float]] = defaultdict(list)
    wins = ties = losses = 0
    absolute: list[float] = []
    paired_instances = 0
    baseline_zero_instances = 0
    for row in aggregates:
        if row["suite"] != "main" or row["budget_ms"] != budget_ms:
            continue
        key = ("main", row["instance_id"], row["method"], budget_ms)
        if row["method"] != candidate:
            continue
        other = lookup.get(("main", row["instance_id"], baseline, budget_ms))
        if other is None:
            continue
        paired_instances += 1
        a = float(row["credited_median"])
        b = float(other["credited_median"])
        if a > b:
            wins += 1
        elif a < b:
            losses += 1
        else:
            ties += 1
        absolute.append(a - b)
        if b > 0:
            gains_by_scenario[str(row["scenario"])].append((a - b) / b)
        else:
            baseline_zero_instances += 1

    all_gains = [value for values in gains_by_scenario.values() for value in values]
    ci = stratified_bootstrap(gains_by_scenario, samples, seed)
    return {
        "candidate": candidate,
        "baseline": baseline,
        "budget_ms": budget_ms,
        "paired_instances": paired_instances,
        "relative_gain_instances": len(all_gains),
        "baseline_zero_instances": baseline_zero_instances,
        "mean_relative_gain": statistics.fmean(all_gains) if all_gains else 0.0,
        "mean_absolute_gain": statistics.fmean(absolute) if absolute else 0.0,
        "median_relative_gain": statistics.median(all_gains) if all_gains else 0.0,
        "stratified_bootstrap_95_ci": list(ci),
        "scenario_mean_relative_gain": {
            scenario: statistics.fmean(values)
            for scenario, values in sorted(gains_by_scenario.items())
        },
        "wins": wins,
        "ties": ties,
        "losses": losses,
    }


def method_summary(aggregates: Sequence[Mapping[str, object]], method: str) -> dict[str, object]:
    rows = [
        row
        for row in aggregates
        if row["suite"] == "main" and row["budget_ms"] == 87 and row["method"] == method
    ]
    return {
        "instances": len(rows),
        "mean_credited_median": statistics.fmean(float(row["credited_median"]) for row in rows)
        if rows
        else 0.0,
        "mean_satisfaction": statistics.fmean(float(row["satisfaction"]) for row in rows)
        if rows
        else 0.0,
        "mean_wall_p50_ms": statistics.fmean(float(row["wall_p50_ms"]) for row in rows)
        if rows
        else 0.0,
        "wall_p95_ms": percentile(
            [float(row["wall_p95_ms"]) for row in rows], 0.95
        )
        if rows
        else 0.0,
        "wall_worst_ms": max((float(row["wall_worst_ms"]) for row in rows), default=0.0),
        "valid_rate": statistics.fmean(float(row["valid_rate"]) for row in rows)
        if rows
        else 0.0,
        "deadline_miss_rate": statistics.fmean(
            float(row["deadline_miss_rate"]) for row in rows
        )
        if rows
        else 0.0,
    }


def exact_summary(
    aggregates: Sequence[Mapping[str, object]], optima: Mapping[str, int]
) -> dict[str, object]:
    summary: dict[str, object] = {}
    for method in sorted({str(row["method"]) for row in aggregates}):
        gaps = []
        optimal = 0
        rows = [
            row
            for row in aggregates
            if row["suite"] == "exact" and row["method"] == method
        ]
        for row in rows:
            optimum = optima[str(row["instance_id"])]
            gap = (
                (optimum - float(row["credited_median"])) / optimum if optimum else 0.0
            )
            gaps.append(gap)
            if abs(gap) < 1e-12:
                optimal += 1
        summary[method] = {
            "cases": len(gaps),
            "median_gap": statistics.median(gaps) if gaps else 0.0,
            "mean_gap": statistics.fmean(gaps) if gaps else 0.0,
            "max_gap": max(gaps) if gaps else 0.0,
            "optimal_count": optimal,
        }
    return summary


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_checksums(out_dir: Path) -> None:
    checksum = out_dir / "CHECKSUMS.sha256"
    names = sorted(
        path.name for path in out_dir.iterdir() if path.is_file() and path.name != checksum.name
    )
    checksum.write_text(
        "".join(f"{sha256_file(out_dir / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiments", default="main,budget,exact")
    parser.add_argument("--cases-per-scenario", type=int, default=30)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--exact-cases", type=int, default=12)
    parser.add_argument("--main-budget-ms", type=int, default=87)
    parser.add_argument(
        "--budgets", type=lambda value: parse_csv_list(value, cast=int), default=(20, 40, 60, 87)
    )
    parser.add_argument(
        "--methods",
        type=lambda value: parse_csv_list(value, cast=str),
        default=MAIN_METHODS,
    )
    parser.add_argument(
        "--budget-methods",
        type=lambda value: parse_csv_list(value, cast=str),
        default=BUDGET_METHODS,
    )
    parser.add_argument("--deadline-ms", type=float, default=100.0)
    parser.add_argument("--timeout-ms", type=int, default=500)
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260722)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--out", type=Path, default=ROOT / "reproducibility" / "external_comparison")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    if args.quick:
        args.cases_per_scenario = 1
        args.repeats = 1
        args.exact_cases = 1
        args.budgets = (20, 87)
        args.bootstrap_samples = min(args.bootstrap_samples, 250)
    allowed_methods = set(MAIN_METHODS)
    if not set(args.methods).issubset(allowed_methods):
        parser.error(f"--methods must use only {sorted(allowed_methods)}")
    if not set(args.budget_methods).issubset(allowed_methods):
        parser.error(f"--budget-methods must use only {sorted(allowed_methods)}")
    if args.cases_per_scenario < 1 or args.repeats < 1 or args.exact_cases < 1:
        parser.error("case and repeat counts must be positive")
    if args.timeout_ms <= max((*args.budgets, args.main_budget_ms)):
        parser.error("--timeout-ms must exceed every algorithm budget")
    return args


def main() -> None:
    args = parse_args()
    experiments = tuple(token.strip() for token in args.experiments.split(",") if token.strip())
    allowed_experiments = {"main", "budget", "exact"}
    if not set(experiments).issubset(allowed_experiments):
        raise SystemExit(f"unknown experiment in {experiments}; allowed={sorted(allowed_experiments)}")

    bundles: list[protocol.CaseBundle] = []
    if "main" in experiments or "budget" in experiments:
        bundles = protocol.heldout_bundles(args.cases_per_scenario)
    exact_bundles: list[protocol.CaseBundle] = []
    if "exact" in experiments:
        exact_bundles = protocol.exact_bundles(args.exact_cases)

    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="external-compare-build-") as build_name:
        scheduler, external = compile_binaries(Path(build_name), args.compiler)
        records: list[dict[str, object]] = []
        optima: dict[str, int] = {}
        if "main" in experiments:
            records.extend(
                run_main(
                    scheduler,
                    external,
                    bundles,
                    methods=args.methods,
                    repeats=args.repeats,
                    budget_ms=args.main_budget_ms,
                    deadline_ms=args.deadline_ms,
                    timeout_ms=args.timeout_ms,
                    quiet=args.quiet,
                )
            )
        if "budget" in experiments:
            records.extend(
                run_budget(
                    scheduler,
                    external,
                    bundles,
                    methods=args.budget_methods,
                    budgets=args.budgets,
                    repeats=args.repeats,
                    deadline_ms=args.deadline_ms,
                    timeout_ms=args.timeout_ms,
                    quiet=args.quiet,
                )
            )
        if "exact" in experiments:
            exact_records, optima = run_exact(
                scheduler,
                external,
                exact_bundles,
                methods=args.methods,
                repeats=args.repeats,
                budget_ms=args.main_budget_ms,
                deadline_ms=args.deadline_ms,
                timeout_ms=args.timeout_ms,
                quiet=args.quiet,
            )
            records.extend(exact_records)

        aggregates = aggregate(records)
        write_csv(args.out / "run_results.csv", records)
        write_csv(args.out / "instance_results.csv", aggregates)
        if bundles:
            write_csv(
                args.out / "case_manifest.csv",
                [
                    {
                        "scenario": bundle.scenario.name,
                        "seed": bundle.seed,
                        "instance_id": bundle.instance_id,
                        "case_sha256": bundle.case_sha256,
                        "P": bundle.case.P,
                        "N": bundle.case.N,
                        "K": bundle.case.K,
                        "T": bundle.case.T,
                        "beam_max": bundle.case.beam_max,
                        "max_group_size": bundle.max_group_size,
                        "double_memberships": bundle.double_memberships,
                        "nonadjacent_memberships": bundle.nonadjacent_memberships,
                    }
                    for bundle in bundles
                ],
            )

        summary: dict[str, object] = {
            "schema_version": 1,
            "protocol": {
                "main_methods": list(args.methods),
                "budget_methods": list(args.budget_methods),
                "main_budget_ms": args.main_budget_ms,
                "budgets_ms": list(args.budgets),
                "deadline_ms": args.deadline_ms,
                "timeout_ms": args.timeout_ms,
                "repeats": args.repeats,
                "unit_of_quality_analysis": "instance-level median over repeated process runs",
                "strict_credit_rule": "zero on invalid output, timeout, or external deadline miss",
                "case_source": "experiments.paper_experiments.heldout_bundles",
                "external_baselines": {
                    "ALNS": "src/external_alns_baseline.cpp",
                    "Tabu": "src/external_tabu_ga_baseline.cpp",
                    "GA": "src/external_tabu_ga_baseline.cpp",
                    "SA": "src/external_sa_ils_grasp.cpp",
                    "ILS": "src/external_sa_ils_grasp.cpp",
                    "GRASP": "src/external_sa_ils_grasp.cpp",
                },
            },
            "launches": len(records),
            "valid_launches": sum(1 for row in records if row["valid"]),
            "deadline_misses": sum(1 for row in records if row["deadline_miss"]),
            "methods": {
                method: method_summary(aggregates, method) for method in args.methods
            },
            "comparisons": {},
            "exact": exact_summary(aggregates, optima) if optima else {},
            "budget_curve": {},
        }
        for baseline in ("BeamFirst", "Base", "ALNS", "Tabu", "GA", "SA", "ILS", "GRASP"):
            if baseline in args.methods and "Full" in args.methods:
                summary["comparisons"][f"Full_vs_{baseline}"] = paired_comparison(
                    aggregates,
                    candidate="Full",
                    baseline=baseline,
                    budget_ms=args.main_budget_ms,
                    samples=args.bootstrap_samples,
                    seed=stable_seed("bootstrap", baseline, args.bootstrap_seed),
                )

        for budget in args.budgets:
            budget_rows = [
                row
                for row in aggregates
                if row["suite"] == "budget" and row["budget_ms"] == budget
            ]
            summary["budget_curve"][str(budget)] = {
                method: {
                    "instances": sum(1 for row in budget_rows if row["method"] == method),
                    "mean_credited_median": statistics.fmean(
                        float(row["credited_median"])
                        for row in budget_rows
                        if row["method"] == method
                    )
                    if any(row["method"] == method for row in budget_rows)
                    else 0.0,
                    "mean_wall_p50_ms": statistics.fmean(
                        float(row["wall_p50_ms"])
                        for row in budget_rows
                        if row["method"] == method
                    )
                    if any(row["method"] == method for row in budget_rows)
                    else 0.0,
                }
                for method in args.budget_methods
            }

        manifest = {
            "schema_version": 1,
            "generator": "external-comparison-v3",
            "experiments": list(experiments),
            "methods": list(args.methods),
            "budget_methods": list(args.budget_methods),
            "compiler": args.compiler,
            "compile_flags": ["-std=c++17", "-O2"],
            "scheduler_binary_sha256": sha256_file(scheduler),
            "external_binary_sha256": {
                method: sha256_file(binary) for method, binary in external.items()
            },
            "source_sha256": {
                str(path.relative_to(ROOT)): sha256_file(path)
                for path in (
                    ROOT / "src" / "scheduler.cpp",
                    ROOT / "src" / "core.cpp",
                    ROOT / "src" / "external_alns_baseline.cpp",
                    ROOT / "src" / "external_tabu_ga_baseline.cpp",
                    ROOT / "src" / "external_sa_ils_grasp.cpp",
                    ROOT / "tools" / "scheduler_validator.py",
                    ROOT / "experiments" / "paper_experiments.py",
                    ROOT / "experiments" / "external_comparison.py",
                )
            },
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "processor": platform.processor(),
            },
            "case_count": len(bundles),
            "exact_case_count": len(exact_bundles),
        }
        (args.out / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (args.out / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    write_checksums(args.out)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
