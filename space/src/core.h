#ifndef SCHEDULER_CORE_H
#define SCHEDULER_CORE_H

enum class PipelineStage {
    BeamFirst = 0,
    Base = 1,
    Global = 2,
    CompatibilityGroups = 3,
    Remask = 4,
    Full = 5,
};

struct SolverOptions {
    PipelineStage stage = PipelineStage::Base;
    int budgetMs = 87;
    bool trace = false;
};

void solve();
void solvePipeline(const SolverOptions& options);
int runPipelineMain(int argc, char** argv, PipelineStage defaultStage);

#endif
