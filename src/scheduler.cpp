#include "core.h"

// Full cumulative pipeline including pair ruin-and-refill.
int main(int argc, char** argv) {
    return runPipelineMain(argc, argv, PipelineStage::Full);
}
