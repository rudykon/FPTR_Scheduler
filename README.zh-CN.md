# FPTR 联合波束与资源调度器

[English](README.md) | **简体中文**

这是 **FPTR（Feasibility-Preserving Transactional Refinement，可行性保持事务式细化）** 面向截止时间约束联合波束与资源分配的纯代码公开版本。

本仓库有意不包含论文正文、编译后的论文、第三方文献 PDF 和封存实验工件。

## 方法概览

单线程 C++17 调度器持续保留一个可行 incumbent，同时由有界细化阶段在私有状态中构造候选解。候选解只有在完整、及时、结构合法且严格提升目标值时才会整体提交；否则直接丢弃，原 incumbent 保持不变。

累积阶段包括：

1. `BeamFirst`：独立的聚合波束掩码参考方法；
2. `Base`：基于多样化掩码的可行解构造；
3. `Global`：面向缓存的边际收益重定价；
4. `CG`：兼容组约束下的合法多用户共享；
5. `Remask`：基于剩余需求的波束掩码修复；
6. `Full`：在上述阶段之后执行双资源 ruin-and-recreate。

## 仓库结构

- `src/`：C++17 调度器实现及各阶段封装；
- `experiments/`：实例生成、实验编排、分析与绘图代码；
- `tools/scheduler_validator.py`：独立解析器、可行性验证器和目标值重算工具；
- `tools/audit_exact_suite.py`：针对外部结果工件的独立精确审计流程；
- `tools/check_paper_release.py`：为可复现工作流保留的发布检查工具；
- `tests/`：验证器、模型契约、调度器和工具回归测试；
- `PROJECT_OVERVIEW.md`：模型、算法和组件概览。

## 编译调度器

```bash
g++ -std=c++17 -O2 src/scheduler.cpp src/core.cpp -o scheduler
```

可执行文件从标准输入读取一个调度实例。例如，选择完整累积阶段和 87 ms 时间预算：

```bash
./scheduler --stage full --budget-ms 87 < instance.in
```

加入 `--trace` 可将阶段诊断写入标准错误，同时不改变标准输出中的分配结果。

## 运行测试

```bash
python3 -m unittest discover -s tests -v
```

测试会在临时目录中编译调度器，并检查输入契约、可行性约束、链路自适应、兼容组共享、累积阶段轨迹和发布检查辅助函数。

## 运行实验

部分实验脚本保留了历史 `paper/...` 默认路径。由于公共仓库不包含论文工件，请显式指定输出路径。

快速集成运行：

```bash
python3 experiments/paper_experiments.py \
  --quick \
  --out /tmp/fptr-quick-results
```

完整协议示例，结果写入已被 Git 忽略的本地目录：

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

## 生成图件

```bash
python3 -m pip install -r requirements-figures.txt
python3 experiments/plot_scheduler_pipeline.py \
  --output artifacts/figures/scheduler_pipeline
python3 experiments/plot_paper_results.py \
  --results-dir artifacts/results \
  --output-dir artifacts/figures
```

生成的结果和图件建议放入 `artifacts/`；该目录默认被 Git 忽略。
