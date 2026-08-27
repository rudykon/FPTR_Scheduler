#define FPTR_EXTERNAL_NO_MAIN
#include "../../src/external_alns_baseline.cpp"
#include "../../src/external_tabu_ga_baseline.cpp"
#include "../../src/external_sa_ils_grasp.cpp"
#undef FPTR_EXTERNAL_NO_MAIN

#ifdef __EMSCRIPTEN__
#include <emscripten/emscripten.h>
#define FPTR_KEEPALIVE EMSCRIPTEN_KEEPALIVE
#else
#define FPTR_KEEPALIVE
#endif

#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {

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

external_alns::Solution runMethod(const std::string& method,
                                  const external_alns::Problem& problem,
                                  const external_alns::Options& options,
                                  const external_alns::TimePoint& started) {
    if (method == "alns") return external_alns::runAlns(problem, options, started);
    if (method == "tabu") return external_meta::runTabu(problem, options, started);
    if (method == "ga") return external_meta::runGenetic(problem, options, started);
    if (method == "sa") {
        return external_extra::runSimulatedAnnealing(problem, options, started);
    }
    if (method == "ils") {
        return external_extra::runIteratedLocalSearch(problem, options, started);
    }
    if (method == "grasp") return external_extra::runGrasp(problem, options, started);
    throw std::invalid_argument("unknown external baseline");
}

}  // namespace

extern "C" {

FPTR_KEEPALIVE const char* fptr_baseline_run(const char* input, const char* method,
                                             int budgetMs, int seed) {
    static std::string response;
    try {
        if (input == nullptr || method == nullptr) {
            throw std::invalid_argument("input and method are required");
        }
        if (budgetMs < 5 || budgetMs > 2000) {
            throw std::invalid_argument("budget must lie in 5..2000 ms");
        }

        external_alns::Options options;
        options.budgetMs = budgetMs;
        options.seed = static_cast<uint64_t>(static_cast<uint32_t>(seed));
        options.trace = true;

        std::string output;
        std::string trace;
        {
            StreamRedirect streams(input);
            const external_alns::TimePoint started = external_alns::Clock::now();
            external_alns::Problem problem;
            if (!external_alns::readProblem(problem)) {
                throw std::invalid_argument("input does not satisfy the scheduler contract");
            }
            const external_alns::Solution solution =
                runMethod(method, problem, options, started);
            external_alns::outputSolution(problem, solution);
            output = streams.output();
            trace = streams.trace();
        }
        if (output.empty()) {
            throw std::runtime_error("baseline produced no output");
        }
        response = "{\"ok\":true,\"output\":" + jsonEscape(output) +
                   ",\"trace\":" + jsonEscape(trace) + "}";
    } catch (const std::exception& error) {
        response = "{\"ok\":false,\"error\":" + jsonEscape(error.what()) + "}";
    } catch (...) {
        response = "{\"ok\":false,\"error\":\"unknown baseline failure\"}";
    }
    return response.c_str();
}

}  // extern "C"
