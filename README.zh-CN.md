<p align="center">
  <a href="README.md">English</a> · <strong>简体中文</strong>
</p>

<p align="center">
  <img src="docs/FPTR Scheduler.png" width="520" alt="FPTR Scheduler 品牌标识">
</p>

<h1 align="center">FPTR 联合波束与资源调度器</h1>

<p align="center">
  <strong>面向截止时间约束无线调度的可行性保持事务式细化方法</strong><br>
  一套仅包含代码的 C++17/Python 公开版本，覆盖联合波束规划、资源分配、验证、实验与图件生成。
</p>

<p align="center">
  <a href="https://rudykon.github.io/FPTR_Scheduler/"><img src="https://img.shields.io/badge/项目主页-打开_FPTR-2563EB?style=for-the-badge&logo=googlechrome&logoColor=white" alt="打开 FPTR 项目主页"></a>
  <a href="https://rudykon.github.io/FPTR_Scheduler/demo/"><img src="https://img.shields.io/badge/GitHub_Pages-交互_Demo-9554E8?style=for-the-badge&logo=github&logoColor=white" alt="打开 FPTR 官方交互 Demo"></a>
</p>

<p align="center">
  <a href="https://isocpp.org/"><img src="https://img.shields.io/badge/C%2B%2B-17-00599C?style=flat-square&logo=cplusplus&logoColor=white" alt="C++17"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.x-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3"></a>
  <a href="https://github.com/rudykon/FPTR_Scheduler/actions/workflows/pages.yml"><img src="https://github.com/rudykon/FPTR_Scheduler/actions/workflows/pages.yml/badge.svg" alt="GitHub Pages 自动部署"></a>
  <a href="#validation"><img src="https://img.shields.io/badge/Validation-unittest%20%2B%20validator-2CA02C?style=flat-square" alt="单元测试与验证器"></a>
</p>

<p align="center">
  <a href="https://rudykon.github.io/FPTR_Scheduler/">项目主页</a> ·
  <a href="https://rudykon.github.io/FPTR_Scheduler/demo/">交互 Demo</a> ·
  <a href="#overview">项目概览</a> ·
  <a href="#method">方法</a> ·
  <a href="#visual-summary">图示</a> ·
  <a href="#quick-start">快速开始</a> ·
  <a href="#experiments">实验</a> ·
  <a href="#appendices">附录</a> ·
  <a href="#repository-map">项目结构</a>
</p>

<a id="overview"></a>
## 项目概览

FPTR 是 Feasibility-Preserving Transactional Refinement（可行性保持事务式细化）的缩写，是面向截止时间约束联合波束与资源分配的单线程启发式调度器。它始终保留一个可发布的可行 incumbent，在私有状态中构造每个细化候选，并且只有当候选解完整、及时、结构合法且严格提升传输量时才提交。

| 目标 | 实现方式 | 公开证据路径 |
| --- | --- | --- |
| 在紧截止时间内返回合法分配 | 空分配兜底 + 随时可发布的可行 incumbent | 独立 Python 解析器、验证器和目标值重算 |
| 在耦合约束下提升传输量 | 从 `Base` 到 `Full` 的累积 FPTR 阶段 | 阶段轨迹与可复现合成实验框架 |
| 保持实验输出可审计 | 显式输出到被忽略的本地目录 | 单元测试、快速集成运行和图件生成脚本 |

调度器从标准输入读取一个分配实例，并将分配结果写入标准输出。可选轨迹写入标准错误，因此诊断信息不会改变解的输出格式。

<a id="method"></a>
## 方法

资源容量、用户缓存、波束掩码、兼容组、链路自适应和截止时间彼此耦合。FPTR 通过以下累积阶段处理这种耦合：

| 阶段 | 作用 |
| --- | --- |
| `BeamFirst` | 独立聚合波束掩码参考方法 |
| `Base` | 基于多样化掩码的可行解构造 |
| `Global` | 面向缓存的边际收益重定价 |
| `CG` | 兼容组约束下的合法多用户共享 |
| `Remask` | 基于剩余需求的掩码修复 |
| `Full` | 在前述阶段之后执行双资源 ruin-and-recreate |

各阶段共享同一提交规则：被拒绝、超时、不完整或不可行的候选解不能修改 incumbent。

<a id="visual-summary"></a>
## 图示概览

<p align="center">
  <a href="docs/images/scenario_constraint_coupling.png">
    <img src="docs/images/scenario_constraint_coupling.png" alt="FPTR 问题场景与约束耦合" width="92%">
  </a>
</p>
<p align="center"><em>图 1｜资源容量、用户需求、掩码、共享组、链路自适应和截止时间共同定义耦合调度实例。</em></p>

<p align="center">
  <a href="https://github.com/rudykon/FPTR_Scheduler/blob/main/docs/images/Deadline_Aware_FPTR_Scheduler.pdf">
    <img src="docs/images/Deadline_Aware_FPTR_Scheduler.png?v=20260806-2338" alt="面向截止时间的 FPTR 调度器" width="92%">
  </a>
</p>
<p align="center"><em>图 2｜每个有界细化阶段都构造私有候选解，并且只能通过提交或丢弃验证进入 incumbent。</em></p>

<details>
<summary><strong>展开结果与压力测试图</strong></summary>
<br>

<p align="center">
  <a href="docs/images/results_quality_runtime.png">
    <img src="docs/images/results_quality_runtime.png" alt="FPTR 质量与运行时间结果" width="92%">
  </a>
</p>
<p align="center"><em>图 3｜累积细化在在线运行时间预算内提升分配质量。</em></p>

<p align="center">
  <a href="docs/images/results_stress_optimality.png">
    <img src="docs/images/results_stress_optimality.png" alt="FPTR 压力测试与最优性结果" width="92%">
  </a>
</p>
<p align="center"><em>图 4｜压力测试检验截止时间鲁棒性，小规模精确比较用于校准相对最优解的质量。</em></p>

</details>

<a id="quick-start"></a>
## 快速开始

```bash
git clone https://github.com/rudykon/FPTR_Scheduler.git
cd FPTR_Scheduler

g++ -std=c++17 -O2 src/scheduler.cpp src/core.cpp -o scheduler
./scheduler --help
```

对单个实例运行完整累积调度器：

```bash
./scheduler --stage full --budget-ms 87 < instance.in
```

加入 `--trace` 可查看累积阶段轨迹，同时不改变写入标准输出的分配结果：

```bash
./scheduler --stage full --budget-ms 87 --trace < instance.in > allocation.out
```

<a id="validation"></a>
## 验证

```bash
python3 -m unittest discover -s tests -v
```

测试会在临时目录中编译 C++ 调度器，并检查解析器、可行性规则、链路自适应、兼容组共享、累积阶段轨迹和精确审计辅助函数。

如需独立验证已生成的分配结果，可使用：

```bash
python3 tools/scheduler_validator.py --help
```

<a id="experiments"></a>
## 实验

运行实验脚本时请显式指定输出路径，使生成工件保存在所选本地目录中。

快速集成运行：

```bash
python3 experiments/paper_experiments.py \
  --quick \
  --out /tmp/fptr-quick-results
```

完整协议示例，结果写入被 Git 忽略的本地目录：

```bash
python3 experiments/paper_experiments.py \
  --experiments main,budget,stress,exact \
  --seeds-per-scenario 30 \
  --repeats 5 \
  --stress-seeds 10 \
  --exact-cases 12 \
  --main-budget-ms 87 \
  --budgets 20,40,60,87 \
  --stress-methods Base,CG,Full \
  --deadline-ms 100 \
  --timeout-ms 500 \
  --bootstrap-samples 5000 \
  --bootstrap-seed 20260722 \
  --out artifacts/results
```

重新生成说明图与定量图：

```bash
python3 -m pip install -r requirements-figures.txt
python3 experiments/plot_scheduler_pipeline.py \
  --output artifacts/figures/scheduler_pipeline
python3 experiments/plot_paper_results.py \
  --results-dir artifacts/results \
  --output-dir artifacts/figures
```

生成的结果和图件应放在 `artifacts/` 下，该目录已被 Git 忽略。

<a id="appendices"></a>
## 独立证据附录

公开版本还提供两份独立证据附录：

- [英文附录（PDF）](docs/appendices/Appendix.pdf)
- [中文附录（PDF）](docs/appendices/Appendix_zh.pdf)

附录汇总执行核算、外部基线比较、精确校准和工件完整性。论文正文和文献文件仍不包含在这个以代码为主的公开版本中。

<a id="repository-map"></a>
## 项目结构

| 路径 | 作用 |
| --- | --- |
| `src/` | C++17 调度器实现、共享模型和阶段入口 |
| `tools/scheduler_validator.py` | 独立解析器、可行性验证器和目标值重算工具 |
| `tools/audit_exact_suite.py` | 针对外部结果工件的独立精确审计流程 |
| `experiments/` | 确定性实例生成、实验编排、分析与绘图 |
| `tests/` | 验证器、模型契约和调度器回归测试 |
| `space/` | 浏览器 Demo 源码：实时执行 C++17 WebAssembly，支持自定义输入、独立验证与 JSON 运行记录 |
| `docs/images/` | 用于公开 README 的已确认说明图与结果图 |
| `docs/index.html` | 通过 GitHub Pages 部署的双语静态项目网页 |
| `.github/workflows/pages.yml` | GitHub Pages 自动部署工作流 |
| `PROJECT_OVERVIEW.md` | 模型、算法和组件概览 |
