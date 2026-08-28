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
    users: "users", resources: "resources", beams: "beams", subbands: "subbands",
    stage: "Stage", score: "Score", gain: "Gain", elapsed: "Elapsed", cutoff: "Cutoff", decision: "Decision",
    versus: "vs BeamFirst", validated: "Independently validated",
    improved: "Improved incumbent", retained: "Incumbent retained", cutoffReached: "cutoff reached", user: "User", requested: "Requested",
    delivered: "Delivered", served: "Served", assigned: "Assigned resources", instanceHash: "Instance SHA-256", sourceCommit: "Scheduler source commit",
    snapshotContract: "Live-run contract", validContract: "Input parsed · output feasible · score recomputed · trace consistent", fixedSeed: "Scenario seed",
    currentStage: "Executed stage", staticNote: "Every row comes from checked-in C++17 code compiled to WebAssembly; no result table or JavaScript approximation is used.",
    shareSize: "Share size", unmet: "Unmet", active: "active", inactive: "off",
    engineReady: "FPTR and baseline WebAssembly ready", stale: "Configuration changed · run again",
    running: "Running the live comparison…", runningComparison: "Running comparison", runError: "Run failed",
    loadError: "Could not load the WebAssembly demo", customInputLabel: "Custom local input", executionMode: "Execution mode",
    runIdentity: "Live run", browserWall: "Browser wall time", liveExecution: "Live C++17 WebAssembly in this browser",
    inputName: "Input source", browserHost: "Browser host",
    stagesUnit: "stages", iterationsUnit: "iterations",
    recommended: "recommended", paperDefaultTitle: "paper internal budget",
    demandDelivery: "Demand delivery", fptrAlgorithmTime: "FPTR internal algorithm time", selectedStageTime: "Selected-stage internal time", budgetUsed: "Internal budget used",
    browserFptrWall: "This browser's FPTR wall time", timingContract: "Timing contract",
    stageChartAria: "FPTR cumulative score by refinement stage"
  },
  zh: {
    users: "用户", resources: "资源", beams: "波束", subbands: "子带",
    stage: "阶段", score: "得分", gain: "增益", elapsed: "用时", cutoff: "截止", decision: "判定",
    versus: "相对 BeamFirst", validated: "已独立验证",
    improved: "最优解提升", retained: "保留原最优解", cutoffReached: "达到截止", user: "用户", requested: "需求",
    delivered: "已传输", served: "满足率", assigned: "分配资源", instanceHash: "实例 SHA-256", sourceCommit: "调度器源码提交",
    snapshotContract: "真实运行契约", validContract: "输入解析通过 · 输出可行 · 得分独立重算 · trace 一致", fixedSeed: "场景种子",
    currentStage: "已执行阶段", staticNote: "表中每一行都来自仓库 C++17 源码编译的 WebAssembly；不读取结果表，也不使用 JavaScript 近似算法。",
    shareSize: "共享人数", unmet: "未满足", active: "激活", inactive: "关闭",
    engineReady: "FPTR 与基线 WebAssembly 已就绪", stale: "配置已修改 · 请重新运行",
    running: "正在运行实时算法对比…", runningComparison: "正在对比", runError: "运行失败",
    loadError: "无法加载 WebAssembly 演示", customInputLabel: "本地自定义输入", executionMode: "执行方式",
    runIdentity: "实时运行", browserWall: "浏览器总耗时", liveExecution: "当前浏览器内实时执行 C++17 WebAssembly",
    inputName: "输入来源", browserHost: "浏览器主机",
    stagesUnit: "阶段", iterationsUnit: "次迭代",
    recommended: "推荐", paperDefaultTitle: "论文内部预算",
    demandDelivery: "需求交付", fptrAlgorithmTime: "FPTR 内部算法时间", selectedStageTime: "所选阶段内部时间", budgetUsed: "内部预算占用",
    browserFptrWall: "本次浏览器 FPTR 墙钟", timingContract: "时间契约",
    stageChartAria: "FPTR 各细化阶段的累计得分图"
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
  scenarioId: "small-balanced", budgetMs: 87,
  stageId: "full", customText: null, customName: null, result: null, currentMeta: null,
  currentInput: null, currentHash: null, runSerial: 0, rawOutputRun: 0
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
function budget() { return state.budgetMs; }
function timing() { return state.data.timing; }
function externalDeadline() { return timing().externalDeadlineMs; }
function enginesReady() { return Boolean(state.module && (!state.comparisonEnabled || state.baselineModule)); }

function setStatus(kind, key, detail = "") {
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
  syncBudgetControl();
  $("#downloadButton").disabled = true;
}

function populateScenarioOptions() {
  const select = $("#scenarioSelect");
  select.innerHTML = state.data.scenarios.map((item) => {
    const suffix = item.id === "small-balanced" ? ` (${t("recommended")})` : "";
    return `<option value="${item.id}">${escapeHtml(labelFor(item) + suffix)}</option>`;
  }).join("");
  select.value = state.scenarioId;
}

function syncBudgetControl() {
  const slider = $("#budgetSlider");
  const control = $("#budgetControl");
  if (!slider || !control || !state.data) return;
  const config = timing().internalBudget;
  const minimum = config.minimumMs;
  const maximum = config.maximumMs;
  const paperDefault = config.paperMs;
  state.budgetMs = Math.min(maximum, Math.max(minimum, Math.round(state.budgetMs)));
  const progress = 100 * (state.budgetMs - minimum) / Math.max(1, maximum - minimum);
  slider.min = String(minimum);
  slider.max = String(maximum);
  slider.step = String(config.stepMs);
  slider.value = String(state.budgetMs);
  slider.setAttribute(
    "aria-valuetext",
    `${state.budgetMs} ms${state.budgetMs === paperDefault ? ` · ${t("paperDefaultTitle")}` : ""}`
  );
  control.style.setProperty("--budget-progress", `${progress.toFixed(3)}%`);
  $("#budgetValue").value = `${state.budgetMs} ms`;
  $("#budgetValue").textContent = `${state.budgetMs} ms`;
  $("#budgetMin").textContent = `${minimum} ms`;
  $("#budgetPaperDefaultValue").textContent = `${paperDefault} ms`;
  $("#externalDeadlineValue").textContent = `D = ${externalDeadline()} ms`;
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
  syncBudgetControl();
  populateStageButtons();
  $("#scenarioSelect").disabled = !enginesReady();
  $("#budgetSlider").disabled = !enginesReady();
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
  const timeLabel = item.stageId === "full" ? t("fptrAlgorithmTime") : t("selectedStageTime");
  const cards = [
    [t("demandDelivery"), `${fmt.format(current.score)} / ${fmt.format(inst.demand)}`, `${satisfaction.toFixed(1)}%`, ""],
    [t("versus"), `${current.deltaVsBaseline >= 0 ? "+" : ""}${fmt.format(current.deltaVsBaseline)}`, `${deltaPercent >= 0 ? "+" : ""}${deltaPercent.toFixed(1)}%`, deltaClass],
    [timeLabel, `${current.algorithmMs.toFixed(2)} ms / B = ${item.budgetMs} ms`, `${t("budgetUsed")} ${budgetPercent.toFixed(1)}%`, ""]
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
    return `<line x1="${left}" y1="${yy}" x2="${W-right}" y2="${yy}" stroke="${DEMO_COLORS.grid}"/><text x="${left-10}" y="${yy+4}" text-anchor="end" fill="${DEMO_COLORS.axis}" font-size="12">${escapeHtml(fmt.format(Math.round(value)))}</text>`;
  }).join("");
  const path = trace.map((item, i) => `${i ? "L" : "M"}${x(i)},${y(item.score)}`).join(" ");
  const baselineY = y(current.baselineScore);
  const points = trace.map((item, i) => {
    const traceLabel = TRACE_LABELS[item.stage] || [item.stage, item.stage];
    const label = traceLabel[state.language === "zh" ? 1 : 0];
    return `<g><circle cx="${x(i)}" cy="${y(item.score)}" r="6" fill="${DEMO_COLORS.primary}" stroke="${DEMO_COLORS.white}" stroke-width="3"/><text x="${x(i)}" y="${y(item.score)-13}" text-anchor="middle" fill="${DEMO_COLORS.structure}" font-size="13" font-weight="800">${escapeHtml(fmt.format(item.score))}</text><text x="${x(i)}" y="${H-31}" text-anchor="middle" fill="${DEMO_COLORS.inkSoft}" font-size="12" font-weight="700">${escapeHtml(label)}</text><text x="${x(i)}" y="${H-16}" text-anchor="middle" fill="${DEMO_COLORS.muted}" font-size="11">${item.elapsedMs.toFixed(2)} ms</text></g>`;
  }).join("");
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeHtml(t("stageChartAria"))}">${grid}<line x1="${left}" y1="${baselineY}" x2="${W-right}" y2="${baselineY}" stroke="${DEMO_COLORS.baseline}" stroke-width="2" stroke-dasharray="6 6"/><text x="${W-right}" y="${baselineY-8}" text-anchor="end" fill="${DEMO_COLORS.baseline}" font-size="12" font-weight="800">BeamFirst · ${escapeHtml(fmt.format(current.baselineScore))}</text><path d="${path}" fill="none" stroke="${DEMO_COLORS.primary}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>${points}</svg>`;
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
  ctx.fillStyle = DEMO_COLORS.axis; ctx.font = "12px system-ui"; ctx.textAlign = "right"; ctx.textBaseline = "middle";
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
  ctx.strokeStyle = DEMO_COLORS.grid; ctx.fillStyle = DEMO_COLORS.axis; ctx.font = "12px system-ui"; ctx.textAlign = "right";
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
  const hostLabel = location.hostname.endsWith("github.io") ? "GitHub Pages" : t("browserHost");
  $("#provenanceCard").innerHTML=`<article><span>${t("instanceHash")}</span><code>${escapeHtml(item.sha256)}</code></article><article><span>${t("sourceCommit")}</span><code><a href="https://github.com/rudykon/FPTR_Scheduler/commit/${state.data.schedulerSourceCommit}" target="_blank" rel="noreferrer">${escapeHtml(state.data.schedulerSourceCommit)}</a></code></article><article><span>${t("inputName")}</span><b>${escapeHtml(item.inputName)}</b></article><article><span>${t("fixedSeed")}</span><b>${escapeHtml(seed)}</b></article><article><span>${t("currentStage")}</span><b>${escapeHtml(stageLabel)}</b></article><article><span>${t("timingContract")}</span><b>B = ${item.budgetMs} ms · D = ${item.externalDeadlineMs} ms</b></article><article><span>${t("runIdentity")}</span><b>#${item.runSerial} · ${t("browserWall")} ${current.totalWallMs.toFixed(2)} ms</b></article><article><span>${t("executionMode")}</span><b>${t("liveExecution")}</b></article><article><span>${t("snapshotContract")}</span><b>${t("validContract")}</b></article><article><span>${hostLabel}</span><b>${t("staticNote")}</b></article>`;
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
  const executedStage=state.data.stages.find((entry)=>entry.id===item.stageId);
  const stageLabel=executedStage?labelFor(executedStage):item.stageId;
  $("#instanceSummary").textContent=`${labelFor(item)} · ${stageLabel} · ${item.instance.users} ${t("users")} · ${item.instance.resources} ${t("resources")} · ${item.instance.beams} ${t("beams")} · B = ${item.budgetMs} ms · D = ${item.externalDeadlineMs} ms`;
  $("#browserTimingSummary").textContent=`${t("browserFptrWall")}: ${current.wallMs.toFixed(2)} ms`;
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
  $("#budgetSlider").disabled=busy||!enginesReady();
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
    const selectedLabel=state.stageId==="full"?"FPTR":`FPTR · ${labelFor(selectedStage)}`;
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
      seed:externalSeed,inputName,sha256:digest,stageId:state.stageId,budgetMs,externalDeadlineMs:externalDeadline(),runSerial:state.runSerial,
      instance:FPTRRuntime.instanceView(caseData)
    };
    state.currentInput=input;state.currentHash=digest;state.result=selected;state.rawOutputRun=0;
    const results=$("#results");
    results.hidden=false;
    results.classList.remove("is-stale");
    $("#staleBanner").hidden=true;
    $("#rawOutput").textContent="";
    $("#rawTrace").textContent="";
    render();
    if($("#rawDetails").open)populateRawOutput();
    $("#downloadButton").disabled=false;
    setStatus("ready","engineReady");
    await new Promise((resolve)=>requestAnimationFrame(()=>resolve()));
    $("#resultTitle").focus({preventScroll:true});
    const reducedMotion=matchMedia("(prefers-reduced-motion: reduce)").matches;
    results.scrollIntoView({behavior:reducedMotion?"auto":"smooth",block:"start"});
  }catch(error){
    console.error(error);
    if($("#rawTrace"))$("#rawTrace").textContent=error.stack||String(error);
    setStatus("error","runError",String(error.message||error).slice(0,120));
  }finally{controlsBusy(false);updateInputSource();}
}

function downloadSnapshot(){
  if(!state.result||!state.currentMeta)return;
  const item=state.currentMeta;
  const payload={schemaVersion:3,execution:"live-cpp17-webassembly",runId:item.runSerial,input:{name:item.inputName,sha256:item.sha256,text:state.currentInput},stage:item.stageId,timing:{internalBudgetMs:item.budgetMs,externalDeadlineMs:item.externalDeadlineMs,browserFptrWallMs:state.result.wallMs,browserWallScope:"single-fptr-wasm-call",paperDeadlineScope:"native-cpp-subprocess-wall"},schedulerSourceCommit:state.data.schedulerSourceCommit,instance:item.instance,result:state.result};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"});const url=URL.createObjectURL(blob);const anchor=document.createElement("a");anchor.href=url;
  const safeName=item.id.replace(/[^a-z0-9_-]+/gi,"-");anchor.download=`fptr-live-${safeName}-B${item.budgetMs}ms-D${item.externalDeadlineMs}ms-${item.stageId}.json`;anchor.click();URL.revokeObjectURL(url);
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
  $("#scenarioSelect").addEventListener("change",(event)=>{state.scenarioId=event.target.value;markStale();});
  $("#budgetSlider").addEventListener("input",(event)=>{state.budgetMs=Number(event.target.value);markStale();});
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
    initializeControls();setStatus("ready","engineReady");
  }catch(error){console.error(error);setStatus("error","loadError",String(error.message||error).slice(0,120));}
}

start();
