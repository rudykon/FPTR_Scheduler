#define main external_alns_reference_entrypoint
#include "external_alns_baseline.cpp"
#undef main

#include <deque>
#include <unordered_map>

namespace external_meta {

using external_alns::Clock;
using external_alns::Options;
using external_alns::Problem;
using external_alns::RateTable;
using external_alns::Solution;
using external_alns::TimePoint;

bool expired(const TimePoint& deadline) {
    return Clock::now() >= deadline;
}

uint64_t solutionKey(const Solution& solution) {
    uint64_t hash = 1469598103934665603ULL;
    auto mix = [&hash](uint64_t value) {
        hash ^= value;
        hash *= 1099511628211ULL;
    };
    for (uint32_t mask : solution.masks) mix(mask);
    for (const auto& users : solution.resourceUsers) {
        mix(users.size());
        for (int user : users) mix(static_cast<uint64_t>(user));
    }
    return hash;
}

Solution randomSolution(const Problem& problem, std::mt19937_64& rng, bool dense,
                        double greediness) {
    Solution seed = external_alns::emptySolution(problem);
    const std::vector<uint32_t> masks = external_alns::randomMasks(problem, rng, dense);
    return external_alns::randomizedRecreate(problem, masks, std::move(seed), rng, greediness);
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
        0.25 + 0.20 * static_cast<double>(mode % 3));
}

Solution runTabu(const Problem& problem, const Options& options,
                 const TimePoint& started) {
    const int reserveMs = options.budgetMs >= 40 ? 2 : 1;
    const TimePoint deadline = started + std::chrono::milliseconds(
        std::max(1, options.budgetMs - reserveMs));
    std::mt19937_64 rng(options.seed ^ 0x544142555F534541ULL);

    Solution best = external_alns::emptySolution(problem);
    Solution current = randomSolution(problem, rng, true, 0.10);
    if (current.score > best.score) best = current;

    std::deque<uint64_t> tabuQueue;
    std::unordered_map<uint64_t, int> tabuUntil;
    int iteration = 0;
    int accepted = 0;
    constexpr int kNeighbourCount = 5;
    constexpr int kTabuTenure = 8;

    while (!expired(deadline)) {
        Solution chosen;
        int chosenScore = std::numeric_limits<int>::min();
        uint64_t chosenKey = 0;
        bool found = false;
        bool foundAspiration = false;

        for (int index = 0; index < kNeighbourCount && !expired(deadline); ++index) {
            const int mode = (iteration + index) % 4;
            Solution candidate = neighbour(problem, current, mode, rng);
            if (!external_alns::structurallyValid(problem, candidate)) continue;
            const uint64_t key = solutionKey(candidate);
            const auto tabu = tabuUntil.find(key);
            const bool isTabu = tabu != tabuUntil.end() && tabu->second > iteration;
            const bool aspiration = candidate.score > best.score;
            if (isTabu && !aspiration) continue;
            if (!found || candidate.score > chosenScore ||
                (candidate.score == chosenScore && aspiration && !foundAspiration)) {
                chosen = std::move(candidate);
                chosenScore = chosen.score;
                chosenKey = key;
                found = true;
                foundAspiration = aspiration;
            }
        }

        if (!found) break;
        current = std::move(chosen);
        ++accepted;
        tabuUntil[chosenKey] = iteration + kTabuTenure +
                                static_cast<int>(rng() % 4ULL);
        tabuQueue.push_back(chosenKey);
        while (tabuQueue.size() > 32) {
            const uint64_t old = tabuQueue.front();
            tabuQueue.pop_front();
            auto it = tabuUntil.find(old);
            if (it != tabuUntil.end() && it->second <= iteration) tabuUntil.erase(it);
        }
        if (current.score > best.score) best = current;
        ++iteration;
    }

    if (options.trace) {
        const double elapsed =
            std::chrono::duration<double, std::milli>(Clock::now() - started).count();
        std::cerr << "TRACE external=tabu score=" << best.score
                  << " elapsed_ms=" << elapsed << " iterations=" << iteration
                  << " accepted=" << accepted << '\n';
    }
    return external_alns::structurallyValid(problem, best) ? best
                                                            : external_alns::emptySolution(problem);
}

int tournament(const std::vector<Solution>& population, std::mt19937_64& rng) {
    std::uniform_int_distribution<int> pick(0, static_cast<int>(population.size()) - 1);
    int selected = pick(rng);
    for (int round = 0; round < 2; ++round) {
        const int candidate = pick(rng);
        if (population[candidate].score > population[selected].score) selected = candidate;
    }
    return selected;
}

Solution childOf(const Problem& problem, const Solution& first, const Solution& second,
                 std::mt19937_64& rng) {
    Solution child = external_alns::emptySolution(problem);
    std::uniform_int_distribution<int> parent(0, 1);
    for (int band = 1; band <= problem.T; ++band) {
        child.masks[band] = parent(rng) == 0 ? first.masks[band] : second.masks[band];
    }
    if (rng() % 100ULL < 35ULL) {
        external_alns::mutateMasks(problem, child.masks,
                                    static_cast<int>(rng() % 4ULL), rng);
    }
    external_alns::normalizeBudget(problem, child.masks, rng);
    const std::vector<uint32_t> masks = child.masks;
    return external_alns::randomizedRecreate(problem, masks, std::move(child), rng, 0.35);
}

Solution runGenetic(const Problem& problem, const Options& options,
                    const TimePoint& started) {
    const int reserveMs = options.budgetMs >= 40 ? 2 : 1;
    const TimePoint deadline = started + std::chrono::milliseconds(
        std::max(1, options.budgetMs - reserveMs));
    std::mt19937_64 rng(options.seed ^ 0x47454E455449435FULL);
    constexpr int kPopulationSize = 7;

    std::vector<Solution> population;
    population.reserve(kPopulationSize);
    for (int index = 0; index < kPopulationSize && !expired(deadline); ++index) {
        population.push_back(randomSolution(problem, rng, index < 2, 0.15 + 0.08 * index));
    }
    if (population.empty()) return external_alns::emptySolution(problem);

    Solution best = population.front();
    for (const Solution& candidate : population) {
        if (candidate.score > best.score) best = candidate;
    }

    int generation = 0;
    int offspring = 0;
    while (!expired(deadline)) {
        std::sort(population.begin(), population.end(),
                  [](const Solution& left, const Solution& right) {
                      return left.score > right.score;
                  });
        if (population.front().score > best.score) best = population.front();

        std::vector<Solution> next;
        next.reserve(kPopulationSize);
        next.push_back(population.front());
        while (static_cast<int>(next.size()) < kPopulationSize && !expired(deadline)) {
            const int first = tournament(population, rng);
            const int second = tournament(population, rng);
            Solution child = childOf(problem, population[first], population[second], rng);
            if (external_alns::structurallyValid(problem, child)) {
                if (child.score > best.score) best = child;
                next.push_back(std::move(child));
                ++offspring;
            }
        }
        if (next.size() == 1) break;
        population = std::move(next);
        ++generation;
    }

    if (options.trace) {
        const double elapsed =
            std::chrono::duration<double, std::milli>(Clock::now() - started).count();
        std::cerr << "TRACE external=ga score=" << best.score
                  << " elapsed_ms=" << elapsed << " iterations=" << generation
                  << " accepted=" << offspring << '\n';
    }
    return external_alns::structurallyValid(problem, best) ? best
                                                            : external_alns::emptySolution(problem);
}

}  // namespace external_meta

int main(int argc, char** argv) {
    external_alns::Options options;
    std::string method = "tabu";
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--help" || argument == "-h") {
            std::cout << "usage: external_tabu_ga [--method tabu|ga] [--budget-ms N] "
                         "[--seed N] [--trace]\n";
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
    if (method == "tabu" || method == "ts") {
        solution = external_meta::runTabu(problem, options, started);
    } else if (method == "ga") {
        solution = external_meta::runGenetic(problem, options, started);
    } else {
        std::cerr << "unknown method: " << method << '\n';
        return 2;
    }
    external_alns::outputSolution(problem, solution);
    return 0;
}
