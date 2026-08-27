#!/usr/bin/env python3
"""Interactive Hugging Face demo for the real FPTR C++ scheduler."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import math
import os
import re
import subprocess
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Any

import gradio as gr
import plotly.graph_objects as go

from experiments.paper_experiments import HELDOUT_SCENARIOS, generate_case
from tools import scheduler_validator


ROOT = Path(__file__).resolve().parent
BINARY = Path(os.environ.get("FPTR_BINARY", ROOT / "scheduler"))
LOGO = ROOT / "assets" / "logo.png"
SOURCE_REPOSITORY = "https://github.com/rudykon/FPTR_Scheduler"
MAX_CUSTOM_BYTES = 2 * 1024 * 1024
_COMPILE_LOCK = threading.Lock()

TRACE_RE = re.compile(
    r"^TRACE stage=(?P<stage>[a-z_]+) score=(?P<score>-?[0-9]+) "
    r"elapsed_ms=(?P<elapsed>[0-9]+(?:\.[0-9]+)?) "
    r"deadline_hit=(?P<deadline>[01])$"
)

COLORS = {
    "navy": "#0B2B57",
    "blue": "#2587FF",
    "cyan": "#16C6C7",
    "green": "#35C96F",
    "orange": "#FFB22E",
    "purple": "#8D4DE8",
    "red": "#E65A67",
    "ink": "#17324D",
    "muted": "#65758B",
    "panel": "#F5F8FC",
    "grid": "#DDE7F2",
}

SCENARIO_LABELS = {
    "Small · balanced": "small-balanced",
    "Medium · long-tail traffic": "medium-longtail",
    "Medium · tight beam budget": "medium-tight",
    "Large · mixed workload": "large-mixed",
    "Large · non-adjacent overlap": "large-nonadjacent",
}
SCENARIOS = {scenario.name: scenario for scenario in HELDOUT_SCENARIOS}
SCENARIO_NOTES = {
    "small-balanced": "20 users · balanced traffic and channels · quickest visual example",
    "medium-longtail": "50 users · long-tail demand · clustered channel strengths",
    "medium-tight": "50 users · bimodal demand · heterogeneous channels · scarce beams",
    "large-mixed": "100 users · 72 resources · clustered channels · high compatibility coverage",
    "large-nonadjacent": "100 users · tight beams · mostly non-adjacent dual-subband memberships",
}

STAGE_LABELS = {
    "Full · all refinements": "full",
    "Remask · through mask repair": "remask",
    "CG · through legal sharing": "cg",
    "Global · through repricing": "global",
    "Base · feasible construction": "base",
    "BeamFirst · external reference": "beamfirst",
}
TRACE_LABELS = {
    "beam_first": "BeamFirst",
    "base": "Base",
    "global": "Global",
    "cg": "CG",
    "remask": "Remask",
    "pair": "Full · Pair",
    "final": "Final audit",
}

DEFAULT_SCENARIO = "Medium · tight beam budget"
DEFAULT_SEED = 20260801
DEFAULT_BUDGET = 87
DEFAULT_STAGE = "Full · all refinements"


def ensure_binary() -> Path:
    """Build the checked-in C++ scheduler when not prebuilt by Docker."""

    if BINARY.is_file() and os.access(BINARY, os.X_OK):
        return BINARY
    with _COMPILE_LOCK:
        if BINARY.is_file() and os.access(BINARY, os.X_OK):
            return BINARY
        command = [
            "g++",
            "-std=c++17",
            "-O2",
            str(ROOT / "src" / "scheduler.cpp"),
            str(ROOT / "src" / "core.cpp"),
            "-o",
            str(BINARY),
        ]
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"C++ scheduler build failed: {result.stderr.strip()}")
        BINARY.chmod(0o755)
    return BINARY


def parse_trace(stderr: str) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
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


def run_solver(instance_text: str, stage: str, budget_ms: int) -> dict[str, Any]:
    binary = ensure_binary()
    started = time.perf_counter()
    process = subprocess.run(
        [str(binary), "--stage", stage, "--budget-ms", str(budget_ms), "--trace"],
        input=instance_text,
        text=True,
        capture_output=True,
        cwd=ROOT,
        timeout=max(3.0, budget_ms / 1000.0 + 2.0),
        check=False,
    )
    wall_ms = (time.perf_counter() - started) * 1000.0
    if process.returncode != 0:
        message = " ".join(process.stderr.split())[:800]
        raise RuntimeError(f"scheduler returned {process.returncode}: {message}")
    traces = parse_trace(process.stderr)
    if not traces:
        raise RuntimeError("scheduler produced no stage trace")
    return {"output": process.stdout, "trace": traces, "wall_ms": wall_ms}


def load_instance(
    scenario_label: str,
    seed: float | int,
    custom_file: str | None,
) -> tuple[str, scheduler_validator.CaseInput, str, str]:
    if custom_file:
        custom_path = Path(custom_file)
        payload = custom_path.read_bytes()
        if len(payload) > MAX_CUSTOM_BYTES:
            raise ValueError("custom instance exceeds the 2 MiB demo limit")
        try:
            instance_text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("custom instance must be UTF-8 text") from exc
        case_id = custom_path.stem[:80] or "custom"
        case = scheduler_validator.parse_case_text(instance_text, case_id=case_id)
        return instance_text, case, f"Custom · {case_id}", "User-supplied scheduler contract"

    scenario_name = SCENARIO_LABELS[scenario_label]
    scenario = SCENARIOS[scenario_name]
    resolved_seed = int(seed)
    instance_text = generate_case(scenario, resolved_seed)
    case_id = f"{scenario_name}-{resolved_seed}"
    case = scheduler_validator.parse_case_text(instance_text, case_id=case_id)
    return instance_text, case, scenario_label, SCENARIO_NOTES[scenario_name]


def per_user_traffic(
    case: scheduler_validator.CaseInput,
    solution: scheduler_validator.ParsedSolution,
) -> tuple[list[int], list[int]]:
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
    delivered = [min(case.buffer[user], raw[user]) for user in range(1, case.N + 1)]
    return raw[1:], delivered


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


def audit_rows(
    trace: list[dict[str, Any]],
    baseline: dict[str, Any] | None,
    budget_ms: int,
) -> list[list[Any]]:
    rows: list[list[Any]] = []
    if baseline is not None:
        reference = next(item for item in baseline["trace"] if item["stage"] == "beam_first")
        rows.append(
            [
                "BeamFirst",
                reference["score"],
                "—",
                round(reference["elapsed_ms"], 3),
                cutoff_ms("beam_first", budget_ms),
                "External reference",
            ]
        )

    previous = 0
    for item in trace:
        stage = item["stage"]
        score = int(item["score"])
        gain = score - previous
        if stage == "final":
            decision = "Independently validated"
        elif gain > 0:
            decision = "Improved incumbent"
        else:
            decision = "Incumbent retained"
        if item["deadline_hit"]:
            decision += " · cutoff reached"
        rows.append(
            [
                TRACE_LABELS[stage],
                score,
                f"+{gain:,}" if gain > 0 else "0",
                round(float(item["elapsed_ms"]), 3),
                cutoff_ms(stage, budget_ms),
                decision,
            ]
        )
        previous = score
    return rows


def common_layout(fig: go.Figure, *, height: int = 390) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=55, r=24, t=68, b=52),
        font=dict(family="Inter, ui-sans-serif, system-ui, sans-serif", color=COLORS["ink"]),
        paper_bgcolor="white",
        plot_bgcolor="white",
        hoverlabel=dict(bgcolor="white", font_color=COLORS["ink"]),
    )
    fig.update_xaxes(gridcolor=COLORS["grid"], zeroline=False)
    fig.update_yaxes(gridcolor=COLORS["grid"], zeroline=False)
    return fig


def make_stage_plot(
    trace: list[dict[str, Any]],
    baseline_score: int,
    budget_ms: int,
) -> go.Figure:
    stages = [TRACE_LABELS[item["stage"]] for item in trace]
    scores = [int(item["score"]) for item in trace]
    elapsed = [float(item["elapsed_ms"]) for item in trace]
    cutoffs = [cutoff_ms(item["stage"], budget_ms) for item in trace]
    tick_text = [f"{stage}<br><span style='font-size:10px'>{ms:.2f} ms</span>" for stage, ms in zip(stages, elapsed)]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=stages,
            y=scores,
            mode="lines+markers+text",
            line=dict(color=COLORS["blue"], width=4, shape="hv"),
            marker=dict(size=12, color=COLORS["blue"], line=dict(color="white", width=2)),
            text=[f"{score:,}" for score in scores],
            textposition="top center",
            customdata=list(zip(elapsed, cutoffs)),
            hovertemplate=(
                "<b>%{x}</b><br>Traffic: %{y:,}<br>Elapsed: %{customdata[0]:.3f} ms"
                "<br>Stage cutoff: %{customdata[1]} ms<extra></extra>"
            ),
            name="FPTR incumbent",
        )
    )
    fig.add_hline(
        y=baseline_score,
        line=dict(color=COLORS["orange"], width=2, dash="dot"),
        annotation_text=f"BeamFirst reference · {baseline_score:,}",
        annotation_position="bottom right",
        annotation_font_color=COLORS["orange"],
    )
    fig.update_layout(
        title=dict(
            text="Cumulative traffic gain · only complete, valid improvements are committed",
            font=dict(size=17),
        ),
        showlegend=False,
    )
    fig.update_xaxes(tickmode="array", tickvals=stages, ticktext=tick_text, title=None)
    fig.update_yaxes(title="Transmitted traffic", rangemode="tozero")
    return common_layout(fig, height=410)


def make_allocation_plot(
    case: scheduler_validator.CaseInput,
    solution: scheduler_validator.ParsedSolution,
) -> go.Figure:
    max_share = max((len(users) for users in solution.resource_users[1:]), default=1)
    z: list[list[int]] = []
    hover: list[list[str]] = []
    for user in range(1, case.N + 1):
        row: list[int] = []
        row_hover: list[str] = []
        user_group = case.ru_id[user] + 1 if case.ru_id[user] >= 0 else None
        for resource in range(1, case.K + 1):
            assigned = user in solution.resource_users[resource]
            share = len(solution.resource_users[resource]) if assigned else 0
            row.append(share)
            group_text = f"CG {user_group}" if user_group is not None else "singleton only"
            row_hover.append(
                f"User {user}<br>Resource {resource}<br>Share size: {share}<br>{group_text}"
            )
        z.append(row)
        hover.append(row_hover)

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=[f"R{resource}" for resource in range(1, case.K + 1)],
            y=[f"U{user}" for user in range(1, case.N + 1)],
            text=hover,
            hovertemplate="%{text}<extra></extra>",
            zmin=0,
            zmax=max(1, max_share),
            colorscale=[
                [0.0, "#F3F7FB"],
                [0.001, "#A8DAFF"],
                [0.5, COLORS["blue"]],
                [1.0, COLORS["purple"]],
            ],
            colorbar=dict(title="Users / resource", thickness=12),
            xgap=1,
            ygap=1,
        )
    )
    shared = sum(len(users) > 1 for users in solution.resource_users[1:])
    used = sum(bool(users) for users in solution.resource_users[1:])
    fig.update_layout(
        title=dict(text=f"Final resource allocation · {used}/{case.K} resources used · {shared} shared", font=dict(size=17))
    )
    fig.update_xaxes(title="Resource block", tickangle=0)
    fig.update_yaxes(title="User", autorange="reversed")
    return common_layout(fig, height=max(470, min(720, case.N * 6 + 170)))


def make_demand_plot(case: scheduler_validator.CaseInput, delivered: list[int]) -> go.Figure:
    users = [f"U{user}" for user in range(1, case.N + 1)]
    demand = case.buffer[1:]
    unmet = [max(0, requested - served) for requested, served in zip(demand, delivered)]
    fig = go.Figure()
    fig.add_bar(
        x=users,
        y=delivered,
        name="Delivered",
        marker_color=COLORS["green"],
        hovertemplate="%{x}<br>Delivered: %{y:,}<extra></extra>",
    )
    fig.add_bar(
        x=users,
        y=unmet,
        name="Unmet demand",
        marker_color="#DCE5EF",
        hovertemplate="%{x}<br>Unmet: %{y:,}<extra></extra>",
    )
    fig.update_layout(
        barmode="stack",
        title=dict(text="Per-user demand coverage", font=dict(size=17)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(title="User", nticks=min(case.N, 25))
    fig.update_yaxes(title="Traffic")
    return common_layout(fig, height=430)


def make_beam_plot(
    case: scheduler_validator.CaseInput,
    solution: scheduler_validator.ParsedSolution,
) -> go.Figure:
    z = [
        [1 if beam in solution.beams[band] else 0 for beam in range(1, case.P + 1)]
        for band in range(1, case.T + 1)
    ]
    hover = [
        [
            f"Subband {band}<br>Beam {beam}<br>{'Active' if z[band - 1][beam - 1] else 'Off'}"
            for beam in range(1, case.P + 1)
        ]
        for band in range(1, case.T + 1)
    ]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=[f"B{beam}" for beam in range(1, case.P + 1)],
            y=[f"S{band}" for band in range(1, case.T + 1)],
            text=hover,
            hovertemplate="%{text}<extra></extra>",
            zmin=0,
            zmax=1,
            colorscale=[[0, "#F2F6FA"], [0.49, "#F2F6FA"], [0.5, COLORS["cyan"]], [1, COLORS["blue"]]],
            showscale=False,
            xgap=2,
            ygap=2,
        )
    )
    fig.update_layout(
        title=dict(
            text=f"Selected beam masks · {solution.beam_used}/{case.beam_max} global beam slots used",
            font=dict(size=17),
        )
    )
    fig.update_xaxes(title="Candidate beam")
    fig.update_yaxes(title="Subband", autorange="reversed")
    return common_layout(fig, height=max(350, case.T * 22 + 190))


def status_html(
    *,
    case: scheduler_validator.CaseInput,
    case_label: str,
    case_note: str,
    transmitted: int,
    baseline_score: int,
    algorithm_ms: float,
    beam_used: int,
    audit_pass: bool,
) -> str:
    demand = sum(case.buffer[1:])
    satisfaction = 100.0 * transmitted / demand if demand else 0.0
    delta = transmitted - baseline_score
    overlaps = sum(len(case.res_bands[resource]) == 2 for resource in range(1, case.K + 1))
    max_group = max((len(group) for group in case.ru), default=1)
    audit_class = "pass" if audit_pass else "warn"
    audit_text = "PASS · feasible & consistent" if audit_pass else "CHECK · see audit table"
    return f"""
    <section class="result-shell">
      <div class="result-heading">
        <div><span class="eyebrow">CURRENT INSTANCE</span><h3>{html.escape(case_label)}</h3></div>
        <span class="audit-pill {audit_class}">{audit_text}</span>
      </div>
      <p class="case-note">{html.escape(case_note)}</p>
      <div class="kpi-grid">
        <article><span>Transmitted</span><strong>{transmitted:,}</strong><small>of {demand:,} demand</small></article>
        <article><span>Demand served</span><strong>{satisfaction:.1f}%</strong><small>buffer-capped objective</small></article>
        <article><span>vs BeamFirst</span><strong>{delta:+,}</strong><small>same instance & budget</small></article>
        <article><span>Algorithm time</span><strong>{algorithm_ms:.2f} ms</strong><small>through final audit</small></article>
        <article><span>Beam budget</span><strong>{beam_used}/{case.beam_max}</strong><small>global mask slots</small></article>
      </div>
      <div class="instance-strip">
        <span><b>{case.N}</b> users</span><span><b>{case.K}</b> resources</span>
        <span><b>{case.P}</b> beams</span><span><b>{case.T}</b> subbands</span>
        <span><b>{len(case.ru)}</b> groups · max {max_group}</span><span><b>{overlaps}</b> dual memberships</span>
      </div>
    </section>
    """


def build_bundle(
    *,
    instance_text: str,
    solution_text: str,
    trace: list[dict[str, Any]],
    baseline_score: int,
    metadata: dict[str, Any],
) -> str:
    digest = hashlib.sha256(instance_text.encode("utf-8")).hexdigest()
    out_dir = Path(tempfile.gettempdir()) / "fptr-demo-bundles"
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"fptr-{digest[:10]}-{metadata['stage']}-{metadata['budget_ms']}ms.zip"
    audit = {**metadata, "instance_sha256": digest, "baseline_score": baseline_score, "trace": trace}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        handle.writestr("instance.in", instance_text)
        handle.writestr("allocation.out", solution_text)
        handle.writestr("trace.json", json.dumps(trace, indent=2))
        handle.writestr("audit.json", json.dumps(audit, indent=2))
    return str(archive)


def run_demo(
    scenario_label: str,
    seed: float | int,
    budget_ms: float | int,
    stage_label: str,
    custom_file: str | None,
) -> tuple[Any, ...]:
    try:
        budget = int(budget_ms)
        if not 5 <= budget <= 200:
            raise ValueError("demo budget must lie in 5..200 ms")
        stage = STAGE_LABELS[stage_label]
        instance_text, case, case_label, case_note = load_instance(scenario_label, seed, custom_file)

        main_run = run_solver(instance_text, stage, budget)
        scored = scheduler_validator.validate_and_score(case, main_run["output"])
        solution = scheduler_validator.parse_output_text(case, main_run["output"])
        _, delivered = per_user_traffic(case, solution)
        if sum(delivered) != scored.transmitted:
            raise RuntimeError("independent per-user recomputation disagrees with validator")

        if stage == "beamfirst":
            baseline_run = main_run
            baseline_score = scored.transmitted
            baseline_for_table = None
        else:
            baseline_run = run_solver(instance_text, "beamfirst", budget)
            baseline_validated = scheduler_validator.validate_and_score(case, baseline_run["output"])
            baseline_score = baseline_validated.transmitted
            baseline_for_table = baseline_run

        trace = main_run["trace"]
        trace_scores = [int(item["score"]) for item in trace]
        monotone = all(current >= previous for previous, current in zip(trace_scores, trace_scores[1:]))
        score_consistent = trace_scores[-1] == scored.transmitted
        within_budget = not bool(trace[-1]["deadline_hit"])
        audit_pass = monotone and score_consistent and within_budget
        algorithm_ms = max(float(item["elapsed_ms"]) for item in trace)

        rows = audit_rows(trace, baseline_for_table, budget)
        user_rows = []
        for user in range(1, case.N + 1):
            resources = solution.user_resources[user]
            group = f"CG {case.ru_id[user] + 1}" if case.ru_id[user] >= 0 else "—"
            served = delivered[user - 1]
            requested = case.buffer[user]
            user_rows.append(
                [
                    user,
                    requested,
                    served,
                    round(100.0 * served / requested, 1),
                    len(resources),
                    group,
                ]
            )

        bundle_path = build_bundle(
            instance_text=instance_text,
            solution_text=main_run["output"],
            trace=trace,
            baseline_score=baseline_score,
            metadata={
                "case_id": case.case_id,
                "stage": stage,
                "budget_ms": budget,
                "transmitted": scored.transmitted,
                "beam_used": scored.beam_used,
                "algorithm_ms": algorithm_ms,
                "solver_wall_ms": main_run["wall_ms"],
                "valid": True,
                "trace_monotone": monotone,
                "trace_score_consistent": score_consistent,
                "within_budget": within_budget,
            },
        )

        return (
            status_html(
                case=case,
                case_label=case_label,
                case_note=case_note,
                transmitted=scored.transmitted,
                baseline_score=baseline_score,
                algorithm_ms=algorithm_ms,
                beam_used=scored.beam_used,
                audit_pass=audit_pass,
            ),
            make_stage_plot(trace, baseline_score, budget),
            make_allocation_plot(case, solution),
            make_demand_plot(case, delivered),
            make_beam_plot(case, solution),
            rows,
            user_rows,
            bundle_path,
            main_run["output"],
        )
    except Exception as exc:
        raise gr.Error(f"FPTR run failed: {exc}") from exc


def scenario_note(label: str) -> str:
    scenario_name = SCENARIO_LABELS[label]
    return f"**Preset:** {SCENARIO_NOTES[scenario_name]}  \nThe seed deterministically regenerates the complete scheduler input."


def reset_inputs() -> tuple[str, int, int, str, None]:
    return DEFAULT_SCENARIO, DEFAULT_SEED, DEFAULT_BUDGET, DEFAULT_STAGE, None


LOGO_URI = "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode("ascii")

CSS = """
:root { --fptr-navy: #0B2B57; --fptr-blue: #2587FF; --fptr-cyan: #16C6C7; }
.gradio-container { max-width: 1440px !important; margin: 0 auto !important; }
.hero { display:flex; align-items:center; gap:26px; padding:20px 4px 28px; }
.hero img { width:min(420px,42vw); max-height:170px; object-fit:contain; }
.hero-copy h1 { margin:0 0 8px; color:var(--fptr-navy); font-size:clamp(1.8rem,3vw,3rem); line-height:1.05; }
.hero-copy p { margin:0; color:#65758B; font-size:1.04rem; max-width:700px; }
.hero-copy .tag { display:inline-flex; margin-bottom:10px; padding:5px 10px; border-radius:999px; background:#EAF4FF; color:#146FD1; font-size:.78rem; font-weight:750; letter-spacing:.06em; }
.control-card { border:1px solid #DDE7F2 !important; border-radius:18px !important; padding:16px !important; background:#FBFDFF !important; }
.run-button { background:linear-gradient(100deg,#2587FF,#16C6C7) !important; border:none !important; }
.result-shell { border:1px solid #DDE7F2; border-radius:18px; background:white; padding:18px; box-shadow:0 10px 34px rgba(11,43,87,.06); }
.result-heading { display:flex; align-items:center; justify-content:space-between; gap:16px; }
.result-heading h3 { margin:2px 0 0; color:#0B2B57; font-size:1.15rem; }
.eyebrow { color:#2587FF; font-size:.72rem; font-weight:800; letter-spacing:.09em; }
.case-note { color:#65758B; margin:7px 0 15px; }
.audit-pill { padding:7px 10px; border-radius:999px; font-size:.76rem; font-weight:800; white-space:nowrap; }
.audit-pill.pass { color:#14753C; background:#E7F8EE; }
.audit-pill.warn { color:#9B5B00; background:#FFF2D7; }
.kpi-grid { display:grid; grid-template-columns:repeat(5,minmax(110px,1fr)); gap:10px; }
.kpi-grid article { border-radius:14px; padding:12px; background:#F5F8FC; min-width:0; }
.kpi-grid span,.kpi-grid small { display:block; color:#65758B; font-size:.72rem; }
.kpi-grid strong { display:block; margin:3px 0; color:#17324D; font-size:1.28rem; }
.instance-strip { display:flex; flex-wrap:wrap; gap:7px; margin-top:11px; }
.instance-strip span { padding:5px 8px; background:#F2F8FF; border-radius:8px; color:#526479; font-size:.74rem; }
.footer-note { color:#718096; text-align:center; padding:18px 0 8px; font-size:.82rem; }
@media (max-width: 900px) {
  .hero { flex-direction:column; text-align:center; }
  .hero img { width:min(520px,90vw); }
  .kpi-grid { grid-template-columns:repeat(2,minmax(120px,1fr)); }
}
"""

THEME = gr.themes.Soft(
    primary_hue=gr.themes.colors.blue,
    secondary_hue=gr.themes.colors.cyan,
    neutral_hue=gr.themes.colors.slate,
).set(
    button_primary_background_fill="#2587FF",
    button_primary_background_fill_hover="#146FD1",
    block_border_width="1px",
    block_radius="14px",
)

with gr.Blocks(title="FPTR Joint Beam & Resource Scheduler") as demo:
    gr.HTML(
        f"""
        <header class="hero">
          <img src="{LOGO_URI}" alt="FPTR Scheduler logo">
          <div class="hero-copy">
            <span class="tag">REAL C++17 SCHEDULER · INTERACTIVE AUDIT</span>
            <h1>Deadline-aware joint beam & resource scheduling</h1>
            <p>选择一个无线负载场景，观察 FPTR 如何在截止时间内逐阶段改进可行解，并检查最终波束、资源与用户分配。</p>
          </div>
        </header>
        """
    )

    with gr.Row(equal_height=False):
        with gr.Column(scale=4, min_width=310, elem_classes="control-card"):
            gr.Markdown("### Configure · 配置")
            scenario_input = gr.Dropdown(
                choices=list(SCENARIO_LABELS), value=DEFAULT_SCENARIO, label="场景 / Scenario"
            )
            scenario_help = gr.Markdown(scenario_note(DEFAULT_SCENARIO))
            seed_input = gr.Number(
                value=DEFAULT_SEED,
                precision=0,
                minimum=0,
                maximum=4_294_967_295,
                label="随机种子 / Seed",
            )
            budget_input = gr.Slider(
                minimum=5,
                maximum=200,
                value=DEFAULT_BUDGET,
                step=1,
                label="截止预算 / Budget (ms)",
                info="87 ms is the paper protocol default",
            )
            stage_input = gr.Dropdown(
                choices=list(STAGE_LABELS), value=DEFAULT_STAGE, label="累积终点 / Pipeline endpoint"
            )
            with gr.Accordion("自定义实例 / Custom scheduler input", open=False):
                custom_input = gr.File(
                    label="Optional .in or .txt file",
                    file_types=[".in", ".txt"],
                    type="filepath",
                )
                gr.Markdown("上传后将忽略预设场景和随机种子；输入仍由仓库的严格验证器检查。")
            with gr.Row():
                run_button = gr.Button("运行 FPTR / Run", variant="primary", elem_classes="run-button")
                reset_button = gr.Button("重置 / Reset")

        with gr.Column(scale=8, min_width=520):
            status_output = gr.HTML()
            stage_plot = gr.Plot(show_label=False)

    with gr.Tabs():
        with gr.Tab("资源分配 / Allocation"):
            allocation_plot = gr.Plot(show_label=False)
            gr.Markdown(
                "颜色表示同一资源上的共享人数；空白表示未分配。多用户共享只允许发生在同一个兼容组内。"
            )
        with gr.Tab("用户需求 / Users"):
            demand_plot = gr.Plot(show_label=False)
            user_table = gr.Dataframe(
                headers=["User", "Demand", "Delivered", "Served %", "Resources", "Compatibility group"],
                datatype=["number", "number", "number", "number", "number", "str"],
                interactive=False,
                wrap=True,
                label="Per-user audit",
            )
        with gr.Tab("波束掩码 / Beams"):
            beam_plot = gr.Plot(show_label=False)
            gr.Markdown("全局波束预算对所有子带的激活波束数求和；每个已用资源的相关子带必须拥有非空掩码。")
        with gr.Tab("事务审计 / Audit"):
            audit_table = gr.Dataframe(
                headers=["Stage", "Traffic", "Gain", "Elapsed (ms)", "Cutoff (ms)", "Decision"],
                datatype=["str", "number", "str", "number", "number", "str"],
                interactive=False,
                wrap=True,
                label="Commit-or-retain trace",
            )
            with gr.Accordion("原始调度输出 / Raw allocation contract", open=False):
                raw_output = gr.Code(language=None, interactive=False, label="allocation.out")
            bundle_output = gr.File(label="下载可审计运行包 / Download audit bundle")

    gr.HTML(
        f'<p class="footer-note">Synthetic public scenarios · Real FPTR C++ scheduler · '
        f'<a href="{SOURCE_REPOSITORY}" target="_blank">Source on GitHub ↗</a></p>'
    )

    run_inputs = [scenario_input, seed_input, budget_input, stage_input, custom_input]
    run_outputs = [
        status_output,
        stage_plot,
        allocation_plot,
        demand_plot,
        beam_plot,
        audit_table,
        user_table,
        bundle_output,
        raw_output,
    ]

    run_button.click(
        fn=run_demo,
        inputs=run_inputs,
        outputs=run_outputs,
        api_name="run_fptr",
        show_progress="minimal",
    )
    scenario_input.change(fn=scenario_note, inputs=scenario_input, outputs=scenario_help, queue=False)
    reset_event = reset_button.click(
        fn=reset_inputs,
        inputs=None,
        outputs=run_inputs,
        queue=False,
    )
    reset_event.then(fn=scenario_note, inputs=scenario_input, outputs=scenario_help, queue=False).then(
        fn=run_demo,
        inputs=run_inputs,
        outputs=run_outputs,
        show_progress="minimal",
    )
    demo.load(
        fn=run_demo,
        inputs=run_inputs,
        outputs=run_outputs,
        show_progress="hidden",
    )


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=2, max_size=20).launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", "7860")),
        show_error=True,
        theme=THEME,
        css=CSS,
    )
