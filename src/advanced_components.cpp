#include "core.h"

// Legacy compatibility-group-stage entry point.
int main(int argc, char** argv) {
    return runPipelineMain(argc, argv, PipelineStage::CompatibilityGroups);
}
