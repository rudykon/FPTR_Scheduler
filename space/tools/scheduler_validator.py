#!/usr/bin/env python3
"""Strict scheduler validator, scorer, and judge-like runner.

This module implements the paper scheduler input, feasibility, rate, and output contract.
It deliberately rejects malformed inputs and legacy output variants.

Every user may be scheduled alone, regardless of whether it appears in the optional
SU list or in a resource-unit/compatibility group. Compatibility groups constrain
only multi-user sharing: all users sharing one resource must belong to the same
group. Consequently, RU and SU metadata need not cover every user.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "src"
_INT_RE = re.compile(r"-?[0-9]+\Z")


@dataclass
class CaseInput:
    path: Path | None
    case_id: str
    P: int
    N: int
    K: int
    T: int
    beam_max: int
    ru: list[tuple[int, ...]]
    ru_id: list[int]
    su: set[int]
    cap: list[list[float]]
    total_cap: list[float]
    buffer: list[int]
    sinr: list[float]
    sub_resources: list[tuple[int, ...]]
    res_bands: list[tuple[int, ...]]


@dataclass
class ParsedSolution:
    beams: list[set[int]]
    user_resources: list[list[int]]
    resource_users: list[list[int]]
    beam_used: int
    line_count: int


@dataclass
class ScoreResult:
    transmitted: int
    beam_used: int
    line_count: int


@dataclass
class RunResult:
    case_id: str
    repeat: int
    valid: bool
    transmitted: int = 0
    beam_used: int = 0
    line_count: int = 0
    elapsed_ms: float = 0.0
    official_score: float | None = None
    error: str = ""


def _parse_int(token: str, name: str) -> int:
    if not _INT_RE.fullmatch(token):
        raise ValueError(f"{name}: expected an integer, got {token!r}")
    return int(token, 10)


def _parse_float(token: str, name: str) -> float:
    try:
        value = float(token)
    except ValueError as exc:
        raise ValueError(f"{name}: expected a number, got {token!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name}: value must be finite")
    return value


def _int_line(line: str, name: str) -> list[int]:
    tokens = line.split()
    if not tokens:
        raise ValueError(f"{name}: empty line")
    return [_parse_int(token, name) for token in tokens]


def _counted_ids(
    line: str,
    name: str,
    *,
    minimum_count: int,
    maximum_count: int,
    maximum_id: int,
    duplicate_name: str = "id",
) -> list[int]:
    values = _int_line(line, name)
    count = values[0]
    ids = values[1:]
    if not minimum_count <= count <= maximum_count:
        raise ValueError(f"{name}: count {count} outside {minimum_count}..{maximum_count}")
    if len(ids) != count:
        raise ValueError(f"{name}: declared count {count} but found {len(ids)} ids")
    if any(not 1 <= value <= maximum_id for value in ids):
        raise ValueError(f"{name}: id outside 1..{maximum_id}")
    if len(set(ids)) != len(ids):
        raise ValueError(f"{name}: duplicate {duplicate_name}")
    return ids


def parse_case_text(text: str, *, case_id: str = "<memory>", path: Path | None = None) -> CaseInput:
    lines = text.splitlines()
    if len(lines) < 2:
        raise ValueError("input: expected at least two lines")

    header = _int_line(lines[0], "header")
    if len(header) != 5:
        raise ValueError(f"header: expected 5 integers, got {len(header)}")
    P, N, K, T, beam_max = header
    if not 1 <= P <= 32:
        raise ValueError(f"P: {P} outside 1..32")
    if not 1 <= N <= 100:
        raise ValueError(f"N: {N} outside 1..100")
    if not 2 <= K <= 72:
        raise ValueError(f"K: {K} outside 2..72")
    if not 1 <= T <= 18:
        raise ValueError(f"T: {T} outside 1..18")
    if not 2 <= beam_max <= 255:
        raise ValueError(f"beamMaxNum: {beam_max} outside 2..255")

    m_values = _int_line(lines[1], "M")
    if len(m_values) != 1:
        raise ValueError(f"M: expected 1 integer, got {len(m_values)}")
    M = m_values[0]
    if not 0 <= M <= 16:
        raise ValueError(f"M: {M} outside 0..16")

    expected_lines = 3 + M + 2 * N + T
    if len(lines) != expected_lines:
        raise ValueError(f"input line count {len(lines)} != expected {expected_lines}")

    cursor = 2
    ru: list[tuple[int, ...]] = []
    ru_id = [-1] * (N + 1)
    grouped_users: set[int] = set()
    for group_id in range(M):
        users = _counted_ids(
            lines[cursor],
            f"RU line {group_id + 1}",
            minimum_count=2,
            maximum_count=20,
            maximum_id=N,
        )
        cursor += 1
        overlap = grouped_users.intersection(users)
        if overlap:
            raise ValueError(f"RU line {group_id + 1}: users repeated across RU groups: {sorted(overlap)}")
        for user in users:
            grouped_users.add(user)
            ru_id[user] = group_id
        ru.append(tuple(users))

    su_ids = _counted_ids(
        lines[cursor],
        "SU line",
        minimum_count=0,
        maximum_count=29,
        maximum_id=N,
    )
    cursor += 1
    su = set(su_ids)
    overlap = grouped_users.intersection(su)
    if overlap:
        raise ValueError(f"SU line: users also present in RU groups: {sorted(overlap)}")

    cap = [[0.0] * (P + 1) for _ in range(N + 1)]
    total_cap = [0.0] * (N + 1)
    for user in range(1, N + 1):
        tokens = lines[cursor].split()
        cursor += 1
        if len(tokens) != P:
            raise ValueError(f"cap line {user}: expected {P} values, got {len(tokens)}")
        for beam, token in enumerate(tokens, start=1):
            value = _parse_float(token, f"cap[{user}][{beam}]")
            if not 0.0 < value <= 65535.0:
                raise ValueError(f"cap[{user}][{beam}]: {value} outside (0,65535]")
            cap[user][beam] = value
            total_cap[user] += value

    buffer = [0] * (N + 1)
    sinr = [0.0] * (N + 1)
    for user in range(1, N + 1):
        tokens = lines[cursor].split()
        cursor += 1
        if len(tokens) != 2:
            raise ValueError(f"buffer/sinr line {user}: expected 2 values, got {len(tokens)}")
        buffer_value = _parse_int(tokens[0], f"buffer[{user}]")
        sinr_value = _parse_float(tokens[1], f"sinr[{user}]")
        if not 1 <= buffer_value <= 10000:
            raise ValueError(f"buffer[{user}]: {buffer_value} outside 1..10000")
        if not -30.0 <= sinr_value <= 100.0:
            raise ValueError(f"sinr[{user}]: {sinr_value} outside [-30,100]")
        buffer[user] = buffer_value
        sinr[user] = sinr_value

    sub_resources: list[tuple[int, ...]] = [tuple()]
    memberships: list[list[int]] = [[] for _ in range(K + 1)]
    for band in range(1, T + 1):
        resources = _counted_ids(
            lines[cursor],
            f"RSub line {band}",
            minimum_count=0,
            maximum_count=K,
            maximum_id=K,
        )
        cursor += 1
        sub_resources.append(tuple(resources))
        for resource in resources:
            memberships[resource].append(band)

    res_bands: list[tuple[int, ...]] = [tuple()]
    for resource in range(1, K + 1):
        bands = memberships[resource]
        if not bands:
            raise ValueError(f"RSub lines do not cover resource {resource}")
        if len(bands) not in (1, 2):
            raise ValueError(f"resource {resource} must belong to one or two subbands, got {len(bands)}")
        res_bands.append(tuple(bands))

    return CaseInput(
        path=path,
        case_id=case_id,
        P=P,
        N=N,
        K=K,
        T=T,
        beam_max=beam_max,
        ru=ru,
        ru_id=ru_id,
        su=su,
        cap=cap,
        total_cap=total_cap,
        buffer=buffer,
        sinr=sinr,
        sub_resources=sub_resources,
        res_bands=res_bands,
    )


def parse_case(path: Path) -> CaseInput:
    return parse_case_text(path.read_text(encoding="utf-8"), case_id=path.stem, path=path)


def parse_output_text(case: CaseInput, output: str) -> ParsedSolution:
    lines = output.splitlines()
    expected_lines = case.T + case.N
    if len(lines) != expected_lines:
        raise ValueError(f"output line count {len(lines)} != expected {expected_lines}")

    beams: list[set[int]] = [set() for _ in range(case.T + 1)]
    beam_used = 0
    for band in range(1, case.T + 1):
        ids = _counted_ids(
            lines[band - 1],
            f"beam line {band}",
            minimum_count=0,
            maximum_count=case.P,
            maximum_id=case.P,
        )
        beams[band] = set(ids)
        beam_used += len(ids)
    if beam_used > case.beam_max:
        raise ValueError(f"beam budget {beam_used} > {case.beam_max}")

    user_resources: list[list[int]] = [[] for _ in range(case.N + 1)]
    resource_users: list[list[int]] = [[] for _ in range(case.K + 1)]
    for user in range(1, case.N + 1):
        resources = _counted_ids(
            lines[case.T + user - 1],
            f"user line {user}",
            minimum_count=0,
            maximum_count=case.K,
            maximum_id=case.K,
            duplicate_name="resource id",
        )
        user_resources[user] = resources
        for resource in resources:
            resource_users[resource].append(user)

    for resource in range(1, case.K + 1):
        users = resource_users[resource]
        if users:
            for band in case.res_bands[resource]:
                if not beams[band]:
                    raise ValueError(
                        f"resource {resource}: related subband {band} has an empty beam set"
                    )
        # Group metadata constrains sharing only. In particular, an RU member,
        # an SU-listed user, or a user absent from both lists may all use a
        # resource as a singleton.
        if len(users) <= 1:
            continue
        group = case.ru_id[users[0]]
        if group < 0 or any(case.ru_id[user] != group for user in users):
            raise ValueError(
                f"resource {resource}: shared users are not in the same compatibility group: {users}"
            )

    return ParsedSolution(
        beams=beams,
        user_resources=user_resources,
        resource_users=resource_users,
        beam_used=beam_used,
        line_count=len(lines),
    )


def cap_of(fse: float) -> int:
    if fse <= -10.0:
        return 0
    if fse <= 0.0:
        return 8
    if fse <= 3.0:
        return 24
    if fse <= 10.0:
        return 90
    if fse <= 15.0:
        return 120
    if fse <= 20.0:
        return 162
    return 222


def validate_and_score(case: CaseInput, output: str) -> ScoreResult:
    solution = parse_output_text(case, output)
    raw = [0] * (case.N + 1)

    for resource in range(1, case.K + 1):
        users = solution.resource_users[resource]
        if not users:
            continue
        share = len(users)
        bands = case.res_bands[resource]
        denominator = bands[-1] - bands[0] + 1
        for user in users:
            selected_sum = 0.0
            for band in bands:
                selected_sum += sum(case.cap[user][beam] for beam in solution.beams[band])
            selected_average = selected_sum / denominator
            if selected_average <= 0.0:
                raise ValueError(f"user {user}, resource {resource}: selected capability is zero")
            fse = (
                case.sinr[user]
                + 10.0 * math.log10(1.0 / share)
                + 10.0 * math.log10(selected_average / case.total_cap[user])
            )
            raw[user] += cap_of(fse)

    transmitted = sum(min(case.buffer[user], raw[user]) for user in range(1, case.N + 1))
    return ScoreResult(
        transmitted=transmitted,
        beam_used=solution.beam_used,
        line_count=solution.line_count,
    )


def case_score(transmitted: int, t_base: float, score_base: float) -> float:
    if not math.isfinite(t_base) or t_base <= 0.0:
        raise ValueError("T_base must be finite and positive")
    if not math.isfinite(score_base) or score_base < 0.0:
        raise ValueError("Score_base must be finite and non-negative")
    return transmitted / t_base * score_base


def load_baselines(path: Path | None) -> dict[str, tuple[float, float]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("baseline file must contain a JSON object")
    raw_cases = payload.get("cases", payload)
    if not isinstance(raw_cases, Mapping):
        raise ValueError("baseline 'cases' must be a JSON object")
    result: dict[str, tuple[float, float]] = {}
    for case_id, values in raw_cases.items():
        if not isinstance(case_id, str) or not isinstance(values, Mapping):
            raise ValueError("each baseline case must map a string id to an object")
        try:
            t_base = float(values["T_base"])
            score_base = float(values["Score_base"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"baseline {case_id}: expected numeric T_base and Score_base") from exc
        case_score(0, t_base, score_base)
        result[case_id] = (t_base, score_base)
    return result


def compile_solver(src_dir: Path, build_dir: Path) -> Path:
    required = [src_dir / "scheduler.cpp", src_dir / "core.cpp", src_dir / "core.h"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing scheduler source files: {', '.join(missing)}")
    solver = build_dir / "traffic_scheduler_scheduler"
    subprocess.run(
        [
            "g++",
            "-std=c++17",
            "-O2",
            str(src_dir / "scheduler.cpp"),
            str(src_dir / "core.cpp"),
            "-o",
            str(solver),
        ],
        check=True,
    )
    return solver


def run_solver(solver: Path, case_path: Path, timeout_ms: float) -> tuple[str, float]:
    started = time.perf_counter()
    proc = subprocess.run(
        [str(solver)],
        input=case_path.read_bytes(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_ms / 1000.0,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"solver exit code {proc.returncode}: {stderr}")
    return proc.stdout.decode("utf-8", errors="strict"), elapsed_ms


def percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]


def print_results(results: list[RunResult], repeats: int, baselines: Mapping[str, tuple[float, float]]) -> None:
    print("case  run  valid  T_i     beams  lines  time_ms  score/note")
    print("----  ---  -----  ------  -----  -----  -------  ----------")
    for result in results:
        if result.valid:
            score_text = f"{result.official_score:.4f}" if result.official_score is not None else "-"
            print(
                f"{result.case_id:<4}  {result.repeat:<3}  yes    {result.transmitted:<6}  "
                f"{result.beam_used:<5}  {result.line_count:<5}  {result.elapsed_ms:>7.2f}  {score_text}"
            )
        else:
            print(
                f"{result.case_id:<4}  {result.repeat:<3}  no     {'-':<6}  {'-':<5}  "
                f"{'-':<5}  {result.elapsed_ms:>7.2f}  {result.error}"
            )

    valid = [result for result in results if result.valid]
    print("\nsummary")
    print(f"  valid_runs: {len(valid)}/{len(results)}")
    if not valid:
        return
    elapsed = [result.elapsed_ms for result in valid]
    print(f"  repeats_per_case: {repeats}")
    print(f"  time_ms_median: {statistics.median(elapsed):.2f}")
    print(f"  time_ms_p95: {percentile(elapsed, 0.95):.2f}")
    print(f"  time_ms_worst: {max(elapsed):.2f}")

    by_repeat: dict[int, list[RunResult]] = {}
    for result in valid:
        by_repeat.setdefault(result.repeat, []).append(result)
    total_t = [sum(item.transmitted for item in run) for run in by_repeat.values()]
    if total_t:
        print(f"  total_T_min: {min(total_t)}")
        print(f"  total_T_max: {max(total_t)}")
    if baselines and all(result.official_score is not None for result in valid):
        total_score = [sum(item.official_score or 0.0 for item in run) for run in by_repeat.values()]
        print(f"  official_score_min: {min(total_score):.4f}")
        print(f"  official_score_max: {max(total_score):.4f}")
    elif baselines:
        print("  official_score: unavailable for at least one case")
    else:
        print("  official_score: unavailable; provide per-case T_base and Score_base metadata")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and score scheduler resource-allocation outputs.")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="scheduler C++ source directory")
    parser.add_argument(
        "--samples",
        type=Path,
        required=True,
        help="directory containing scheduler *.in (required; this artifact has no bundled default cases)",
    )
    parser.add_argument("--solver", type=Path, default=None, help="existing solver binary")
    parser.add_argument("--output-dir", type=Path, default=None, help="validate <case>.out files instead of running")
    parser.add_argument("--baseline", type=Path, default=None, help="JSON with per-case T_base and Score_base")
    parser.add_argument("--timeout-ms", type=float, default=100.0, help="per-process timeout in milliseconds")
    parser.add_argument("--repeat", type=int, default=1, help="number of judge-like runs per case")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.timeout_ms <= 0.0:
        parser.error("--timeout-ms must be positive")
    if args.repeat <= 0:
        parser.error("--repeat must be positive")
    if args.output_dir is not None and args.repeat != 1:
        parser.error("--repeat must be 1 with --output-dir")

    sample_paths = sorted(args.samples.glob("*.in"), key=lambda path: path.stem)
    if not sample_paths:
        print(f"no scheduler samples found in {args.samples}", file=sys.stderr)
        return 2
    try:
        cases = [parse_case(path) for path in sample_paths]
        baselines = load_baselines(args.baseline)
    except Exception as exc:  # noqa: BLE001 - CLI reports contract failures.
        print(f"input/baseline error: {exc}", file=sys.stderr)
        return 2

    solver = args.solver
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    try:
        if args.output_dir is None and solver is None:
            temp_dir = tempfile.TemporaryDirectory(prefix="traffic_scheduler_scheduler_")
            solver = compile_solver(args.src, Path(temp_dir.name))

        results: list[RunResult] = []
        for repeat in range(1, args.repeat + 1):
            for case in cases:
                elapsed_ms = 0.0
                try:
                    if args.output_dir is not None:
                        output = (args.output_dir / f"{case.case_id}.out").read_text(encoding="utf-8")
                    else:
                        assert solver is not None
                        output, elapsed_ms = run_solver(solver, case.path or Path(), args.timeout_ms)
                    scored = validate_and_score(case, output)
                    official_score = None
                    if case.case_id in baselines:
                        official_score = case_score(scored.transmitted, *baselines[case.case_id])
                    results.append(
                        RunResult(
                            case_id=case.case_id,
                            repeat=repeat,
                            valid=True,
                            transmitted=scored.transmitted,
                            beam_used=scored.beam_used,
                            line_count=scored.line_count,
                            elapsed_ms=elapsed_ms,
                            official_score=official_score,
                        )
                    )
                except subprocess.TimeoutExpired:
                    results.append(
                        RunResult(
                            case_id=case.case_id,
                            repeat=repeat,
                            valid=False,
                            elapsed_ms=args.timeout_ms,
                            error=f"timeout > {args.timeout_ms:.2f} ms",
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - collect all case failures.
                    results.append(
                        RunResult(
                            case_id=case.case_id,
                            repeat=repeat,
                            valid=False,
                            elapsed_ms=elapsed_ms,
                            error=str(exc),
                        )
                    )

        print_results(results, args.repeat, baselines)
        return 0 if all(result.valid for result in results) else 1
    except subprocess.CalledProcessError as exc:
        print(f"compile failed with exit code {exc.returncode}", file=sys.stderr)
        return 2
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
