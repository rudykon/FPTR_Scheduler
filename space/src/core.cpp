#include "core.h"

#include <algorithm>
#include <array>
#include <cerrno>
#include <charconv>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;
using TimePoint = Clock::time_point;

constexpr int kMaxShare = 20;
constexpr int kInvalidScore = -1000000000;

struct Problem {
    int P = 0;
    int N = 0;
    int K = 0;
    int T = 0;
    int beamMaxNum = 0;
    int M = 0;
    std::vector<std::vector<int>> ru;
    std::vector<int> ruId;
    std::vector<char> isSu;
    std::vector<std::vector<double>> cap;
    std::vector<double> totalCap;
    std::vector<int> buffer;
    std::vector<double> sinr;
    std::vector<std::vector<int>> subResources;
    std::vector<std::vector<int>> resourceBands;
    std::array<double, kMaxShare + 1> sharePenalty{};
};

struct Solution {
    int score = 0;
    std::vector<uint32_t> masks;
    std::vector<std::vector<int>> resourceUsers;
};

struct GroupChoice {
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
          values(static_cast<size_t>(resourceCount + 1) * (kMaxShare + 1) * (userCount + 1), 0) {}

    int& at(int resource, int share, int user) {
        return values[(static_cast<size_t>(resource) * (kMaxShare + 1) + share) * (N + 1) + user];
    }

    int get(int resource, int share, int user) const {
        return values[(static_cast<size_t>(resource) * (kMaxShare + 1) + share) * (N + 1) + user];
    }
};

bool expired(const TimePoint& deadline) {
    return Clock::now() >= deadline;
}

bool parseInt(const std::string& token, int& value) {
    if (token.empty()) return false;
    long long parsed = 0;
    const char* begin = token.data();
    const char* end = begin + token.size();
    auto result = std::from_chars(begin, end, parsed);
    if (result.ec != std::errc() || result.ptr != end) return false;
    if (parsed < std::numeric_limits<int>::min() || parsed > std::numeric_limits<int>::max()) return false;
    value = static_cast<int>(parsed);
    return true;
}

bool parseDouble(const std::string& token, double& value) {
    if (token.empty()) return false;
    errno = 0;
    char* end = nullptr;
    value = std::strtod(token.c_str(), &end);
    if (errno == ERANGE || end != token.c_str() + token.size()) return false;
    return std::isfinite(value);
}

bool readTokens(std::istream& input, std::vector<std::string>& tokens) {
    std::string line;
    if (!std::getline(input, line)) return false;
    std::istringstream stream(line);
    tokens.clear();
    std::string token;
    while (stream >> token) tokens.push_back(token);
    return !tokens.empty();
}

bool readIntLine(std::istream& input, int expected, std::vector<int>& values) {
    std::vector<std::string> tokens;
    if (!readTokens(input, tokens) || static_cast<int>(tokens.size()) != expected) return false;
    values.resize(expected);
    for (int i = 0; i < expected; ++i) {
        if (!parseInt(tokens[i], values[i])) return false;
    }
    return true;
}

bool readCountedIds(std::istream& input, int minCount, int maxCount, int maxId,
                    std::vector<int>& ids) {
    std::vector<std::string> tokens;
    if (!readTokens(input, tokens)) return false;
    int count = 0;
    if (!parseInt(tokens[0], count) || count < minCount || count > maxCount) return false;
    if (static_cast<int>(tokens.size()) != count + 1) return false;
    ids.resize(count);
    std::vector<char> seen(maxId + 1, 0);
    for (int i = 0; i < count; ++i) {
        if (!parseInt(tokens[i + 1], ids[i]) || ids[i] < 1 || ids[i] > maxId || seen[ids[i]]) return false;
        seen[ids[i]] = 1;
    }
    return true;
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

void prepareThresholds(Problem& in) {
    in.sharePenalty.fill(0.0);
    for (int share = 1; share <= kMaxShare; ++share) {
        in.sharePenalty[share] = 10.0 * std::log10(1.0 / share);
    }
}

int rateFromLinkTerm(const Problem& in, int user, double linkTerm, int share) {
    if (share < 1 || share > kMaxShare) return 0;
    const double fse = in.sinr[user] + in.sharePenalty[share] + linkTerm;
    return rateOfFse(fse);
}

[[maybe_unused]] int rateFromAverage(const Problem& in, int user, double average, int share) {
    if (average <= 0.0) return 0;
    const double linkTerm = 10.0 * std::log10(average / in.totalCap[user]);
    return rateFromLinkTerm(in, user, linkTerm, share);
}

bool readProblem(Problem& in) {
    std::vector<int> values;
    if (!readIntLine(std::cin, 5, values)) return false;
    in.P = values[0];
    in.N = values[1];
    in.K = values[2];
    in.T = values[3];
    in.beamMaxNum = values[4];
    if (in.P < 1 || in.P > 32 || in.N < 1 || in.N > 100 || in.K < 2 || in.K > 72 ||
        in.T < 1 || in.T > 18 || in.beamMaxNum < 2 || in.beamMaxNum > 255) {
        return false;
    }

    if (!readIntLine(std::cin, 1, values)) return false;
    in.M = values[0];
    if (in.M < 0 || in.M > 16) return false;
    in.ru.assign(in.M, {});
    in.ruId.assign(in.N + 1, -1);
    for (int group = 0; group < in.M; ++group) {
        if (!readCountedIds(std::cin, 2, 20, in.N, in.ru[group])) return false;
        for (int user : in.ru[group]) {
            if (in.ruId[user] != -1) return false;
            in.ruId[user] = group;
        }
    }

    std::vector<int> su;
    if (!readCountedIds(std::cin, 0, 29, in.N, su)) return false;
    in.isSu.assign(in.N + 1, 0);
    for (int user : su) {
        if (in.ruId[user] != -1) return false;
        in.isSu[user] = 1;
    }

    in.cap.assign(in.N + 1, std::vector<double>(in.P + 1, 0.0));
    in.totalCap.assign(in.N + 1, 0.0);
    for (int user = 1; user <= in.N; ++user) {
        std::vector<std::string> tokens;
        if (!readTokens(std::cin, tokens) || static_cast<int>(tokens.size()) != in.P) return false;
        for (int beam = 1; beam <= in.P; ++beam) {
            double capability = 0.0;
            if (!parseDouble(tokens[beam - 1], capability) || capability <= 0.0 || capability > 65535.0) {
                return false;
            }
            in.cap[user][beam] = capability;
            in.totalCap[user] += capability;
        }
    }

    in.buffer.assign(in.N + 1, 0);
    in.sinr.assign(in.N + 1, 0.0);
    for (int user = 1; user <= in.N; ++user) {
        std::vector<std::string> tokens;
        if (!readTokens(std::cin, tokens) || tokens.size() != 2) return false;
        if (!parseInt(tokens[0], in.buffer[user]) || in.buffer[user] < 1 || in.buffer[user] > 10000) {
            return false;
        }
        if (!parseDouble(tokens[1], in.sinr[user]) || in.sinr[user] < -30.0 || in.sinr[user] > 100.0) {
            return false;
        }
    }

    in.subResources.assign(in.T + 1, {});
    in.resourceBands.assign(in.K + 1, {});
    for (int band = 1; band <= in.T; ++band) {
        if (!readCountedIds(std::cin, 0, in.K, in.K, in.subResources[band])) return false;
        for (int resource : in.subResources[band]) in.resourceBands[resource].push_back(band);
    }
    for (int resource = 1; resource <= in.K; ++resource) {
        const auto& bands = in.resourceBands[resource];
        if (bands.size() != 1 && bands.size() != 2) return false;
    }

    std::string trailing;
    while (std::getline(std::cin, trailing)) {
        if (trailing.find_first_not_of(" \t\r") != std::string::npos) return false;
    }
    prepareThresholds(in);
    return true;
}

int bitCount(uint32_t value) {
    return __builtin_popcount(value);
}

bool hasBeam(uint32_t mask, int beam) {
    return (mask & (uint32_t{1} << (beam - 1))) != 0;
}

uint32_t fullMask(int beamCount) {
    return beamCount == 32 ? std::numeric_limits<uint32_t>::max()
                           : (uint32_t{1} << beamCount) - 1u;
}

int totalBeams(const std::vector<uint32_t>& masks) {
    int total = 0;
    for (size_t band = 1; band < masks.size(); ++band) total += bitCount(masks[band]);
    return total;
}

std::vector<int> orderByScore(const std::vector<double>& score, int count) {
    std::vector<int> order(count);
    std::iota(order.begin(), order.end(), 1);
    std::sort(order.begin(), order.end(), [&](int left, int right) {
        if (std::fabs(score[left] - score[right]) > 1e-12) return score[left] > score[right];
        return left < right;
    });
    return order;
}

void addUniqueOrder(std::vector<std::vector<int>>& orders, std::vector<int> order) {
    if (std::find(orders.begin(), orders.end(), order) == orders.end()) orders.push_back(std::move(order));
}

std::vector<std::vector<int>> buildBeamOrders(const Problem& in) {
    std::vector<double> normalized(in.P + 1, 0.0);
    std::vector<double> raw(in.P + 1, 0.0);
    std::vector<double> need(in.P + 1, 0.0);
    std::vector<double> rateWeighted(in.P + 1, 0.0);
    std::vector<double> peak(in.P + 1, 0.0);
    std::vector<double> ruWeighted(in.P + 1, 0.0);
    for (int user = 1; user <= in.N; ++user) {
        double demand = std::max(1.0, std::min<double>(in.buffer[user], in.K * 222.0));
        double baseRate = std::max(1, rateOfFse(in.sinr[user]));
        double groupWeight = in.ruId[user] >= 0 ? 1.25 : 0.85;
        for (int beam = 1; beam <= in.P; ++beam) {
            double ratio = in.cap[user][beam] / in.totalCap[user];
            normalized[beam] += ratio;
            raw[beam] += in.cap[user][beam];
            need[beam] += ratio * demand;
            rateWeighted[beam] += ratio * demand * baseRate;
            peak[beam] = std::max(peak[beam], ratio * demand * baseRate);
            ruWeighted[beam] += ratio * demand * baseRate * groupWeight;
        }
    }
    std::vector<std::vector<int>> orders;
    addUniqueOrder(orders, orderByScore(rateWeighted, in.P));
    addUniqueOrder(orders, orderByScore(need, in.P));
    addUniqueOrder(orders, orderByScore(ruWeighted, in.P));
    addUniqueOrder(orders, orderByScore(normalized, in.P));
    addUniqueOrder(orders, orderByScore(raw, in.P));
    addUniqueOrder(orders, orderByScore(peak, in.P));
    std::vector<int> natural(in.P);
    std::iota(natural.begin(), natural.end(), 1);
    addUniqueOrder(orders, natural);
    std::reverse(natural.begin(), natural.end());
    addUniqueOrder(orders, natural);
    return orders;
}

std::vector<int> buildBandOrder(const Problem& in, std::vector<int>& impact) {
    impact.assign(in.T + 1, 0);
    for (int resource = 1; resource <= in.K; ++resource) {
        for (int band : in.resourceBands[resource]) ++impact[band];
    }
    std::vector<int> order(in.T);
    std::iota(order.begin(), order.end(), 1);
    std::sort(order.begin(), order.end(), [&](int left, int right) {
        if (impact[left] != impact[right]) return impact[left] > impact[right];
        return left < right;
    });
    return order;
}

std::vector<int> allocateBeamCounts(const Problem& in, const std::vector<int>& bandOrder,
                                    const std::vector<int>& impact, int usedBands, int mode) {
    std::vector<int> count(in.T + 1, 0);
    usedBands = std::max(1, std::min({usedBands, in.T, in.beamMaxNum}));
    int budget = std::min(in.beamMaxNum, usedBands * in.P);
    for (int index = 0; index < usedBands && budget > 0; ++index) {
        count[bandOrder[index]] = 1;
        --budget;
    }
    while (budget-- > 0) {
        int bestBand = -1;
        double bestPriority = -1.0;
        for (int index = 0; index < usedBands; ++index) {
            int band = bandOrder[index];
            if (count[band] >= in.P) continue;
            double priority = 0.0;
            if (mode == 0) {
                priority = -count[band] - index * 1e-3;
            } else if (mode == 1) {
                priority = static_cast<double>(std::max(1, impact[band])) / (count[band] + 0.5);
            } else {
                priority = (in.P - count[band]) * (index == 0 ? 1000.0 : 1.0) - index * 1e-3;
            }
            if (priority > bestPriority) {
                bestPriority = priority;
                bestBand = band;
            }
        }
        if (bestBand < 0) break;
        ++count[bestBand];
    }
    return count;
}

std::vector<uint32_t> masksFromOrder(const Problem& in, const std::vector<int>& count,
                                     const std::vector<int>& beamOrder) {
    std::vector<uint32_t> masks(in.T + 1, 0);
    for (int band = 1; band <= in.T; ++band) {
        for (int index = 0; index < count[band] && index < in.P; ++index) {
            masks[band] |= uint32_t{1} << (beamOrder[index] - 1);
        }
    }
    return masks;
}

std::vector<uint32_t> makeUserFocusedMasks(const Problem& in, const std::vector<int>& count,
                                           int variant) {
    std::vector<int> users(in.N);
    std::iota(users.begin(), users.end(), 1);
    std::sort(users.begin(), users.end(), [&](int left, int right) {
        double leftWeight = std::min<double>(in.buffer[left], in.K * 222.0) *
                            std::max(1, rateOfFse(in.sinr[left]));
        double rightWeight = std::min<double>(in.buffer[right], in.K * 222.0) *
                             std::max(1, rateOfFse(in.sinr[right]));
        if (std::fabs(leftWeight - rightWeight) > 1e-12) return leftWeight > rightWeight;
        return left < right;
    });
    int userLimit = std::min(in.N, 20);
    std::vector<uint32_t> masks(in.T + 1, 0);
    for (int band = 1; band <= in.T; ++band) {
        if (count[band] == 0) continue;
        int user = users[(variant * 3 + band * (variant + 1)) % userLimit];
        std::vector<int> beams(in.P);
        std::iota(beams.begin(), beams.end(), 1);
        std::sort(beams.begin(), beams.end(), [&](int left, int right) {
            if (std::fabs(in.cap[user][left] - in.cap[user][right]) > 1e-12) {
                return in.cap[user][left] > in.cap[user][right];
            }
            return left < right;
        });
        for (int index = 0; index < count[band]; ++index) {
            masks[band] |= uint32_t{1} << (beams[index] - 1);
        }
    }
    return masks;
}

std::vector<std::vector<uint32_t>> generateMasks(const Problem& in,
                                                 const TimePoint& deadline) {
    std::vector<std::vector<uint32_t>> result;
    std::set<std::vector<uint32_t>> seen;
    auto add = [&](std::vector<uint32_t> masks) {
        if (totalBeams(masks) <= in.beamMaxNum && seen.insert(masks).second) {
            result.push_back(std::move(masks));
        }
    };
    if (in.P * in.T <= in.beamMaxNum) {
        std::vector<uint32_t> masks(in.T + 1, fullMask(in.P));
        masks[0] = 0;
        add(std::move(masks));
        return result;
    }

    std::vector<int> impact;
    std::vector<int> bandOrder = buildBandOrder(in, impact);
    if (expired(deadline)) return result;
    auto beamOrders = buildBeamOrders(in);
    int maxUsed = std::min({in.T, in.beamMaxNum, in.K});
    std::vector<int> usedOptions = {maxUsed, std::max(1, maxUsed - 1), std::max(1, maxUsed / 2)};
    std::sort(usedOptions.begin(), usedOptions.end());
    usedOptions.erase(std::unique(usedOptions.begin(), usedOptions.end()), usedOptions.end());
    std::reverse(usedOptions.begin(), usedOptions.end());

            if (expired(deadline)) return result;
    for (int orderIndex = 0; orderIndex < static_cast<int>(beamOrders.size()); ++orderIndex) {
        for (int used : usedOptions) {
            add(masksFromOrder(in, allocateBeamCounts(in, bandOrder, impact, used, 1),
                               beamOrders[orderIndex]));
            if (orderIndex < 4 && used == maxUsed) {
                add(masksFromOrder(in, allocateBeamCounts(in, bandOrder, impact, used, 0),
                                   beamOrders[orderIndex]));
            }
            if (orderIndex < 2 && used != maxUsed) {
                add(masksFromOrder(in, allocateBeamCounts(in, bandOrder, impact, used, 2),
                                   beamOrders[orderIndex]));
            }
        }
    }

    auto focusedCounts = allocateBeamCounts(in, bandOrder, impact, maxUsed, 1);
    for (int variant = 0; variant < 10 && !expired(deadline); ++variant) {
        add(makeUserFocusedMasks(in, focusedCounts, variant));
    }
    return result;
}

bool resourceEnabled(const Problem& in, const std::vector<uint32_t>& masks, int resource) {
    for (int band : in.resourceBands[resource]) {
        if (masks[band] == 0) return false;
    }
    return true;
}

bool buildRates(const Problem& in, const std::vector<uint32_t>& masks, RateTable& rates,
                const TimePoint& deadline) {
    if (expired(deadline)) return false;
    std::vector<std::vector<double>> selected(in.T + 1,
                                              std::vector<double>(in.N + 1, 0.0));
    for (int band = 1; band <= in.T; ++band) {
        for (int beam = 1; beam <= in.P; ++beam) {
            if (!hasBeam(masks[band], beam)) continue;
            for (int user = 1; user <= in.N; ++user) {
                selected[band][user] += in.cap[user][beam];
            }
            if (expired(deadline)) return false;
        }
    }

    rates = RateTable(in.K, in.N);
    for (int resource = 1; resource <= in.K; ++resource) {
        const auto& bands = in.resourceBands[resource];
        const double denominator = static_cast<double>(bands.back() - bands.front() + 1);
        for (int user = 1; user <= in.N; ++user) {
            double selectedSum = 0.0;
            for (int band : bands) selectedSum += selected[band][user];
            const double average = selectedSum / denominator;
            if (average <= 0.0) continue;
            const double linkTerm = 10.0 * std::log10(average / in.totalCap[user]);
            for (int share = 1; share <= kMaxShare; ++share) {
                rates.at(resource, share, user) =
                    rateFromLinkTerm(in, user, linkTerm, share);
            }
        }
        if (expired(deadline)) return false;
    }
    return true;
}

GroupChoice bestGroup(const Problem& in, const RateTable& rates, int resource,
                      const std::vector<int>& remaining, const TimePoint& deadline,
                      bool& completed) {
    GroupChoice best;
    completed = false;
    if (expired(deadline)) return best;
    for (int user = 1; user <= in.N; ++user) {
        int gain = std::min(remaining[user], rates.get(resource, 1, user));
        if (gain > best.gain ||
            (gain == best.gain && gain > 0 && (best.users.empty() || user < best.users.front()))) {
            best.gain = gain;
            best.users.assign(1, user);
        }
        if ((user & 15) == 0 && expired(deadline)) return best;
    }

    for (const auto& group : in.ru) {
        if (expired(deadline)) return best;
        int groupSize = static_cast<int>(group.size());
        for (int share = 2; share <= groupSize; ++share) {
            if (expired(deadline)) return best;
            std::vector<std::pair<int, int>> values;
            values.reserve(groupSize);
            for (int user : group) {
                int gain = std::min(remaining[user], rates.get(resource, share, user));
                if (gain > 0) values.push_back({gain, user});
            }
            if (static_cast<int>(values.size()) < share) continue;
            std::sort(values.begin(), values.end(), [](const auto& left, const auto& right) {
                if (left.first != right.first) return left.first > right.first;
                return left.second < right.second;
            });
            if (expired(deadline)) return best;
            int gain = 0;
            std::vector<int> users;
            users.reserve(share);
            for (int index = 0; index < share; ++index) {
                gain += values[index].first;
                users.push_back(values[index].second);
            }
            std::sort(users.begin(), users.end());
            if (gain > best.gain ||
                (gain == best.gain && gain > 0 &&
                 (users.size() > best.users.size() ||
                  (users.size() == best.users.size() && users < best.users)))) {
                best.gain = gain;
                best.users = std::move(users);
            }
        }
    }
    completed = !expired(deadline);
    return best;
}

Solution allocateResources(const Problem& in, const std::vector<uint32_t>& masks,
                           const RateTable& rates, int orderMode, const TimePoint& deadline,
                           bool& completed) {
    completed = false;
    if (expired(deadline)) return Solution{};
    std::vector<int> remaining = in.buffer;
    std::vector<int> resources;
    resources.reserve(in.K);
    std::vector<int> potential(in.K + 1, 0);
    for (int resource = 1; resource <= in.K; ++resource) {
        if (!resourceEnabled(in, masks, resource)) continue;
        resources.push_back(resource);
        if (orderMode == 0) {
            bool groupCompleted = false;
            potential[resource] =
                bestGroup(in, rates, resource, remaining, deadline, groupCompleted).gain;
            if (!groupCompleted) return Solution{};
        }
    }
    if (orderMode == 0) {
        std::sort(resources.begin(), resources.end(), [&](int left, int right) {
            if (potential[left] != potential[right]) return potential[left] > potential[right];
            int leftWidth = static_cast<int>(in.resourceBands[left].size());
            int rightWidth = static_cast<int>(in.resourceBands[right].size());
            if (leftWidth != rightWidth) return leftWidth > rightWidth;
            return left < right;
        });
    } else if (orderMode == 1) {
        std::sort(resources.begin(), resources.end(), [&](int left, int right) {
            int leftWidth = static_cast<int>(in.resourceBands[left].size());
            int rightWidth = static_cast<int>(in.resourceBands[right].size());
            if (leftWidth != rightWidth) return leftWidth > rightWidth;
            return left < right;
        });
    } else if (orderMode == 2) {
        std::reverse(resources.begin(), resources.end());
    }
    if (expired(deadline)) return Solution{};

    Solution solution;
    solution.score = 0;
    solution.masks = masks;
    solution.resourceUsers.assign(in.K + 1, {});
    int checks = 0;
    for (int resource : resources) {
        bool groupCompleted = false;
        GroupChoice choice = bestGroup(in, rates, resource, remaining, deadline, groupCompleted);
        if (!groupCompleted) return solution;
        if (choice.gain > 0 && !choice.users.empty()) {
            int share = static_cast<int>(choice.users.size());
            for (int user : choice.users) {
                int increment = std::min(remaining[user], rates.get(resource, share, user));
                remaining[user] -= increment;
                solution.score += increment;
            }
            solution.resourceUsers[resource] = std::move(choice.users);
        }
        if ((++checks & 3) == 0 && expired(deadline)) return solution;
    }
    completed = !expired(deadline);
    return solution;
}

std::vector<int> computeRaw(const Problem& in, const RateTable& rates,
                            const std::vector<std::vector<int>>& resourceUsers) {
    std::vector<int> raw(in.N + 1, 0);
    for (int resource = 1; resource <= in.K; ++resource) {
        int share = static_cast<int>(resourceUsers[resource].size());
        if (share == 0) continue;
        for (int user : resourceUsers[resource]) raw[user] += rates.get(resource, share, user);
    }
    return raw;
}

int scoreFromRaw(const Problem& in, const std::vector<int>& raw) {
    int score = 0;
    for (int user = 1; user <= in.N; ++user) score += std::min(in.buffer[user], raw[user]);
    return score;
}

bool improveResources(const Problem& in, Solution& solution, const RateTable& rates,
                      const TimePoint& deadline) {
    std::vector<int> raw = computeRaw(in, rates, solution.resourceUsers);
    solution.score = scoreFromRaw(in, raw);
    for (int pass = 0; pass < 3 && !expired(deadline); ++pass) {
        bool improved = false;
        for (int resource = 1; resource <= in.K; ++resource) {
            if (!resourceEnabled(in, solution.masks, resource)) continue;
            const std::vector<int> oldUsers = solution.resourceUsers[resource];
            int oldShare = static_cast<int>(oldUsers.size());
            if (oldShare > 0) {
                for (int user : oldUsers) raw[user] -= rates.get(resource, oldShare, user);
            }
            int baseScore = scoreFromRaw(in, raw);
            std::vector<int> remaining(in.N + 1, 0);
            for (int user = 1; user <= in.N; ++user) {
                remaining[user] = std::max(0, in.buffer[user] - raw[user]);
            }
            bool groupCompleted = false;
            GroupChoice choice = bestGroup(in, rates, resource, remaining, deadline, groupCompleted);
            if (!groupCompleted) return false;
            int candidateScore = baseScore + choice.gain;
            if (candidateScore > solution.score && !choice.users.empty()) {
                int share = static_cast<int>(choice.users.size());
                for (int user : choice.users) raw[user] += rates.get(resource, share, user);
                solution.resourceUsers[resource] = std::move(choice.users);
                solution.score = candidateScore;
                improved = true;
            } else {
                if (oldShare > 0) {
                    for (int user : oldUsers) raw[user] += rates.get(resource, oldShare, user);
                }
            }
            if ((resource & 7) == 0 && expired(deadline)) break;
        }
        if (!improved) break;
    }
    return !expired(deadline);
}

std::vector<uint32_t> makeScheduledMasks(const Problem& in, const Solution& seed,
                                         const RateTable& rates, int variant,
                                         const TimePoint& deadline, bool& completed) {
    completed = false;
    if (expired(deadline)) return {};
    std::vector<int> raw = computeRaw(in, rates, seed.resourceUsers);
    std::vector<std::vector<double>> userWeight(in.T + 1,
                                                std::vector<double>(in.N + 1, 0.0));
    for (int resource = 1; resource <= in.K; ++resource) {
        const auto& users = seed.resourceUsers[resource];
        if (users.empty()) continue;
        int share = static_cast<int>(users.size());
        for (int user : users) {
            int delivered = std::min(in.buffer[user], raw[user]);
            int residual = std::max(0, in.buffer[user] - delivered);
            double weight = 1.0 + residual + 0.08 * std::sqrt(static_cast<double>(in.buffer[user]));
            if (in.ruId[user] >= 0) weight *= variant == 0 ? 1.20 : 1.35;
            if (expired(deadline)) return {};
            weight *= 1.0 + 0.10 * share;
            for (int band : in.resourceBands[resource]) userWeight[band][user] += weight;
        }
    }

    std::vector<uint32_t> masks(in.T + 1, 0);
    for (int band = 1; band <= in.T; ++band) {
        int count = bitCount(seed.masks[band]);
        if (count == 0) continue;
        std::vector<double> score(in.P + 1, 0.0);
        bool active = false;
        for (int user = 1; user <= in.N; ++user) {
            double weight = userWeight[band][user];
            if (weight <= 0.0) continue;
            active = true;
            for (int beam = 1; beam <= in.P; ++beam) {
                score[beam] += weight * in.cap[user][beam] / in.totalCap[user];
            }
        }
        if (!active) {
            for (int user = 1; user <= in.N; ++user) {
                double weight = std::min<double>(in.buffer[user], in.K * 222.0);
                for (int beam = 1; beam <= in.P; ++beam) {
                    score[beam] += weight * in.cap[user][beam] / in.totalCap[user];
                }
            }
        }
        for (int beam = 1; beam <= in.P; ++beam) {
            if (hasBeam(seed.masks[band], beam)) score[beam] *= 1.02;
        }
        std::vector<int> order = orderByScore(score, in.P);
        for (int index = 0; index < count; ++index) masks[band] |= uint32_t{1} << (order[index] - 1);
        if (expired(deadline)) return {};
    }
    completed = !expired(deadline);
    return masks;
}

bool validateSolution(const Problem& in, const Solution& solution) {
    if (static_cast<int>(solution.masks.size()) != in.T + 1 ||
        static_cast<int>(solution.resourceUsers.size()) != in.K + 1 ||
        solution.masks[0] != 0 || totalBeams(solution.masks) > in.beamMaxNum) {
        return false;
    }
    const uint32_t allowedMask = fullMask(in.P);
    for (int band = 1; band <= in.T; ++band) {
        if ((solution.masks[band] & ~allowedMask) != 0) return false;
    }
    for (int resource = 1; resource <= in.K; ++resource) {
        const auto& users = solution.resourceUsers[resource];
        if (users.size() > kMaxShare) return false;
        std::vector<char> seen(in.N + 1, 0);
        for (int user : users) {
            if (user < 1 || user > in.N || seen[user]) return false;
            seen[user] = 1;
        }
        if (!users.empty()) {
            for (int band : in.resourceBands[resource]) {
                if (solution.masks[band] == 0) return false;
            }
        }
        if (users.size() > 1) {
            int group = in.ruId[users.front()];
            if (group < 0) return false;
            for (int user : users) {
                if (in.ruId[user] != group) return false;
            }
        }
    }
    return true;
}

Solution emptySolution(const Problem& in) {
    Solution solution;
    solution.score = 0;
    solution.masks.assign(in.T + 1, 0);
    solution.resourceUsers.assign(in.K + 1, {});
    return solution;
}

void outputSolution(const Problem& in, const Solution& solution) {
    for (int band = 1; band <= in.T; ++band) {
        std::cout << bitCount(solution.masks[band]);
        for (int beam = 1; beam <= in.P; ++beam) {
            if (hasBeam(solution.masks[band], beam)) std::cout << ' ' << beam;
        }
        std::cout << '\n';
    }
    std::vector<std::vector<int>> userResources(in.N + 1);
    for (int resource = 1; resource <= in.K; ++resource) {
        for (int user : solution.resourceUsers[resource]) userResources[user].push_back(resource);
    }
    for (int user = 1; user <= in.N; ++user) {
        std::cout << userResources[user].size();
        for (int resource : userResources[user]) std::cout << ' ' << resource;
        std::cout << '\n';
    }
}


struct RankedPlan {
    int score = 0;
    std::vector<uint32_t> masks;
};

void rememberPlan(std::vector<RankedPlan>& plans, int score,
                  const std::vector<uint32_t>& masks) {
    for (auto& plan : plans) {
        if (plan.masks == masks) {
            plan.score = std::max(plan.score, score);
            return;
        }
    }
    plans.push_back({score, masks});
    std::sort(plans.begin(), plans.end(), [](const RankedPlan& left, const RankedPlan& right) {
        return left.score != right.score ? left.score > right.score : left.masks < right.masks;
    });
    if (plans.size() > 10) plans.resize(10);
}

bool considerCandidate(const Problem& in, Solution candidate, bool completed,
                       const TimePoint& deadline, Solution& incumbent) {
    if (!completed || expired(deadline) || candidate.score <= incumbent.score) return false;
    if (!validateSolution(in, candidate) || expired(deadline)) return false;
    incumbent = std::move(candidate);
    return true;
}

Solution allocateGlobal(const Problem& in, const std::vector<uint32_t>& masks,
                        const RateTable& rates, const TimePoint& deadline,
                        bool& completed) {
    completed = false;
    Solution solution;
    solution.masks = masks;
    solution.resourceUsers.assign(in.K + 1, {});
    if (expired(deadline)) return solution;
    std::vector<int> remaining = in.buffer;
    std::vector<char> available(in.K + 1, 0);
    for (int resource = 1; resource <= in.K; ++resource) {
        available[resource] = resourceEnabled(in, masks, resource);
    }
    for (int step = 0; step < in.K; ++step) {
        if (expired(deadline)) return solution;
        int bestResource = -1;
        GroupChoice bestChoice;
        for (int resource = 1; resource <= in.K; ++resource) {
            if (!available[resource]) continue;
            bool groupCompleted = false;
            GroupChoice choice =
                bestGroup(in, rates, resource, remaining, deadline, groupCompleted);
            if (!groupCompleted) return solution;
            if (choice.gain > bestChoice.gain ||
                (choice.gain == bestChoice.gain && choice.gain > 0 &&
                 (bestResource < 0 || resource < bestResource))) {
                bestResource = resource;
                bestChoice = std::move(choice);
            }
        }
        if (expired(deadline)) return solution;
        if (bestResource < 0 || bestChoice.gain <= 0 || bestChoice.users.empty()) break;
        available[bestResource] = 0;
        int share = static_cast<int>(bestChoice.users.size());
        for (int user : bestChoice.users) {
            int increment = std::min(remaining[user], rates.get(bestResource, share, user));
            remaining[user] -= increment;
            solution.score += increment;
        }
        solution.resourceUsers[bestResource] = std::move(bestChoice.users);
    }
    completed = !expired(deadline);
    return solution;
}

std::vector<uint32_t> compatibilityMasks(const Problem& in, int variant,
                                         const TimePoint& deadline, bool& completed) {
    completed = false;
    std::vector<uint32_t> masks(in.T + 1, 0);
    if (expired(deadline)) return masks;
    std::vector<int> impact;
    std::vector<int> bandOrder = buildBandOrder(in, impact);
    int used = std::min({in.T, in.beamMaxNum, in.K});
    std::vector<int> count = allocateBeamCounts(in, bandOrder, impact, used, 1);
    std::vector<int> groups(in.M);
    std::iota(groups.begin(), groups.end(), 0);
    auto weight = [&](int user) {
        return std::max(1, rateOfFse(in.sinr[user])) *
               std::max(1.0, std::min<double>(in.buffer[user], in.K * 222.0));
    };
    std::sort(groups.begin(), groups.end(), [&](int left, int right) {
        double leftWeight = 0.0, rightWeight = 0.0;
        for (int user : in.ru[left]) leftWeight += weight(user);
        for (int user : in.ru[right]) rightWeight += weight(user);
        return std::fabs(leftWeight - rightWeight) > 1e-12 ? leftWeight > rightWeight
                                                            : left < right;
    });
    if (groups.empty()) {
        completed = !expired(deadline);
        return masks;
    }
    for (int band = 1; band <= in.T; ++band) {
        if (expired(deadline)) return masks;
        if (count[band] == 0) continue;
        const auto& group = in.ru[groups[(band * (variant + 1) + variant) % groups.size()]];
        int target = std::min<int>(group.size(), 2 + ((variant / 4 + band) % 4));
        std::vector<double> score(in.P + 1, 0.0);
        for (int beam = 1; beam <= in.P; ++beam) {
            std::vector<double> values;
            values.reserve(group.size());
            double total = 0.0;
            for (int user : group) {
                double value = in.cap[user][beam] / in.totalCap[user] * weight(user);
                values.push_back(value);
                total += value;
            }
            std::sort(values.begin(), values.end(), std::greater<double>());
            double top = 0.0;
            for (int index = 0; index < target; ++index) top += values[index];
            score[beam] = top + ((variant & 1) ? 0.35 : 0.12) * total;
        }
        std::vector<int> order = orderByScore(score, in.P);
        for (int index = 0; index < count[band]; ++index) {
            masks[band] |= uint32_t{1} << (order[index] - 1);
        }
    }
    completed = !expired(deadline);
    return masks;
}

struct PairTrial {
    int score = kInvalidScore;
    std::vector<int> firstUsers;
    std::vector<int> secondUsers;
    std::vector<int> raw;
};

PairTrial refillPair(const Problem& in, const RateTable& rates, int first, int second,
                     const std::vector<int>& baseRaw, const TimePoint& deadline,
                     bool& completed) {
    completed = false;
    PairTrial trial;
    trial.raw = baseRaw;
    std::vector<int> remaining(in.N + 1, 0);
    for (int user = 1; user <= in.N; ++user) {
        remaining[user] = std::max(0, in.buffer[user] - trial.raw[user]);
    }
    bool groupCompleted = false;
    GroupChoice firstChoice =
        bestGroup(in, rates, first, remaining, deadline, groupCompleted);
    if (!groupCompleted) return trial;
    int firstShare = static_cast<int>(firstChoice.users.size());
    for (int user : firstChoice.users) trial.raw[user] += rates.get(first, firstShare, user);
    for (int user = 1; user <= in.N; ++user) {
        remaining[user] = std::max(0, in.buffer[user] - trial.raw[user]);
    }
    GroupChoice secondChoice =
        bestGroup(in, rates, second, remaining, deadline, groupCompleted);
    if (!groupCompleted) return trial;
    int secondShare = static_cast<int>(secondChoice.users.size());
    for (int user : secondChoice.users) trial.raw[user] += rates.get(second, secondShare, user);
    if (expired(deadline)) return trial;
    trial.score = scoreFromRaw(in, trial.raw);
    trial.firstUsers = std::move(firstChoice.users);
    trial.secondUsers = std::move(secondChoice.users);
    completed = true;
    return trial;
}

bool improvePairs(const Problem& in, Solution& solution, const RateTable& rates,
                  const TimePoint& deadline) {
    std::vector<int> raw = computeRaw(in, rates, solution.resourceUsers);
    solution.score = scoreFromRaw(in, raw);
    for (int first = 1; first <= in.K; ++first) {
        if (expired(deadline)) return false;
        if (!resourceEnabled(in, solution.masks, first)) continue;
        for (int second = first + 1; second <= in.K; ++second) {
            if (expired(deadline)) return false;
            if (!resourceEnabled(in, solution.masks, second)) continue;
            std::vector<int> baseRaw = raw;
            int firstShare = static_cast<int>(solution.resourceUsers[first].size());
            int secondShare = static_cast<int>(solution.resourceUsers[second].size());
            for (int user : solution.resourceUsers[first]) {
                baseRaw[user] -= rates.get(first, firstShare, user);
            }
            for (int user : solution.resourceUsers[second]) {
                baseRaw[user] -= rates.get(second, secondShare, user);
            }
            bool forwardCompleted = false, reverseCompleted = false;
            PairTrial forward = refillPair(in, rates, first, second, baseRaw, deadline,
                                           forwardCompleted);
            if (!forwardCompleted) return false;
            PairTrial reverse = refillPair(in, rates, second, first, baseRaw, deadline,
                                           reverseCompleted);
            if (!reverseCompleted) return false;
            if (reverse.score > forward.score) {
                std::swap(reverse.firstUsers, reverse.secondUsers);
                forward = std::move(reverse);
            }
            if (expired(deadline)) return false;
            if (forward.score > solution.score) {
                solution.resourceUsers[first] = std::move(forward.firstUsers);
                solution.resourceUsers[second] = std::move(forward.secondUsers);
                raw = std::move(forward.raw);
                solution.score = forward.score;
            }
        }
    }
    return !expired(deadline);
}

struct StageDeadlines {
    TimePoint base;
    TimePoint global;
    TimePoint compatibilityGroups;
    TimePoint remask;
    TimePoint pair;
    TimePoint final;
};

StageDeadlines makeDeadlines(const TimePoint& started, int budgetMs) {
    const int reserveMs = budgetMs >= 20 ? 3 : 1;
    const int searchMs = std::max(1, budgetMs - reserveMs);
    auto endAt = [&](int numerator) {
        return started + std::chrono::milliseconds(
                             std::max(1, searchMs * numerator / 84));
    };
    return {endAt(45), endAt(60), endAt(70), endAt(78), endAt(84),
            started + std::chrono::milliseconds(budgetMs)};
}

bool includesStage(PipelineStage selected, PipelineStage required) {
    if (selected == PipelineStage::BeamFirst) return required == PipelineStage::BeamFirst;
    return static_cast<int>(selected) >= static_cast<int>(required);
}

void traceStage(bool enabled, const char* stage, int score, const TimePoint& started,
                const TimePoint& deadline) {
    if (!enabled) return;
    double elapsed = std::chrono::duration<double, std::milli>(Clock::now() - started).count();
    std::cerr << "TRACE stage=" << stage << " score=" << score << " elapsed_ms="
              << std::fixed << std::setprecision(3) << elapsed
              << " deadline_hit=" << (expired(deadline) ? 1 : 0) << '\n';
}

void runConfiguredPipeline(const SolverOptions& options) {
    const TimePoint started = Clock::now();
    const StageDeadlines deadlines = makeDeadlines(started, options.budgetMs);
    Problem in;
    if (!readProblem(in)) return;
    Solution fallback = emptySolution(in);
    Solution best = fallback;

    if (options.stage == PipelineStage::BeamFirst) {
        auto plans = generateMasks(in, deadlines.base);
        if (!plans.empty() && !expired(deadlines.base)) {
            RateTable rates;
            if (buildRates(in, plans.front(), rates, deadlines.base)) {
                bool completed = false;
                Solution candidate =
                    allocateResources(in, plans.front(), rates, 0, deadlines.base, completed);
                considerCandidate(in, std::move(candidate), completed, deadlines.base, best);
            }
        }
        traceStage(options.trace, "beam_first", best.score, started, deadlines.base);
        if (!validateSolution(in, best)) best = fallback;
        traceStage(options.trace, "final", best.score, started, deadlines.final);
        outputSolution(in, best);
        return;
    }

    std::vector<RankedPlan> topPlans;
    auto candidates = generateMasks(in, deadlines.base);
    int work = in.N * in.K;
    int candidateLimit = work > 5000 ? 10 : (work > 2500 ? 16 : 30);
    if (static_cast<int>(candidates.size()) > candidateLimit) candidates.resize(candidateLimit);
    double averageCandidateMs = 0.0;
    int completedCandidates = 0;
    for (int index = 0; index < static_cast<int>(candidates.size()); ++index) {
        TimePoint now = Clock::now();
        if (now >= deadlines.base) break;
        if (completedCandidates > 0) {
            double remainingMs =
                std::chrono::duration<double, std::milli>(deadlines.base - now).count();
            if (remainingMs < averageCandidateMs * 1.25 + 0.20) break;
        }
        TimePoint candidateStarted = now;
        RateTable rates;
        if (!buildRates(in, candidates[index], rates, deadlines.base)) break;
        int planScore = 0;
        bool completed = false;
        Solution candidate =
            allocateResources(in, candidates[index], rates, 0, deadlines.base, completed);
        if (completed) planScore = std::max(planScore, candidate.score);
        considerCandidate(in, std::move(candidate), completed, deadlines.base, best);
        if (index < 4 && work <= 3000 && !expired(deadlines.base)) {
            Solution alternate = allocateResources(in, candidates[index], rates,
                                                   1 + (index & 1), deadlines.base,
                                                   completed);
            if (completed) planScore = std::max(planScore, alternate.score);
            considerCandidate(in, std::move(alternate), completed, deadlines.base, best);
        }
        if (!expired(deadlines.base)) rememberPlan(topPlans, planScore, candidates[index]);
        double elapsed =
            std::chrono::duration<double, std::milli>(Clock::now() - candidateStarted).count();
        averageCandidateMs =
            (averageCandidateMs * completedCandidates + elapsed) / (completedCandidates + 1);
        ++completedCandidates;
    }
    traceStage(options.trace, "base", best.score, started, deadlines.base);

    if (includesStage(options.stage, PipelineStage::Global)) {
        int globalLimit = work <= 3000 ? 5 : 2;
        for (int index = 0; index < static_cast<int>(topPlans.size()) && index < globalLimit;
             ++index) {
            if (expired(deadlines.global)) break;
            RateTable rates;
            if (!buildRates(in, topPlans[index].masks, rates, deadlines.global)) break;
            bool completed = false;
            Solution candidate = allocateGlobal(in, topPlans[index].masks, rates,
                                                deadlines.global, completed);
            considerCandidate(in, std::move(candidate), completed, deadlines.global, best);
        }
        traceStage(options.trace, "global", best.score, started, deadlines.global);
    }

    if (includesStage(options.stage, PipelineStage::CompatibilityGroups)) {
        for (int variant = 0; variant < 8 && !expired(deadlines.compatibilityGroups);
             ++variant) {
            bool masksCompleted = false;
            auto masks = compatibilityMasks(in, variant, deadlines.compatibilityGroups,
                                            masksCompleted);
            if (!masksCompleted || totalBeams(masks) > in.beamMaxNum) break;
            RateTable rates;
            if (!buildRates(in, masks, rates, deadlines.compatibilityGroups)) break;
            bool completed = false;
            Solution candidate =
                allocateGlobal(in, masks, rates, deadlines.compatibilityGroups, completed);
            considerCandidate(in, std::move(candidate), completed,
                              deadlines.compatibilityGroups, best);
        }
        traceStage(options.trace, "cg", best.score, started,
                   deadlines.compatibilityGroups);
    }

    if (includesStage(options.stage, PipelineStage::Remask) && best.score > 0 &&
        !expired(deadlines.remask)) {
        RateTable incumbentRates;
        if (buildRates(in, best.masks, incumbentRates, deadlines.remask)) {
            for (int variant = 0; variant < 2 && !expired(deadlines.remask); ++variant) {
                bool masksCompleted = false;
                auto masks = makeScheduledMasks(in, best, incumbentRates, variant,
                                                deadlines.remask, masksCompleted);
                if (!masksCompleted) break;
                if (masks == best.masks || totalBeams(masks) > in.beamMaxNum) continue;
                RateTable trialRates;
                if (!buildRates(in, masks, trialRates, deadlines.remask)) break;
                bool completed = false;
                Solution candidate =
                    allocateGlobal(in, masks, trialRates, deadlines.remask, completed);
                if (considerCandidate(in, std::move(candidate), completed,
                                      deadlines.remask, best)) {
                    incumbentRates = std::move(trialRates);
                }
            }
            if (!expired(deadlines.remask)) {
                Solution candidate = best;
                bool completed = improveResources(in, candidate, incumbentRates,
                                                  deadlines.remask);
                considerCandidate(in, std::move(candidate), completed,
                                  deadlines.remask, best);
            }
        }
        traceStage(options.trace, "remask", best.score, started, deadlines.remask);
    } else if (includesStage(options.stage, PipelineStage::Remask)) {
        traceStage(options.trace, "remask", best.score, started, deadlines.remask);
    }

    if (includesStage(options.stage, PipelineStage::Full) && best.score > 0 &&
        !expired(deadlines.pair)) {
        RateTable incumbentRates;
        if (buildRates(in, best.masks, incumbentRates, deadlines.pair)) {
            Solution candidate = best;
            bool completed = improvePairs(in, candidate, incumbentRates, deadlines.pair);
            considerCandidate(in, std::move(candidate), completed, deadlines.pair, best);
        }
        traceStage(options.trace, "pair", best.score, started, deadlines.pair);
    } else if (includesStage(options.stage, PipelineStage::Full)) {
        traceStage(options.trace, "pair", best.score, started, deadlines.pair);
    }

    // Search ends before this point. The reserved tail is used only for the
    // independent feasibility check and stdout serialization.
    if (!validateSolution(in, best)) best = fallback;
    traceStage(options.trace, "final", best.score, started, deadlines.final);
    outputSolution(in, best);
}

bool parseStage(const std::string& value, PipelineStage& stage) {
    if (value == "beam-first" || value == "beam_first" || value == "beamfirst") {
        stage = PipelineStage::BeamFirst;
    } else if (value == "base" || value == "b0") {
        stage = PipelineStage::Base;
    } else if (value == "global") {
        stage = PipelineStage::Global;
    } else if (value == "cg" || value == "compatibility-groups" ||
               value == "compatibility_groups") {
        stage = PipelineStage::CompatibilityGroups;
    } else if (value == "remask") {
        stage = PipelineStage::Remask;
    } else if (value == "full" || value == "pair") {
        stage = PipelineStage::Full;
    } else {
        return false;
    }
    return true;
}

}  // namespace

void solvePipeline(const SolverOptions& options) {
    SolverOptions normalized = options;
    normalized.budgetMs = std::max(5, std::min(10000, normalized.budgetMs));
    runConfiguredPipeline(normalized);
}

void solve() {
    solvePipeline(SolverOptions{});
}

int runPipelineMain(int argc, char** argv, PipelineStage defaultStage) {
    SolverOptions options;
    options.stage = defaultStage;
    for (int index = 1; index < argc; ++index) {
        std::string argument = argv[index];
        if (argument == "--help" || argument == "-h") {
            std::cout << "usage: scheduler [--stage beamfirst|base|global|cg|remask|full] "
                         "[--budget-ms N] [--trace]\n"
                         "stages are cumulative: base -> global -> cg -> remask -> "
                         "full(+pair); beamfirst is an external simple baseline\n";
            return 0;
        } else if (argument == "--trace") {
            options.trace = true;
        } else if (argument == "--stage" && index + 1 < argc) {
            if (!parseStage(argv[++index], options.stage)) {
                std::cerr << "unknown pipeline stage\n";
                return 2;
            }
        } else if (argument.rfind("--stage=", 0) == 0) {
            if (!parseStage(argument.substr(8), options.stage)) {
                std::cerr << "unknown pipeline stage\n";
                return 2;
            }
        } else if (argument == "--budget-ms" && index + 1 < argc) {
            if (!parseInt(argv[++index], options.budgetMs) || options.budgetMs < 5) {
                std::cerr << "invalid --budget-ms value\n";
                return 2;
            }
        } else if (argument.rfind("--budget-ms=", 0) == 0) {
            if (!parseInt(argument.substr(12), options.budgetMs) || options.budgetMs < 5) {
                std::cerr << "invalid --budget-ms value\n";
                return 2;
            }
        } else {
            std::cerr << "unknown solver option: " << argument << '\n';
            return 2;
        }
    }
    solvePipeline(options);
    return 0;
}
