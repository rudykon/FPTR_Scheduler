"use strict";

const APP_SCRIPT = [...document.scripts].find((script) => /\/app\.js(?:\?|$)/.test(script.src));
const DEMO_BASE_URL = new URL(".", APP_SCRIPT ? APP_SCRIPT.src : window.location.href);
const demoAssetUrl = (path) => new URL(path, DEMO_BASE_URL).href;
const rootStyle = getComputedStyle(document.documentElement);
const cssColor = (name) => {
  const value = rootStyle.getPropertyValue(name).trim();
  if (!value) throw new Error(`Missing registered visual color: ${name}`);
  return value;
};
const DEMO_COLORS = Object.freeze({
  primary: cssColor("--signal"),
  baseline: cssColor("--chart-baseline"),
  grid: cssColor("--chart-grid"),
  axis: cssColor("--chart-axis"),
  structure: cssColor("--structure"),
  inkSoft: cssColor("--ink-soft"),
  muted: cssColor("--muted"),
  white: cssColor("--white"),
  share: [
    cssColor("--chart-share-0"),
    cssColor("--chart-share-1"),
    cssColor("--chart-share-2"),
    cssColor("--chart-share-3"),
  ],
  delivered: cssColor("--signal"),
  unmet: cssColor("--chart-unmet"),
});

const COPY = {
  en: {
    demoHeroTitle: "Live Scheduling Demo",
    demoCommit: "Commit",
    eyebrow: "REAL C++17 · WASM",
    intro: "Run FPTR and seven references on the same input and budget.",
    demoRuntimeLine: "C++17 / WASM · local execution · independent validation",
    realSnapshots: "Live C++17 WebAssembly", audit: "Independent validator", freeStatic: "Runs locally in your browser",
    configure: "Run Settings", configureHint: "Choose a scenario and budget, then run all eight methods.",
    scenario: "Traffic scenario", deadline: "Deadline budget", deadlineHint: "The same cutoff controls every compared method.",
    stopStage: "FPTR stopping stage", stageHint: "Later stages may only commit complete, feasible improvements.",
    inspect: "This Run", download: "Export JSON", transactional: "TRANSACTIONAL REFINEMENT",
    pipelineTitle: "Cumulative incumbent score", pipelineNote: "A stage is accepted only after the candidate passes the full feasibility contract.",
    readChart: "HOW TO READ THIS", whyTransactional: "Why “transactional”?", propose: "Propose", proposeText: "change beams or assignments",
    validate: "Validate", validateText: "check budget, sharing, and subbands", commit: "Commit", commitText: "keep only a complete score gain",
    auditPass: "Audit passed", auditPassText: "score, deadline, and feasibility agree", jointAllocation: "JOINT ALLOCATION",
    allocationTitle: "Who uses each resource block?", none: "None", shared: "Shared", trafficCoverage: "TRAFFIC COVERAGE",
    demandTitle: "Delivered versus unmet demand", maskDesign: "MASK DESIGN", beamTitle: "Active beams by subband",
    verify: "Run Audit", verifyHint: "Trace every accepted stage and every user's served traffic.",
    auditTrail: "Stage audit", userDetail: "User detail", provenance: "Provenance",
    footerText: "Real C++17 execution · independent browser validation · no server upload", viewSource: "View source ↗",
    ready: "C++ WebAssembly ready", loadError: "Could not load the WebAssembly demo", transmitted: "Transmitted", demandServed: "Demand served",
    versus: "vs BeamFirst", algorithmTime: "Algorithm time", beamBudget: "Beam budget", ofDemand: "of demand", sameBudget: "same instance & budget",
    throughAudit: "through final audit", globalSlots: "global mask slots", users: "users", resources: "resources", beams: "beams",
    subbands: "subbands", groups: "groups", dual: "dual memberships", stage: "Stage", score: "Score", gain: "Gain",
    elapsed: "Elapsed", cutoff: "Cutoff", decision: "Decision", reference: "External reference", validated: "Independently validated",
    improved: "Improved incumbent", retained: "Incumbent retained", cutoffReached: "cutoff reached", user: "User", requested: "Requested",
    delivered: "Delivered", served: "Served", assigned: "Assigned resources", instanceHash: "Instance SHA-256", sourceCommit: "Scheduler source commit",
    snapshotContract: "Live-run contract", validContract: "Input parsed · output feasible · score recomputed · trace consistent", fixedSeed: "Scenario seed",
    currentStage: "Executed stage", staticNote: "Every row comes from checked-in C++17 code compiled to WebAssembly; no result table or JavaScript approximation is used.",
    resource: "Resource", shareSize: "Share size", unmet: "Unmet", active: "active", inactive: "off",
    engineLoading: "Loading C++ WebAssembly…", engineReady: "FPTR and baseline WebAssembly ready", stale: "Configuration changed · run again",
    running: "Running the live comparison…", runningComparison: "Running comparison", runPassed: "All live runs validated", runError: "Run failed",
    customInput: "Use custom .in file", clearCustom: "Use preset", runReal: "Start Run", runEight: "Run 8 methods",
    advancedSettings: "Advanced Settings",
    advancedResults: "View Detailed Results",
    verificationDetails: "View Run Audit and Raw Output",
    executionNote: "The input is never uploaded; all eight methods use the same instance and budget.",
    presetInput: "Preset input", customInputLabel: "Custom local input", rawOutput: "Raw output",
    solverStdout: "Scheduler stdout", solverTrace: "Scheduler trace", executionMode: "Execution mode",
    runIdentity: "Live run", browserWall: "Browser wall time", liveExecution: "Live C++17 WebAssembly in this browser",
    inputName: "Input source", liveComparison: "8 METHODS · LIVE",
    comparisonTitle: "Algorithm Comparison",
    comparisonHint: "BeamFirst and all six matched search baselines are rescored and constraint-checked by the same independent validator.",
    method: "Method", versusFptr: "vs selected FPTR", searchWork: "Search work", validation: "Validation",
    comparisonNote: "Randomized methods use fixed seeds. Timings and scores come from this browser run, not precomputed results.",
    stagesUnit: "stages", iterationsUnit: "iterations", selectedMethod: "Selected FPTR",
    comparisonCount: "validated C++ / WASM runs",
    comparisonTableDetails: "Open the complete algorithm table",
    demoBoundaryTitle: "Boundary between the Demo and paper timing",
    demoBoundary: "The browser Demo explains one instance. The paper's timing distributions and statistics come from native C++ subprocess experiments and cannot be replaced by one WebAssembly timing.",
    runPrompt: "Choose a scenario and budget, then run all eight methods.",
    resultValidated: "All 8 methods passed independent validation",
    staleNotice: "Parameters changed. These are still the previous run's results.", rerun: "Run again with new parameters",
    recommended: "recommended", paperDefault: "paper default",
    demandDelivery: "Demand delivery", browserAlgorithmTime: "Browser algorithm time", budgetUsed: "of budget",
    scoreComparison: "Scores on the same input and budget",
    comparisonBoundary: "Browser timing explains one instance; paper statistics come from native C++ subprocess experiments.",
    paperResultsLink: "View experimental results →", deepAnalysis: "Deep analysis",
    analysisStage: "Stages", analysisAllocation: "Allocation", analysisUsers: "Users", analysisRecord: "Record",
    stageAuditTitle: "Stage scores and audit", methodGateSummary: "A candidate commits only after completeness, timeliness, legality, and improvement checks pass.",
    methodLink: "Understand the FPTR method →", allocationAnalysisTitle: "Resource allocation", userAnalysisTitle: "User demand",
    recordAnalysisTitle: "Run record", recordHint: "Complete comparison, run identity, and exportable evidence.",
    completeComparison: "Complete algorithm comparison", runProvenance: "Run identity", rawDetails: "View raw stdout and trace"
  },
  zh: {
    demoHeroTitle: "在线调度 Demo", demoCommit: "提交",
    eyebrow: "REAL C++17 · WASM",
    intro: "同一输入、同一预算，实时运行 FPTR 与 7 个参考方法。",
    demoRuntimeLine: "C++17 / WASM · 本地运行 · 独立验证",
    realSnapshots: "实时 C++17 WebAssembly", audit: "独立验证器", freeStatic: "在本地浏览器运行",
    configure: "运行设置", configureHint: "选择场景与预算，再运行 8 种方法。",
    scenario: "流量场景", deadline: "截止时间预算", deadlineHint: "所有对比方法使用相同的时间截止条件。",
    stopStage: "FPTR 停止阶段", stageHint: "后续阶段只能提交完整且可行的改进。",
    inspect: "本次结果", download: "导出 JSON", transactional: "事务式细化",
    pipelineTitle: "累计最优解得分", pipelineNote: "候选方案通过完整可行性契约后，阶段结果才会被接受。",
    readChart: "图表说明", whyTransactional: "为何称为“事务式”？", propose: "提出", proposeText: "修改波束或资源分配",
    validate: "验证", validateText: "检查预算、共享与子带约束", commit: "提交", commitText: "仅保留完整有效的得分提升",
    auditPass: "审计通过", auditPassText: "得分、截止时间与可行性一致", jointAllocation: "联合分配",
    allocationTitle: "每个资源块由谁使用？", none: "未用", shared: "共享", trafficCoverage: "流量覆盖",
    demandTitle: "已传输与未满足需求", maskDesign: "掩码设计", beamTitle: "各子带激活波束",
    verify: "运行审计", verifyHint: "追踪每个接受阶段以及每位用户的服务流量。",
    auditTrail: "阶段审计", userDetail: "用户明细", provenance: "结果来源",
    footerText: "真实 C++17 执行 · 浏览器独立验证 · 输入不上传服务器", viewSource: "查看源码 ↗",
    ready: "C++ WebAssembly 已就绪", loadError: "无法加载 WebAssembly 演示", transmitted: "已传输", demandServed: "需求满足率",
    versus: "相对 BeamFirst", algorithmTime: "算法时间", beamBudget: "波束预算", ofDemand: "总需求", sameBudget: "相同实例与预算",
    throughAudit: "截至最终审计", globalSlots: "全局掩码槽位", users: "用户", resources: "资源", beams: "波束",
    subbands: "子带", groups: "兼容组", dual: "双子带归属", stage: "阶段", score: "得分", gain: "增益",
    elapsed: "用时", cutoff: "截止", decision: "判定", reference: "外部基线", validated: "已独立验证",
    improved: "最优解提升", retained: "保留原最优解", cutoffReached: "达到截止", user: "用户", requested: "需求",
    delivered: "已传输", served: "满足率", assigned: "分配资源", instanceHash: "实例 SHA-256", sourceCommit: "调度器源码提交",
    snapshotContract: "真实运行契约", validContract: "输入解析通过 · 输出可行 · 得分独立重算 · trace 一致", fixedSeed: "场景种子",
    currentStage: "已执行阶段", staticNote: "表中每一行都来自仓库 C++17 源码编译的 WebAssembly；不读取结果表，也不使用 JavaScript 近似算法。",
    resource: "资源", shareSize: "共享人数", unmet: "未满足", active: "激活", inactive: "关闭",
    engineLoading: "正在加载 C++ WebAssembly…", engineReady: "FPTR 与基线 WebAssembly 已就绪", stale: "配置已修改 · 请重新运行",
    running: "正在运行实时算法对比…", runningComparison: "正在对比", runPassed: "全部实时运行与验证通过", runError: "运行失败",
    customInput: "使用自定义 .in 文件", clearCustom: "恢复预设", runReal: "开始运行", runEight: "运行 8 种方法",
    advancedSettings: "高级设置",
    advancedResults: "查看详细结果",
    verificationDetails: "查看运行审计与原始输出",
    executionNote: "输入不会上传；8 种方法使用同一实例和预算。",
    presetInput: "预设输入", customInputLabel: "本地自定义输入", rawOutput: "原始输出",
    solverStdout: "调度器 stdout", solverTrace: "调度器 trace", executionMode: "执行方式",
    runIdentity: "实时运行", browserWall: "浏览器总耗时", liveExecution: "当前浏览器内实时执行 C++17 WebAssembly",
    inputName: "输入来源", liveComparison: "8 METHODS · LIVE",
    comparisonTitle: "算法对比",
    comparisonHint: "BeamFirst 与六种匹配搜索基线的输出均由同一独立验证器重算得分并检查约束。",
    method: "算法", versusFptr: "相对所选 FPTR", searchWork: "搜索工作量", validation: "验证",
    comparisonNote: "随机搜索方法使用固定种子；计时与得分来自本次浏览器运行，不读取预计算结果。",
    stagesUnit: "阶段", iterationsUnit: "次迭代", selectedMethod: "所选 FPTR",
    comparisonCount: "个已验证 C++ / WASM 运行",
    comparisonTableDetails: "展开完整算法比较表",
    demoBoundaryTitle: "Demo 与论文计时的边界",
    demoBoundary: "浏览器 Demo 解释单个实例的算法行为；论文的时延分布与统计结论来自原生 C++ 独立进程实验，不能由一次 WebAssembly 计时替代。",
    runPrompt: "选择场景和预算，然后运行 8 种方法。",
    resultValidated: "8 种方法均通过独立验证",
    staleNotice: "参数已经改变，当前显示的是上一次运行结果。", rerun: "使用新参数重新运行",
    recommended: "推荐", paperDefault: "论文默认",
    demandDelivery: "需求交付", browserAlgorithmTime: "浏览器算法时间", budgetUsed: "预算占用",
    scoreComparison: "同一输入与预算下的得分",
    comparisonBoundary: "浏览器计时用于解释单个实例；论文统计来自原生 C++ 独立进程实验。",
    paperResultsLink: "查看实验结果 →", deepAnalysis: "深入分析",
    analysisStage: "阶段", analysisAllocation: "分配", analysisUsers: "用户", analysisRecord: "记录",
    stageAuditTitle: "阶段得分与审计", methodGateSummary: "候选只有通过完整、及时、合法和更优四项检查才会提交。",
    methodLink: "了解 FPTR 方法 →", allocationAnalysisTitle: "资源分配", userAnalysisTitle: "用户需求",
    recordAnalysisTitle: "运行记录", recordHint: "完整比较、运行身份与可导出记录。",
    completeComparison: "完整算法比较", runProvenance: "运行身份", rawDetails: "查看原始 stdout 与 trace"
  }
};

const TRACE_LABELS = {
  beam_first: ["BeamFirst", "BeamFirst"], base: ["Base", "基础"], global: ["Global", "全局"],
  cg: ["CG", "兼容组"], remask: ["Remask", "重掩码"], pair: ["Full · Pair", "完整 · 配对"], final: ["Final audit", "最终审计"]
};

const EXTERNAL_METHODS = [
  { id: "alns", label: "ALNS" },
  { id: "tabu", label: "Tabu" },
  { id: "ga", label: "GA" },
  { id: "sa", label: "SA" },
  { id: "ils", label: "ILS" },
  { id: "grasp", label: "GRASP" }
];

const state = {
  data: null, module: null, baselineModule: null, comparisonEnabled: false,
  language: document.documentElement.lang.toLowerCase().startsWith("zh") ? "zh" : "en",
  scenarioId: "small-balanced", budgetIndex: 2,
  stageId: "full", customText: null, customName: null, result: null, currentMeta: null,
  currentInput: null, currentHash: null, runSerial: 0, rawOutputRun: 0,
  status: { kind: "loading", key: "engineLoading", detail: "" }
};
const presetCache = new Map();
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const fmt = new Intl.NumberFormat("en-US");
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
const t = (key) => COPY[state.language][key] || COPY.en[key] || key;
const labelFor = (item) => state.language === "zh" ? item.labelZh : item.label;

function scenario() { return state.data.scenarios.find((item) => item.id === state.scenarioId) || state.data.scenarios[0]; }
function stageMeta() { return state.data.stages.find((item) => item.id === state.stageId); }
function budget() { return state.data.budgets[state.budgetIndex]; }
function enginesReady() { return Boolean(state.module && (!state.comparisonEnabled || state.baselineModule)); }

function setStatus(kind, key, detail = "") {
  state.status = { kind, key, detail };
  const node = $("#dataStatus");
  node.className = `status-pill ${kind}`;
  node.textContent = `${t(key)}${detail ? ` · ${detail}` : ""}`;
}

function updateInputSource() {
  const selected = scenario();
  const dimensions = selected.dimensions || {};
  $("#inputSourceLabel").textContent = state.customText ? state.customName : labelFor(selected);
  $("#inputSourceDetail").textContent = state.customText
    ? `${t("customInputLabel")} · ${(new Blob([state.customText]).size / 1024).toFixed(1)} KiB`
    : `${dimensions.users} ${t("users")} · ${dimensions.resources} ${t("resources")} · ${dimensions.beams} ${t("beams")} · ${dimensions.subbands} ${t("subbands")}`;
  $("#scenarioSelect").disabled = Boolean(state.customText) || !enginesReady();
  $("#clearCustomButton").hidden = !state.customText;
}

function markStale() {
  if (state.result) {
    setStatus("stale", "stale");
    $("#results").classList.add("is-stale");
    $("#staleBanner").hidden = false;
  }
  updateInputSource();
  populateBudgetButtons();
  $("#downloadButton").disabled = true;
}

function applyLanguage() {
  document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";
  const scope = $(".demo-app") || document;
  [...scope.querySelectorAll('[data-i18n]')].forEach((node) => { node.textContent = t(node.dataset.i18n); });
  const languageToggle = $("#languageToggle");
  if (languageToggle) languageToggle.textContent = state.language === "zh" ? "EN" : "中文";
  setStatus(state.status.kind, state.status.key, state.status.detail);
  if (state.data) {
    populateScenarioOptions();
    populateBudgetButtons();
    populateStageButtons();
    updateInputSource();
    if (state.result) render();
  }
}

function populateScenarioOptions() {
  const select = $("#scenarioSelect");
  select.innerHTML = state.data.scenarios.map((item) => {
    const suffix = item.id === "small-balanced" ? ` (${t("recommended")})` : "";
    return `<option value="${item.id}">${escapeHtml(labelFor(item) + suffix)}</option>`;
  }).join("");
  select.value = state.scenarioId;
}

function populateBudgetButtons() {
  const container = $("#budgetButtons");
  if (!container || !state.data) return;
  container.innerHTML = state.data.budgets.map((value, index) => {
    const note = value === 87 ? `<span>${escapeHtml(t("paperDefault"))}</span>` : "";
    return `<button type="button" data-budget-index="${index}" aria-pressed="${index === state.budgetIndex ? "true" : "false"}"><b>${value}</b> ms${note}</button>`;
  }).join("");
  container.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => {
    state.budgetIndex = Number(button.dataset.budgetIndex);
    markStale();
  }));
}

function populateStageButtons() {
  const container = $("#stageButtons");
  const fptrStages = state.data.stages.filter((item) => item.id !== "beamfirst");
  container.innerHTML = fptrStages.map((item) => `<button type="button" data-stage="${item.id}" class="${item.id === state.stageId ? "active" : ""}">${escapeHtml(labelFor(item))}</button>`).join("");
  container.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => {
    state.stageId = button.dataset.stage;
    populateStageButtons();
    markStale();
  }));
}

function initializeControls() {
  populateScenarioOptions();
  populateBudgetButtons();
  populateStageButtons();
  $("#scenarioSelect").disabled = !enginesReady();
  $("#runButton").disabled = !enginesReady();
  $("#downloadButton").disabled = true;
  updateInputSource();
}

function updateKpis(item, current) {
  const inst = item.instance;
  const satisfaction = inst.demand ? 100 * current.score / inst.demand : 0;
  const deltaPercent = current.baselineScore ? 100 * current.deltaVsBaseline / current.baselineScore : 0;
  const budgetPercent = item.budgetMs ? 100 * current.algorithmMs / item.budgetMs : 0;
  const deltaClass = current.deltaVsBaseline > 0 ? "positive" : "neutral";
  const cards = [
    [t("demandDelivery"), `${fmt.format(current.score)} / ${fmt.format(inst.demand)}`, `${satisfaction.toFixed(1)}%`, ""],
    [t("versus"), `${current.deltaVsBaseline >= 0 ? "+" : ""}${fmt.format(current.deltaVsBaseline)}`, `${deltaPercent >= 0 ? "+" : ""}${deltaPercent.toFixed(1)}%`, deltaClass],
    [t("browserAlgorithmTime"), `${current.algorithmMs.toFixed(2)} / ${item.budgetMs} ms`, `${budgetPercent.toFixed(1)}% ${t("budgetUsed")}`, ""]
  ];
  $("#kpiGrid").innerHTML = cards.map(([label, value, note, klass]) => `<article class="kpi ${klass}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></article>`).join("");
}

function renderComparison(item, current) {
  const chart = $("#comparisonBars"), body = $("#comparisonBody");
  if (!chart || !body) return;
  const rows = current.comparisons || [];
  if (!rows.length) return;
  const maximum = Math.max(...rows.map((row) => row.result.score), 1);
  chart.innerHTML = rows.map((row) => {
    const width = Math.max(1, 100 * row.result.score / maximum);
    return `<div class="comparison-bar ${row.primary ? "primary" : ""}"><span class="comparison-bar-label">${escapeHtml(row.label)}</span><span class="comparison-bar-track"><i class="comparison-bar-fill" style="width:${width.toFixed(2)}%"></i></span><strong class="comparison-bar-value">${escapeHtml(fmt.format(row.result.score))}</strong></div>`;
  }).join("");

  body.innerHTML = rows.map((row) => {
    const result = row.result;
    const served = item.instance.demand ? 100 * result.score / item.instance.demand : 0;
    const delta = result.score - current.score;
    const percent = current.score ? 100 * delta / current.score : 0;
    const deltaClass = delta > 0 ? "positive" : delta < 0 ? "negative" : "";
    const deltaText = row.primary ? "—" : `${delta >= 0 ? "+" : ""}${fmt.format(delta)} (${percent >= 0 ? "+" : ""}${percent.toFixed(1)}%)`;
    const work = Number.isFinite(result.iterations)
      ? `${fmt.format(result.iterations)} ${t("iterationsUnit")}`
      : `${result.trace.length} ${t("stagesUnit")}`;
    return `<tr class="${row.primary ? "primary-row" : ""}"><td><span class="method-name"><i></i>${escapeHtml(row.label)}</span></td><td><b>${escapeHtml(fmt.format(result.score))}</b></td><td>${served.toFixed(1)}%</td><td><span class="comparison-delta ${deltaClass}">${escapeHtml(deltaText)}</span></td><td>${result.algorithmMs.toFixed(2)} ms</td><td>${escapeHtml(work)}</td><td><span class="pass-badge">✓ ${escapeHtml(t("validated"))}</span></td></tr>`;
  }).join("");
}

function renderStageChart(current) {
  const host = $("#stageChart");
  const trace = current.trace;
  const scores = trace.map((item) => item.score).concat([current.baselineScore]);
  const maxScore = Math.max(...scores, 1);
  const minScore = Math.min(...scores, 0);
  const span = Math.max(1, maxScore - minScore);
  const low = Math.max(0, minScore - span * 0.15);
  const high = maxScore + span * 0.23;
  const W = 900, H = 285, left = 68, right = 24, top = 30, bottom = 58;
  const plotW = W - left - right, plotH = H - top - bottom;
  const x = (i) => trace.length === 1 ? left + plotW / 2 : left + (i * plotW / (trace.length - 1));
  const y = (value) => top + (high - value) * plotH / (high - low);
  const grid = [0, .25, .5, .75, 1].map((fraction) => {
    const value = low + (high - low) * fraction;
    const yy = y(value);
    return `<line x1="${left}" y1="${yy}" x2="${W-right}" y2="${yy}" stroke="${DEMO_COLORS.grid}"/><text x="${left-10}" y="${yy+4}" text-anchor="end" fill="${DEMO_COLORS.axis}" font-size="10">${escapeHtml(fmt.format(Math.round(value)))}</text>`;
  }).join("");
  const path = trace.map((item, i) => `${i ? "L" : "M"}${x(i)},${y(item.score)}`).join(" ");
  const baselineY = y(current.baselineScore);
  const points = trace.map((item, i) => {
    const traceLabel = TRACE_LABELS[item.stage] || [item.stage, item.stage];
    const label = traceLabel[state.language === "zh" ? 1 : 0];
    return `<g><circle cx="${x(i)}" cy="${y(item.score)}" r="6" fill="${DEMO_COLORS.primary}" stroke="${DEMO_COLORS.white}" stroke-width="3"/><text x="${x(i)}" y="${y(item.score)-13}" text-anchor="middle" fill="${DEMO_COLORS.structure}" font-size="10" font-weight="800">${escapeHtml(fmt.format(item.score))}</text><text x="${x(i)}" y="${H-31}" text-anchor="middle" fill="${DEMO_COLORS.inkSoft}" font-size="10" font-weight="700">${escapeHtml(label)}</text><text x="${x(i)}" y="${H-17}" text-anchor="middle" fill="${DEMO_COLORS.muted}" font-size="8">${item.elapsedMs.toFixed(2)} ms</text></g>`;
  }).join("");
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="FPTR cumulative score chart">${grid}<line x1="${left}" y1="${baselineY}" x2="${W-right}" y2="${baselineY}" stroke="${DEMO_COLORS.baseline}" stroke-width="2" stroke-dasharray="6 6"/><text x="${W-right}" y="${baselineY-7}" text-anchor="end" fill="${DEMO_COLORS.baseline}" font-size="10" font-weight="800">BeamFirst · ${escapeHtml(fmt.format(current.baselineScore))}</text><path d="${path}" fill="none" stroke="${DEMO_COLORS.primary}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>${points}</svg>`;
}

function setupCanvas(canvas, logicalWidth, logicalHeight) {
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.style.width = `${logicalWidth}px`;
  canvas.style.height = `${logicalHeight}px`;
  canvas.width = Math.round(logicalWidth * ratio);
  canvas.height = Math.round(logicalHeight * ratio);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return ctx;
}

function bindTooltip(canvas, tooltip, metrics, contentFor) {
  canvas.onmouseleave = () => { tooltip.style.display = "none"; };
  canvas.onmousemove = (event) => {
    const rect = canvas.getBoundingClientRect();
    const point = metrics(event.clientX - rect.left, event.clientY - rect.top);
    if (!point) { tooltip.style.display = "none"; return; }
    tooltip.innerHTML = contentFor(point);
    tooltip.style.display = "block";
    const panelRect = tooltip.parentElement.getBoundingClientRect();
    tooltip.style.left = `${Math.min(event.clientX - panelRect.left + 12, panelRect.width - 170)}px`;
    tooltip.style.top = `${event.clientY - panelRect.top + 12}px`;
  };
}

function renderAllocation(item, current) {
  const canvas = $("#allocationCanvas"), tooltip = $("#allocationTooltip");
  const N = item.instance.users, K = item.instance.resources;
  const left = 42, top = 28, cellW = K <= 36 ? 18 : 12, cellH = N <= 20 ? 15 : N <= 50 ? 9 : 6;
  const width = Math.max(canvas.parentElement.clientWidth - 2, left + K * cellW + 10);
  const height = top + N * cellH + 20;
  const ctx = setupCanvas(canvas, width, height);
  ctx.fillStyle = DEMO_COLORS.white; ctx.fillRect(0, 0, width, height);
  const resourceUsers = current.resourceUsers;
  for (let user = 0; user < N; user += 1) {
    for (let resource = 0; resource < K; resource += 1) {
      const share = resourceUsers[resource].includes(user + 1) ? resourceUsers[resource].length : 0;
      ctx.fillStyle = DEMO_COLORS.share[Math.min(share, DEMO_COLORS.share.length - 1)];
      ctx.fillRect(left + resource * cellW + .5, top + user * cellH + .5, Math.max(1, cellW - 1), Math.max(1, cellH - 1));
    }
  }
  ctx.fillStyle = DEMO_COLORS.axis; ctx.font = "9px system-ui"; ctx.textAlign = "right"; ctx.textBaseline = "middle";
  const userStep = N <= 20 ? 2 : N <= 50 ? 5 : 10;
  for (let user = 0; user < N; user += userStep) ctx.fillText(`U${user+1}`, left - 6, top + user * cellH + cellH / 2);
  ctx.textAlign = "center"; ctx.textBaseline = "bottom";
  const resourceStep = K <= 36 ? 4 : 8;
  for (let resource = 0; resource < K; resource += resourceStep) ctx.fillText(`R${resource+1}`, left + resource * cellW + cellW/2, top - 5);
  bindTooltip(canvas, tooltip, (mx, my) => {
    const resource = Math.floor((mx - left) / cellW), user = Math.floor((my - top) / cellH);
    return resource >= 0 && resource < K && user >= 0 && user < N ? {resource, user} : null;
  }, ({resource, user}) => {
    const users = resourceUsers[resource], assigned = users.includes(user + 1);
    const bands = item.instance.resourceBands[resource].join(", ");
    return `<b>U${user+1} · R${resource+1}</b><br>${t("shareSize")}: ${assigned ? users.length : 0}<br>${t("subbands")}: ${escapeHtml(bands)}`;
  });
}

function renderDemand(item, current) {
  const canvas = $("#demandCanvas"), tooltip = $("#demandTooltip");
  const requested = item.instance.requested, delivered = current.delivered, N = requested.length;
  const left = 45, top = 15, bottom = 34, barW = N <= 20 ? 18 : N <= 50 ? 10 : 7, gap = 2;
  const width = Math.max(canvas.parentElement.clientWidth - 2, left + N * (barW + gap) + 10), height = 320;
  const ctx = setupCanvas(canvas, width, height);
  const maxValue = Math.max(...requested, 1), plotH = height - top - bottom;
  ctx.fillStyle = DEMO_COLORS.white; ctx.fillRect(0,0,width,height);
  ctx.strokeStyle = DEMO_COLORS.grid; ctx.fillStyle = DEMO_COLORS.axis; ctx.font = "9px system-ui"; ctx.textAlign = "right";
  [0,.25,.5,.75,1].forEach((fraction) => { const yy = top + plotH * (1-fraction); ctx.beginPath(); ctx.moveTo(left,yy);ctx.lineTo(width-5,yy);ctx.stroke();ctx.fillText(fmt.format(Math.round(maxValue*fraction)),left-6,yy+3); });
  for (let i=0;i<N;i+=1) {
    const x = left+i*(barW+gap), deliveredH = delivered[i]/maxValue*plotH, unmetH = (requested[i]-delivered[i])/maxValue*plotH;
    ctx.fillStyle=DEMO_COLORS.delivered;ctx.fillRect(x,top+plotH-deliveredH,barW,deliveredH);
    ctx.fillStyle=DEMO_COLORS.unmet;ctx.fillRect(x,top+plotH-deliveredH-unmetH,barW,unmetH);
  }
  ctx.fillStyle=DEMO_COLORS.axis;ctx.textAlign="center";const step=N<=20?2:N<=50?5:10;
  for(let i=0;i<N;i+=step)ctx.fillText(`U${i+1}`,left+i*(barW+gap)+barW/2,height-12);
  bindTooltip(canvas,tooltip,(mx,my)=>{const user=Math.floor((mx-left)/(barW+gap));return user>=0&&user<N&&my>=top&&my<=top+plotH?{user}:null;},({user})=>`<b>U${user+1}</b><br>${t("delivered")}: ${fmt.format(delivered[user])}<br>${t("unmet")}: ${fmt.format(Math.max(0,requested[user]-delivered[user]))}<br>${t("requested")}: ${fmt.format(requested[user])}`);
}

function renderBeams(item, current) {
  const host=$("#beamGrid"), P=item.instance.beams, T=item.instance.subbands;
  host.style.setProperty("--beam-count",P);
  let html='<span></span>'+Array.from({length:P},(_,i)=>`<span class="beam-label">B${i+1}</span>`).join("");
  for(let band=0;band<T;band+=1){html+=`<span class="beam-label">S${band+1}</span>`;for(let beam=1;beam<=P;beam+=1){const active=current.beams[band].includes(beam);html+=`<span class="beam-cell ${active?"active":""}" title="S${band+1} · B${beam} · ${active?t("active"):t("inactive")}"></span>`;}}
  host.innerHTML=html;
}

function renderTables(item,current){
  $("#auditHead").innerHTML=`<tr><th>${t("stage")}</th><th>${t("score")}</th><th>${t("gain")}</th><th>${t("elapsed")}</th><th>${t("cutoff")}</th><th>${t("decision")}</th></tr>`;
  let previous=0;
  $("#auditBody").innerHTML=current.trace.map((entry)=>{const gain=entry.score-previous;previous=entry.score;const labels=TRACE_LABELS[entry.stage]||[entry.stage,entry.stage];let decision=entry.stage==="final"?t("validated"):(gain>0?t("improved"):t("retained"));if(entry.deadlineHit)decision+=` · ${t("cutoffReached")}`;return `<tr><td><b>${escapeHtml(labels[state.language==="zh"?1:0])}</b></td><td>${fmt.format(entry.score)}</td><td>${gain>0?"+":""}${fmt.format(gain)}</td><td>${entry.elapsedMs.toFixed(3)} ms</td><td>${entry.cutoffMs} ms</td><td><span class="pass-badge">✓ ${escapeHtml(decision)}</span></td></tr>`;}).join("");
  $("#usersHead").innerHTML=`<tr><th>${t("user")}</th><th>${t("requested")}</th><th>${t("delivered")}</th><th>${t("served")}</th><th>${t("assigned")}</th></tr>`;
  $("#usersBody").innerHTML=item.instance.requested.map((requested,i)=>{const delivered=current.delivered[i],served=100*delivered/requested,resources=current.userResources[i].map((r)=>`R${r}`).join(", ")||"—";return `<tr><td><b>U${i+1}</b></td><td>${fmt.format(requested)}</td><td>${fmt.format(delivered)}</td><td>${served.toFixed(1)}%</td><td>${escapeHtml(resources)}</td></tr>`;}).join("");
}

function renderProvenance(item, current){
  const executedStage=state.data.stages.find((entry)=>entry.id===item.stageId);
  const stageLabel=executedStage?labelFor(executedStage):item.stageId;
  const seed=item.seed===null||item.seed===undefined?"—":item.seed;
  const hostLabel = location.hostname.endsWith("github.io") ? "GitHub Pages" : "Browser host";
  $("#provenanceCard").innerHTML=`<article><span>${t("instanceHash")}</span><code>${escapeHtml(item.sha256)}</code></article><article><span>${t("sourceCommit")}</span><code><a href="https://github.com/rudykon/FPTR_Scheduler/commit/${state.data.schedulerSourceCommit}" target="_blank" rel="noreferrer">${escapeHtml(state.data.schedulerSourceCommit)}</a></code></article><article><span>${t("inputName")}</span><b>${escapeHtml(item.inputName)}</b></article><article><span>${t("fixedSeed")}</span><b>${escapeHtml(seed)}</b></article><article><span>${t("currentStage")}</span><b>${escapeHtml(stageLabel)} · ${item.budgetMs} ms</b></article><article><span>${t("runIdentity")}</span><b>#${item.runSerial} · ${t("browserWall")} ${current.totalWallMs.toFixed(2)} ms</b></article><article><span>${t("executionMode")}</span><b>${t("liveExecution")}</b></article><article><span>${t("snapshotContract")}</span><b>${t("validContract")}</b></article><article><span>${hostLabel}</span><b>${t("staticNote")}</b></article>`;
}

function populateRawOutput() {
  if (!state.result || !state.currentMeta || state.rawOutputRun === state.currentMeta.runSerial) return;
  $("#rawOutput").textContent = state.result.output;
  $("#rawTrace").textContent = state.result.traceText;
  state.rawOutputRun = state.currentMeta.runSerial;
}

function renderAnalysisPanel(name) {
  if (!state.result || !state.currentMeta) return;
  if (name === "allocation") {
    renderAllocation(state.currentMeta, state.result);
    renderBeams(state.currentMeta, state.result);
  } else if (name === "users") {
    renderDemand(state.currentMeta, state.result);
  } else if (name === "record") {
    renderProvenance(state.currentMeta, state.result);
  }
}

function render(){
  if(!state.result||!state.currentMeta)return;
  const item=state.currentMeta,current=state.result;
  $("#instanceSummary").textContent=`${labelFor(item)} · ${item.instance.users} ${t("users")} · ${item.instance.resources} ${t("resources")} · ${item.instance.beams} ${t("beams")} · ${item.budgetMs} ms`;
  updateKpis(item,current);
  renderComparison(item,current);
  renderStageChart(current);
  renderTables(item,current);
  renderProvenance(item,current);
  const activeTab=$(".analysis-tabs .tab.active")?.dataset.tab;
  if(activeTab)renderAnalysisPanel(activeTab);
}

async function sha256(text){
  const bytes=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(text));
  return [...new Uint8Array(bytes)].map((value)=>value.toString(16).padStart(2,"0")).join("");
}

async function presetInput(item){
  if(presetCache.has(item.id))return presetCache.get(item.id);
  const response=await fetch(demoAssetUrl(item.path),{cache:"no-cache"});
  if(!response.ok)throw new Error(`Could not load ${item.path}: HTTP ${response.status}`);
  const text=await response.text();presetCache.set(item.id,text);return text;
}

function executeOne(input,stage,budgetMs){
  const started=performance.now();
  const raw=state.module.ccall("fptr_run","string",["string","string","number"],[input,stage,budgetMs]);
  const wallMs=performance.now()-started;
  let payload;
  try{payload=JSON.parse(raw);}catch(error){throw new Error(`WebAssembly bridge returned invalid JSON: ${error.message}`);}
  if(!payload.ok)throw new Error(payload.error||"C++ scheduler failed");
  return FPTRRuntime.validateRun(state.activeCase,payload.output,payload.trace,budgetMs,wallMs);
}

function executeExternal(input,method,budgetMs,seed){
  const started=performance.now();
  const raw=state.baselineModule.ccall(
    "fptr_baseline_run","string",["string","string","number","number"],
    [input,method,budgetMs,seed]
  );
  const wallMs=performance.now()-started;
  let payload;
  try{payload=JSON.parse(raw);}catch(error){throw new Error(`Baseline WebAssembly bridge returned invalid JSON: ${error.message}`);}
  if(!payload.ok)throw new Error(payload.error||`${method} baseline failed`);
  return FPTRRuntime.validateExternalRun(
    state.activeCase,payload.output,payload.trace,budgetMs,wallMs,method
  );
}

function controlsBusy(busy){
  $("#runButton").disabled=busy||!enginesReady();
  $("#scenarioSelect").disabled=busy||Boolean(state.customText)||!enginesReady();
  $("#customInput").disabled=busy||!enginesReady();
  $("#clearCustomButton").disabled=busy;
  $$("#budgetButtons button").forEach((button)=>{button.disabled=busy||!enginesReady();});
  $$("#stageButtons button").forEach((button)=>{button.disabled=busy;});
}

function comparisonResult(result){
  return {
    score:result.score,algorithmMs:result.algorithmMs,wallMs:result.wallMs,
    beamUsed:result.beamUsed,resourcesUsed:result.resourcesUsed,
    sharedResources:result.sharedResources,valid:result.valid,
    deadlineHit:result.deadlineHit,iterations:Number.isFinite(result.iterations)?result.iterations:null,
    trace:result.trace.map((entry)=>({...entry}))
  };
}

async function runDemo(){
  if(!enginesReady()||!state.data)return;
  controlsBusy(true);$("#downloadButton").disabled=true;setStatus("running","running");
  await new Promise((resolve)=>requestAnimationFrame(()=>resolve()));
  try{
    const preset=scenario();
    const input=state.customText===null?await presetInput(preset):state.customText;
    const inputName=state.customText===null?preset.path:state.customName;
    const caseData=FPTRRuntime.parseCaseText(input,inputName);
    const digest=await sha256(input);
    if(state.customText===null&&digest!==preset.sha256)throw new Error(`Preset SHA-256 mismatch for ${preset.id}`);
    state.activeCase=caseData;
    const budgetMs=budget();
    const totalRuns=2+(state.comparisonEnabled?EXTERNAL_METHODS.length:0);
    const announce=async(index,label)=>{
      setStatus("running","runningComparison",`${index}/${totalRuns} · ${label}`);
      await new Promise((resolve)=>requestAnimationFrame(()=>resolve()));
    };
    const selectedStage=stageMeta();
    const selectedLabel=`FPTR · ${labelFor(selectedStage)}`;
    await announce(1,selectedLabel);
    const selected=executeOne(input,state.stageId,budgetMs);
    await announce(2,"BeamFirst");
    const baseline=executeOne(input,"beamfirst",budgetMs);
    const comparisons=[
      {id:"fptr",label:selectedLabel,primary:true,result:comparisonResult(selected)},
      {id:"beamfirst",label:"BeamFirst",primary:false,result:comparisonResult(baseline)}
    ];
    let totalWallMs=selected.wallMs+baseline.wallMs;
    const externalSeed=(state.customText===null?preset.seed:Number.parseInt(digest.slice(0,8),16))>>>0;
    if(state.comparisonEnabled){
      for(let index=0;index<EXTERNAL_METHODS.length;index+=1){
        const method=EXTERNAL_METHODS[index];
        await announce(index+3,method.label);
        const result=executeExternal(input,method.id,budgetMs,externalSeed);
        totalWallMs+=result.wallMs;
        comparisons.push({id:method.id,label:method.label,primary:false,seed:externalSeed,result:comparisonResult(result)});
      }
    }
    selected.baselineScore=baseline.score;
    selected.deltaVsBaseline=selected.score-baseline.score;
    selected.totalWallMs=totalWallMs;
    selected.baseline={score:baseline.score,algorithmMs:baseline.algorithmMs,wallMs:baseline.wallMs,output:baseline.output,traceText:baseline.traceText};
    selected.comparisons=comparisons;
    state.runSerial+=1;
    const custom=state.customText!==null;
    const customNote=`${caseData.N} ${t("users")} · ${caseData.K} ${t("resources")} · ${caseData.P} ${t("beams")}`;
    state.currentMeta={
      id:custom?"custom":preset.id,label:custom?state.customName:preset.label,labelZh:custom?state.customName:preset.labelZh,
      note:custom?`Custom local input · ${customNote}`:preset.note,noteZh:custom?`本地自定义输入 · ${customNote}`:preset.noteZh,
      seed:externalSeed,inputName,sha256:digest,stageId:state.stageId,budgetMs,runSerial:state.runSerial,
      instance:FPTRRuntime.instanceView(caseData)
    };
    state.currentInput=input;state.currentHash=digest;state.result=selected;state.rawOutputRun=0;
    const results=$("#results");
    results.hidden=false;
    results.classList.remove("is-stale");
    $("#staleBanner").hidden=true;
    $("#runPrompt").hidden=true;
    $("#rawOutput").textContent="";
    $("#rawTrace").textContent="";
    render();
    if($("#rawDetails").open)populateRawOutput();
    $("#downloadButton").disabled=false;
    setStatus("ready","runPassed",`#${state.runSerial} · ${fmt.format(selected.score)}`);
    await new Promise((resolve)=>requestAnimationFrame(()=>resolve()));
    $("#resultTitle").focus({preventScroll:true});
    results.scrollIntoView({behavior:"smooth",block:"start"});
  }catch(error){
    console.error(error);
    if($("#rawTrace"))$("#rawTrace").textContent=error.stack||String(error);
    setStatus("error","runError",String(error.message||error).slice(0,120));
  }finally{controlsBusy(false);updateInputSource();}
}

function downloadSnapshot(){
  if(!state.result||!state.currentMeta)return;
  const item=state.currentMeta;
  const payload={schemaVersion:2,execution:"live-cpp17-webassembly",runId:item.runSerial,input:{name:item.inputName,sha256:item.sha256,text:state.currentInput},stage:item.stageId,budgetMs:item.budgetMs,schedulerSourceCommit:state.data.schedulerSourceCommit,instance:item.instance,result:state.result};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"});const url=URL.createObjectURL(blob);const anchor=document.createElement("a");anchor.href=url;
  const safeName=item.id.replace(/[^a-z0-9_-]+/gi,"-");anchor.download=`fptr-live-${safeName}-${item.budgetMs}ms-${item.stageId}.json`;anchor.click();URL.revokeObjectURL(url);
}

function setupTabs(){
  const tabs=$$(".analysis-tabs .tab");
  const activate=(button,moveFocus=false)=>{
    tabs.forEach((item)=>{
      const active=item===button;
      item.classList.toggle("active",active);
      item.setAttribute("aria-selected",active?"true":"false");
      item.tabIndex=active?0:-1;
      const panel=$(`#${item.dataset.tab}Tab`);
      panel.classList.toggle("active",active);
      panel.hidden=!active;
    });
    if(moveFocus)button.focus();
    requestAnimationFrame(()=>renderAnalysisPanel(button.dataset.tab));
  };
  tabs.forEach((button,index)=>{
    button.addEventListener("click",()=>activate(button));
    button.addEventListener("keydown",(event)=>{
      let next=null;
      if(event.key==="ArrowRight")next=(index+1)%tabs.length;
      else if(event.key==="ArrowLeft")next=(index-1+tabs.length)%tabs.length;
      else if(event.key==="Home")next=0;
      else if(event.key==="End")next=tabs.length-1;
      if(next===null)return;
      event.preventDefault();activate(tabs[next],true);
    });
  });
  $("#deepAnalysis").addEventListener("toggle",()=>{
    if($("#deepAnalysis").open){const active=$(".analysis-tabs .tab.active");if(active)requestAnimationFrame(()=>renderAnalysisPanel(active.dataset.tab));}
  });
  $("#rawDetails > summary").addEventListener("click",populateRawOutput);
}

async function start(){
  setupTabs();
  state.comparisonEnabled=Boolean($("#comparisonBody"));
  const languageToggle = $("#languageToggle");
  if (languageToggle) {
    languageToggle.addEventListener("click",()=>{state.language=state.language==="en"?"zh":"en";applyLanguage();});
  } else {
    $$('[data-locale]').forEach((button)=>button.addEventListener("click",()=>{
      state.language=button.dataset.locale==="en"?"en":"zh";
      applyLanguage();
    }));
  }
  $("#scenarioSelect").addEventListener("change",(event)=>{state.scenarioId=event.target.value;markStale();});
  $("#runButton").addEventListener("click",runDemo);
  $("#rerunButton").addEventListener("click",runDemo);
  $("#customInput").addEventListener("change",async(event)=>{
    const file=event.target.files&&event.target.files[0];if(!file)return;
    try{
      if(file.size>2*1024*1024)throw new Error("Custom input must be 2 MiB or smaller");
      const text=await file.text();FPTRRuntime.parseCaseText(text,file.name);
      state.customText=text;state.customName=file.name;markStale();
    }catch(error){event.target.value="";console.error(error);setStatus("error","runError",String(error.message||error).slice(0,120));}
  });
  $("#clearCustomButton").addEventListener("click",()=>{state.customText=null;state.customName=null;$("#customInput").value="";markStale();});
  $("#downloadButton").addEventListener("click",downloadSnapshot);
  let resizeTimer;window.addEventListener("resize",()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(render,120);});
  try{
    if(typeof createFPTRModule!=="function")throw new Error("WebAssembly module factory is unavailable");
    if(state.comparisonEnabled&&typeof createFPTRBaselineModule!=="function")throw new Error("Baseline WebAssembly module factory is unavailable");
    const pending=[fetch(demoAssetUrl("data/manifest.json"),{cache:"no-cache"}),createFPTRModule()];
    if(state.comparisonEnabled)pending.push(createFPTRBaselineModule());
    const [response,module,baselineModule]=await Promise.all(pending);
    if(!response.ok)throw new Error(`Manifest HTTP ${response.status}`);
    state.data=await response.json();state.module=module;state.baselineModule=baselineModule||null;
    initializeControls();setStatus("ready","engineReady");applyLanguage();
  }catch(error){console.error(error);setStatus("error","loadError",String(error.message||error).slice(0,120));}
}

start();
