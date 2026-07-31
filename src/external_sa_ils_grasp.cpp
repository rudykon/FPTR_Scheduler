// Independent simulated-annealing, iterated-local-search, and GRASP baselines.
//
// The search routines use the same public input/output contract as the other
// external references, but do not call FPTR's scheduler or refinement stages.
// Outputs are reparsed and scored by tools/scheduler_validator.py.

#define main external_alns_reference_entrypoint
#include "external_alns_baseline.cpp"
#undef main

#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <random>
#include <string>

namespace external_extra {

using external_alns::Clock;
using external_alns::Options;
using external_alns::Problem;
using external_alns::Solution;
using external_alns::TimePoint;

bool expired(const TimePoint& deadline) {
    return Clock::now() >= deadline;
}

Solution randomizedSolution(const Problem& problem, std::mt19937_64& rng,
                            bool dense, double greediness) {
    Solution seed = external_alns::emptySolution(problem);
    const std::vector<uint32_t> masks = external_alns::randomMasks(problem, rng, dense);
    return external_alns::randomizedRecreate(
        problem, masks, std::move(seed), rng, greediness);
}

Solution neighbour(const Problem& problem, const Solution& current, int mode,
                   std::mt19937_64& rng) {
    Solution candidate = current;
    if (mode == 0) {
        external_alns::destroyResources(problem, candidate, 0, rng);
        external_alns::mutateMasks(problem, candidate.masks, 0, rng);
    } else if (mode == 1) {
        external_alns::destroyResources(problem, candidate, 1, rng);
        external_alns::mutateMasks(problem, candidate.masks, 1, rng);
    } else if (mode == 2) {
        external_alns::destroyResources(problem, candidate, 0, rng);
        external_alns::mutateMasks(problem, candidate.masks, 2, rng);
    } else {
        candidate.masks = external_alns::randomMasks(problem, rng, false);
        candidate.resourceUsers.assign(problem.K + 1, {});
    }
    const std::vector<uint32_t> masks = candidate.masks;
    return external_alns::randomizedRecreate(
        problem, masks, std::move(candidate), rng,
        0.20 + 0.20 * static_cast<double>(mode % 4));
}

TimePoint searchDeadline(const Options& options, const TimePoint& started) {
    const int reserve_ms = options.budgetMs >= 40 ? 2 : 1;
    return started + std::chrono::milliseconds(
        std::max(1, options.budgetMs - reserve_ms));
}

void trace(const Options& options, const char* name, int score,
           const TimePoint& started, int iterations, int accepted) {
    if (!options.trace) return;
    const double elapsed =
        std::chrono::duration<double, std::milli>(Clock::now() - started).count();
    std::cerr << "TRACE external=" << name << " score=" << score
              << " elapsed_ms=" << elapsed << " iterations=" << iterations
              << " accepted=" << accepted << '\n';
}

Solution runSimulatedAnnealing(const Problem& problem, const Options& options,
                               const TimePoint& started) {
    const TimePoint deadline = searchDeadline(options, started);
    std::mt19937_64 rng(options.seed ^ 0x53494D554C415445ULL);
    Solution current = randomizedSolution(problem, rng, true, 0.12);
    Solution best = current;
    int iterations = 0;
    int accepted = 0;

    while (!expired(deadline)) {
        const int mode = iterations % 4;
        Solution candidate = neighbour(problem, current, mode, rng);
        if (!external_alns::structurallyValid(problem, candidate)) break;

        const double elapsed_fraction = std::min(
            1.0, std::chrono::duration<double>(Clock::now() - started).count() /
                     std::max(0.001, options.budgetMs / 1000.0));
        const double temperature =
            std::max(1.0, 260.0 * (1.0 - elapsed_fraction) + 4.0);
        const int delta = candidate.score - current.score;
        bool accept = delta >= 0;
        if (!accept) {
            const double probability = std::exp(static_cast<double>(delta) / temperature);
            std::uniform_real_distribution<double> coin(0.0, 1.0);
            accept = coin(rng) < probability;
        }
        if (candidate.score > best.score) best = candidate;
        if (accept) {
            current = std::move(candidate);
            ++accepted;
        }
        ++iterations;
    }

    trace(options, "sa", best.score, started, iterations, accepted);
    return external_alns::structurallyValid(problem, best)
               ? best
               : external_alns::emptySolution(problem);
}

Solution runIteratedLocalSearch(const Problem& problem, const Options& options,
                                const TimePoint& started) {
    const TimePoint deadline = searchDeadline(options, started);
    std::mt19937_64 rng(options.seed ^ 0x494C535F42415345ULL);
    Solution current = randomizedSolution(problem, rng, true, 0.10);
    Solution best = current;
    int iterations = 0;
    int accepted = 0;
    int stagnation = 0;

    while (!expired(deadline)) {
        Solution local = current;
        bool improved = false;
        for (int pass = 0; pass < 2 && !expired(deadline); ++pass) {
            Solution candidate = neighbour(problem, local, (iterations + pass) % 3, rng);
            if (!external_alns::structurallyValid(problem, candidate)) continue;
            if (candidate.score > local.score) {
                local = std::move(candidate);
                improved = true;
            }
        }

        if (local.score >= current.score) {
            current = std::move(local);
            ++accepted;
            stagnation = improved ? 0 : stagnation + 1;
        } else {
            ++stagnation;
        }
        if (current.score > best.score) best = current;

        if (stagnation >= 6) {
            // Perturb the incumbent; periodic restarts prevent one basin from
            // monopolizing the entire short execution window.
            if ((iterations & 1) == 0) {
                current = randomizedSolution(problem, rng, false, 0.35);
            } else {
                current = neighbour(problem, best, 3, rng);
            }
            if (current.score > best.score) best = current;
            stagnation = 0;
            ++accepted;
        }
        ++iterations;
    }

    trace(options, "ils", best.score, started, iterations, accepted);
    return external_alns::structurallyValid(problem, best)
               ? best
               : external_alns::emptySolution(problem);
}

Solution runGrasp(const Problem& problem, const Options& options,
                  const TimePoint& started) {
    const TimePoint deadline = searchDeadline(options, started);
    std::mt19937_64 rng(options.seed ^ 0x47524153505F4241ULL);
    Solution best = external_alns::emptySolution(problem);
    int iterations = 0;
    int accepted = 0;

    while (!expired(deadline)) {
        const bool dense = (rng() & 1ULL) != 0;
        const double greediness = 0.05 +
            0.70 * static_cast<double>(rng() % 1000ULL) / 999.0;
        Solution candidate = randomizedSolution(problem, rng, dense, greediness);
        if (!external_alns::structurallyValid(problem, candidate)) break;
        if (candidate.score > best.score) {
            best = candidate;
            ++accepted;
        }

        // GRASP's local-search phase uses one bounded repair after each
        // randomized construction, without importing FPTR's transactional gate.
        if (!expired(deadline)) {
            Solution refined = neighbour(problem, candidate, iterations % 3, rng);
            if (external_alns::structurallyValid(problem, refined) &&
                refined.score > best.score) {
                best = std::move(refined);
                ++accepted;
            }
        }
        ++iterations;
    }

    trace(options, "grasp", best.score, started, iterations, accepted);
    return external_alns::structurallyValid(problem, best)
               ? best
               : external_alns::emptySolution(problem);
}

}  // namespace external_extra

int main(int argc, char** argv) {
    external_alns::Options options;
    std::string method = "sa";
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--help" || argument == "-h") {
            std::cout << "usage: external_sa_ils_grasp --method sa|ils|grasp "
                         "[--budget-ms N] [--seed N] [--trace]\n";
            return 0;
        }
        if (argument == "--trace") {
            options.trace = true;
        } else if (argument == "--method" && index + 1 < argc) {
            method = argv[++index];
        } else if (argument.rfind("--method=", 0) == 0) {
            method = argument.substr(9);
        } else if (argument == "--budget-ms" && index + 1 < argc) {
            try {
                options.budgetMs = std::stoi(argv[++index]);
            } catch (...) {
                return 2;
            }
        } else if (argument.rfind("--budget-ms=", 0) == 0) {
            try {
                options.budgetMs = std::stoi(argument.substr(12));
            } catch (...) {
                return 2;
            }
        } else if (argument == "--seed" && index + 1 < argc) {
            try {
                options.seed = std::stoull(argv[++index]);
            } catch (...) {
                return 2;
            }
        } else if (argument.rfind("--seed=", 0) == 0) {
            try {
                options.seed = std::stoull(argument.substr(7));
            } catch (...) {
                return 2;
            }
        } else {
            std::cerr << "unknown option: " << argument << '\n';
            return 2;
        }
    }
    options.budgetMs = std::max(5, std::min(10000, options.budgetMs));
    const external_alns::TimePoint started = external_alns::Clock::now();
    external_alns::Problem problem;
    if (!external_alns::readProblem(problem)) return 0;

    external_alns::Solution solution;
    if (method == "sa" || method == "simulated-annealing") {
        solution = external_extra::runSimulatedAnnealing(problem, options, started);
    } else if (method == "ils" || method == "iterated-local-search") {
        solution = external_extra::runIteratedLocalSearch(problem, options, started);
    } else if (method == "grasp") {
        solution = external_extra::runGrasp(problem, options, started);
    } else {
        std::cerr << "unknown method: " << method << '\n';
        return 2;
    }
    external_alns::outputSolution(problem, solution);
    return 0;
}
