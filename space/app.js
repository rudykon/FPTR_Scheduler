"use strict";

const COPY = {
  en: {
    eyebrow: "INTERACTIVE SCHEDULER WALKTHROUGH",
    title: "See joint beam and resource scheduling take shape.",
    intro: "Pick a workload, deadline, and FPTR stopping stage. Every view is backed by a validated snapshot produced by the repository's real C++17 scheduler.",
    realSnapshots: "Real C++ snapshots", audit: "Independent validator", freeStatic: "Free static Space",
    configure: "Configure the snapshot", configureHint: "Changes apply instantly—no queue and no server round-trip.",
    scenario: "Traffic scenario", deadline: "Deadline budget", deadlineHint: "The same cutoff controls every compared method.",
    stopStage: "FPTR stopping stage", stageHint: "Later stages may only commit complete, feasible improvements.",
    inspect: "Inspect the incumbent", download: "Download snapshot", transactional: "TRANSACTIONAL REFINEMENT",
    pipelineTitle: "Cumulative incumbent score", pipelineNote: "A stage is accepted only after the candidate passes the full feasibility contract.",
    readChart: "HOW TO READ THIS", whyTransactional: "Why “transactional”?", propose: "Propose", proposeText: "change beams or assignments",
    validate: "Validate", validateText: "check budget, sharing, and subbands", commit: "Commit", commitText: "keep only a complete score gain",
    auditPass: "Audit passed", auditPassText: "score, deadline, and feasibility agree", jointAllocation: "JOINT ALLOCATION",
    allocationTitle: "Who uses each resource block?", none: "None", shared: "Shared", trafficCoverage: "TRAFFIC COVERAGE",
    demandTitle: "Delivered versus unmet demand", maskDesign: "MASK DESIGN", beamTitle: "Active beams by subband",
    verify: "Verify the details", verifyHint: "Trace every accepted stage and every user's served traffic.",
    auditTrail: "Stage audit", userDetail: "User detail", provenance: "Provenance",
    footerText: "Synthetic public scenarios · validated C++17 outputs · browser-only visualization", viewSource: "View source ↗",
    ready: "Validated snapshots ready", loadError: "Could not load snapshots", transmitted: "Transmitted", demandServed: "Demand served",
    versus: "vs BeamFirst", algorithmTime: "Algorithm time", beamBudget: "Beam budget", ofDemand: "of demand", sameBudget: "same instance & budget",
    throughAudit: "through final audit", globalSlots: "global mask slots", users: "users", resources: "resources", beams: "beams",
    subbands: "subbands", groups: "groups", dual: "dual memberships", stage: "Stage", score: "Score", gain: "Gain",
    elapsed: "Elapsed", cutoff: "Cutoff", decision: "Decision", reference: "External reference", validated: "Independently validated",
    improved: "Improved incumbent", retained: "Incumbent retained", cutoffReached: "cutoff reached", user: "User", requested: "Requested",
    delivered: "Delivered", served: "Served", assigned: "Assigned resources", instanceHash: "Instance SHA-256", sourceCommit: "Scheduler source commit",
    snapshotContract: "Snapshot contract", validContract: "Validator passed · score recomputed · allocation feasible", fixedSeed: "Deterministic seed",
    currentStage: "Selected stopping stage", staticNote: "The browser visualizes precomputed outputs from the real scheduler; it does not approximate FPTR in JavaScript.",
    resource: "Resource", shareSize: "Share size", unmet: "Unmet", active: "active", inactive: "off"
  },
  zh: {
    eyebrow: "交互式调度器导览", title: "直观看见联合波束与资源调度如何成形。",
    intro: "选择工作负载、截止时间与 FPTR 停止阶段。每个视图都来自仓库真实 C++17 调度器生成并经独立验证的快照。",
    realSnapshots: "真实 C++ 快照", audit: "独立验证器", freeStatic: "免费 Static Space",
    configure: "配置调度快照", configureHint: "修改立即生效，无需排队或访问后端服务器。",
    scenario: "流量场景", deadline: "截止时间预算", deadlineHint: "所有对比方法使用相同的时间截止条件。",
    stopStage: "FPTR 停止阶段", stageHint: "后续阶段只能提交完整且可行的改进。",
    inspect: "检查当前最优解", download: "下载快照", transactional: "事务式细化",
    pipelineTitle: "累计最优解得分", pipelineNote: "候选方案通过完整可行性契约后，阶段结果才会被接受。",
    readChart: "图表说明", whyTransactional: "为何称为“事务式”？", propose: "提出", proposeText: "修改波束或资源分配",
    validate: "验证", validateText: "检查预算、共享与子带约束", commit: "提交", commitText: "仅保留完整有效的得分提升",
    auditPass: "审计通过", auditPassText: "得分、截止时间与可行性一致", jointAllocation: "联合分配",
    allocationTitle: "每个资源块由谁使用？", none: "未用", shared: "共享", trafficCoverage: "流量覆盖",
    demandTitle: "已传输与未满足需求", maskDesign: "掩码设计", beamTitle: "各子带激活波束",
    verify: "核验详细结果", verifyHint: "追踪每个接受阶段以及每位用户的服务流量。",
    auditTrail: "阶段审计", userDetail: "用户明细", provenance: "结果来源",
    footerText: "合成公开场景 · 经验证的 C++17 输出 · 纯浏览器可视化", viewSource: "查看源码 ↗",
    ready: "验证快照已就绪", loadError: "无法加载快照", transmitted: "已传输", demandServed: "需求满足率",
    versus: "相对 BeamFirst", algorithmTime: "算法时间", beamBudget: "波束预算", ofDemand: "总需求", sameBudget: "相同实例与预算",
    throughAudit: "截至最终审计", globalSlots: "全局掩码槽位", users: "用户", resources: "资源", beams: "波束",
    subbands: "子带", groups: "兼容组", dual: "双子带归属", stage: "阶段", score: "得分", gain: "增益",
    elapsed: "用时", cutoff: "截止", decision: "判定", reference: "外部基线", validated: "已独立验证",
    improved: "最优解提升", retained: "保留原最优解", cutoffReached: "达到截止", user: "用户", requested: "需求",
    delivered: "已传输", served: "满足率", assigned: "分配资源", instanceHash: "实例 SHA-256", sourceCommit: "调度器源码提交",
    snapshotContract: "快照契约", validContract: "验证器通过 · 得分重算一致 · 分配可行", fixedSeed: "确定性种子",
    currentStage: "当前停止阶段", staticNote: "浏览器展示真实调度器预计算输出，并未使用 JavaScript 近似 FPTR。",
    resource: "资源", shareSize: "共享人数", unmet: "未满足", active: "激活", inactive: "关闭"
  }
};

const TRACE_LABELS = {
  beam_first: ["BeamFirst", "BeamFirst"], base: ["Base", "基础"], global: ["Global", "全局"],
  cg: ["CG", "兼容组"], remask: ["Remask", "重掩码"], pair: ["Full · Pair", "完整 · 配对"], final: ["Final audit", "最终审计"]
};

const state = { data: null, language: "en", scenarioId: "medium-tight", budgetIndex: 2, stageId: "full", result: null };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const fmt = new Intl.NumberFormat("en-US");
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
const t = (key) => COPY[state.language][key] || COPY.en[key] || key;
const labelFor = (item) => state.language === "zh" ? item.labelZh : item.label;

function scenario() { return state.data.scenarios.find((item) => item.id === state.scenarioId) || state.data.scenarios[0]; }
function stageMeta() { return state.data.stages.find((item) => item.id === state.stageId); }
function budget() { return state.data.budgets[state.budgetIndex]; }

function applyLanguage() {
  document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";
  $$('[data-i18n]').forEach((node) => { node.textContent = t(node.dataset.i18n); });
  $("#languageToggle").textContent = state.language === "zh" ? "EN" : "中文";
  if ($("#dataStatus").classList.contains("ready")) $("#dataStatus").textContent = t("ready");
  if ($("#dataStatus").classList.contains("error")) $("#dataStatus").textContent = t("loadError");
  if (state.data) {
    populateScenarioOptions();
    populateStageButtons();
    render();
  }
}

function populateScenarioOptions() {
  const select = $("#scenarioSelect");
  select.innerHTML = state.data.scenarios.map((item) => `<option value="${item.id}">${escapeHtml(labelFor(item))}</option>`).join("");
  select.value = state.scenarioId;
}

function populateStageButtons() {
  const container = $("#stageButtons");
  container.innerHTML = state.data.stages.map((item) => `<button type="button" data-stage="${item.id}" class="${item.id === state.stageId ? "active" : ""}">${escapeHtml(labelFor(item))}</button>`).join("");
  container.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => {
    state.stageId = button.dataset.stage;
    populateStageButtons();
    render();
  }));
}

function initializeControls() {
  populateScenarioOptions();
  populateStageButtons();
  const slider = $("#budgetSlider");
  slider.max = String(state.data.budgets.length - 1);
  slider.value = String(state.budgetIndex);
  $("#budgetTicks").innerHTML = state.data.budgets.map((item) => `<span>${item}</span>`).join("");
  $("#scenarioSelect").disabled = false;
  slider.disabled = false;
  $("#downloadButton").disabled = false;
}

function updateKpis(item, current) {
  const inst = item.instance;
  const satisfaction = inst.demand ? 100 * current.score / inst.demand : 0;
  const deltaClass = current.deltaVsBaseline > 0 ? "positive" : "neutral";
  const cards = [
    [t("transmitted"), fmt.format(current.score), `${t("ofDemand")} ${fmt.format(inst.demand)}`, ""],
    [t("demandServed"), `${satisfaction.toFixed(1)}%`, `${current.delivered.filter((value, i) => value >= inst.requested[i]).length}/${inst.users} ${t("users")}`, "positive"],
    [t("versus"), `${current.deltaVsBaseline >= 0 ? "+" : ""}${fmt.format(current.deltaVsBaseline)}`, t("sameBudget"), deltaClass],
    [t("algorithmTime"), `${current.algorithmMs.toFixed(2)} ms`, t("throughAudit"), ""],
    [t("beamBudget"), `${current.beamUsed}/${inst.beamMax}`, t("globalSlots"), ""]
  ];
  $("#kpiGrid").innerHTML = cards.map(([label, value, note, klass]) => `<article class="kpi ${klass}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></article>`).join("");
}

function renderStageChart(current) {
  const host = $("#stageChart");
  host.classList.remove("chart-empty");
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
    return `<line x1="${left}" y1="${yy}" x2="${W-right}" y2="${yy}" stroke="#e4ecf4"/><text x="${left-10}" y="${yy+4}" text-anchor="end" fill="#8190a2" font-size="10">${escapeHtml(fmt.format(Math.round(value)))}</text>`;
  }).join("");
  const path = trace.map((item, i) => `${i ? "L" : "M"}${x(i)},${y(item.score)}`).join(" ");
  const baselineY = y(current.baselineScore);
  const points = trace.map((item, i) => {
    const traceLabel = TRACE_LABELS[item.stage] || [item.stage, item.stage];
    const label = traceLabel[state.language === "zh" ? 1 : 0];
    return `<g><circle cx="${x(i)}" cy="${y(item.score)}" r="6" fill="#2587ff" stroke="#fff" stroke-width="3"/><text x="${x(i)}" y="${y(item.score)-13}" text-anchor="middle" fill="#17324d" font-size="10" font-weight="800">${escapeHtml(fmt.format(item.score))}</text><text x="${x(i)}" y="${H-31}" text-anchor="middle" fill="#52677e" font-size="10" font-weight="700">${escapeHtml(label)}</text><text x="${x(i)}" y="${H-17}" text-anchor="middle" fill="#8a99aa" font-size="8">${item.elapsedMs.toFixed(2)} ms</text></g>`;
  }).join("");
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="FPTR cumulative score chart">${grid}<line x1="${left}" y1="${baselineY}" x2="${W-right}" y2="${baselineY}" stroke="#ffad2f" stroke-width="2" stroke-dasharray="6 6"/><text x="${W-right}" y="${baselineY-7}" text-anchor="end" fill="#d68810" font-size="10" font-weight="800">BeamFirst · ${escapeHtml(fmt.format(current.baselineScore))}</text><path d="${path}" fill="none" stroke="#2587ff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>${points}</svg>`;
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
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, width, height);
  const resourceUsers = current.resourceUsers;
  for (let user = 0; user < N; user += 1) {
    for (let resource = 0; resource < K; resource += 1) {
      const share = resourceUsers[resource].includes(user + 1) ? resourceUsers[resource].length : 0;
      ctx.fillStyle = share === 0 ? "#edf3f8" : share === 1 ? "#9dd6ff" : share === 2 ? "#2587ff" : "#8d4de8";
      ctx.fillRect(left + resource * cellW + .5, top + user * cellH + .5, Math.max(1, cellW - 1), Math.max(1, cellH - 1));
    }
  }
  ctx.fillStyle = "#718399"; ctx.font = "9px system-ui"; ctx.textAlign = "right"; ctx.textBaseline = "middle";
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
  ctx.fillStyle = "#fff"; ctx.fillRect(0,0,width,height);
  ctx.strokeStyle = "#e4ecf4"; ctx.fillStyle = "#8190a2"; ctx.font = "9px system-ui"; ctx.textAlign = "right";
  [0,.25,.5,.75,1].forEach((fraction) => { const yy = top + plotH * (1-fraction); ctx.beginPath(); ctx.moveTo(left,yy);ctx.lineTo(width-5,yy);ctx.stroke();ctx.fillText(fmt.format(Math.round(maxValue*fraction)),left-6,yy+3); });
  for (let i=0;i<N;i+=1) {
    const x = left+i*(barW+gap), deliveredH = delivered[i]/maxValue*plotH, unmetH = (requested[i]-delivered[i])/maxValue*plotH;
    ctx.fillStyle="#2fc66d";ctx.fillRect(x,top+plotH-deliveredH,barW,deliveredH);
    ctx.fillStyle="#dce6ef";ctx.fillRect(x,top+plotH-deliveredH-unmetH,barW,unmetH);
  }
  ctx.fillStyle="#718399";ctx.textAlign="center";const step=N<=20?2:N<=50?5:10;
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

function renderProvenance(item){
  $("#provenanceCard").innerHTML=`<article><span>${t("instanceHash")}</span><code>${escapeHtml(item.sha256)}</code></article><article><span>${t("sourceCommit")}</span><code><a href="https://github.com/rudykon/FPTR_Scheduler/commit/${state.data.schedulerSourceCommit}" target="_blank" rel="noreferrer">${escapeHtml(state.data.schedulerSourceCommit)}</a></code></article><article><span>${t("fixedSeed")}</span><b>${item.seed}</b></article><article><span>${t("currentStage")}</span><b>${escapeHtml(labelFor(stageMeta()))} · ${budget()} ms</b></article><article><span>${t("snapshotContract")}</span><b>${t("validContract")}</b></article><article><span>Static Space</span><b>${t("staticNote")}</b></article>`;
}

function render(){
  if(!state.data)return;
  const item=scenario(),current=item.results[String(budget())][state.stageId];state.result=current;
  $("#budgetValue").textContent=`${budget()} ms`;
  $("#scenarioNote").textContent=state.language==="zh"?item.noteZh:item.note;
  $("#instanceSummary").textContent=`${labelFor(item)} · ${item.instance.users} ${t("users")} · ${item.instance.resources} ${t("resources")} · ${item.instance.beams} ${t("beams")} · ${item.instance.subbands} ${t("subbands")} · ${item.instance.groups} ${t("groups")} · ${item.instance.dualMemberships} ${t("dual")}`;
  updateKpis(item,current);renderStageChart(current);renderAllocation(item,current);renderDemand(item,current);renderBeams(item,current);renderTables(item,current);renderProvenance(item);
}

function downloadSnapshot(){
  const item=scenario();const payload={schemaVersion:state.data.schemaVersion,scenario:item.id,scenarioLabel:labelFor(item),seed:item.seed,budgetMs:budget(),stage:state.stageId,instance:item.instance,instanceSha256:item.sha256,schedulerSourceCommit:state.data.schedulerSourceCommit,result:state.result};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"});const url=URL.createObjectURL(blob);const anchor=document.createElement("a");anchor.href=url;anchor.download=`fptr-${item.id}-${budget()}ms-${state.stageId}.json`;anchor.click();URL.revokeObjectURL(url);
}

function setupTabs(){
  $$(".tab").forEach((button)=>button.addEventListener("click",()=>{$$(".tab").forEach((item)=>{item.classList.toggle("active",item===button);item.setAttribute("aria-selected",item===button?"true":"false");});$$(".tab-panel").forEach((panel)=>panel.classList.remove("active"));$(`#${button.dataset.tab}Tab`).classList.add("active");}));
}

async function start(){
  setupTabs();
  $("#languageToggle").addEventListener("click",()=>{state.language=state.language==="en"?"zh":"en";applyLanguage();});
  $("#scenarioSelect").addEventListener("change",(event)=>{state.scenarioId=event.target.value;render();});
  $("#budgetSlider").addEventListener("input",(event)=>{state.budgetIndex=Number(event.target.value);render();});
  $("#downloadButton").addEventListener("click",downloadSnapshot);
  let resizeTimer;window.addEventListener("resize",()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(render,120);});
  try{
    const response=await fetch("data/results.json",{cache:"no-cache"});if(!response.ok)throw new Error(`HTTP ${response.status}`);state.data=await response.json();
    initializeControls();$("#dataStatus").className="status-pill ready";$("#dataStatus").textContent=t("ready");applyLanguage();
  }catch(error){console.error(error);$("#dataStatus").className="status-pill error";$("#dataStatus").textContent=t("loadError");}
}

start();
