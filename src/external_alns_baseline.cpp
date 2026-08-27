// Independent adaptive large-neighborhood search (ALNS) baseline.
//
// This implementation deliberately does not call the FPTR code in core.cpp.
// It uses the same input/output contract and objective, but searches with
// randomized destroy/recreate neighborhoods and simulated-annealing
// acceptance. Final outputs are checked by tools/scheduler_validator.py.

#ifndef FPTR_EXTERNAL_ALNS_BASELINE_IMPLEMENTATION
#define FPTR_EXTERNAL_ALNS_BASELINE_IMPLEMENTATION

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <string>
#include <utility>
#include <vector>

namespace external_alns {

using Clock = std::chrono::steady_clock;
using TimePoint = Clock::time_point;

constexpr int kMaxShare = 20;

struct Problem {
    int P = 0;
    int N = 0;
    int K = 0;
    int T = 0;
    int beamMaxNum = 0;
    int M = 0;
    std::vector<std::vector<int>> groups;
    std::vector<int> groupId;
    std::vector<std::vector<double>> cap;
    std::vector<double> totalCap;
    std::vector<int> buffer;
    std::vector<double> sinr;
    std::vector<std::vector<int>> resourceBands;
};

struct Solution {
    int score = 0;
    std::vector<uint32_t> masks;
    std::vector<std::vector<int>> resourceUsers;
};

struct Choice {
    int gain = 0;
    std::vector<int> users;
};

struct RateTable {
    int K = 0;
    int N = 0;
    std::vector<int> values;

    RateTable() = default;
    RateTable(int resourceCount, int userCount)
        : K(resourceCount), N(userCount),
          values(static_cast<size_t>(resourceCount + 1) * (kMaxShare + 1) *
                 (userCount + 1), 0) {}

    int& at(int resource, int share, int user) {
        return values[(static_cast<size_t>(resource) * (kMaxShare + 1) + share) *
                          (N + 1) + user];
    }

    int get(int resource, int share, int user) const {
        return values[(static_cast<size_t>(resource) * (kMaxShare + 1) + share) *
                          (N + 1) + user];
    }
};

struct Options {
    int budgetMs = 87;
    uint64_t seed = 1;
    bool trace = false;
};

bool expired(const TimePoint& deadline) {
    return Clock::now() >= deadline;
}

int rateOfFse(double fse) {
    if (fse <= -10.0) return 0;
    if (fse <= 0.0) return 8;
    if (fse <= 3.0) return 24;
    if (fse <= 10.0) return 90;
    if (fse <= 15.0) return 120;
    if (fse <= 20.0) return 162;
    return 222;
}

bool readCounted(int minimum, int maximum, int maxId, std::vector<int>& ids) {
    int count = 0;
    if (!(std::cin >> count) || count < minimum || count > maximum) return false;
    ids.assign(count, 0);
    std::vector<char> seen(static_cast<size_t>(maxId + 1), 0);
    for (int index = 0; index < count; ++index) {
        int id = 0;
        if (!(std::cin >> id) || id < 1 || id > maxId || seen[id]) return false;
        seen[id] = 1;
        ids[index] = id;
    }
    return true;
}

bool readProblem(Problem& problem) {
    if (!(std::cin >> problem.P >> problem.N >> problem.K >> problem.T >>
          problem.beamMaxNum)) {
        return false;
    }
    if (problem.P < 1 || problem.P > 32 || problem.N < 1 || problem.N > 100 ||
        problem.K < 2 || problem.K > 72 || problem.T < 1 || problem.T > 18 ||
        problem.beamMaxNum < 2 || problem.beamMaxNum > 255) {
        return false;
    }
    if (!(std::cin >> problem.M) || problem.M < 0 || problem.M > 16) return false;

    problem.groups.assign(problem.M, {});
    problem.groupId.assign(problem.N + 1, -1);
    for (int group = 0; group < problem.M; ++group) {
        if (!readCounted(2, 20, problem.N, problem.groups[group])) return false;
        for (int user : problem.groups[group]) {
            if (problem.groupId[user] != -1) return false;
            problem.groupId[user] = group;
        }
    }

    std::vector<int> singletonUsers;
    if (!readCounted(0, 29, problem.N, singletonUsers)) return false;
    for (int user : singletonUsers) {
        if (problem.groupId[user] != -1) return false;
    }

    problem.cap.assign(problem.N + 1, std::vector<double>(problem.P + 1, 0.0));
    problem.totalCap.assign(problem.N + 1, 0.0);
    for (int user = 1; user <= problem.N; ++user) {
        for (int beam = 1; beam <= problem.P; ++beam) {
            double value = 0.0;
            if (!(std::cin >> value) || !std::isfinite(value) || value <= 0.0 ||
                value > 65535.0) {
                return false;
            }
            problem.cap[user][beam] = value;
            problem.totalCap[user] += value;
        }
    }

    problem.buffer.assign(problem.N + 1, 0);
    problem.sinr.assign(problem.N + 1, 0.0);
    for (int user = 1; user <= problem.N; ++user) {
        if (!(std::cin >> problem.buffer[user] >> problem.sinr[user]) ||
            problem.buffer[user] < 1 || problem.buffer[user] > 10000 ||
            !std::isfinite(problem.sinr[user]) || problem.sinr[user] < -30.0 ||
            problem.sinr[user] > 100.0) {
            return false;
        }
    }

    problem.resourceBands.assign(problem.K + 1, {});
    for (int band = 1; band <= problem.T; ++band) {
        std::vector<int> resources;
        if (!readCounted(0, problem.K, problem.K, resources)) return false;
        for (int resource : resources) problem.resourceBands[resource].push_back(band);
    }
    for (int resource = 1; resource <= problem.K; ++resource) {
        if (problem.resourceBands[resource].size() < 1 ||
            problem.resourceBands[resource].size() > 2) {
            return false;
        }
    }
    return true;
}

int bitCount(uint32_t value) {
    return __builtin_popcount(value);
}

bool hasBeam(uint32_t mask, int beam) {
    return (mask & (uint32_t{1} << (beam - 1))) != 0;
}

int totalBeams(const std::vector<uint32_t>& masks) {
    int total = 0;
    for (size_t band = 1; band < masks.size(); ++band) total += bitCount(masks[band]);
    return total;
}

bool resourceEnabled(const Problem& problem, const std::vector<uint32_t>& masks,
                     int resource) {
    for (int band : problem.resourceBands[resource]) {
        if (masks[band] == 0) return false;
    }
    return true;
}

RateTable buildRates(const Problem& problem, const std::vector<uint32_t>& masks) {
    std::vector<std::vector<double>> selected(
        problem.T + 1, std::vector<double>(problem.N + 1, 0.0));
    for (int band = 1; band <= problem.T; ++band) {
        for (int beam = 1; beam <= problem.P; ++beam) {
            if (!hasBeam(masks[band], beam)) continue;
            for (int user = 1; user <= problem.N; ++user) {
                selected[band][user] += problem.cap[user][beam];
            }
        }
    }

    RateTable rates(problem.K, problem.N);
    for (int resource = 1; resource <= problem.K; ++resource) {
        const auto& bands = problem.resourceBands[resource];
        const double denominator = static_cast<double>(bands.back() - bands.front() + 1);
        for (int user = 1; user <= problem.N; ++user) {
            double selectedSum = 0.0;
            for (int band : bands) selectedSum += selected[band][user];
            const double average = selectedSum / denominator;
            if (average <= 0.0) continue;
            const double linkTerm = 10.0 * std::log10(average / problem.totalCap[user]);
            for (int share = 1; share <= kMaxShare; ++share) {
                const double fse = problem.sinr[user] +
                                   10.0 * std::log10(1.0 / share) + linkTerm;
                rates.at(resource, share, user) = rateOfFse(fse);
            }
        }
    }
    return rates;
}

std::vector<int> rawFromSolution(const Problem& problem, const RateTable& rates,
                                 const Solution& solution) {
    std::vector<int> raw(problem.N + 1, 0);
    for (int resource = 1; resource <= problem.K; ++resource) {
        const int share = static_cast<int>(solution.resourceUsers[resource].size());
        if (share == 0 || share > kMaxShare) continue;
        for (int user : solution.resourceUsers[resource]) {
            raw[user] += rates.get(resource, share, user);
        }
    }
    return raw;
}

int scoreFromRaw(const Problem& problem, const std::vector<int>& raw) {
    int score = 0;
    for (int user = 1; user <= problem.N; ++user) {
        score += std::min(problem.buffer[user], raw[user]);
    }
    return score;
}

int marginal(const Problem& problem, const RateTable& rates, int resource, int user,
             int share, const std::vector<int>& raw) {
    const int before = std::min(problem.buffer[user], raw[user]);
    const int after = std::min(problem.buffer[user], raw[user] +
                                               rates.get(resource, share, user));
    return after - before;
}

Choice bestChoice(const Problem& problem, const RateTable& rates, int resource,
                  const std::vector<int>& raw) {
    Choice best;
    for (int user = 1; user <= problem.N; ++user) {
        const int gain = marginal(problem, rates, resource, user, 1, raw);
        if (gain > best.gain ||
            (gain == best.gain && gain > 0 &&
             (best.users.empty() || user < best.users.front()))) {
            best.gain = gain;
            best.users = {user};
        }
    }

    for (const auto& group : problem.groups) {
        const int maxShare = std::min<int>(kMaxShare, group.size());
        for (int share = 2; share <= maxShare; ++share) {
            std::vector<std::pair<int, int>> values;
            values.reserve(group.size());
            for (int user : group) {
                const int gain = marginal(problem, rates, resource, user, share, raw);
                if (gain > 0) values.push_back({gain, user});
            }
            if (static_cast<int>(values.size()) < share) continue;
            std::sort(values.begin(), values.end(), [](const auto& left, const auto& right) {
                if (left.first != right.first) return left.first > right.first;
                return left.second < right.second;
            });
            Choice candidate;
            candidate.users.reserve(share);
            for (int index = 0; index < share; ++index) {
                candidate.gain += values[index].first;
                candidate.users.push_back(values[index].second);
            }
            std::sort(candidate.users.begin(), candidate.users.end());
            if (candidate.gain > best.gain ||
                (candidate.gain == best.gain && candidate.gain > 0 &&
                 (candidate.users.size() > best.users.size() ||
                  (candidate.users.size() == best.users.size() &&
                   candidate.users < best.users)))) {
                best = std::move(candidate);
            }
        }
    }
    return best;
}

Solution emptySolution(const Problem& problem) {
    Solution solution;
    solution.masks.assign(problem.T + 1, 0);
    solution.resourceUsers.assign(problem.K + 1, {});
    return solution;
}

void clearDisabledResources(const Problem& problem, Solution& solution) {
    for (int resource = 1; resource <= problem.K; ++resource) {
        if (!resourceEnabled(problem, solution.masks, resource)) {
            solution.resourceUsers[resource].clear();
        }
    }
}

Solution randomizedRecreate(const Problem& problem, const std::vector<uint32_t>& masks,
                            Solution seedSolution, std::mt19937_64& rng,
                            double greediness) {
    seedSolution.masks = masks;
    clearDisabledResources(problem, seedSolution);
    const RateTable rates = buildRates(problem, masks);
    std::vector<int> raw = rawFromSolution(problem, rates, seedSolution);
    std::vector<char> freeResource(problem.K + 1, 0);
    for (int resource = 1; resource <= problem.K; ++resource) {
        if (resourceEnabled(problem, masks, resource) &&
            seedSolution.resourceUsers[resource].empty()) {
            freeResource[resource] = 1;
        }
    }

    for (int step = 0; step < problem.K; ++step) {
        std::vector<std::pair<int, Choice>> choices;
        int bestGain = 0;
        int worstGain = std::numeric_limits<int>::max();
        for (int resource = 1; resource <= problem.K; ++resource) {
            if (!freeResource[resource]) continue;
            Choice choice = bestChoice(problem, rates, resource, raw);
            choices.push_back({resource, std::move(choice)});
            bestGain = std::max(bestGain, choices.back().second.gain);
            worstGain = std::min(worstGain, choices.back().second.gain);
        }
        if (choices.empty() || bestGain <= 0) break;
        if (worstGain == std::numeric_limits<int>::max()) worstGain = 0;
        const double threshold = static_cast<double>(bestGain) -
                                 greediness * static_cast<double>(bestGain - worstGain);
        std::vector<int> rcl;
        for (int index = 0; index < static_cast<int>(choices.size()); ++index) {
            if (choices[index].second.gain + 1e-9 >= threshold) rcl.push_back(index);
        }
        if (rcl.empty()) rcl.push_back(0);
        std::uniform_int_distribution<int> pick(0, static_cast<int>(rcl.size()) - 1);
        const auto& selected = choices[rcl[pick(rng)]];
        const int resource = selected.first;
        const Choice& choice = selected.second;
        freeResource[resource] = 0;
        if (choice.users.empty()) continue;
        const int share = static_cast<int>(choice.users.size());
        for (int user : choice.users) raw[user] += rates.get(resource, share, user);
        seedSolution.resourceUsers[resource] = choice.users;
    }
    seedSolution.score = scoreFromRaw(problem, raw);
    return seedSolution;
}

std::vector<uint32_t> randomMasks(const Problem& problem, std::mt19937_64& rng,
                                  bool dense) {
    std::vector<uint32_t> masks(problem.T + 1, 0);
    const int positionBudget = std::min(problem.beamMaxNum, problem.P * problem.T);
    const int lower = std::max(1, dense ? positionBudget * 3 / 4 : positionBudget / 3);
    std::uniform_int_distribution<int> targetDist(lower, positionBudget);
    const int target = targetDist(rng);
    const int usedBands = std::max(1, std::min(problem.T, target));
    std::vector<int> bands(problem.T);
    std::iota(bands.begin(), bands.end(), 1);
    std::shuffle(bands.begin(), bands.end(), rng);
    std::vector<int> counts(problem.T + 1, 0);
    for (int index = 0; index < usedBands; ++index) counts[bands[index]] = 1;
    int remaining = target - usedBands;
    while (remaining > 0) {
        std::vector<int> expandable;
        for (int index = 0; index < usedBands; ++index) {
            if (counts[bands[index]] < problem.P) expandable.push_back(bands[index]);
        }
        if (expandable.empty()) break;
        std::uniform_int_distribution<int> pick(0, static_cast<int>(expandable.size()) - 1);
        ++counts[expandable[pick(rng)]];
        --remaining;
    }
    for (int band = 1; band <= problem.T; ++band) {
        if (counts[band] == 0) continue;
        std::vector<int> beams(problem.P);
        std::iota(beams.begin(), beams.end(), 1);
        std::shuffle(beams.begin(), beams.end(), rng);
        for (int index = 0; index < counts[band]; ++index) {
            masks[band] |= uint32_t{1} << (beams[index] - 1);
        }
    }
    return masks;
}

void normalizeBudget(const Problem& problem, std::vector<uint32_t>& masks,
                     std::mt19937_64& rng) {
    while (totalBeams(masks) > problem.beamMaxNum) {
        std::vector<std::pair<int, int>> active;
        for (int band = 1; band <= problem.T; ++band) {
            for (int beam = 1; beam <= problem.P; ++beam) {
                if (hasBeam(masks[band], beam)) active.push_back({band, beam});
            }
        }
        if (active.empty()) break;
        std::uniform_int_distribution<int> pick(0, static_cast<int>(active.size()) - 1);
        const auto selected = active[pick(rng)];
        masks[selected.first] &= ~(uint32_t{1} << (selected.second - 1));
    }
}

void mutateMasks(const Problem& problem, std::vector<uint32_t>& masks, int mode,
                 std::mt19937_64& rng) {
    if (mode == 3) {
        masks = randomMasks(problem, rng, false);
        return;
    }
    std::uniform_int_distribution<int> bandPick(1, problem.T);
    if (mode == 0) {
        const int band = bandPick(rng);
        masks[band] = 0;
        std::uniform_int_distribution<int> countPick(0, problem.P);
        const int count = countPick(rng);
        std::vector<int> beams(problem.P);
        std::iota(beams.begin(), beams.end(), 1);
        std::shuffle(beams.begin(), beams.end(), rng);
        for (int index = 0; index < count; ++index) {
            masks[band] |= uint32_t{1} << (beams[index] - 1);
        }
    } else if (mode == 1) {
        const int band = bandPick(rng);
        masks[band] = 0;
        std::uniform_int_distribution<int> countPick(1, problem.P);
        const int count = countPick(rng);
        std::vector<int> beams(problem.P);
        std::iota(beams.begin(), beams.end(), 1);
        std::shuffle(beams.begin(), beams.end(), rng);
        for (int index = 0; index < count; ++index) {
            masks[band] |= uint32_t{1} << (beams[index] - 1);
        }
    } else {
        const int changes = std::max(1, std::min(problem.T, 1 + problem.T / 4));
        for (int index = 0; index < changes; ++index) masks[bandPick(rng)] = 0;
        for (int band = 1; band <= problem.T; ++band) {
            if (masks[band] != 0) continue;
            std::uniform_int_distribution<int> countPick(0, problem.P);
            const int count = countPick(rng);
            std::vector<int> beams(problem.P);
            std::iota(beams.begin(), beams.end(), 1);
            std::shuffle(beams.begin(), beams.end(), rng);
            for (int index = 0; index < count; ++index) {
                masks[band] |= uint32_t{1} << (beams[index] - 1);
            }
        }
    }
    normalizeBudget(problem, masks, rng);
}

void destroyResources(const Problem& problem, Solution& solution, int mode,
                      std::mt19937_64& rng) {
    std::vector<int> occupied;
    for (int resource = 1; resource <= problem.K; ++resource) {
        if (!solution.resourceUsers[resource].empty()) occupied.push_back(resource);
    }
    if (occupied.empty()) return;
    const int count = std::max(1, std::min<int>(occupied.size(), 1 + problem.K / 6));
    if (mode == 1) {
        std::sort(occupied.begin(), occupied.end(), [&](int left, int right) {
            return solution.resourceUsers[left].size() < solution.resourceUsers[right].size();
        });
    } else {
        std::shuffle(occupied.begin(), occupied.end(), rng);
    }
    for (int index = 0; index < count; ++index) {
        solution.resourceUsers[occupied[index]].clear();
    }
}

bool structurallyValid(const Problem& problem, const Solution& solution) {
    if (static_cast<int>(solution.masks.size()) != problem.T + 1 ||
        static_cast<int>(solution.resourceUsers.size()) != problem.K + 1 ||
        totalBeams(solution.masks) > problem.beamMaxNum) {
        return false;
    }
    for (int resource = 1; resource <= problem.K; ++resource) {
        const auto& users = solution.resourceUsers[resource];
        if (users.size() > kMaxShare) return false;
        std::vector<char> seen(problem.N + 1, 0);
        for (int user : users) {
            if (user < 1 || user > problem.N || seen[user]) return false;
            seen[user] = 1;
        }
        if (!users.empty() && !resourceEnabled(problem, solution.masks, resource)) {
            return false;
        }
        if (users.size() > 1) {
            const int group = problem.groupId[users.front()];
            if (group < 0) return false;
            for (int user : users) {
                if (problem.groupId[user] != group) return false;
            }
        }
    }
    return true;
}

Solution runAlns(const Problem& problem, const Options& options,
                 const TimePoint& started) {
    const int reserveMs = options.budgetMs >= 20 ? 2 : 1;
    const TimePoint deadline = started + std::chrono::milliseconds(
        std::max(1, options.budgetMs - reserveMs));
    std::mt19937_64 rng(options.seed);
    Solution best = emptySolution(problem);
    Solution current = best;
    std::array<double, 4> weights = {1.0, 1.0, 1.0, 1.0};
    int iterations = 0;
    int accepted = 0;

    while (!expired(deadline)) {
        Solution candidate;
        int operatorIndex = 0;
        if (iterations < 4) {
            candidate.masks = randomMasks(problem, rng, iterations == 0);
            candidate.resourceUsers.assign(problem.K + 1, {});
            const std::vector<uint32_t> masks = candidate.masks;
            candidate = randomizedRecreate(problem, masks, std::move(candidate), rng,
                                            0.25 + 0.15 * iterations);
            operatorIndex = 3;
        } else {
            std::discrete_distribution<int> choose(weights.begin(), weights.end());
            operatorIndex = choose(rng);
            candidate = current;
            if (operatorIndex == 0) {
                destroyResources(problem, candidate, 0, rng);
            } else if (operatorIndex == 1) {
                destroyResources(problem, candidate, 1, rng);
                mutateMasks(problem, candidate.masks, 0, rng);
            } else if (operatorIndex == 2) {
                destroyResources(problem, candidate, 0, rng);
                mutateMasks(problem, candidate.masks, 2, rng);
            } else {
                candidate.masks = randomMasks(problem, rng, false);
                candidate.resourceUsers.assign(problem.K + 1, {});
            }
            const std::vector<uint32_t> masks = candidate.masks;
            candidate = randomizedRecreate(
                problem, masks, std::move(candidate), rng,
                0.35 + 0.35 * (static_cast<double>(iterations % 7) / 6.0));
        }
        if (!structurallyValid(problem, candidate)) break;

        if (candidate.score > best.score) {
            best = candidate;
            weights[operatorIndex] += 4.0;
        } else if (candidate.score > current.score) {
            weights[operatorIndex] += 2.0;
        } else {
            weights[operatorIndex] += 0.05;
        }

        const double fraction = std::min(
            1.0, std::chrono::duration<double>(Clock::now() - started).count() /
                       std::max(0.001, options.budgetMs / 1000.0));
        const double temperature = std::max(1.0, 120.0 * (1.0 - fraction));
        bool accept = candidate.score >= current.score;
        if (!accept) {
            const double probability =
                std::exp(static_cast<double>(candidate.score - current.score) / temperature);
            std::uniform_real_distribution<double> coin(0.0, 1.0);
            accept = coin(rng) < probability;
        }
        if (accept) {
            current = std::move(candidate);
            ++accepted;
        }
        ++iterations;
        if ((iterations & 31) == 0) {
            for (double& weight : weights) weight = std::max(0.25, weight * 0.96);
        }
    }

    if (options.trace) {
        const double elapsed =
            std::chrono::duration<double, std::milli>(Clock::now() - started).count();
        std::cerr << "TRACE external=alns score=" << best.score
                  << " elapsed_ms=" << elapsed << " iterations=" << iterations
                  << " accepted=" << accepted << '\n';
    }
    return structurallyValid(problem, best) ? best : emptySolution(problem);
}

void outputSolution(const Problem& problem, const Solution& solution) {
    for (int band = 1; band <= problem.T; ++band) {
        std::cout << bitCount(solution.masks[band]);
        for (int beam = 1; beam <= problem.P; ++beam) {
            if (hasBeam(solution.masks[band], beam)) std::cout << ' ' << beam;
        }
        std::cout << '\n';
    }
    std::vector<std::vector<int>> userResources(problem.N + 1);
    for (int resource = 1; resource <= problem.K; ++resource) {
        for (int user : solution.resourceUsers[resource]) {
            userResources[user].push_back(resource);
        }
    }
    for (int user = 1; user <= problem.N; ++user) {
        std::sort(userResources[user].begin(), userResources[user].end());
        std::cout << userResources[user].size();
        for (int resource : userResources[user]) std::cout << ' ' << resource;
        std::cout << '\n';
    }
}

}  // namespace external_alns

#ifndef FPTR_EXTERNAL_NO_MAIN
int main(int argc, char** argv) {
    external_alns::Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--help" || argument == "-h") {
            std::cout << "usage: external_alns [--budget-ms N] [--seed N] [--trace]\n";
            return 0;
        }
        if (argument == "--trace") {
            options.trace = true;
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
    const external_alns::Solution solution =
        external_alns::runAlns(problem, options, started);
    external_alns::outputSolution(problem, solution);
    return 0;
}
#endif

#endif  // FPTR_EXTERNAL_ALNS_BASELINE_IMPLEMENTATION
