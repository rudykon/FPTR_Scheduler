(() => {
  "use strict";

  const translations = {
    zh: {
      title: "FPTR Scheduler · 联合波束与资源调度",
      description: "FPTR：面向截止时间约束的联合波束与资源调度器，以可行性保持的事务式细化持续提升传输量。",
      skip: "跳到主要内容",
      navAria: "主要导航",
      navProblem: "问题",
      navMethod: "方法",
      navEvidence: "证据",
      navReproduce: "复现",
      eyebrow: "联合波束与资源调度 · C++17 / Python",
      heroTitleA: "每一步都守住可行性，",
      heroTitleB: "再把吞吐量往前推。",
      heroBody: "FPTR 面向截止时间约束的无线调度：始终保留一个可发布的可行解，在私有状态中尝试细化，并且只提交完整、及时、合法且更优的候选解。",
      heroArtAlt: "智能基站协调彩色资源块与截止路径",
      heroArtSignal: "智能协同",
      heroArtFeasible: "保持可行",
      heroArtDeadline: "截止时间感知",
      source: "查看源代码",
      explore: "理解 FPTR",
      statBudget: "默认总预算",
      statStages: "累积细化阶段",
      statChecks: "事务提交检查",
      consoleTitle: "一次有界调度运行",
      consoleStatus: "随时可发布",
      consoleInput: "耦合调度实例",
      consoleIncumbent: "当前 incumbent",
      consoleCandidate: "私有候选 C",
      consoleCommit: "验证后提交",
      consoleFinal: "87 ms 前输出合法分配",
      problemKicker: "01 · 为什么难",
      problemTitle: "六类约束不是排队出现，而是同时咬合。",
      problemBody: "波束选择会改变可用速率，资源成员关系会影响共享，缓存上限又会改变每一步的真实收益。任何局部修改，都可能让原本合法的分配越界。",
      constraintBeam: "全局波束预算",
      constraintMask: "子带波束掩码",
      constraintBuffer: "有限用户缓存",
      constraintLink: "阶梯式链路自适应",
      constraintGroup: "兼容组共享约束",
      constraintDeadline: "硬截止时间",
      figureProblemAlt: "调度快照与资源—子带耦合",
      figureProblem: "调度快照与资源—子带耦合。图件来自公开仓库。",
      problemAsideTitle: "传统“先改再修”的风险",
      problemAsideBody: "如果细化直接写入当前解，超时或验证失败时可能只留下一个半成品。FPTR 把候选解隔离开，让失败只损失这次尝试，不损坏已经可用的结果。",
      methodKicker: "02 · 核心方法",
      methodTitle: "像事务一样细化：候选只能整体提交或整体丢弃。",
      methodBody: "I 是始终可发布的 incumbent，C 是隔离构造的候选。四项检查全部通过才执行 I ← C；任一检查失败，I 保持不变。",
      candidateIsolation: "隔离构造候选",
      checkComplete: "候选解完整",
      checkTime: "阶段截止前完成",
      checkValid: "结构验证通过",
      checkImprove: "传输量严格提升",
      pass: "全部通过",
      commit: "COMMIT · 更新 I ← C",
      fail: "任一失败",
      discard: "DISCARD · 保留 I",
      timelineTitle: "有界、累积、按绝对截止点推进",
      timelineBody: "每个阶段继承前一阶段的最好可行解，并拥有独立完成截止点。最后预留时间用于最终验证与序列化。",
      stageBase: "多样化掩码构造首个可行解",
      stageGlobal: "按缓存感知的边际收益全局重定价",
      stageCg: "在兼容组内进行合法多用户共享",
      stageRemask: "根据剩余需求修复掩码与单资源分配",
      stagePair: "双资源 ruin-and-refill，完成 Full 阶段",
      deadline: "最终输出",
      reference: "BeamFirst 是独立参考方法，不进入这条累积链。",
      methodFigureAlt: "完整的有界阶段链与通用事务门",
      methodFigure: "完整的有界阶段链与通用事务门。",
      evidenceKicker: "03 · 公开证据",
      evidenceTitle: "结果不靠一句“更好”，而靠阶段轨迹、压力测试与精确校准。",
      evidenceBody: "公开仓库提供实验协议、独立验证器和绘图脚本。下列图展示累积阶段增益、预算—质量权衡、运行时间分布，以及兼容组压力与小规模精确比较。",
      resultA: "质量与运行时间",
      resultAAlt: "质量与运行时间实验结果",
      resultACaption: "150 个配对实例、每个实例 5 次运行的仓库图件：展示有序阶段增益、分场景提升、预算曲线与 87 ms 运行时间 ECDF。",
      resultB: "压力测试与精确校准",
      resultBAlt: "压力测试与精确校准结果",
      resultBCaption: "兼容组规模压力测试与 12 个小规模精确案例，用于观察鲁棒性并校准相对最优解的差距。",
      release: "Code-only public release",
      evidenceNote: "这是 code-only 公开版本。历史密封结果与论文正文不在仓库中；所有性能主张应由重新生成的工件或单独提供的证据复核。",
      reproduceKicker: "04 · 复现路径",
      reproduceTitle: "从编译到独立验证，只需要三步。",
      reproduceBody: "调度结果写入标准输出；可选阶段轨迹写入标准错误，因此诊断不会污染分配格式。",
      runLabel: "编译并运行 Full",
      validateLabel: "独立验证",
      experimentLabel: "快速实验",
      repoTitle: "一份能被检查的研究代码，而不是黑盒演示。",
      repoBody: "实现、验证器、实验编排和图件生成彼此分离，便于逐层检查模型契约和结论来源。",
      appendix: "证据附录",
      englishAppendix: "英文附录",
      chineseAppendix: "中文附录",
      repoSrc: "C++17 调度器、共享模型与阶段入口",
      repoTools: "独立解析、可行性验证与目标值重算",
      repoExperiments: "确定性实例、实验编排、分析与绘图",
      repoTests: "模型契约与端到端回归测试",
      footer: "可行性保持事务式细化 · 面向截止时间约束的无线调度"
    },
    en: {
      title: "FPTR Scheduler · Joint Beam & Resource Scheduling",
      description: "FPTR applies feasibility-preserving transactional refinement to deadline-aware joint beam and resource scheduling.",
      skip: "Skip to main content",
      navAria: "Main navigation",
      navProblem: "Problem",
      navMethod: "Method",
      navEvidence: "Evidence",
      navReproduce: "Reproduce",
      eyebrow: "Joint beam & resource scheduling · C++17 / Python",
      heroTitleA: "Keep every step feasible.",
      heroTitleB: "Then push traffic further.",
      heroBody: "FPTR targets deadline-constrained wireless scheduling. It always preserves a releasable feasible solution, refines candidates in private state, and commits only candidates that are complete, timely, legal, and strictly better.",
      heroArtAlt: "An intelligent base station coordinates resource blocks along a deadline path",
      heroArtSignal: "Coordinated intelligence",
      heroArtFeasible: "Feasibility preserved",
      heroArtDeadline: "Deadline aware",
      source: "View source",
      explore: "Understand FPTR",
      statBudget: "default total budget",
      statStages: "cumulative refinement stages",
      statChecks: "transactional commit checks",
      consoleTitle: "One bounded scheduling run",
      consoleStatus: "always releasable",
      consoleInput: "Coupled scheduling instance",
      consoleIncumbent: "Current incumbent",
      consoleCandidate: "Private candidate C",
      consoleCommit: "Commit after validation",
      consoleFinal: "Emit a legal allocation before 87 ms",
      problemKicker: "01 · Why it is hard",
      problemTitle: "Six constraint families interlock at the same time.",
      problemBody: "Beam choices change available rates, resource memberships shape sharing, and finite buffers change the real value of every move. A local edit can easily invalidate an otherwise legal allocation.",
      constraintBeam: "Global beam budget",
      constraintMask: "Subband beam masks",
      constraintBuffer: "Finite user buffers",
      constraintLink: "Stepwise link adaptation",
      constraintGroup: "Compatibility-group sharing",
      constraintDeadline: "Hard deadline",
      figureProblemAlt: "Scheduling snapshot and resource–subband coupling",
      figureProblem: "Scheduling snapshot and resource–subband coupling. Figure from the public repository.",
      problemAsideTitle: "The risk of edit-then-repair",
      problemAsideBody: "When refinements mutate the live solution, a timeout or failed validation can leave only a partial result. FPTR isolates candidates, so a failed attempt costs that attempt—not the usable incumbent.",
      methodKicker: "02 · Core method",
      methodTitle: "Refine like a transaction: commit the whole candidate or discard it.",
      methodBody: "I is the always-releasable incumbent and C is an isolated candidate. Only four passing checks trigger I ← C; any failure leaves I untouched.",
      candidateIsolation: "Build candidate in isolation",
      checkComplete: "Candidate is complete",
      checkTime: "Finishes before the stage cutoff",
      checkValid: "Passes structural validation",
      checkImprove: "Strictly improves transmitted traffic",
      pass: "All pass",
      commit: "COMMIT · update I ← C",
      fail: "Any failure",
      discard: "DISCARD · keep I",
      timelineTitle: "Bounded, cumulative, and driven by absolute cutoffs",
      timelineBody: "Each stage inherits the best feasible solution from its predecessor and has its own completion cutoff. The tail is reserved for final validation and serialization.",
      stageBase: "Build the first feasible solution with diversified masks",
      stageGlobal: "Reprice globally with buffer-aware marginal gains",
      stageCg: "Enable legal multi-user sharing inside compatibility groups",
      stageRemask: "Repair masks and one-resource allocation from residual demand",
      stagePair: "Two-resource ruin-and-refill to complete the Full stage",
      deadline: "Final output",
      reference: "BeamFirst is an independent reference method, outside this cumulative chain.",
      methodFigureAlt: "The complete bounded stage chain and common transactional gate",
      methodFigure: "The complete bounded stage chain and common transactional gate.",
      evidenceKicker: "03 · Public evidence",
      evidenceTitle: "The case is made with traces, stress tests, and exact calibration—not a single claim.",
      evidenceBody: "The public repository includes experiment protocols, an independent validator, and plotting scripts. These figures cover stage gains, the budget–quality trade-off, runtime distributions, compatibility-group stress, and small-instance exact comparisons.",
      resultA: "Quality and runtime",
      resultAAlt: "Quality and runtime experiment results",
      resultACaption: "Repository figure over 150 paired instances with five runs each: ordered stage gain, scenario-wise improvement, budget curve, and the 87 ms runtime ECDF.",
      resultB: "Stress and exact calibration",
      resultBAlt: "Stress-test and exact-calibration results",
      resultBCaption: "Compatibility-group size stress plus 12 small exact cases, used to probe robustness and calibrate gaps to optimum.",
      release: "Code-only public release",
      evidenceNote: "This is a code-only public release. Historical sealed results and the manuscript are not in the repository; performance claims should be checked with regenerated artifacts or separately supplied evidence.",
      reproduceKicker: "04 · Reproduction path",
      reproduceTitle: "From compilation to independent validation in three steps.",
      reproduceBody: "Allocations go to standard output; optional stage traces go to standard error, so diagnostics never alter the solution contract.",
      runLabel: "Build and run Full",
      validateLabel: "Validate independently",
      experimentLabel: "Run a quick experiment",
      repoTitle: "Inspectable research code, not a black-box demo.",
      repoBody: "Implementation, validator, experiment harness, and figure generation are separated so the model contract and evidence path can be checked layer by layer.",
      appendix: "Evidence appendices",
      englishAppendix: "English appendix",
      chineseAppendix: "Chinese appendix",
      repoSrc: "C++17 scheduler, shared model, and stage entry points",
      repoTools: "Independent parsing, feasibility checks, and score recomputation",
      repoExperiments: "Deterministic instances, experiment orchestration, analysis, and plots",
      repoTests: "Model-contract and end-to-end regression tests",
      footer: "Feasibility-preserving transactional refinement · Deadline-aware wireless scheduling"
    }
  };

  const localeButtons = Array.from(document.querySelectorAll("[data-locale]"));
  const metaDescription = document.querySelector('meta[name="description"]');

  function applyLocale(locale) {
    const normalized = locale === "en" ? "en" : "zh";
    const strings = translations[normalized];

    document.documentElement.lang = normalized === "zh" ? "zh-CN" : "en";
    document.title = strings.title;
    if (metaDescription) metaDescription.setAttribute("content", strings.description);

    document.querySelectorAll("[data-i18n]").forEach((element) => {
      const key = element.getAttribute("data-i18n");
      if (key && strings[key]) element.textContent = strings[key];
    });

    document.querySelectorAll("[data-i18n-alt]").forEach((element) => {
      const key = element.getAttribute("data-i18n-alt");
      if (key && strings[key]) element.setAttribute("alt", strings[key]);
    });

    document.querySelectorAll("[data-i18n-aria]").forEach((element) => {
      const key = element.getAttribute("data-i18n-aria");
      if (key && strings[key]) element.setAttribute("aria-label", strings[key]);
    });

    localeButtons.forEach((button) => {
      const selected = button.getAttribute("data-locale") === normalized;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });

    try {
      localStorage.setItem("fptr-locale", normalized);
    } catch (_) {
      // The preference is optional; the site remains fully functional without storage.
    }
  }

  localeButtons.forEach((button) => {
    button.addEventListener("click", () => applyLocale(button.getAttribute("data-locale")));
  });

  let initialLocale = "zh";
  try {
    initialLocale = localStorage.getItem("fptr-locale") || "zh";
  } catch (_) {
    initialLocale = "zh";
  }
  applyLocale(initialLocale);
})();
