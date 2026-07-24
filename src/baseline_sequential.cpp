#include "core.h"

// Cumulative base stage.
int main(int argc, char** argv) {
    return runPipelineMain(argc, argv, PipelineStage::Base);
}
