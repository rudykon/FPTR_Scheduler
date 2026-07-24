# Project Overview

## Objective

FPTR is a single-threaded heuristic scheduler for a discrete wireless allocation snapshot with finite user buffers, stepwise link adaptation, a global beam budget, per-subband beam masks, explicit one- or two-subband resource memberships, and compatibility-group constraints on multi-user sharing.

This public repository contains implementation and reproducibility code only. The manuscript, compiled PDFs, third-party literature, and sealed evaluation artifacts are not included.

## Scheduler design

FPTR separates a releasable feasible incumbent from private refinement candidates. The empty allocation is an unconditional fallback. Base seeks a useful feasible incumbent, and optional Global, CG, Remask, and Pair refinements target different residual structures.

A private candidate replaces the incumbent only if it:

1. is complete;
2. finishes before its stage cutoff;
3. passes the structural validator; and
4. strictly improves transmitted traffic.

Rejected, expired, incomplete, or infeasible candidates cannot modify the incumbent. The term *transactional* refers only to this whole-candidate commit-or-discard behavior.

## Exact local primitive

For fixed beam masks, one resource, accumulated user capacities, one compatibility group, and sharing cardinality `s`, the exact size-`s` subset is obtained by selecting the `s` largest buffer-aware marginal gains. Scanning fixed cardinalities avoids exponential subset enumeration.

## Main components

- `src/core.cpp` and `src/core.h`: parser, model, objective, validation, and cumulative scheduler implementation;
- `src/scheduler.cpp`: command-line entry point;
- `src/beam_first.cpp`, `baseline_sequential.cpp`, `global_greedy.cpp`, `compatibility_groups.cpp`, `remask.cpp`, and `pair_refill.cpp`: reference-stage wrappers;
- `tools/scheduler_validator.py`: independent Python contract implementation;
- `experiments/paper_experiments.py`: deterministic scenario generation and process-level experiment harness;
- `experiments/analyze_results.py`: paired and within-run trace analysis;
- `experiments/plot_*.py`: architecture and quantitative plotting workflows;
- `tests/`: contract and end-to-end regression coverage.

## Public-release boundary

Performance claims should be evaluated using newly generated artifacts or separately supplied sealed evidence. Scripts that retain historical `paper/...` defaults must be invoked with explicit input/output paths in this code-only release.
