#!/usr/bin/env python3
"""Rebuild and independently audit the sealed 12-case exact suite.

The script has three deliberately separated roles:

1. Gate execution on fixed SHA256 digests for the formal generator and sealed
   exact-result artifacts.
2. Reconstruct the predeclared mixed exact suite through the hash-gated formal
   generator and compare every generated case with the sealed case manifest.
3. Recompute every optimum with an independently instrumented dynamic program.

All generated evidence is deterministic and is written under
``reproducibility/audit``. The sealed files in ``reproducibility/results`` are
read only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import itertools
import json
import math
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
FORMAL_GENERATOR = ROOT / "experiments" / "paper_experiments.py"
FORMAL_RESULTS = ROOT / "reproducibility" / "results"
DEFAULT_OUTPUT = ROOT / "reproducibility" / "audit"

SEALED_GENERATOR_SHA256 = (
    "37abf277fcd1301e75c505e081174df78fb643e301aad60fca8e24f30698116a"
)
CURRENT_GENERATOR_SHA256 = (
    "b0d919f99e95e01e40553bbfe516c2d62205388db4647e05336078b2fe34c0ea"
)
EXPECTED_FORMAL_SHA256 = {
    "case_manifest.csv": (
        "a0578bcfcf6514f067e9e650209eb70c71453ea34e6e52af13c59d1c79e6601b"
    ),
    "exact_results.csv": (
        "72f66613cd507656552df3ff19177647fc5c809e260140a4c4e0064d8db037dc"
    ),
    "exact_run_results.csv": (
        "25c284e0cf9122718987fdde8769b332f9210389e9ff7f61ad55a5c27660f5da"
    ),
    "experiment_manifest.json": (
        "fda25cde535c0b0f6e0d27e211d888e556d35bc65b3dfc3521f22f56a9a53589"
    ),
}
FORMAL_EXACT_SEED_BASE = 20281001
FORMAL_EXACT_CASES = 12
EXPECTED_METHODS = {"BeamFirst", "Base", "Global", "CG", "Remask", "Full"}

SUMMARY_FIELDS = (
    "scenario",
    "seed",
    "instance_id",
    "case_sha256",
    "P",
    "N",
    "K",
    "T",
    "beam_max",
    "beam_plans",
    "resource_layers",
    "resource_choice_vectors",
    "transition_attempts",
    "unique_pre_prune_states",
    "duplicates_collapsed",
    "dominated_removed",
    "retained_frontier_states",
    "terminal_frontier_states",
    "peak_pre_prune_states",
    "peak_frontier_states",
    "formal_optimum",
    "audited_optimum",
    "optimum_match",
    "optimal_beam_plans",
    "minimum_active_beams_at_optimum",
    "maximum_active_beams_at_optimum",
)

LAYER_FIELDS = (
    "scenario",
    "seed",
    "instance_id",
    "beam_plan_index",
    "active_beams",
    "beam_masks_hex",
    "resource",
    "choice_vectors",
    "frontier_before",
    "transition_attempts",
    "unique_pre_prune_states",
    "duplicates_collapsed",
    "dominated_removed",
    "retained_frontier_states",
    "best_retained_value",
)

CASE_FIELDS = (
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
    "reconstructed_input",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_formal_checksums() -> dict[str, str]:
    path = FORMAL_RESULTS / "CHECKSUMS.sha256"
    entries: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise AssertionError(f"{path}:{line_number}: malformed checksum line")
        digest, name = parts
        name = name.strip()
        if name.startswith("*"):
            name = name[1:]
        if name in entries:
            raise AssertionError(f"{path}:{line_number}: duplicate entry {name!r}")
        entries[name] = digest
    return entries


def validate_hash_gate() -> dict[str, dict[str, Any]]:
    observed_generator = sha256_file(FORMAL_GENERATOR)
    if observed_generator != CURRENT_GENERATOR_SHA256:
        raise AssertionError(
            "formal generator hash mismatch: "
            f"expected {CURRENT_GENERATOR_SHA256}, observed {observed_generator}"
        )

    formal_checksums = read_formal_checksums()
    evidence: dict[str, dict[str, Any]] = {
        "experiments/paper_experiments.py": {
            "expected_sha256": CURRENT_GENERATOR_SHA256,
            "observed_sha256": observed_generator,
            "sealed_manifest_sha256": SEALED_GENERATOR_SHA256,
            "migration_note": (
                "The current source changes the default output directory from paper/results "
                "to reproducibility/results; reconstructed case hashes remain gated below."
            ),
            "verified": True,
        }
    }
    for name, expected in EXPECTED_FORMAL_SHA256.items():
        path = FORMAL_RESULTS / name
        observed = sha256_file(path)
        if observed != expected:
            raise AssertionError(
                f"sealed artifact hash mismatch for {name}: "
                f"expected {expected}, observed {observed}"
            )
        if formal_checksums.get(name) != expected:
            raise AssertionError(
                f"formal CHECKSUMS.sha256 does not bind {name} to {expected}"
            )
        evidence[f"reproducibility/results/{name}"] = {
            "expected_sha256": expected,
            "observed_sha256": observed,
            "formal_checksums_entry": formal_checksums[name],
            "verified": True,
        }
    return evidence


def load_hash_gated_generator() -> ModuleType:
    """Import the formal generator only after its fixed digest has passed."""

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    module_name = "_hash_gated_formal_paper_experiments"
    spec = importlib.util.spec_from_file_location(module_name, FORMAL_GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {FORMAL_GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def validate_formal_manifest() -> dict[str, Any]:
    path = FORMAL_RESULTS / "experiment_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))

    protocol = manifest.get("exact_seed_protocol")
    expected_protocol = {
        "base": FORMAL_EXACT_SEED_BASE,
        "count": FORMAL_EXACT_CASES,
        "continuous_unfiltered_interval": True,
        "scenario_mix": {
            "offset_0": "tiny-widebeam",
            "offset_1_onward": "tiny-exact",
        },
    }
    if protocol != expected_protocol:
        raise AssertionError(
            "formal exact seed protocol mismatch: "
            f"expected {expected_protocol!r}, observed {protocol!r}"
        )

    source_hash = manifest.get("source_sha256", {}).get(
        "experiments/paper_experiments.py"
    )
    if source_hash != SEALED_GENERATOR_SHA256:
        raise AssertionError("experiment manifest records an unexpected generator hash")

    for name, expected in EXPECTED_FORMAL_SHA256.items():
        if name == "experiment_manifest.json":
            continue
        metadata = manifest.get("result_artifacts", {}).get(name)
        if not isinstance(metadata, dict) or metadata.get("sha256") != expected:
            raise AssertionError(
                f"experiment manifest records an unexpected hash for {name}"
            )
    return manifest


def parse_formal_case_rows() -> dict[str, dict[str, str]]:
    rows = [
        row
        for row in read_csv(FORMAL_RESULTS / "case_manifest.csv")
        if row["experiment"] == "exact"
    ]
    if len(rows) != FORMAL_EXACT_CASES:
        raise AssertionError(
            f"expected {FORMAL_EXACT_CASES} exact case-manifest rows, found {len(rows)}"
        )
    indexed = {row["instance_id"]: row for row in rows}
    if len(indexed) != len(rows):
        raise AssertionError("duplicate exact instance_id in case_manifest.csv")
    return indexed


def parse_formal_optima() -> tuple[dict[str, int], dict[str, dict[str, str]]]:
    rows = read_csv(FORMAL_RESULTS / "exact_results.csv")
    if len(rows) != FORMAL_EXACT_CASES * len(EXPECTED_METHODS):
        raise AssertionError(
            "unexpected exact_results.csv row count: "
            f"expected {FORMAL_EXACT_CASES * len(EXPECTED_METHODS)}, found {len(rows)}"
        )

    optima: dict[str, int] = {}
    identities: dict[str, dict[str, str]] = {}
    methods: dict[str, set[str]] = {}
    for row in rows:
        instance_id = row["instance_id"]
        optimum = int(float(row["optimum"]))
        if instance_id in optima and optima[instance_id] != optimum:
            raise AssertionError(f"inconsistent optimum for {instance_id}")
        optima[instance_id] = optimum
        methods.setdefault(instance_id, set()).add(row["method"])
        identity = {
            "scenario": row["scenario"],
            "seed": row["seed"],
            "case_sha256": row["case_sha256"],
            "demand": row["demand"],
        }
        if instance_id in identities and identities[instance_id] != identity:
            raise AssertionError(f"inconsistent identity fields for {instance_id}")
        identities[instance_id] = identity

    if len(optima) != FORMAL_EXACT_CASES:
        raise AssertionError(
            f"expected {FORMAL_EXACT_CASES} exact instances, found {len(optima)}"
        )
    for instance_id, observed_methods in methods.items():
        if observed_methods != EXPECTED_METHODS:
            raise AssertionError(
                f"{instance_id}: expected methods {sorted(EXPECTED_METHODS)}, "
                f"found {sorted(observed_methods)}"
            )
    return optima, identities


def cap_of(fse: float) -> int:
    """Independent copy of the benchmark's seven-level rate map."""

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


def legal_user_groups(case: Any) -> tuple[tuple[int, ...], ...]:
    """Enumerate legal singleton and within-compatibility-group assignments."""

    groups: set[tuple[int, ...]] = {()}
    groups.update((user,) for user in range(1, case.N + 1))
    for compatibility_group in case.ru:
        for size in range(2, len(compatibility_group) + 1):
            groups.update(itertools.combinations(compatibility_group, size))
    return tuple(sorted(groups, key=lambda users: (len(users), users)))


def beam_plans(case: Any) -> Iterable[tuple[int, ...]]:
    """Enumerate every beam mask satisfying the global beam-count budget."""

    positions = case.T * case.P
    budget = min(case.beam_max, positions)
    for active_count in range(budget + 1):
        for active in itertools.combinations(range(positions), active_count):
            masks = [0] * (case.T + 1)
            for position in active:
                band = position // case.P + 1
                beam = position % case.P
                masks[band] |= 1 << beam
            yield tuple(masks)


def resource_rate_choices(
    case: Any,
    masks: Sequence[int],
    resource: int,
    groups: Sequence[tuple[int, ...]],
) -> tuple[tuple[int, ...], ...]:
    """Compute distinct per-user rate vectors for one fixed resource."""

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
                raise AssertionError("positive capability matrix produced a zero average")
            fse = (
                case.sinr[user]
                + 10.0 * math.log10(1.0 / share)
                + 10.0 * math.log10(selected_average / case.total_cap[user])
            )
            rates[user - 1] = cap_of(fse)
        choices.add(tuple(rates))
    return tuple(sorted(choices))


def dominates(left: tuple[int, ...], right: tuple[int, ...]) -> bool:
    return all(a >= b for a, b in zip(left, right))


def dominance_prune(states: set[tuple[int, ...]]) -> set[tuple[int, ...]]:
    """Retain the component-wise maximal antichain of clipped capacities."""

    ordered = sorted(states, key=lambda state: (sum(state), state), reverse=True)
    frontier: list[tuple[int, ...]] = []
    for state in ordered:
        if any(dominates(kept, state) for kept in frontier):
            continue
        frontier.append(state)
    return set(frontier)


def mask_code(masks: Sequence[int]) -> str:
    return ";".join(f"{band}:{masks[band]:#x}" for band in range(1, len(masks)))


def audit_case(
    bundle: Any,
    formal_optimum: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    case = bundle.case
    groups = legal_user_groups(case)
    buffers = tuple(case.buffer[1:])
    layers: list[dict[str, Any]] = []

    beam_plan_count = 0
    resource_layers = 0
    resource_choice_vectors = 0
    transition_attempts = 0
    unique_pre_prune_states = 0
    duplicates_collapsed = 0
    dominated_removed = 0
    retained_frontier_states = 0
    terminal_frontier_states = 0
    peak_pre_prune_states = 0
    peak_frontier_states = 1
    audited_optimum = 0
    optimal_plans: list[int] = []

    for beam_plan_index, masks in enumerate(beam_plans(case)):
        beam_plan_count += 1
        active_beams = sum(mask.bit_count() for mask in masks[1:])
        states: set[tuple[int, ...]] = {(0,) * case.N}
        for resource in range(1, case.K + 1):
            choices = resource_rate_choices(case, masks, resource, groups)
            frontier_before = len(states)
            attempts = frontier_before * len(choices)
            next_states = {
                tuple(
                    min(buffers[index], state[index] + choice[index])
                    for index in range(case.N)
                )
                for state in states
                for choice in choices
            }
            unique_count = len(next_states)
            duplicate_count = attempts - unique_count
            frontier = dominance_prune(next_states)
            removed_count = unique_count - len(frontier)

            if attempts != unique_count + duplicate_count:
                raise AssertionError("transition accounting identity failed")
            if unique_count != removed_count + len(frontier):
                raise AssertionError("pruning accounting identity failed")
            if not frontier:
                raise AssertionError("dominance pruning produced an empty frontier")

            layer_best = max(sum(state) for state in frontier)
            layers.append(
                {
                    "scenario": bundle.scenario.name,
                    "seed": bundle.seed,
                    "instance_id": bundle.instance_id,
                    "beam_plan_index": beam_plan_index,
                    "active_beams": active_beams,
                    "beam_masks_hex": mask_code(masks),
                    "resource": resource,
                    "choice_vectors": len(choices),
                    "frontier_before": frontier_before,
                    "transition_attempts": attempts,
                    "unique_pre_prune_states": unique_count,
                    "duplicates_collapsed": duplicate_count,
                    "dominated_removed": removed_count,
                    "retained_frontier_states": len(frontier),
                    "best_retained_value": layer_best,
                }
            )

            resource_layers += 1
            resource_choice_vectors += len(choices)
            transition_attempts += attempts
            unique_pre_prune_states += unique_count
            duplicates_collapsed += duplicate_count
            dominated_removed += removed_count
            retained_frontier_states += len(frontier)
            peak_pre_prune_states = max(peak_pre_prune_states, unique_count)
            peak_frontier_states = max(peak_frontier_states, len(frontier))
            states = frontier

        terminal_frontier_states += len(states)
        plan_best = max(sum(state) for state in states)
        if plan_best > audited_optimum:
            audited_optimum = plan_best
            optimal_plans = [active_beams]
        elif plan_best == audited_optimum:
            optimal_plans.append(active_beams)

    if audited_optimum != formal_optimum:
        raise AssertionError(
            f"{bundle.instance_id}: audited optimum {audited_optimum} "
            f"!= sealed optimum {formal_optimum}"
        )
    if resource_layers != beam_plan_count * case.K:
        raise AssertionError("resource-layer count does not match beam plans times K")
    if transition_attempts != unique_pre_prune_states + duplicates_collapsed:
        raise AssertionError("case-level transition accounting identity failed")
    if unique_pre_prune_states != dominated_removed + retained_frontier_states:
        raise AssertionError("case-level pruning accounting identity failed")

    summary = {
        "scenario": bundle.scenario.name,
        "seed": bundle.seed,
        "instance_id": bundle.instance_id,
        "case_sha256": bundle.case_sha256,
        "P": case.P,
        "N": case.N,
        "K": case.K,
        "T": case.T,
        "beam_max": case.beam_max,
        "beam_plans": beam_plan_count,
        "resource_layers": resource_layers,
        "resource_choice_vectors": resource_choice_vectors,
        "transition_attempts": transition_attempts,
        "unique_pre_prune_states": unique_pre_prune_states,
        "duplicates_collapsed": duplicates_collapsed,
        "dominated_removed": dominated_removed,
        "retained_frontier_states": retained_frontier_states,
        "terminal_frontier_states": terminal_frontier_states,
        "peak_pre_prune_states": peak_pre_prune_states,
        "peak_frontier_states": peak_frontier_states,
        "formal_optimum": formal_optimum,
        "audited_optimum": audited_optimum,
        "optimum_match": True,
        "optimal_beam_plans": len(optimal_plans),
        "minimum_active_beams_at_optimum": min(optimal_plans),
        "maximum_active_beams_at_optimum": max(optimal_plans),
    }
    return summary, layers


def reconstructed_case_row(bundle: Any, relative_input: str) -> dict[str, Any]:
    case = bundle.case
    return {
        "experiment": "exact",
        "scenario": bundle.scenario.name,
        "seed": bundle.seed,
        "instance_id": bundle.instance_id,
        "case_sha256": bundle.case_sha256,
        "P": case.P,
        "N": case.N,
        "K": case.K,
        "T": case.T,
        "beam_max": case.beam_max,
        "compatibility_groups": len(case.ru),
        "max_group_size": bundle.max_group_size,
        "double_memberships": bundle.double_memberships,
        "nonadjacent_memberships": bundle.nonadjacent_memberships,
        "reconstructed_input": relative_input,
    }


def assert_reconstructed_case(
    bundle: Any,
    formal_case: Mapping[str, str],
    formal_identity: Mapping[str, str],
    formal_manifest: Mapping[str, Any],
) -> None:
    expected = reconstructed_case_row(bundle, "")
    for field in CASE_FIELDS:
        if field == "reconstructed_input":
            continue
        observed = str(expected[field])
        sealed = formal_case[field]
        if observed != sealed:
            raise AssertionError(
                f"{bundle.instance_id}: case-manifest field {field} "
                f"expected {sealed!r}, reconstructed {observed!r}"
            )

    if formal_identity["scenario"] != bundle.scenario.name:
        raise AssertionError(f"{bundle.instance_id}: exact-results scenario mismatch")
    if int(formal_identity["seed"]) != bundle.seed:
        raise AssertionError(f"{bundle.instance_id}: exact-results seed mismatch")
    if formal_identity["case_sha256"] != bundle.case_sha256:
        raise AssertionError(f"{bundle.instance_id}: exact-results case hash mismatch")
    if int(float(formal_identity["demand"])) != bundle.demand:
        raise AssertionError(f"{bundle.instance_id}: exact-results demand mismatch")
    manifest_hash = formal_manifest.get("case_hashes", {}).get(bundle.instance_id)
    if manifest_hash != bundle.case_sha256:
        raise AssertionError(f"{bundle.instance_id}: experiment-manifest hash mismatch")
    if sha256_text(bundle.text) != bundle.case_sha256:
        raise AssertionError(f"{bundle.instance_id}: in-memory text hash mismatch")


def prepare_output_directory(out_dir: Path, input_names: set[str]) -> Path:
    resolved = out_dir.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"output directory must remain inside repository: {resolved}") from exc

    allowed_top_level = {
        "audit_manifest.json",
        "exact_dp_layers.csv",
        "exact_suite_audit.csv",
        "reconstructed_case_manifest.csv",
        "CHECKSUMS.sha256",
        "inputs",
    }
    if resolved.exists():
        unexpected = sorted(path.name for path in resolved.iterdir() if path.name not in allowed_top_level)
        if unexpected:
            raise RuntimeError(
                f"refusing to overwrite output directory containing unexpected entries: {unexpected}"
            )
    resolved.mkdir(parents=True, exist_ok=True)
    inputs = resolved / "inputs"
    if inputs.exists():
        unexpected_inputs = sorted(
            path.name for path in inputs.iterdir() if path.name not in input_names
        )
        if unexpected_inputs:
            raise RuntimeError(
                "refusing to overwrite inputs directory containing unexpected entries: "
                f"{unexpected_inputs}"
            )
    inputs.mkdir(parents=True, exist_ok=True)
    return resolved


def write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def write_checksums(out_dir: Path) -> None:
    checksum_path = out_dir / "CHECKSUMS.sha256"
    paths = sorted(
        (
            path
            for path in out_dir.rglob("*")
            if path.is_file() and path != checksum_path
        ),
        key=lambda path: path.relative_to(out_dir).as_posix(),
    )
    lines = [
        f"{sha256_file(path)}  {path.relative_to(out_dir).as_posix()}\n"
        for path in paths
    ]
    checksum_path.write_text("".join(lines), encoding="utf-8")


def verify_written_checksums(out_dir: Path) -> int:
    checksum_path = out_dir / "CHECKSUMS.sha256"
    count = 0
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split(maxsplit=1)
        path = out_dir / relative.strip()
        observed = sha256_file(path)
        if observed != digest:
            raise AssertionError(
                f"written checksum mismatch for {relative}: {observed} != {digest}"
            )
        count += 1
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(
            "audit output directory inside the repository "
            "(default: reproducibility/audit)"
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    hash_gate = validate_hash_gate()
    formal_manifest = validate_formal_manifest()
    formal_cases = parse_formal_case_rows()
    formal_optima, formal_identities = parse_formal_optima()
    generator = load_hash_gated_generator()

    bundles = generator.exact_bundles(
        FORMAL_EXACT_CASES,
        FORMAL_EXACT_SEED_BASE,
    )
    if len(bundles) != FORMAL_EXACT_CASES:
        raise AssertionError(
            f"formal generator returned {len(bundles)} exact cases, expected {FORMAL_EXACT_CASES}"
        )
    expected_seeds = list(
        range(FORMAL_EXACT_SEED_BASE, FORMAL_EXACT_SEED_BASE + FORMAL_EXACT_CASES)
    )
    if [bundle.seed for bundle in bundles] != expected_seeds:
        raise AssertionError("formal generator did not preserve the consecutive seed interval")
    expected_scenarios = ["tiny-widebeam", *("tiny-exact" for _ in range(11))]
    if [bundle.scenario.name for bundle in bundles] != expected_scenarios:
        raise AssertionError("formal generator returned an unexpected mixed-suite order")

    generated_ids = {bundle.instance_id for bundle in bundles}
    if generated_ids != set(formal_cases):
        raise AssertionError("reconstructed case identities differ from case_manifest.csv")
    if generated_ids != set(formal_optima):
        raise AssertionError("reconstructed case identities differ from exact_results.csv")

    input_names = {f"{bundle.instance_id}.in" for bundle in bundles}
    out_dir = prepare_output_directory(args.out_dir, input_names)
    input_dir = out_dir / "inputs"

    summaries: list[dict[str, Any]] = []
    all_layers: list[dict[str, Any]] = []
    reconstructed_rows: list[dict[str, Any]] = []
    for index, bundle in enumerate(bundles, 1):
        assert_reconstructed_case(
            bundle,
            formal_cases[bundle.instance_id],
            formal_identities[bundle.instance_id],
            formal_manifest,
        )

        input_path = input_dir / f"{bundle.instance_id}.in"
        input_path.write_bytes(bundle.text.encode("utf-8"))
        if sha256_file(input_path) != bundle.case_sha256:
            raise AssertionError(f"{bundle.instance_id}: written input hash mismatch")
        relative_input = input_path.relative_to(out_dir).as_posix()
        reconstructed_rows.append(reconstructed_case_row(bundle, relative_input))

        print(f"[{index:02d}/{FORMAL_EXACT_CASES}] auditing {bundle.instance_id}", flush=True)
        summary, layers = audit_case(bundle, formal_optima[bundle.instance_id])
        summaries.append(summary)
        all_layers.extend(layers)

    write_csv(
        out_dir / "reconstructed_case_manifest.csv",
        sorted(reconstructed_rows, key=lambda row: row["instance_id"]),
        CASE_FIELDS,
    )
    write_csv(out_dir / "exact_suite_audit.csv", summaries, SUMMARY_FIELDS)
    write_csv(out_dir / "exact_dp_layers.csv", all_layers, LAYER_FIELDS)

    aggregate = {
        "cases": len(summaries),
        "core_cases": sum(row["scenario"] == "tiny-exact" for row in summaries),
        "wider_cases": sum(row["scenario"] == "tiny-widebeam" for row in summaries),
        "all_optima_match": all(row["optimum_match"] for row in summaries),
        "beam_plans": sum(row["beam_plans"] for row in summaries),
        "resource_layers": sum(row["resource_layers"] for row in summaries),
        "resource_choice_vectors": sum(
            row["resource_choice_vectors"] for row in summaries
        ),
        "transition_attempts": sum(row["transition_attempts"] for row in summaries),
        "unique_pre_prune_states": sum(
            row["unique_pre_prune_states"] for row in summaries
        ),
        "duplicates_collapsed": sum(
            row["duplicates_collapsed"] for row in summaries
        ),
        "dominated_removed": sum(row["dominated_removed"] for row in summaries),
        "retained_frontier_states": sum(
            row["retained_frontier_states"] for row in summaries
        ),
        "peak_pre_prune_states": max(
            row["peak_pre_prune_states"] for row in summaries
        ),
        "peak_frontier_states": max(row["peak_frontier_states"] for row in summaries),
    }
    if aggregate["transition_attempts"] != (
        aggregate["unique_pre_prune_states"] + aggregate["duplicates_collapsed"]
    ):
        raise AssertionError("suite-level transition accounting identity failed")
    if aggregate["unique_pre_prune_states"] != (
        aggregate["dominated_removed"] + aggregate["retained_frontier_states"]
    ):
        raise AssertionError("suite-level pruning accounting identity failed")

    audit_manifest = {
        "schema_version": 1,
        "audit": "independent-instrumented-exact-suite-dp",
        "formal_generator": {
            "path": "experiments/paper_experiments.py",
            "entry_point_used_for_reconstruction": "exact_bundles",
            "exact_solver_functions_used": [],
            "hash_gated_before_import": True,
        },
        "formal_seed_protocol": formal_manifest["exact_seed_protocol"],
        "hash_gate": hash_gate,
        "definitions": {
            "transition_attempts": (
                "sum over resource layers of frontier_before times distinct "
                "resource choice vectors"
            ),
            "unique_pre_prune_states": (
                "distinct clipped accumulated-capacity states after all transitions "
                "of a resource layer and before dominance pruning"
            ),
            "duplicates_collapsed": (
                "transition attempts mapping to a pre-prune state already generated "
                "within the same resource layer"
            ),
            "dominated_removed": (
                "unique pre-prune states removed because another state is "
                "component-wise no smaller"
            ),
            "retained_frontier_states": (
                "sum of post-prune component-wise maximal states over all resource layers"
            ),
            "peak_frontier_states": (
                "largest post-prune frontier at any resource layer"
            ),
            "optimum": "maximum sum of clipped per-user capacities over all beam plans",
        },
        "accounting_identities": {
            "transition_attempts": (
                "unique_pre_prune_states + duplicates_collapsed"
            ),
            "unique_pre_prune_states": (
                "dominated_removed + retained_frontier_states"
            ),
            "asserted_at": ["every resource layer", "every case", "whole suite"],
        },
        "aggregate": aggregate,
        "cases": summaries,
        "outputs": {
            "case_summary": "exact_suite_audit.csv",
            "resource_layer_trace": "exact_dp_layers.csv",
            "reconstructed_case_manifest": "reconstructed_case_manifest.csv",
            "reconstructed_inputs": "inputs/*.in",
        },
    }
    (out_dir / "audit_manifest.json").write_text(
        json.dumps(audit_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_checksums(out_dir)
    checksum_count = verify_written_checksums(out_dir)

    print(
        "audit complete: "
        f"{aggregate['cases']} cases, {aggregate['beam_plans']} beam plans, "
        f"{aggregate['transition_attempts']} transition attempts, "
        f"{checksum_count} checksum-bound files",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
