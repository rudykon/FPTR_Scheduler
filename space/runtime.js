(function attachRuntime(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.FPTRRuntime = api;
})(typeof window !== "undefined" ? window : null, function createRuntime() {
  "use strict";

  const INTEGER_RE = /^-?[0-9]+$/;
  const TRACE_RE = /^TRACE stage=([a-z_]+) score=(-?[0-9]+) elapsed_ms=([0-9]+(?:\.[0-9]+)?) deadline_hit=([01])$/;

  function fail(message) { throw new Error(message); }

  function integer(token, name) {
    if (!INTEGER_RE.test(token)) fail(`${name}: expected an integer, got ${JSON.stringify(token)}`);
    return Number.parseInt(token, 10);
  }

  function finiteNumber(token, name) {
    const value = Number(token);
    if (!Number.isFinite(value)) fail(`${name}: expected a finite number, got ${JSON.stringify(token)}`);
    return value;
  }

  function integerLine(line, name) {
    const tokens = line.trim().split(/\s+/).filter(Boolean);
    if (!tokens.length) fail(`${name}: empty line`);
    return tokens.map((token) => integer(token, name));
  }

  function countedIds(line, name, minimum, maximum, maximumId) {
    const values = integerLine(line, name);
    const count = values[0], ids = values.slice(1);
    if (count < minimum || count > maximum) fail(`${name}: count ${count} outside ${minimum}..${maximum}`);
    if (ids.length !== count) fail(`${name}: declared ${count} ids but found ${ids.length}`);
    if (ids.some((id) => id < 1 || id > maximumId)) fail(`${name}: id outside 1..${maximumId}`);
    if (new Set(ids).size !== ids.length) fail(`${name}: duplicate id`);
    return ids;
  }

  function contractLines(text, name) {
    if (typeof text !== "string") fail(`${name}: expected UTF-8 text`);
    const normalized = text.replace(/\r\n?/g, "\n").replace(/\n+$/, "");
    if (!normalized) fail(`${name}: empty text`);
    return normalized.split("\n");
  }

  function parseCaseText(text, caseId = "browser-input") {
    const lines = contractLines(text, "input");
    if (lines.length < 2) fail("input: expected at least two lines");
    const header = integerLine(lines[0], "header");
    if (header.length !== 5) fail(`header: expected 5 integers, got ${header.length}`);
    const [P, N, K, T, beamMax] = header;
    if (P < 1 || P > 32) fail(`P: ${P} outside 1..32`);
    if (N < 1 || N > 100) fail(`N: ${N} outside 1..100`);
    if (K < 2 || K > 72) fail(`K: ${K} outside 2..72`);
    if (T < 1 || T > 18) fail(`T: ${T} outside 1..18`);
    if (beamMax < 2 || beamMax > 255) fail(`beamMaxNum: ${beamMax} outside 2..255`);

    const mLine = integerLine(lines[1], "M");
    if (mLine.length !== 1) fail("M: expected one integer");
    const M = mLine[0];
    if (M < 0 || M > 16) fail(`M: ${M} outside 0..16`);
    const expectedLines = 3 + M + 2 * N + T;
    if (lines.length !== expectedLines) fail(`input line count ${lines.length} != expected ${expectedLines}`);

    let cursor = 2;
    const ru = [], ruId = Array(N).fill(-1), grouped = new Set();
    for (let group = 0; group < M; group += 1) {
      const users = countedIds(lines[cursor], `RU line ${group + 1}`, 2, 20, N);
      cursor += 1;
      users.forEach((user) => {
        if (grouped.has(user)) fail(`RU line ${group + 1}: user ${user} repeated across groups`);
        grouped.add(user); ruId[user - 1] = group;
      });
      ru.push(users);
    }

    const suIds = countedIds(lines[cursor], "SU line", 0, 29, N);
    cursor += 1;
    suIds.forEach((user) => { if (grouped.has(user)) fail(`SU line: user ${user} also appears in an RU group`); });

    const cap = [], totalCap = [];
    for (let user = 0; user < N; user += 1) {
      const tokens = lines[cursor].trim().split(/\s+/).filter(Boolean);
      cursor += 1;
      if (tokens.length !== P) fail(`cap line ${user + 1}: expected ${P} values, got ${tokens.length}`);
      const values = tokens.map((token, beam) => {
        const value = finiteNumber(token, `cap[${user + 1}][${beam + 1}]`);
        if (value <= 0 || value > 65535) fail(`cap[${user + 1}][${beam + 1}]: outside (0,65535]`);
        return value;
      });
      cap.push(values); totalCap.push(values.reduce((sum, value) => sum + value, 0));
    }

    const buffer = [], sinr = [];
    for (let user = 0; user < N; user += 1) {
      const tokens = lines[cursor].trim().split(/\s+/).filter(Boolean);
      cursor += 1;
      if (tokens.length !== 2) fail(`buffer/sinr line ${user + 1}: expected 2 values`);
      const demand = integer(tokens[0], `buffer[${user + 1}]`);
      const quality = finiteNumber(tokens[1], `sinr[${user + 1}]`);
      if (demand < 1 || demand > 10000) fail(`buffer[${user + 1}]: ${demand} outside 1..10000`);
      if (quality < -30 || quality > 100) fail(`sinr[${user + 1}]: ${quality} outside -30..100`);
      buffer.push(demand); sinr.push(quality);
    }

    const subResources = [], resBands = Array.from({ length: K }, () => []);
    for (let band = 1; band <= T; band += 1) {
      const resources = countedIds(lines[cursor], `RSub line ${band}`, 0, K, K);
      cursor += 1; subResources.push(resources);
      resources.forEach((resource) => resBands[resource - 1].push(band));
    }
    resBands.forEach((bands, resource) => {
      if (bands.length !== 1 && bands.length !== 2) fail(`resource ${resource + 1}: expected one or two subbands, got ${bands.length}`);
    });

    return { caseId, P, N, K, T, beamMax, ru, ruId, su: new Set(suIds), cap, totalCap, buffer, sinr, subResources, resBands };
  }

  function parseSolution(caseData, output) {
    const lines = contractLines(output, "output");
    const expected = caseData.T + caseData.N;
    if (lines.length !== expected) fail(`output line count ${lines.length} != expected ${expected}`);
    const beams = [];
    for (let band = 0; band < caseData.T; band += 1) {
      beams.push(countedIds(lines[band], `beam line ${band + 1}`, 0, caseData.P, caseData.P));
    }
    const beamUsed = beams.reduce((sum, selected) => sum + selected.length, 0);
    if (beamUsed > caseData.beamMax) fail(`beam budget ${beamUsed} > ${caseData.beamMax}`);

    const userResources = [], resourceUsers = Array.from({ length: caseData.K }, () => []);
    for (let user = 1; user <= caseData.N; user += 1) {
      const resources = countedIds(lines[caseData.T + user - 1], `user line ${user}`, 0, caseData.K, caseData.K);
      userResources.push(resources);
      resources.forEach((resource) => resourceUsers[resource - 1].push(user));
    }
    resourceUsers.forEach((users, resource) => {
      if (users.length) {
        caseData.resBands[resource].forEach((band) => {
          if (!beams[band - 1].length) fail(`resource ${resource + 1}: subband ${band} has an empty beam set`);
        });
      }
      if (users.length > 1) {
        const group = caseData.ruId[users[0] - 1];
        if (group < 0 || users.some((user) => caseData.ruId[user - 1] !== group)) {
          fail(`resource ${resource + 1}: shared users are not in one compatibility group`);
        }
      }
    });
    return { beams, userResources, resourceUsers, beamUsed };
  }

  function capOf(fse) {
    if (fse <= -10) return 0;
    if (fse <= 0) return 8;
    if (fse <= 3) return 24;
    if (fse <= 10) return 90;
    if (fse <= 15) return 120;
    if (fse <= 20) return 162;
    return 222;
  }

  function perUserTraffic(caseData, solution) {
    const raw = Array(caseData.N).fill(0);
    for (let resource = 0; resource < caseData.K; resource += 1) {
      const users = solution.resourceUsers[resource];
      if (!users.length) continue;
      const bands = caseData.resBands[resource];
      const denominator = bands[bands.length - 1] - bands[0] + 1;
      users.forEach((userId) => {
        const user = userId - 1;
        let selectedSum = 0;
        bands.forEach((band) => solution.beams[band - 1].forEach((beam) => { selectedSum += caseData.cap[user][beam - 1]; }));
        const selectedAverage = selectedSum / denominator;
        const fse = caseData.sinr[user] + 10 * Math.log10(1 / users.length) + 10 * Math.log10(selectedAverage / caseData.totalCap[user]);
        raw[user] += capOf(fse);
      });
    }
    return raw.map((value, user) => Math.min(caseData.buffer[user], value));
  }

  function cutoffMs(stage, budgetMs) {
    const reserve = budgetMs >= 20 ? 3 : 1;
    const search = Math.max(1, budgetMs - reserve);
    const numerators = { beam_first: 45, base: 45, global: 60, cg: 70, remask: 78, pair: 84, final: null };
    return numerators[stage] === null ? budgetMs : Math.max(1, Math.floor(search * numerators[stage] / 84));
  }

  function parseTrace(stderr, budgetMs) {
    const trace = [];
    stderr.split(/\r?\n/).forEach((line) => {
      const match = TRACE_RE.exec(line.trim());
      if (!match) return;
      trace.push({
        stage: match[1], score: Number(match[2]), elapsedMs: Number(match[3]),
        cutoffMs: cutoffMs(match[1], budgetMs), deadlineHit: match[4] === "1"
      });
    });
    if (!trace.length) fail("scheduler emitted no stage trace");
    return trace;
  }

  function validateRun(caseData, output, stderr, budgetMs, wallMs) {
    const solution = parseSolution(caseData, output);
    const delivered = perUserTraffic(caseData, solution);
    const score = delivered.reduce((sum, value) => sum + value, 0);
    const trace = parseTrace(stderr, budgetMs);
    if (trace[trace.length - 1].score !== score) fail(`trace score ${trace[trace.length - 1].score} != independently recomputed ${score}`);
    for (let index = 1; index < trace.length; index += 1) {
      if (trace[index].score < trace[index - 1].score) fail("stage trace is not monotone");
    }
    return {
      score, beamUsed: solution.beamUsed,
      resourcesUsed: solution.resourceUsers.filter((users) => users.length).length,
      sharedResources: solution.resourceUsers.filter((users) => users.length > 1).length,
      algorithmMs: trace[trace.length - 1].elapsedMs, wallMs,
      deadlineHit: trace.some((entry) => entry.deadlineHit), valid: true, trace,
      beams: solution.beams, resourceUsers: solution.resourceUsers,
      userResources: solution.userResources, delivered, output, traceText: stderr
    };
  }

  function instanceView(caseData) {
    return {
      users: caseData.N, resources: caseData.K, beams: caseData.P, subbands: caseData.T,
      beamMax: caseData.beamMax, groups: caseData.ru.length,
      maxGroup: Math.max(1, ...caseData.ru.map((group) => group.length)),
      dualMemberships: caseData.resBands.filter((bands) => bands.length === 2).length,
      demand: caseData.buffer.reduce((sum, value) => sum + value, 0),
      requested: caseData.buffer.slice(), resourceBands: caseData.resBands.map((bands) => bands.slice())
    };
  }

  return { parseCaseText, parseSolution, parseTrace, validateRun, instanceView, capOf, cutoffMs };
});
