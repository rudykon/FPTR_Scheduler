#include "core.h"

// Base plus global and compatibility-group-focused plans.
int main(int argc, char** argv) {
    return runPipelineMain(argc, argv, PipelineStage::CompatibilityGroups);
}
