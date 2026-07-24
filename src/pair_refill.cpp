#include "core.h"

// Legacy pair-refill entry point; use scheduler.cpp for new experiments.
int main(int argc, char** argv) {
    return runPipelineMain(argc, argv, PipelineStage::Full);
}
