#include "core.h"

// Single aggregate beam plan plus sequential allocation.
int main(int argc, char** argv) {
    return runPipelineMain(argc, argv, PipelineStage::BeamFirst);
}
