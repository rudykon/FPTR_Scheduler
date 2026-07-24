#include "core.h"

// Base plus global marginal-gain allocation.
int main(int argc, char** argv) {
    return runPipelineMain(argc, argv, PipelineStage::Global);
}
