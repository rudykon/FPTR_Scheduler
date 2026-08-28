#!/usr/bin/env python3
"""Generate deterministic public inputs for the browser-executed FPTR demo."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from experiments.paper_experiments import HELDOUT_SCENARIOS, generate_case
from tools import scheduler_validator


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CASES = DATA / "cases"
SOURCE_COMMIT = "dca2f77141c2abd8a4741b229bb9c5f3053792ec"
SEED_BASE = 20260801

SCENARIO_COPY = {
    "small-balanced": (
        "Small · balanced",
        "小型 · 均衡",
        "20 users · balanced traffic and channels · quickest live example",
        "20 用户 · 流量与信道均衡 · 最快的实时示例",
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

STAGES = (
    ("full", "Full pipeline", "完整流水线"),
    ("remask", "Through remask", "截至掩码修复"),
    ("cg", "Through legal sharing", "截至合法共享"),
    ("global", "Through repricing", "截至全局重定价"),
    ("base", "Feasible construction", "可行构造"),
    ("beamfirst", "BeamFirst reference", "BeamFirst 基线"),
)


def main() -> None:
    CASES.mkdir(parents=True, exist_ok=True)
    scenarios = []
    for index, scenario in enumerate(HELDOUT_SCENARIOS):
        seed = SEED_BASE + index * 1000
        text = generate_case(scenario, seed)
        case = scheduler_validator.parse_case_text(
            text, case_id=f"{scenario.name}-{seed}"
        )
        filename = f"{scenario.name}.in"
        (CASES / filename).write_text(text, encoding="utf-8")
        label, label_zh, note, note_zh = SCENARIO_COPY[scenario.name]
        scenarios.append(
            {
                "id": scenario.name,
                "label": label,
                "labelZh": label_zh,
                "note": note,
                "noteZh": note_zh,
                "seed": seed,
                "path": f"data/cases/{filename}",
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "dimensions": {
                    "users": case.N,
                    "resources": case.K,
                    "beams": case.P,
                    "subbands": case.T,
                    "beamMax": case.beam_max,
                },
            }
        )

    manifest = {
        "schemaVersion": 3,
        "execution": "browser-webassembly",
        "schedulerSourceCommit": SOURCE_COMMIT,
        "timing": {
            "internalBudget": {
                "minimumMs": 20,
                "maximumMs": 87,
                "stepMs": 1,
                "paperMs": 87,
            },
            "lastRefinementCutoffAtPaperBudgetMs": 84,
            "finalizationReserveMs": 3,
            "externalDeadlineMs": 100,
        },
        "stages": [
            {"id": stage, "label": label, "labelZh": label_zh}
            for stage, label, label_zh in STAGES
        ],
        "scenarios": scenarios,
    }
    (DATA / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(scenarios)} cases and {DATA / 'manifest.json'}")


if __name__ == "__main__":
    main()
