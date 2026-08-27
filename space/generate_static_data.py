#!/usr/bin/env python3
"""Build deterministic browser-demo snapshots with the real FPTR C++ scheduler."""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from experiments.paper_experiments import HELDOUT_SCENARIOS, generate_case
from tools import scheduler_validator


ROOT = Path(__file__).resolve().parent
BINARY = ROOT / "scheduler"
OUTPUT = ROOT / "data" / "results.json"
SOURCE_COMMIT = "dca2f77141c2abd8a4741b229bb9c5f3053792ec"
SEED_BASE = 20260801
BUDGETS = (20, 50, 87, 125, 180)
STAGES = (
    ("full", "Full pipeline", "完整流水线"),
    ("remask", "Through remask", "截至掩码修复"),
    ("cg", "Through legal sharing", "截至合法共享"),
    ("global", "Through repricing", "截至全局重定价"),
    ("base", "Feasible construction", "可行构造"),
    ("beamfirst", "BeamFirst reference", "BeamFirst 基线"),
)
TRACE_RE = re.compile(
    r"^TRACE stage=(?P<stage>[a-z_]+) score=(?P<score>-?[0-9]+) "
    r"elapsed_ms=(?P<elapsed>[0-9]+(?:\.[0-9]+)?) "
    r"deadline_hit=(?P<deadline>[01])$"
)

SCENARIO_COPY = {
    "small-balanced": (
        "Small · balanced",
        "小型 · 均衡",
        "20 users · balanced traffic and channels · quickest visual example",
        "20 用户 · 流量与信道均衡 · 最快的可视化示例",
    ),
    "medium-longtail": (
        "Medium · long-tail traffic",
        "中型 · 长尾流量",
        "50 users · long-tail demand · clustered channel strengths",
        "50 用户 · 长尾需求 · 聚类信道强度",
    ),
    "medium-tight": (
        "Medium · tight beam budget",
        "中型 · 紧张波束预算",
        "50 users · heterogeneous channels · scarce beams",
        "50 用户 · 异构信道 · 波束预算紧张",
    ),
    "large-mixed": (
        "Large · mixed workload",
        "大型 · 混合工作负载",
        "100 users · 72 resources · high compatibility coverage",
        "100 用户 · 72 个资源 · 高兼容组覆盖率",
    ),
    "large-nonadjacent": (
        "Large · non-adjacent overlap",
        "大型 · 非相邻重叠",
        "100 users · tight beams · mostly non-adjacent dual memberships",
        "100 用户 · 波束紧张 · 以非相邻双子带归属为主",
    ),
}


def compile_scheduler() -> None:
    command = [
        "g++",
        "-std=c++17",
        "-O2",
        str(ROOT / "src" / "scheduler.cpp"),
        str(ROOT / "src" / "core.cpp"),
        "-o",
        str(BINARY),
    ]
    subprocess.run(command, cwd=ROOT, check=True)


def cutoff_ms(stage: str, budget_ms: int) -> int:
    reserve = 3 if budget_ms >= 20 else 1
    search = max(1, budget_ms - reserve)
    numerator = {
        "beam_first": 45,
        "base": 45,
        "global": 60,
        "cg": 70,
        "remask": 78,
        "pair": 84,
        "final": None,
    }[stage]
    return budget_ms if numerator is None else max(1, search * numerator // 84)


def per_user_traffic(
    case: scheduler_validator.CaseInput,
    solution: scheduler_validator.ParsedSolution,
) -> list[int]:
    raw = [0] * (case.N + 1)
    for resource in range(1, case.K + 1):
        users = solution.resource_users[resource]
        if not users:
            continue
        share = len(users)
        bands = case.res_bands[resource]
        denominator = bands[-1] - bands[0] + 1
        for user in users:
            selected_sum = sum(
                case.cap[user][beam]
                for band in bands
                for beam in solution.beams[band]
            )
            selected_average = selected_sum / denominator
            fse = (
                case.sinr[user]
                + 10.0 * math.log10(1.0 / share)
                + 10.0 * math.log10(selected_average / case.total_cap[user])
            )
            raw[user] += scheduler_validator.cap_of(fse)
    return [min(case.buffer[user], raw[user]) for user in range(1, case.N + 1)]


def run_solver(
    case: scheduler_validator.CaseInput,
    instance_text: str,
    stage: str,
    budget_ms: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    process = subprocess.run(
        [str(BINARY), "--stage", stage, "--budget-ms", str(budget_ms), "--trace"],
        input=instance_text,
        text=True,
        capture_output=True,
        cwd=ROOT,
        timeout=max(3.0, budget_ms / 1000.0 + 2.0),
        check=False,
    )
    wall_ms = (time.perf_counter() - started) * 1000.0
    if process.returncode != 0:
        raise RuntimeError(f"scheduler failed for {case.case_id}/{stage}/{budget_ms}: {process.stderr}")

    trace: list[dict[str, Any]] = []
    for line in process.stderr.splitlines():
        match = TRACE_RE.fullmatch(line.strip())
        if match:
            trace_stage = match.group("stage")
            trace.append(
                {
                    "stage": trace_stage,
                    "score": int(match.group("score")),
                    "elapsedMs": round(float(match.group("elapsed")), 3),
                    "cutoffMs": cutoff_ms(trace_stage, budget_ms),
                    "deadlineHit": bool(int(match.group("deadline"))),
                }
            )
    if not trace:
        raise RuntimeError(f"scheduler emitted no trace for {case.case_id}/{stage}/{budget_ms}")

    scored = scheduler_validator.validate_and_score(case, process.stdout)
    solution = scheduler_validator.parse_output_text(case, process.stdout)
    delivered = per_user_traffic(case, solution)
    if sum(delivered) != scored.transmitted:
        raise RuntimeError(f"independent score mismatch for {case.case_id}/{stage}/{budget_ms}")

    return {
        "score": scored.transmitted,
        "beamUsed": solution.beam_used,
        "resourcesUsed": sum(bool(users) for users in solution.resource_users[1:]),
        "sharedResources": sum(len(users) > 1 for users in solution.resource_users[1:]),
        "algorithmMs": round(float(trace[-1]["elapsedMs"]), 3),
        "wallMs": round(wall_ms, 3),
        "deadlineHit": any(item["deadlineHit"] for item in trace),
        "valid": True,
        "trace": trace,
        "beams": [sorted(solution.beams[band]) for band in range(1, case.T + 1)],
        "resourceUsers": solution.resource_users[1:],
        "userResources": solution.user_resources[1:],
        "delivered": delivered,
    }


def build() -> dict[str, Any]:
    compile_scheduler()
    scenarios: list[dict[str, Any]] = []
    for index, scenario in enumerate(HELDOUT_SCENARIOS):
        seed = SEED_BASE + index * 1000
        instance_text = generate_case(scenario, seed)
        case = scheduler_validator.parse_case_text(
            instance_text, case_id=f"{scenario.name}-{seed}"
        )
        label, label_zh, note, note_zh = SCENARIO_COPY[scenario.name]
        results: dict[str, dict[str, Any]] = {}
        for budget in BUDGETS:
            budget_results: dict[str, Any] = {}
            baseline = run_solver(case, instance_text, "beamfirst", budget)
            for stage, _, _ in STAGES:
                result = baseline if stage == "beamfirst" else run_solver(
                    case, instance_text, stage, budget
                )
                result = dict(result)
                result["baselineScore"] = baseline["score"]
                result["deltaVsBaseline"] = result["score"] - baseline["score"]
                budget_results[stage] = result
            results[str(budget)] = budget_results

        scenarios.append(
            {
                "id": scenario.name,
                "label": label,
                "labelZh": label_zh,
                "note": note,
                "noteZh": note_zh,
                "seed": seed,
                "sha256": hashlib.sha256(instance_text.encode("utf-8")).hexdigest(),
                "instance": {
                    "users": case.N,
                    "resources": case.K,
                    "beams": case.P,
                    "subbands": case.T,
                    "beamMax": case.beam_max,
                    "groups": len(case.ru),
                    "maxGroup": max((len(group) for group in case.ru), default=1),
                    "dualMemberships": sum(
                        len(case.res_bands[resource]) == 2
                        for resource in range(1, case.K + 1)
                    ),
                    "demand": sum(case.buffer[1:]),
                    "requested": case.buffer[1:],
                    "resourceBands": [list(case.res_bands[r]) for r in range(1, case.K + 1)],
                },
                "results": results,
            }
        )

    return {
        "schemaVersion": 1,
        "schedulerSourceCommit": SOURCE_COMMIT,
        "budgets": list(BUDGETS),
        "stages": [
            {"id": stage, "label": label, "labelZh": label_zh}
            for stage, label, label_zh in STAGES
        ],
        "scenarios": scenarios,
    }


def main() -> None:
    payload = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        f"wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024:.1f} KiB; "
        f"{len(payload['scenarios'])} scenarios)"
    )


if __name__ == "__main__":
    main()
