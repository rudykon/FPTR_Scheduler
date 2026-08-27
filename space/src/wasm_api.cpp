#include "core.h"

#ifdef __EMSCRIPTEN__

#include <emscripten/emscripten.h>

#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {

PipelineStage parseStage(const std::string& value) {
    if (value == "beamfirst" || value == "beam-first" || value == "beam_first") {
        return PipelineStage::BeamFirst;
    }
    if (value == "base") return PipelineStage::Base;
    if (value == "global") return PipelineStage::Global;
    if (value == "cg") return PipelineStage::CompatibilityGroups;
    if (value == "remask") return PipelineStage::Remask;
    if (value == "full") return PipelineStage::Full;
    throw std::invalid_argument("unknown pipeline stage");
}

std::string jsonEscape(const std::string& value) {
    std::ostringstream escaped;
    escaped << '"';
    for (unsigned char character : value) {
        switch (character) {
            case '"': escaped << "\\\""; break;
            case '\\': escaped << "\\\\"; break;
            case '\b': escaped << "\\b"; break;
            case '\f': escaped << "\\f"; break;
            case '\n': escaped << "\\n"; break;
            case '\r': escaped << "\\r"; break;
            case '\t': escaped << "\\t"; break;
            default:
                if (character < 0x20) {
                    escaped << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                            << static_cast<int>(character) << std::dec;
                } else {
                    escaped << character;
                }
        }
    }
    escaped << '"';
    return escaped.str();
}

class StreamRedirect {
public:
    explicit StreamRedirect(const std::string& input) : input_(input) {
        cinBuffer_ = std::cin.rdbuf(input_.rdbuf());
        coutBuffer_ = std::cout.rdbuf(output_.rdbuf());
        cerrBuffer_ = std::cerr.rdbuf(trace_.rdbuf());
        std::cin.clear();
        std::cout.clear();
        std::cerr.clear();
    }

    ~StreamRedirect() {
        std::cout.flush();
        std::cerr.flush();
        std::cin.rdbuf(cinBuffer_);
        std::cout.rdbuf(coutBuffer_);
        std::cerr.rdbuf(cerrBuffer_);
        std::cin.clear();
        std::cout.clear();
        std::cerr.clear();
    }

    std::string output() const { return output_.str(); }
    std::string trace() const { return trace_.str(); }

private:
    std::istringstream input_;
    std::ostringstream output_;
    std::ostringstream trace_;
    std::streambuf* cinBuffer_ = nullptr;
    std::streambuf* coutBuffer_ = nullptr;
    std::streambuf* cerrBuffer_ = nullptr;
};

}  // namespace

extern "C" {

EMSCRIPTEN_KEEPALIVE const char* fptr_run(const char* input, const char* stage,
                                         int budgetMs) {
    static std::string response;
    try {
        if (input == nullptr || stage == nullptr) {
            throw std::invalid_argument("input and stage are required");
        }
        if (budgetMs < 5 || budgetMs > 2000) {
            throw std::invalid_argument("budget must lie in 5..2000 ms");
        }

        SolverOptions options;
        options.stage = parseStage(stage);
        options.budgetMs = budgetMs;
        options.trace = true;

        std::string output;
        std::string trace;
        {
            StreamRedirect streams(input);
            solvePipeline(options);
            output = streams.output();
            trace = streams.trace();
        }
        if (output.empty()) {
            throw std::runtime_error("scheduler produced no output; check the input contract");
        }
        response = "{\"ok\":true,\"output\":" + jsonEscape(output) +
                   ",\"trace\":" + jsonEscape(trace) + "}";
    } catch (const std::exception& error) {
        response = "{\"ok\":false,\"error\":" + jsonEscape(error.what()) + "}";
    } catch (...) {
        response = "{\"ok\":false,\"error\":\"unknown scheduler failure\"}";
    }
    return response.c_str();
}

}  // extern "C"

#endif
