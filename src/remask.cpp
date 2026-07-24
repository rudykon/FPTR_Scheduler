#include "core.h"

// Base plus global, compatibility-group plans, and remasking.
int main(int argc, char** argv) {
    return runPipelineMain(argc, argv, PipelineStage::Remask);
}
