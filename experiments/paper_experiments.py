#!/usr/bin/env python3
"""Reproducible cumulative-ablation experiments for the scheduler paper.

The protocol uses five fixed held-out scenario families, repeated executions,
deterministically randomized method order, instance-level medians, budget sweeps,
compatibility-group stress tests, and exhaustive tiny-instance optima.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import platform
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from contextlib import nullcontext
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments import analyze_results  # noqa: E402
from tools import scheduler_validator  # noqa: E402


METHODS = ("BeamFirst", "Base", "Global", "CG", "Remask", "Full")
STAGE_ARGUMENT = {
    "BeamFirst": "beamfirst",
    "Base": "base",
    "Global": "global",
    "CG": "cg",
    "Remask": "remask",
    "Full": "full",
}
DEFAULT_BUDGETS = (20, 40, 60, 87)
DEFAULT_STRESS_GROUP_SIZES = (2, 5, 10, 15, 20)
DEFAULT_STRESS_METHODS = ("Base", "CG", "Full")
FORMAL_HELDOUT_SEED_BASE = 20261001
FORMAL_STRESS_SEED_BASE = 20271001
FORMAL_EXACT_SEED_BASE = 20281001
QA_HELDOUT_SEED_BASE = 20260801
QA_STRESS_SEED_BASE = 20265801
QA_EXACT_SEED_BASE = 20269801
TRACE_RE = re.compile(
    r"^TRACE stage=(?P<stage>[a-z_]+) score=(?P<score>-?[0-9]+) "
    r"elapsed_ms=(?P<elapsed>[0-9]+(?:\.[0-9]+)?) "
    r"deadline_hit=(?P<deadline>[01])$"
)


@dataclass(frozen=True)
class Scenario:
    name: str
    n: int
    k: int
    p: int
    t: int
    beam_ratio: float
    ru_ratio: float
    overlap_ratio: float
    traffic: str
    channel: str
    fixed_group_size: int | None = None
    nonadjacent_ratio: float = 0.0


HELDOUT_SCENARIOS = (
    Scenario("small-balanced", 20, 18, 8, 4, 0.45, 0.35, 0.10, "uniform", "uniform"),
    Scenario(
        "medium-longtail",
        50,
        36,
        16,
        9,
        0.32,
        0.55,
        0.15,
        "long-tail",
        "clustered",
    ),
    Scenario(
        "medium-tight",
        50,
        36,
        16,
        9,
        0.18,
        0.65,
        0.20,
        "bimodal",
        "heterogeneous",
    ),
    Scenario(
        "large-mixed",
        100,
        72,
        32,
        18,
        0.22,
        0.70,
        0.15,
        "long-tail",
        "clustered",
    ),
    Scenario(
        "large-nonadjacent",
        100,
        72,
        32,
        18,
        0.16,
        0.75,
        0.30,
        "bimodal",
        "heterogeneous",
        nonadjacent_ratio=0.80,
    ),
)


@dataclass(frozen=True)
class CaseBundle:
    scenario: Scenario
    seed: int
    instance_id: str
    text: str
    case_sha256: str
    case: scheduler_validator.CaseInput
    demand: int
    double_memberships: int
    nonadjacent_memberships: int
    max_group_size: int


@dataclass
class RunRecord:
    experiment: str
    scenario: str
    seed: int
    instance_id: str
    case_sha256: str
    method: str
    variant: str
    stage_argument: str
    budget_ms: int
    repeat: int
    execution_order: int
    reused: bool
    transmitted: int
    observed_transmitted: int
    credited_transmitted: int
    demand: int
    satisfaction: float
    elapsed_ms: float
    solver_wall_ms: float
    algorithm_ms: float | None
    validation_ms: float
    end_to_end_ms: float
    beams: int
    valid: bool
    deadline_miss: bool
    timeout: bool
    returncode: int
    trace_deadline_hit: bool | None
    trace_monotone: bool | None
    trace_score_consistent: bool | None
    trace_scores: str
    error: str


RAW_FIELDS = [field.name for field in fields(RunRecord)]
AGGREGATE_FIELDS = [
    "experiment",
    "scenario",
    "seed",
    "instance_id",
    "case_sha256",
    "method",
    "variant",
    "budget_ms",
    "repeats",
    "demand",
    "observed_transmitted",
    "observed_transmitted_median",
    "observed_transmitted_min",
    "observed_transmitted_max",
    "transmitted",
    "transmitted_median",
    "transmitted_min",
    "transmitted_max",
    "satisfaction",
    "score_stdev",
    "score_range",
    "elapsed_ms",
    "runtime_p50_ms",
    "runtime_p95_ms",
    "runtime_worst_ms",
    "algorithm_p50_ms",
    "validation_p50_ms",
    "end_to_end_p50_ms",
    "feasible_rate",
    "valid",
    "deadline_misses",
    "deadline_miss_rate",
    "timeout_rate",
    "trace_monotone_rate",
    "trace_score_consistency_rate",
]
EXACT_FIELDS = [
    *AGGREGATE_FIELDS,
    "optimum",
    "absolute_gap",
    "relative_gap",
    "optimal",
]
CASE_FIELDS = [
    "experiment",
    "scenario",
    "seed",
    "instance_id",
    "case_sha256",
    "P",
    "N",
    "K",
    "T",
    "beam_max",
    "compatibility_groups",
    "max_group_size",
    "double_memberships",
    "nonadjacent_memberships",
]
TRACE_ABLATION_STAGES = analyze_results.TRACE_STAGES
TRACE_ABLATION_SOURCE = {
    "Base": "base",
    "Global": "global",
    "CG": "cg",
    "Remask": "remask",
    "Full": "final",
}
TRACE_ABLATION_FIELDS = [
    "experiment",
    "scenario",
    "seed",
    "instance_id",
    "case_sha256",
    "repeat",
    "stage",
    "stage_order",
    "trace_source",
    "stage_trace_present",
    "budget_ms",
    "demand",
    "observed_stage_score",
    "credited_stage_score",
    "score",
    "satisfaction",
    "stage_elapsed_ms",
    "stage_deadline_hit",
    "run_valid",
    "run_deadline_miss",
    "run_timeout",
    "run_returncode",
    "run_credit_eligible",
    "solver_wall_ms",
]


def _stable_seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile(values: Sequence[float], q: float) -> float:
    return analyze_results.percentile(values, q)


def _clean_error(value: object, limit: int = 320) -> str:
    text = " ".join(str(value).split())
    return text[:limit]


def _parse_csv_list(text: str, *, cast=str) -> tuple:
    values = tuple(cast(token.strip()) for token in text.split(",") if token.strip())
    if not values:
        raise argparse.ArgumentTypeError("expected at least one comma-separated value")
    return values


def partition_users(
    rng: random.Random,
    n: int,
    ru_ratio: float,
    fixed_group_size: int | None = None,
) -> tuple[list[list[int]], list[int]]:
    """Create disjoint compatibility groups and an optional SU metadata list."""

    users = list(range(1, n + 1))
    rng.shuffle(users)
    target = min(n, max(0, round(n * ru_ratio)))
    groups: list[list[int]] = []
    grouped_count = 0

    if target >= 2:
        if fixed_group_size is not None:
            if not 2 <= fixed_group_size <= 20:
                raise ValueError("fixed compatibility-group size must lie in 2..20")
            group_count = min(16, target // fixed_group_size)
            grouped_count = group_count * fixed_group_size
            for group_index in range(group_count):
                begin = group_index * fixed_group_size
                groups.append(sorted(users[begin : begin + fixed_group_size]))
        else:
            minimum_groups = max(1, math.ceil(target / 20))
            maximum_groups = min(16, target // 2)
            desired_groups = max(1, round(target / 6))
            group_count = min(maximum_groups, max(minimum_groups, desired_groups))
            sizes = [target // group_count] * group_count
            for index in range(target % group_count):
                sizes[index] += 1
            cursor = 0
            for size in sizes:
                groups.append(sorted(users[cursor : cursor + size]))
                cursor += size
            grouped_count = cursor

    ungrouped = users[grouped_count:]
    rng.shuffle(ungrouped)
    su = sorted(ungrouped[:29])
    return groups, su


def resource_bands(
    rng: random.Random,
    k: int,
    t: int,
    overlap_ratio: float,
    nonadjacent_ratio: float = 0.0,
) -> list[list[int]]:
    """Assign each resource one or two explicit subband memberships."""

    memberships = [[] for _ in range(k + 1)]
    for resource in range(1, k + 1):
        memberships[resource].append(min(t, (resource - 1) * t // k + 1))

    if t <= 1:
        return memberships

    overlap_count = min(k, max(0, round(k * overlap_ratio)))
    selected = list(range(1, k + 1))
    rng.shuffle(selected)
    selected = selected[:overlap_count]
    nonadjacent_count = min(overlap_count, max(0, round(overlap_count * nonadjacent_ratio)))

    for index, resource in enumerate(selected):
        primary = memberships[resource][0]
        far = [band for band in range(1, t + 1) if abs(band - primary) >= 2]
        adjacent = [band for band in range(1, t + 1) if abs(band - primary) == 1]
        if index < nonadjacent_count and far:
            candidates = far
        else:
            candidates = adjacent or far
        if candidates:
            memberships[resource].append(rng.choice(candidates))
            memberships[resource].sort()
    return memberships


def generate_case(scenario: Scenario, seed: int) -> str:
    rng = random.Random(seed)
    p, n, k, t = scenario.p, scenario.n, scenario.k, scenario.t
    beam_max = max(2, min(255, round(p * t * scenario.beam_ratio)))
    groups, su = partition_users(rng, n, scenario.ru_ratio, scenario.fixed_group_size)
    memberships = resource_bands(
        rng,
        k,
        t,
        scenario.overlap_ratio,
        scenario.nonadjacent_ratio,
    )

    caps: list[list[int]] = []
    buffers: list[int] = []
    sinrs: list[int] = []
    for _user in range(n):
        hot = rng.randrange(p)
        row: list[int] = []
        for beam in range(p):
            if scenario.channel == "clustered":
                distance = min((beam - hot) % p, (hot - beam) % p)
                mean = 4200 / (1 + distance) + 250
                value = int(rng.lognormvariate(math.log(mean), 0.32))
            elif scenario.channel == "heterogeneous":
                scale = 6500 if beam == hot else 700
                value = int(rng.lognormvariate(math.log(scale), 0.65))
            else:
                value = rng.randint(300, 5000)
            row.append(max(1, min(65535, value)))
        caps.append(row)

        if scenario.traffic == "long-tail":
            buffer_value = int(rng.lognormvariate(math.log(900), 1.0))
        elif scenario.traffic == "bimodal":
            buffer_value = rng.randint(80, 500) if rng.random() < 0.55 else rng.randint(3500, 10000)
        else:
            buffer_value = rng.randint(300, 5000)
        buffers.append(max(1, min(10000, buffer_value)))

        if scenario.channel == "heterogeneous":
            sinrs.append(rng.randint(-30, 32))
        elif scenario.channel == "clustered":
            sinrs.append(rng.randint(-25, 30))
        else:
            sinrs.append(rng.randint(-22, 28))

    sub_resources = [[] for _ in range(t + 1)]
    for resource in range(1, k + 1):
        for band in memberships[resource]:
            sub_resources[band].append(resource)

    lines = [f"{p} {n} {k} {t} {beam_max}", str(len(groups))]
    lines.extend(f"{len(group)} {' '.join(map(str, group))}" for group in groups)
    lines.append(f"{len(su)}" + (f" {' '.join(map(str, su))}" if su else ""))
    lines.extend(" ".join(map(str, row)) for row in caps)
    lines.extend(f"{buffers[index]} {sinrs[index]}" for index in range(n))
    for band in range(1, t + 1):
        resources = sub_resources[band]
        lines.append(
            f"{len(resources)}" + (f" {' '.join(map(str, resources))}" if resources else "")
        )
    return "\n".join(lines) + "\n"


def make_bundle(scenario: Scenario, seed: int) -> CaseBundle:
    text = generate_case(scenario, seed)
    instance_id = f"{scenario.name}-{seed}"
    case = scheduler_validator.parse_case_text(text, case_id=instance_id)
    double_memberships = sum(len(case.res_bands[resource]) == 2 for resource in range(1, case.K + 1))
    nonadjacent_memberships = sum(
        len(case.res_bands[resource]) == 2
        and case.res_bands[resource][1] - case.res_bands[resource][0] > 1
        for resource in range(1, case.K + 1)
    )
    return CaseBundle(
        scenario=scenario,
        seed=seed,
        instance_id=instance_id,
        text=text,
        case_sha256=_sha256_text(text),
        case=case,
        demand=sum(case.buffer[1:]),
        double_memberships=double_memberships,
        nonadjacent_memberships=nonadjacent_memberships,
        max_group_size=max((len(group) for group in case.ru), default=0),
    )


def heldout_bundles(
    seeds_per_scenario: int, seed_base: int = FORMAL_HELDOUT_SEED_BASE
) -> list[CaseBundle]:
    bundles: list[CaseBundle] = []
    for scenario_index, scenario in enumerate(HELDOUT_SCENARIOS):
        for offset in range(seeds_per_scenario):
            seed = seed_base + scenario_index * 1000 + offset
            bundles.append(make_bundle(scenario, seed))
    return bundles


def stress_bundles(
    seeds_per_group_size: int, seed_base: int = FORMAL_STRESS_SEED_BASE
) -> list[CaseBundle]:
    bundles: list[CaseBundle] = []
    for size_index, group_size in enumerate(DEFAULT_STRESS_GROUP_SIZES):
        scenario = Scenario(
            f"cg-size-{group_size:02d}",
            60,
            36,
            16,
            9,
            0.24,
            (2 * group_size) / 60,
            0.25,
            "bimodal",
            "heterogeneous",
            fixed_group_size=group_size,
            nonadjacent_ratio=0.40,
        )
        for offset in range(seeds_per_group_size):
            seed = seed_base + size_index * 1000 + offset
            bundles.append(make_bundle(scenario, seed))
    return bundles


def exact_bundles(
    count: int, seed_base: int = FORMAL_EXACT_SEED_BASE
) -> list[CaseBundle]:
    """Build a bounded diagnostic exact suite.

    The provided predeclared consecutive seed interval seed_base..+count-1 is
    used without outcome-based filtering.  Its first seed uses a wider beam
    space; remaining seeds use a smaller family so exhaustive enumeration stays
    bounded.  These cases validate gaps, not the held-out performance claim.
    """

    widebeam_scenario = Scenario(
        "tiny-widebeam",
        8,
        8,
        6,
        4,
        2 / 24,
        1.0,
        0.35,
        "bimodal",
        "heterogeneous",
        fixed_group_size=4,
        nonadjacent_ratio=0.50,
    )
    bundles = [make_bundle(widebeam_scenario, seed_base)]
    if count == 1:
        return bundles

    core_scenario = Scenario(
        "tiny-exact",
        5,
        4,
        4,
        3,
        0.25,
        0.80,
        0.50,
        "bimodal",
        "heterogeneous",
        fixed_group_size=4,
        nonadjacent_ratio=1.0,
    )
    bundles.extend(
        make_bundle(core_scenario, seed_base + index)
        for index in range(1, count)
    )
    return bundles


def compile_scheduler(build_dir: Path, compiler: str = "g++") -> Path:
    binary = build_dir / "scheduler_experiment"
    command = [
        compiler,
        "-std=c++17",
        "-O2",
        str(ROOT / "src" / "scheduler.cpp"),
        str(ROOT / "src" / "core.cpp"),
        "-o",
        str(binary),
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"scheduler compilation failed: {_clean_error(result.stderr, 2000)}")
    return binary


def _parse_trace(stderr: str) -> list[dict[str, object]]:
    traces: list[dict[str, object]] = []
    for line in stderr.splitlines():
        match = TRACE_RE.fullmatch(line.strip())
        if not match:
            continue
        traces.append(
            {
                "stage": match.group("stage"),
                "score": int(match.group("score")),
                "elapsed_ms": float(match.group("elapsed")),
                "deadline_hit": bool(int(match.group("deadline"))),
            }
        )
    return traces


def run_solver(
    binary: Path,
    bundle: CaseBundle,
    *,
    experiment: str,
    method: str,
    budget_ms: int,
    repeat: int,
    execution_order: int,
    timeout_ms: int,
    deadline_ms: float,
    cpu: int | None,
) -> RunRecord:
    command: list[str] = []
    if cpu is not None:
        command.extend(["taskset", "--cpu-list", str(cpu)])
    command.extend(
        [
            str(binary),
            "--stage",
            STAGE_ARGUMENT[method],
            "--budget-ms",
            str(budget_ms),
            "--trace",
        ]
    )

    wall_started = time.perf_counter()
    timed_out = False
    returncode = -1
    stdout = ""
    stderr = ""
    try:
        proc = subprocess.run(
            command,
            input=bundle.text,
            text=True,
            capture_output=True,
            timeout=timeout_ms / 1000.0,
            check=False,
            cwd=ROOT,
        )
        returncode = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    solver_wall_ms = (time.perf_counter() - wall_started) * 1000.0

    traces = _parse_trace(stderr)
    algorithm_ms = max((float(trace["elapsed_ms"]) for trace in traces), default=None)
    trace_deadline_hit = (
        any(bool(trace["deadline_hit"]) for trace in traces) if traces else None
    )
    trace_monotone = (
        all(
            int(traces[index]["score"]) >= int(traces[index - 1]["score"])
            for index in range(1, len(traces))
        )
        if traces
        else None
    )

    observed_transmitted = 0
    beams = 0
    valid = False
    error = ""
    validation_started = time.perf_counter()
    if timed_out:
        error = f"timeout after {timeout_ms} ms"
    elif returncode != 0:
        error = f"return code {returncode}: {_clean_error(stderr)}"
    else:
        try:
            result = scheduler_validator.validate_and_score(bundle.case, stdout)
            observed_transmitted = result.transmitted
            beams = result.beam_used
            valid = True
        except Exception as exc:
            error = f"{type(exc).__name__}: {_clean_error(exc)}"
    validation_ms = (time.perf_counter() - validation_started) * 1000.0

    deadline_miss = timed_out or solver_wall_ms > deadline_ms
    credited_transmitted = (
        observed_transmitted if valid and not deadline_miss else 0
    )
    trace_score_consistent: bool | None = None
    if traces and valid:
        trace_score_consistent = (
            int(traces[-1]["score"]) == observed_transmitted
        )

    return RunRecord(
        experiment=experiment,
        scenario=bundle.scenario.name,
        seed=bundle.seed,
        instance_id=bundle.instance_id,
        case_sha256=bundle.case_sha256,
        method=method,
        variant=method,
        stage_argument=STAGE_ARGUMENT[method],
        budget_ms=budget_ms,
        repeat=repeat,
        execution_order=execution_order,
        reused=False,
        transmitted=credited_transmitted,
        observed_transmitted=observed_transmitted,
        credited_transmitted=credited_transmitted,
        demand=bundle.demand,
        satisfaction=credited_transmitted / bundle.demand,
        elapsed_ms=solver_wall_ms,
        solver_wall_ms=solver_wall_ms,
        algorithm_ms=algorithm_ms,
        validation_ms=validation_ms,
        end_to_end_ms=solver_wall_ms + validation_ms,
        beams=beams,
        valid=valid,
        deadline_miss=deadline_miss,
        timeout=timed_out,
        returncode=returncode,
        trace_deadline_hit=trace_deadline_hit,
        trace_monotone=trace_monotone,
        trace_score_consistent=trace_score_consistent,
        trace_scores=json.dumps(traces, separators=(",", ":")),
        error=error,
    )


def _progress(message: str, quiet: bool) -> None:
    if not quiet:
        print(message, file=sys.stderr, flush=True)


def run_main_experiment(
    binary: Path,
    bundles: Sequence[CaseBundle],
    *,
    repeats: int,
    budget_ms: int,
    timeout_ms: int,
    deadline_ms: float,
    cpu: int | None,
    quiet: bool,
) -> list[RunRecord]:
    records: list[RunRecord] = []
    for bundle_index, bundle in enumerate(bundles, start=1):
        for repeat_index in range(repeats):
            order = list(METHODS)
            random.Random(
                _stable_seed("main-method-order", bundle.instance_id, repeat_index)
            ).shuffle(order)
            for execution_order, method in enumerate(order):
                records.append(
                    run_solver(
                        binary,
                        bundle,
                        experiment="main",
                        method=method,
                        budget_ms=budget_ms,
                        repeat=repeat_index,
                        execution_order=execution_order,
                        timeout_ms=timeout_ms,
                        deadline_ms=deadline_ms,
                        cpu=cpu,
                    )
                )
        _progress(
            f"[main {bundle_index}/{len(bundles)}] {bundle.instance_id} complete",
            quiet,
        )
    return records


def run_budget_experiment(
    binary: Path,
    bundles: Sequence[CaseBundle],
    *,
    repeats: int,
    budgets: Sequence[int],
    main_budget_ms: int,
    main_records: Sequence[RunRecord],
    timeout_ms: int,
    deadline_ms: float,
    cpu: int | None,
    quiet: bool,
) -> list[RunRecord]:
    records: list[RunRecord] = []
    # Every budget point is executed independently.  Keeping the parameters in
    # the signature preserves the public experiment API without reusing main
    # Full runs, so execution_order remains a physical order.
    del main_budget_ms, main_records
    for bundle_index, bundle in enumerate(bundles, start=1):
        for repeat_index in range(repeats):
            order = list(budgets)
            random.Random(
                _stable_seed("budget-order", bundle.instance_id, repeat_index)
            ).shuffle(order)
            for execution_order, budget_ms in enumerate(order):
                records.append(
                    run_solver(
                        binary,
                        bundle,
                        experiment="budget",
                        method="Full",
                        budget_ms=budget_ms,
                        repeat=repeat_index,
                        execution_order=execution_order,
                        timeout_ms=timeout_ms,
                        deadline_ms=deadline_ms,
                        cpu=cpu,
                    )
                )
        _progress(
            f"[budget {bundle_index}/{len(bundles)}] {bundle.instance_id} complete",
            quiet,
        )
    return records


def run_stress_experiment(
    binary: Path,
    bundles: Sequence[CaseBundle],
    *,
    repeats: int,
    methods: Sequence[str],
    budget_ms: int,
    timeout_ms: int,
    deadline_ms: float,
    cpu: int | None,
    quiet: bool,
) -> list[RunRecord]:
    records: list[RunRecord] = []
    for bundle_index, bundle in enumerate(bundles, start=1):
        for repeat_index in range(repeats):
            order = list(methods)
            random.Random(
                _stable_seed("stress-method-order", bundle.instance_id, repeat_index)
            ).shuffle(order)
            for execution_order, method in enumerate(order):
                records.append(
                    run_solver(
                        binary,
                        bundle,
                        experiment="stress",
                        method=method,
                        budget_ms=budget_ms,
                        repeat=repeat_index,
                        execution_order=execution_order,
                        timeout_ms=timeout_ms,
                        deadline_ms=deadline_ms,
                        cpu=cpu,
                    )
                )
        _progress(
            f"[stress {bundle_index}/{len(bundles)}] {bundle.instance_id} complete",
            quiet,
        )
    return records


def legal_groups(case: scheduler_validator.CaseInput) -> list[tuple[int, ...]]:
    groups: set[tuple[int, ...]] = {()}
    groups.update((user,) for user in range(1, case.N + 1))
    for compatibility_group in case.ru:
        for size in range(2, len(compatibility_group) + 1):
            groups.update(itertools.combinations(compatibility_group, size))
    return sorted(groups, key=lambda users: (len(users), users))


def _exact_beam_plans(case: scheduler_validator.CaseInput) -> Iterable[list[int]]:
    positions = case.T * case.P
    budget = min(case.beam_max, positions)
    for active_count in range(budget + 1):
        for active in itertools.combinations(range(positions), active_count):
            masks = [0] * (case.T + 1)
            for position in active:
                band = position // case.P + 1
                beam = position % case.P
                masks[band] |= 1 << beam
            yield masks


def _dominance_prune(states: set[tuple[int, ...]]) -> set[tuple[int, ...]]:
    ordered = sorted(states, key=lambda state: (sum(state), state), reverse=True)
    frontier: list[tuple[int, ...]] = []
    for state in ordered:
        if any(
            all(kept[index] >= state[index] for index in range(len(state)))
            for kept in frontier
        ):
            continue
        frontier.append(state)
    return set(frontier)


def _resource_rate_choices(
    case: scheduler_validator.CaseInput,
    masks: Sequence[int],
    resource: int,
    groups: Sequence[tuple[int, ...]],
) -> tuple[tuple[int, ...], ...]:
    bands = case.res_bands[resource]
    zero = (0,) * case.N
    if any(masks[band] == 0 for band in bands):
        return (zero,)

    denominator = bands[-1] - bands[0] + 1
    choices: set[tuple[int, ...]] = {zero}
    for users in groups:
        if not users:
            continue
        share = len(users)
        rates = [0] * case.N
        for user in users:
            selected_sum = 0.0
            for band in bands:
                selected_sum += sum(
                    case.cap[user][beam]
                    for beam in range(1, case.P + 1)
                    if masks[band] & (1 << (beam - 1))
                )
            selected_average = selected_sum / denominator
            if selected_average <= 0.0:
                continue
            fse = (
                case.sinr[user]
                + 10.0 * math.log10(1.0 / share)
                + 10.0 * math.log10(selected_average / case.total_cap[user])
            )
            rates[user - 1] = scheduler_validator.cap_of(fse)
        choices.add(tuple(rates))
    return tuple(choices)


def exact_optimum(case: scheduler_validator.CaseInput) -> int:
    """Exhaustively optimize beam subsets and resource choices for tiny cases."""

    groups = legal_groups(case)
    buffers = tuple(case.buffer[1:])
    best = 0
    for masks in _exact_beam_plans(case):
        states: set[tuple[int, ...]] = {(0,) * case.N}
        for resource in range(1, case.K + 1):
            choices = _resource_rate_choices(case, masks, resource, groups)
            next_states: set[tuple[int, ...]] = set()
            for state in states:
                for choice in choices:
                    next_states.add(
                        tuple(
                            min(buffers[index], state[index] + choice[index])
                            for index in range(case.N)
                        )
                    )
            states = _dominance_prune(next_states)
        best = max(best, max((sum(state) for state in states), default=0))
    return best


def run_exact_experiment(
    binary: Path,
    bundles: Sequence[CaseBundle],
    *,
    repeats: int,
    budget_ms: int,
    timeout_ms: int,
    deadline_ms: float,
    cpu: int | None,
    quiet: bool,
) -> tuple[list[RunRecord], dict[str, int]]:
    records: list[RunRecord] = []
    optima: dict[str, int] = {}
    for bundle_index, bundle in enumerate(bundles, start=1):
        optimum = exact_optimum(bundle.case)
        optima[bundle.instance_id] = optimum
        for repeat_index in range(repeats):
            order = list(METHODS)
            random.Random(
                _stable_seed("exact-method-order", bundle.instance_id, repeat_index)
            ).shuffle(order)
            for execution_order, method in enumerate(order):
                records.append(
                    run_solver(
                        binary,
                        bundle,
                        experiment="exact",
                        method=method,
                        budget_ms=budget_ms,
                        repeat=repeat_index,
                        execution_order=execution_order,
                        timeout_ms=timeout_ms,
                        deadline_ms=deadline_ms,
                        cpu=cpu,
                    )
                )
        _progress(
            f"[exact {bundle_index}/{len(bundles)}] {bundle.instance_id} optimum={optimum}",
            quiet,
        )
    return records, optima


def aggregate_records(records: Sequence[RunRecord]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[RunRecord]] = defaultdict(list)
    for record in records:
        key = (
            record.experiment,
            record.scenario,
            record.seed,
            record.instance_id,
            record.case_sha256,
            record.method,
            record.budget_ms,
        )
        grouped[key].append(record)

    aggregates: list[dict[str, object]] = []
    for key, rows in sorted(grouped.items()):
        scores = [float(row.transmitted) for row in rows]
        observed_scores = [float(row.observed_transmitted) for row in rows]
        runtimes = [row.solver_wall_ms for row in rows]
        algorithm_times = [row.algorithm_ms for row in rows if row.algorithm_ms is not None]
        validation_times = [row.validation_ms for row in rows]
        end_to_end_times = [row.end_to_end_ms for row in rows]
        trace_monotone = [row.trace_monotone for row in rows if row.trace_monotone is not None]
        trace_consistent = [
            row.trace_score_consistent
            for row in rows
            if row.trace_score_consistent is not None
        ]
        median_score = statistics.median(scores)
        demand = rows[0].demand
        aggregates.append(
            {
                "experiment": key[0],
                "scenario": key[1],
                "seed": key[2],
                "instance_id": key[3],
                "case_sha256": key[4],
                "method": key[5],
                "variant": key[5],
                "budget_ms": key[6],
                "repeats": len(rows),
                "demand": demand,
                "observed_transmitted": statistics.median(observed_scores),
                "observed_transmitted_median": statistics.median(observed_scores),
                "observed_transmitted_min": min(observed_scores),
                "observed_transmitted_max": max(observed_scores),
                "transmitted": median_score,
                "transmitted_median": median_score,
                "transmitted_min": min(scores),
                "transmitted_max": max(scores),
                "satisfaction": median_score / demand,
                "score_stdev": statistics.pstdev(scores),
                "score_range": max(scores) - min(scores),
                "elapsed_ms": percentile(runtimes, 0.50),
                "runtime_p50_ms": percentile(runtimes, 0.50),
                "runtime_p95_ms": percentile(runtimes, 0.95),
                "runtime_worst_ms": max(runtimes),
                "algorithm_p50_ms": (
                    percentile(algorithm_times, 0.50) if algorithm_times else None
                ),
                "validation_p50_ms": percentile(validation_times, 0.50),
                "end_to_end_p50_ms": percentile(end_to_end_times, 0.50),
                "feasible_rate": statistics.fmean(1.0 if row.valid else 0.0 for row in rows),
                "valid": all(row.valid for row in rows),
                "deadline_misses": sum(row.deadline_miss for row in rows),
                "deadline_miss_rate": statistics.fmean(
                    1.0 if row.deadline_miss else 0.0 for row in rows
                ),
                "timeout_rate": statistics.fmean(1.0 if row.timeout else 0.0 for row in rows),
                "trace_monotone_rate": (
                    statistics.fmean(1.0 if value else 0.0 for value in trace_monotone)
                    if trace_monotone
                    else None
                ),
                "trace_score_consistency_rate": (
                    statistics.fmean(1.0 if value else 0.0 for value in trace_consistent)
                    if trace_consistent
                    else None
                ),
            }
        )
    return aggregates


def extract_trace_ablation_rows(
    main_records: Sequence[RunRecord],
) -> list[dict[str, object]]:
    """Extract credited cumulative stages from each repeated Full run."""

    rows: list[dict[str, object]] = []
    full_records = [record for record in main_records if record.method == "Full"]
    for record in full_records:
        traces = json.loads(record.trace_scores) if record.trace_scores else []
        trace_by_source: dict[str, Mapping[str, object]] = {}
        for trace in traces:
            source = str(trace["stage"])
            if source in trace_by_source:
                raise RuntimeError(
                    f"duplicate trace stage {source} for {record.instance_id} "
                    f"repeat {record.repeat}"
                )
            trace_by_source[source] = trace

        credit_eligible = (
            record.valid
            and not record.deadline_miss
            and not record.timeout
            and record.returncode == 0
        )
        selected: dict[str, Mapping[str, object] | None] = {}
        for stage in TRACE_ABLATION_STAGES:
            source = TRACE_ABLATION_SOURCE[stage]
            trace = trace_by_source.get(source)
            if stage == "Full" and trace is None:
                trace = trace_by_source.get("pair")
            selected[stage] = trace

        missing = [stage for stage, trace in selected.items() if trace is None]
        if credit_eligible and missing:
            raise RuntimeError(
                f"credit-eligible Full run {record.instance_id} repeat {record.repeat} "
                f"is missing trace stages {missing}"
            )

        observed = [
            int(selected[stage]["score"])
            for stage in TRACE_ABLATION_STAGES
            if selected[stage] is not None
        ]
        if credit_eligible and any(
            observed[index] < observed[index - 1]
            for index in range(1, len(observed))
        ):
            raise RuntimeError(
                f"nonmonotone eligible Full trace for {record.instance_id} "
                f"repeat {record.repeat}: {observed}"
            )
        final_trace = selected["Full"]
        score_matches = (
            final_trace is not None
            and int(final_trace["score"]) == record.observed_transmitted
        )
        if record.valid and not score_matches:
            raise RuntimeError(
                f"final trace score differs from independent validation for "
                f"{record.instance_id} repeat {record.repeat}"
            )

        for stage_order, stage in enumerate(TRACE_ABLATION_STAGES):
            trace = selected[stage]
            observed_score = int(trace["score"]) if trace is not None else None
            credited_score = (
                observed_score if credit_eligible and observed_score is not None else 0
            )
            rows.append(
                {
                    "experiment": "trace_ablation",
                    "scenario": record.scenario,
                    "seed": record.seed,
                    "instance_id": record.instance_id,
                    "case_sha256": record.case_sha256,
                    "repeat": record.repeat,
                    "stage": stage,
                    "stage_order": stage_order,
                    "trace_source": str(trace["stage"]) if trace is not None else "",
                    "stage_trace_present": trace is not None,
                    "budget_ms": record.budget_ms,
                    "demand": record.demand,
                    "observed_stage_score": observed_score,
                    "credited_stage_score": credited_score,
                    "score": credited_score,
                    "satisfaction": credited_score / record.demand,
                    "stage_elapsed_ms": (
                        float(trace["elapsed_ms"]) if trace is not None else None
                    ),
                    "stage_deadline_hit": (
                        bool(trace["deadline_hit"]) if trace is not None else None
                    ),
                    "run_valid": record.valid,
                    "run_deadline_miss": record.deadline_miss,
                    "run_timeout": record.timeout,
                    "run_returncode": record.returncode,
                    "run_credit_eligible": credit_eligible,
                    "solver_wall_ms": record.solver_wall_ms,
                }
            )
    return rows


def exact_rows(
    aggregates: Sequence[Mapping[str, object]],
    optima: Mapping[str, int],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for aggregate in aggregates:
        optimum = int(optima[str(aggregate["instance_id"])])
        heuristic = float(aggregate["transmitted_median"])
        absolute_gap = optimum - heuristic
        if absolute_gap < 0.0:
            raise RuntimeError(
                f"heuristic score {heuristic} exceeds exact optimum {optimum} "
                f"for {aggregate['instance_id']} and {aggregate['method']}"
            )
        relative_gap = absolute_gap / optimum if optimum > 0 else 0.0
        row = dict(aggregate)
        row.update(
            {
                "optimum": optimum,
                "absolute_gap": absolute_gap,
                "relative_gap": relative_gap,
                "optimal": absolute_gap == 0.0,
            }
        )
        rows.append(row)
    return rows


def _runtime_statistics(rows: Sequence[RunRecord]) -> dict[str, object]:
    runtimes = [row.solver_wall_ms for row in rows]
    end_to_end = [row.end_to_end_ms for row in rows]
    algorithms = [row.algorithm_ms for row in rows if row.algorithm_ms is not None]
    return {
        "runs": len(rows),
        "runtime_p50_ms": percentile(runtimes, 0.50),
        "runtime_p95_ms": percentile(runtimes, 0.95),
        "runtime_worst_ms": max(runtimes),
        "algorithm_p50_ms": percentile(algorithms, 0.50) if algorithms else None,
        "end_to_end_p50_ms": percentile(end_to_end, 0.50),
        "deadline_misses": sum(row.deadline_miss for row in rows),
        "deadline_miss_rate": statistics.fmean(
            1.0 if row.deadline_miss else 0.0 for row in rows
        ),
        "valid_rate": statistics.fmean(1.0 if row.valid else 0.0 for row in rows),
        "timeouts": sum(row.timeout for row in rows),
    }


def summarize(
    *,
    main_records: Sequence[RunRecord],
    main_aggregates: Sequence[Mapping[str, object]],
    budget_records: Sequence[RunRecord],
    budget_aggregates: Sequence[Mapping[str, object]],
    stress_records: Sequence[RunRecord],
    stress_aggregates: Sequence[Mapping[str, object]],
    exact_records_data: Sequence[RunRecord],
    exact_results: Sequence[Mapping[str, object]],
    trace_ablation_analysis: Mapping[str, object],
    repeats: int,
    deadline_ms: float,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "schema_version": 3,
        "protocol": {
            "main_methods": list(METHODS),
            "unit_of_quality_analysis": "instance-level median",
            "repeats_per_instance_method": repeats,
            "deadline_ms": deadline_ms,
            "runtime_clock": "external process wall time; validation reported separately",
            "score_credit_rule": (
                "transmitted is credited quality: zero for timeout, nonzero return, "
                "illegal output, or solver_wall_ms above deadline_ms; "
                "observed_transmitted retains a late but legal score for diagnosis"
            ),
            "algorithm_ms": (
                "internal elapsed time through the final feasibility validation; "
                "stdout serialization is not included"
            ),
            "causal_cumulative_ablation": (
                "Base->Global->CG->Remask->Full effects use stage scores inside "
                "the same repeated Full run"
            ),
            "independent_process_caution": (
                "independent Global/CG/Remask process scores may differ because "
                "wall-clock jitter changes completed work and are not module regressions"
            ),
        },
        "variants": {},
        "scenarios": {},
        "budget_curve": {},
        "cg_stress": {},
        "exact": {"methods": {}},
        "trace_ablation": dict(trace_ablation_analysis),
    }

    if main_aggregates:
        by_method_aggregate = {
            method: [row for row in main_aggregates if row["method"] == method]
            for method in METHODS
        }
        beamfirst_total = sum(
            float(row["transmitted_median"]) for row in by_method_aggregate["BeamFirst"]
        )
        for method in METHODS:
            aggregates = by_method_aggregate[method]
            raw = [row for row in main_records if row.method == method]
            total = sum(float(row["transmitted_median"]) for row in aggregates)
            runtime = _runtime_statistics(raw)
            summary["variants"][method] = {
                "instances": len(aggregates),
                "cases": len(aggregates),
                "runs": len(raw),
                "total_instance_median_transmitted": total,
                "mean_satisfaction": statistics.fmean(
                    float(row["satisfaction"]) for row in aggregates
                ),
                "gain_over_BeamFirst": (
                    (total - beamfirst_total) / beamfirst_total if beamfirst_total > 0 else 0.0
                ),
                "mean_within_instance_score_range": statistics.fmean(
                    float(row["score_range"]) for row in aggregates
                ),
                **runtime,
            }

        for scenario in sorted({str(row["scenario"]) for row in main_aggregates}):
            scenario_rows = [row for row in main_aggregates if row["scenario"] == scenario]
            summary["scenarios"][scenario] = {
                method: {
                    "mean_transmitted": statistics.fmean(
                        float(row["transmitted_median"])
                        for row in scenario_rows
                        if row["method"] == method
                    ),
                    "mean_satisfaction": statistics.fmean(
                        float(row["satisfaction"])
                        for row in scenario_rows
                        if row["method"] == method
                    ),
                }
                for method in METHODS
            }

    for budget in sorted({int(row["budget_ms"]) for row in budget_aggregates}):
        aggregates = [row for row in budget_aggregates if int(row["budget_ms"]) == budget]
        raw = [row for row in budget_records if row.budget_ms == budget]
        summary["budget_curve"][str(budget)] = {
            "instances": len(aggregates),
            "mean_transmitted": statistics.fmean(
                float(row["transmitted_median"]) for row in aggregates
            ),
            "mean_satisfaction": statistics.fmean(
                float(row["satisfaction"]) for row in aggregates
            ),
            **_runtime_statistics(raw),
        }

    for scenario in sorted({str(row["scenario"]) for row in stress_aggregates}):
        group_size = int(scenario.rsplit("-", 1)[-1])
        summary["cg_stress"][str(group_size)] = {}
        for method in sorted(
            {str(row["method"]) for row in stress_aggregates if row["scenario"] == scenario},
            key=lambda name: METHODS.index(name),
        ):
            aggregates = [
                row
                for row in stress_aggregates
                if row["scenario"] == scenario and row["method"] == method
            ]
            raw = [
                row
                for row in stress_records
                if row.scenario == scenario and row.method == method
            ]
            summary["cg_stress"][str(group_size)][method] = {
                "instances": len(aggregates),
                "mean_transmitted": statistics.fmean(
                    float(row["transmitted_median"]) for row in aggregates
                ),
                "mean_satisfaction": statistics.fmean(
                    float(row["satisfaction"]) for row in aggregates
                ),
                **_runtime_statistics(raw),
            }

    if exact_results:
        exact_summary = summary["exact"]
        for method in METHODS:
            rows = [row for row in exact_results if row["method"] == method]
            raw = [row for row in exact_records_data if row.method == method]
            gaps = [float(row["relative_gap"]) for row in rows]
            exact_summary["methods"][method] = {
                "cases": len(rows),
                "mean_gap": statistics.fmean(gaps),
                "median_gap": statistics.median(gaps),
                "max_gap": max(gaps),
                "optimal_count": sum(bool(row["optimal"]) for row in rows),
                **_runtime_statistics(raw),
            }
        full = exact_summary["methods"]["Full"]
        exact_summary.update(
            {
                "cases": full["cases"],
                "mean_gap": full["mean_gap"],
                "median_gap": full["median_gap"],
                "max_gap": full["max_gap"],
                "optimal_count": full["optimal_count"],
            }
        )
    return summary


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _case_rows(experiment: str, bundles: Sequence[CaseBundle]) -> list[dict[str, object]]:
    return [
        {
            "experiment": experiment,
            "scenario": bundle.scenario.name,
            "seed": bundle.seed,
            "instance_id": bundle.instance_id,
            "case_sha256": bundle.case_sha256,
            "P": bundle.case.P,
            "N": bundle.case.N,
            "K": bundle.case.K,
            "T": bundle.case.T,
            "beam_max": bundle.case.beam_max,
            "compatibility_groups": len(bundle.case.ru),
            "max_group_size": bundle.max_group_size,
            "double_memberships": bundle.double_memberships,
            "nonadjacent_memberships": bundle.nonadjacent_memberships,
        }
        for bundle in bundles
    ]


def _compiler_version(compiler: str) -> str:
    try:
        result = subprocess.run(
            [compiler, "--version"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        return result.stdout.splitlines()[0] if result.stdout else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except (OSError, IndexError):
        pass
    return platform.processor()


def _result_artifacts(out_dir: Path) -> dict[str, dict[str, object]]:
    names = (
        "run_results.csv",
        "synthetic_results.csv",
        "trace_ablation_results.csv",
        "trace_ablation_analysis.json",
        "budget_run_results.csv",
        "budget_results.csv",
        "cg_stress_run_results.csv",
        "cg_stress_results.csv",
        "exact_run_results.csv",
        "exact_results.csv",
        "case_manifest.csv",
        "paired_analysis.json",
        "summary.json",
    )
    artifacts: dict[str, dict[str, object]] = {}
    for name in names:
        path = out_dir / name
        if not path.is_file():
            continue
        metadata: dict[str, object] = {
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        if path.suffix == ".csv":
            row_count = 0
            reused_rows = 0
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                columns = list(reader.fieldnames or [])
                for row in reader:
                    row_count += 1
                    if str(row.get("reused", "")).lower() in {"true", "1"}:
                        reused_rows += 1
            metadata.update({"rows": row_count, "columns": columns})
            if "reused" in columns:
                metadata["reused_rows"] = reused_rows
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and "schema_version" in payload:
                metadata["schema_version"] = payload["schema_version"]
        artifacts[name] = metadata
    return artifacts


def _write_checksums(out_dir: Path) -> None:
    checksum_path = out_dir / "CHECKSUMS.sha256"
    names = sorted(
        path.name
        for path in out_dir.iterdir()
        if path.is_file() and path.name != checksum_path.name
    )
    checksum_path.write_text(
        "".join(f"{_sha256_file(out_dir / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )


def build_manifest(
    args: argparse.Namespace,
    *,
    experiments: Sequence[str],
    case_rows: Sequence[Mapping[str, object]],
    binary: Path,
) -> dict[str, object]:
    source_paths = [
        ROOT / "src" / "scheduler.cpp",
        ROOT / "src" / "core.cpp",
        ROOT / "src" / "core.h",
        ROOT / "tools" / "scheduler_validator.py",
        Path(__file__).resolve(),
        ROOT / "experiments" / "analyze_results.py",
    ]
    return {
        "schema_version": 3,
        "generator": "cumulative-ablation-v3",
        "experiments": list(experiments),
        "seed_mode": args.seed_mode,
        "selected_seed_bases": {
            "heldout": args.heldout_seed_base,
            "stress": args.stress_seed_base,
            "exact": args.exact_seed_base,
        },
        "formal_seed_bases": {
            "heldout": FORMAL_HELDOUT_SEED_BASE,
            "stress": FORMAL_STRESS_SEED_BASE,
            "exact": FORMAL_EXACT_SEED_BASE,
        },
        "qa_seed_bases": {
            "heldout": QA_HELDOUT_SEED_BASE,
            "stress": QA_STRESS_SEED_BASE,
            "exact": QA_EXACT_SEED_BASE,
        },
        "heldout_seed_protocol": {
            "base": args.heldout_seed_base,
            "scenario_stride": 1000,
            "seeds_per_scenario": args.seeds_per_scenario,
        },
        "stress_seed_protocol": {
            "base": args.stress_seed_base,
            "group_size_stride": 1000,
            "seeds_per_group_size": args.stress_seeds,
            "fixed_compatibility_group_count": 2,
            "varied_group_sizes": list(DEFAULT_STRESS_GROUP_SIZES),
            "interpretation": (
                "compatibility-group size and covered-user count vary together; "
                "compare methods within each setting and treat cross-setting trends "
                "as a size-and-coverage stress test, not a pure size effect"
            ),
        },
        "exact_seed_protocol": {
            "base": args.exact_seed_base,
            "count": args.exact_cases,
            "continuous_unfiltered_interval": True,
            "scenario_mix": {
                "offset_0": "tiny-widebeam",
                "offset_1_onward": "tiny-exact",
            },
        },
        "methods": list(METHODS),
        "stage_arguments": STAGE_ARGUMENT,
        "ablation_interpretation": {
            "causal_cumulative_source": (
                "trace_ablation_results.csv extracted from stages within each Full run"
            ),
            "independent_process_role": (
                "external BeamFirst/Base/Full quality, feasibility, runtime, and SLA; "
                "independent intermediate-stage differences are descriptive only"
            ),
            "trace_stage_order": list(TRACE_ABLATION_STAGES),
        },
        "main_budget_ms": args.main_budget_ms,
        "budgets_ms": list(args.budgets),
        "budget_protocol": {
            "all_points_executed_independently": True,
            "within_instance_repeat_order": "deterministically randomized",
            "reuse_main_full_records": False,
        },
        "stress_group_sizes": list(DEFAULT_STRESS_GROUP_SIZES),
        "stress_methods": list(args.stress_methods),
        "repeats": args.repeats,
        "deadline_ms": args.deadline_ms,
        "process_timeout_ms": args.timeout_ms,
        "cpu_affinity": args.cpu,
        "compiler": args.compiler,
        "compiler_version": _compiler_version(args.compiler),
        "compile_flags": ["-std=c++17", "-O2"],
        "binary_sha256": _sha256_file(binary),
        "source_sha256": {
            str(path.relative_to(ROOT)): _sha256_file(path)
            for path in source_paths
            if path.is_file()
        },
        "score_metrics": {
            "observed_transmitted": (
                "independently validated score when a legal output is observed, even if late"
            ),
            "transmitted": (
                "credited score used by every quality summary; zero on invalid output, "
                "timeout, nonzero return, or external deadline miss"
            ),
        },
        "runtime_metrics": {
            "solver_wall_ms": (
                "external subprocess wall time including launch, stdin, solver, and stdout"
            ),
            "algorithm_ms": (
                "maximum C++ trace elapsed time through final feasibility validation; "
                "excludes completion of stdout serialization"
            ),
            "validation_ms": "independent Python validation and scoring after process exit",
            "end_to_end_ms": "solver_wall_ms plus validation_ms",
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_model": _cpu_model(),
            "logical_cpu_count": os.cpu_count(),
            "available_cpu_affinity": (
                sorted(os.sched_getaffinity(0))
                if hasattr(os, "sched_getaffinity")
                else None
            ),
            "affinity_enforced": args.cpu is not None,
        },
        "binary_reproduction": {
            "retained_in_repository": False,
            "reason": "repository policy excludes committed binaries",
            "build_command": (
                "g++ -std=c++17 -O2 src/scheduler.cpp src/core.cpp -o scheduler"
            ),
            "expected_sha256": _sha256_file(binary),
        },
        "case_count": len(case_rows),
        "case_hashes": {
            str(row["instance_id"]): str(row["case_sha256"]) for row in case_rows
        },
        "output_schema": {
            "run_results.csv": RAW_FIELDS,
            "synthetic_results.csv": AGGREGATE_FIELDS,
            "trace_ablation_results.csv": TRACE_ABLATION_FIELDS,
            "trace_ablation_analysis.json": (
                "within-run stage medians, adjacent paired gains, wins/ties/losses, "
                "and scenario-stratified bootstrap 95% confidence intervals"
            ),
            "paired_analysis.json": (
                "independent-process paired comparisons with scenario-stratified "
                "bootstrap 95% confidence intervals"
            ),
            "summary.json": "machine-readable aggregate statistics for all experiments",
            "budget_run_results.csv": RAW_FIELDS,
            "budget_results.csv": AGGREGATE_FIELDS,
            "cg_stress_run_results.csv": RAW_FIELDS,
            "cg_stress_results.csv": AGGREGATE_FIELDS,
            "exact_run_results.csv": RAW_FIELDS,
            "exact_results.csv": EXACT_FIELDS,
            "case_manifest.csv": CASE_FIELDS,
        },
    }


def validate_args(args: argparse.Namespace) -> None:
    if args.quick:
        args.seed_mode = "qa"
        args.heldout_seed_base = QA_HELDOUT_SEED_BASE
        args.stress_seed_base = QA_STRESS_SEED_BASE
        args.exact_seed_base = QA_EXACT_SEED_BASE
        args.seeds_per_scenario = 1
        args.repeats = 1
        args.stress_seeds = 1
        args.exact_cases = 1
        args.bootstrap_samples = min(args.bootstrap_samples, 250)
    else:
        args.seed_mode = "formal"
        args.heldout_seed_base = FORMAL_HELDOUT_SEED_BASE
        args.stress_seed_base = FORMAL_STRESS_SEED_BASE
        args.exact_seed_base = FORMAL_EXACT_SEED_BASE
    if args.seeds_per_scenario < 1:
        raise ValueError("seeds per scenario must be positive")
    if args.repeats < 1:
        raise ValueError("repeats must be positive")
    if args.stress_seeds < 1:
        raise ValueError("stress seeds must be positive")
    if args.exact_cases < 1:
        raise ValueError("exact cases must be positive")
    if args.main_budget_ms < 1 or any(budget < 1 for budget in args.budgets):
        raise ValueError("budgets must be positive")
    if len(set(args.budgets)) != len(args.budgets):
        raise ValueError("budget values must be unique")
    if args.timeout_ms <= max((*args.budgets, args.main_budget_ms)):
        raise ValueError("process timeout must exceed every internal algorithm budget")
    if args.deadline_ms <= 0:
        raise ValueError("deadline must be positive")
    unknown = [method for method in args.stress_methods if method not in METHODS]
    if unknown:
        raise ValueError(f"unknown stress methods: {', '.join(unknown)}")
    if args.cpu is not None:
        if shutil.which("taskset") is None:
            raise ValueError("--cpu requires taskset")
        available = os.sched_getaffinity(0) if hasattr(os, "sched_getaffinity") else set()
        if available and args.cpu not in available:
            raise ValueError(f"CPU {args.cpu} is outside available affinity {sorted(available)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--experiments",
        default="main,budget,stress,exact",
        help="comma-separated subset of main,budget,stress,exact",
    )
    parser.add_argument(
        "--seeds-per-scenario",
        "--cases-per-scenario",
        dest="seeds_per_scenario",
        type=int,
        default=30,
    )
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--stress-seeds", type=int, default=10)
    parser.add_argument("--exact-cases", type=int, default=12)
    parser.add_argument("--main-budget-ms", type=int, default=87)
    parser.add_argument(
        "--budgets",
        type=lambda value: _parse_csv_list(value, cast=int),
        default=DEFAULT_BUDGETS,
    )
    parser.add_argument(
        "--stress-methods",
        type=lambda value: _parse_csv_list(value, cast=str),
        default=DEFAULT_STRESS_METHODS,
    )
    parser.add_argument("--deadline-ms", type=float, default=100.0)
    parser.add_argument("--timeout-ms", type=int, default=500)
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260722)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "paper" / "results")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    validate_args(args)

    experiments = tuple(token.strip() for token in args.experiments.split(",") if token.strip())
    allowed = {"main", "budget", "stress", "exact"}
    unknown_experiments = sorted(set(experiments) - allowed)
    if unknown_experiments:
        raise ValueError(f"unknown experiments: {', '.join(unknown_experiments)}")
    if not experiments:
        raise ValueError("select at least one experiment")

    main_bundles: list[CaseBundle] = []
    stress_cases: list[CaseBundle] = []
    exact_cases_data: list[CaseBundle] = []
    if "main" in experiments or "budget" in experiments:
        main_bundles = heldout_bundles(
            args.seeds_per_scenario, args.heldout_seed_base
        )
    if "stress" in experiments:
        stress_cases = stress_bundles(args.stress_seeds, args.stress_seed_base)
    if "exact" in experiments:
        exact_cases_data = exact_bundles(args.exact_cases, args.exact_seed_base)

    if args.binary is not None:
        binary = args.binary.resolve()
        if not binary.is_file():
            raise FileNotFoundError(binary)
        context = nullcontext(None)
    else:
        context = tempfile.TemporaryDirectory(prefix="scheduler-paper-build-")
        binary = Path()

    with context as temporary:
        if args.binary is None:
            binary = compile_scheduler(Path(temporary), args.compiler)

        main_records: list[RunRecord] = []
        budget_records: list[RunRecord] = []
        stress_records: list[RunRecord] = []
        exact_records_data: list[RunRecord] = []
        optima: dict[str, int] = {}

        if "main" in experiments:
            main_records = run_main_experiment(
                binary,
                main_bundles,
                repeats=args.repeats,
                budget_ms=args.main_budget_ms,
                timeout_ms=args.timeout_ms,
                deadline_ms=args.deadline_ms,
                cpu=args.cpu,
                quiet=args.quiet,
            )
        if "budget" in experiments:
            budget_records = run_budget_experiment(
                binary,
                main_bundles,
                repeats=args.repeats,
                budgets=args.budgets,
                main_budget_ms=args.main_budget_ms,
                main_records=main_records,
                timeout_ms=args.timeout_ms,
                deadline_ms=args.deadline_ms,
                cpu=args.cpu,
                quiet=args.quiet,
            )
        if "stress" in experiments:
            stress_records = run_stress_experiment(
                binary,
                stress_cases,
                repeats=args.repeats,
                methods=args.stress_methods,
                budget_ms=args.main_budget_ms,
                timeout_ms=args.timeout_ms,
                deadline_ms=args.deadline_ms,
                cpu=args.cpu,
                quiet=args.quiet,
            )
        if "exact" in experiments:
            exact_records_data, optima = run_exact_experiment(
                binary,
                exact_cases_data,
                repeats=args.repeats,
                budget_ms=args.main_budget_ms,
                timeout_ms=args.timeout_ms,
                deadline_ms=args.deadline_ms,
                cpu=args.cpu,
                quiet=args.quiet,
            )

        main_aggregates = aggregate_records(main_records)
        budget_aggregates = aggregate_records(budget_records)
        stress_aggregates = aggregate_records(stress_records)
        exact_aggregates = aggregate_records(exact_records_data)
        exact_results = exact_rows(exact_aggregates, optima)
        trace_ablation_rows = extract_trace_ablation_rows(main_records)
        trace_ablation_analysis: dict[str, object] = {}
        if trace_ablation_rows:
            trace_ablation_analysis = analyze_results.analyze_trace_rows(
                trace_ablation_rows,
                bootstrap_samples=args.bootstrap_samples,
                bootstrap_seed=args.bootstrap_seed,
            )

        summary = summarize(
            main_records=main_records,
            main_aggregates=main_aggregates,
            budget_records=budget_records,
            budget_aggregates=budget_aggregates,
            stress_records=stress_records,
            stress_aggregates=stress_aggregates,
            exact_records_data=exact_records_data,
            exact_results=exact_results,
            trace_ablation_analysis=trace_ablation_analysis,
            repeats=args.repeats,
            deadline_ms=args.deadline_ms,
        )

        args.out.mkdir(parents=True, exist_ok=True)
        _write_csv(
            args.out / "run_results.csv",
            [asdict(record) for record in main_records],
            RAW_FIELDS,
        )
        _write_csv(args.out / "synthetic_results.csv", main_aggregates, AGGREGATE_FIELDS)
        _write_csv(
            args.out / "trace_ablation_results.csv",
            trace_ablation_rows,
            TRACE_ABLATION_FIELDS,
        )
        (args.out / "trace_ablation_analysis.json").write_text(
            json.dumps(trace_ablation_analysis, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _write_csv(
            args.out / "budget_run_results.csv",
            [asdict(record) for record in budget_records],
            RAW_FIELDS,
        )
        _write_csv(args.out / "budget_results.csv", budget_aggregates, AGGREGATE_FIELDS)
        _write_csv(
            args.out / "cg_stress_run_results.csv",
            [asdict(record) for record in stress_records],
            RAW_FIELDS,
        )
        _write_csv(args.out / "cg_stress_results.csv", stress_aggregates, AGGREGATE_FIELDS)
        _write_csv(
            args.out / "exact_run_results.csv",
            [asdict(record) for record in exact_records_data],
            RAW_FIELDS,
        )
        _write_csv(args.out / "exact_results.csv", exact_results, EXACT_FIELDS)

        all_case_rows = [
            *_case_rows("heldout", main_bundles),
            *_case_rows("stress", stress_cases),
            *_case_rows("exact", exact_cases_data),
        ]
        unique_case_rows = {
            str(row["instance_id"]): row for row in all_case_rows
        }
        ordered_case_rows = [
            unique_case_rows[key] for key in sorted(unique_case_rows)
        ]
        _write_csv(args.out / "case_manifest.csv", ordered_case_rows, CASE_FIELDS)

        paired: dict[str, object] = {}
        if main_aggregates:
            paired = analyze_results.analyze_rows(
                main_aggregates,
                bootstrap_samples=args.bootstrap_samples,
                bootstrap_seed=args.bootstrap_seed,
            )
            (args.out / "paired_analysis.json").write_text(
                json.dumps(paired, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        (args.out / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest = build_manifest(
            args,
            experiments=experiments,
            case_rows=ordered_case_rows,
            binary=binary,
        )
        artifacts = _result_artifacts(args.out)
        raw_names = (
            "run_results.csv",
            "budget_run_results.csv",
            "cg_stress_run_results.csv",
            "exact_run_results.csv",
        )
        raw_records = sum(
            int(artifacts[name]["rows"]) for name in raw_names if name in artifacts
        )
        reused_records = sum(
            int(artifacts[name].get("reused_rows", 0))
            for name in raw_names
            if name in artifacts
        )
        manifest["result_artifacts"] = artifacts
        manifest["execution_accounting"] = {
            "raw_records": raw_records,
            "reused_records": reused_records,
            "physical_subprocess_executions": raw_records - reused_records,
        }
        (args.out / "experiment_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _write_checksums(args.out)

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
