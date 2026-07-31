# Scheduler Source

The academic implementation is single-threaded C++17. All reported variants call the same cumulative FPTR pipeline in `core.cpp`.

- `beam_first.cpp`: external simple baseline (one aggregate beam plan plus sequential allocation).
- `baseline_sequential.cpp`: Base, which constructs a useful feasible incumbent.
- `global_greedy.cpp`: adds buffer-aware marginal repricing (Global).
- `compatibility_groups.cpp`: adds CG-constrained sharing (CG).
- `remask.cpp`: adds demand-driven mask repair and bounded one-resource repair.
- `scheduler.cpp`: Full, adding two-resource ruin-and-recreate (Pair).
- `pair_refill.cpp` and `advanced_components.cpp`: legacy compatibility wrappers; new FPTR experiments should use the six entry points above.
- `external_alns_baseline.cpp`: independent adaptive large-neighborhood search (ALNS) reference.
- `external_tabu_ga_baseline.cpp`: independent tabu-search and genetic-algorithm (GA) references.
- `external_sa_ils_grasp.cpp`: independent simulated-annealing (SA), iterated-local-search (ILS), and GRASP references.

The empty allocation is the unconditional feasible fallback. Global and CG improve buffer- and sharing-aware marginal utility; Remask and Pair perform bounded local reconstruction. The cross-stage commit-or-discard gate is not another search stage: each candidate is built in isolated state and replaces the releasable incumbent only when complete, timely, constraint-valid, and strictly improving.

Compile an entry point with g++ `-std=c++17 -O2`, for example:

```bash
g++ -std=c++17 -O2 src/scheduler.cpp src/core.cpp -o scheduler
```

Every entry point accepts `--budget-ms N`, `--trace`, and an optional stage override:

```bash
./scheduler --stage beamfirst|base|global|cg|remask|full --budget-ms 87 --trace
```

Trace records go only to stderr; the allocation contract on stdout is unchanged. External references use the same contract and are selected with `--method` where applicable, for example:

```bash
g++ -std=c++17 -O2 src/external_sa_ils_grasp.cpp -o external_sa_ils_grasp
./external_sa_ils_grasp --method sa --budget-ms 87 --seed 1 --trace
```
