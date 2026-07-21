# 实验报告 / Experiment Report — QEA Quant/Finance Benchmark 权威性与演化适配性筛选
> 日期/Date: 2026-07-21 · 实验/Experiment: Benchmark Authority & Provenance Screen · 项目/Project: evolving-quant-agent (QEA) · 性质/Type: desk investigation，未运行新 benchmark、未修改框架

---

## 0. 结论摘要 / Executive Summary

**结论：本轮筛选已经明确了不同 benchmark 的权威性、任务形态、grader 和能力覆盖，但尚不能据此直接决定主演化应采用单一 benchmark 还是多个 benchmark。** 当前证据支持形成候选能力地图，而不是把某一种 benchmark suite 提前写成定案：

| 候选能力 | 代表 benchmark | 当前可支持的判断 |
|---|---|---|
| 确定性 quant 任务 | QFBench | reward 最适合观察代码、分析和产物执行能力是否发生变化 |
| 企业财务工作流 | FINCH / FinWorkBench | 更接近 spreadsheet、email、PDF 等组合式 enterprise workflow |
| 投行业务交付物 | BankerToolBench (BTB) | 更接近 banker-authored / banker-validated 的端到端交付任务 |
| 权威专业任务迁移 | GDPval Finance、PRBench Finance | 适合检验提升能否迁移到专家构造的专业任务，但不宜直接视为高频演化 reward |

单 benchmark 还是多 benchmark、是否需要 held-out、以及多 benchmark 应选择相近类别还是互补能力，仍需通过小规模实验决定。

最重要的三项校正：

1. **GDPval 已是 ICLR 2026 主会 Poster**，不再只是 OpenAI report / arXiv。
2. **QFBench 目前是 NeurIPS 2026 submission，不是已录用论文**；保留它是因为 quant 纯度与确定性 reward，而不是 venue。
3. **没有候选可被称为“大银行内部数据集”**。BankerToolBench 和 APEX-Agents 的优势是大行背景从业者参与创建/验证；数据本身主要是公共、标准化或模拟材料。

---

## 1. 实验过程与结果 / Process & Results

### 1.1 目标 / Goal

在不大改 QEA 框架的前提下，从已有候选中筛出一个或一组 benchmark，用于证明：**evolver 能否持续改进 quant/finance worker，并把提升迁移到真实金融工作流。** 本轮额外加入“论文权威性、数据来源可靠性、使用许可”硬筛选，避免只因任务形态好接就选入。

### 1.2 方法与过程 / Method & Process

本轮是 source-grounded desk investigation，没有执行 adapter pilot。每项 benchmark 分别核验：

- **Publication authority**：顶会主会、Datasets & Benchmarks Track、Findings、非存档 workshop、arXiv/company benchmark 分开记录。
- **Data provenance**：真实企业 workspace、专业人士按实际工作构造、公开 SEC/IR/市场数据、比赛数据、模拟 world 分开记录。
- **Reward reliability**：确定性 unit tests、程序 metric、rubric + LLM judge、human pairwise 分开记录。
- **Evolution compatibility**：是否有标量分数、是否能反复运行、是否存在 hidden split、gold/rubric 泄漏、许可证是否允许 scaffold selection。
- **Project fit**：结合 QEA 已有 GDPval/FAB 实验结果与 DSBench source audit，区分“有权威”与“有可恢复 headroom”。

权威性评级口径：`S` = 顶会主会或正式顶会 Datasets & Benchmarks Track；`A` = Findings 或严格行业/企业数据流程；`B` = arXiv、company benchmark、非存档 workshop 或 community project。Venue、数据与 reward 分开判断，不用单一标签掩盖短板。

### 1.3 数据与结果 / Data & Results

#### A. 通过筛选的主要候选

| Benchmark | Publication authority | 数据 provenance | Reward / 复现 | 本项目角色 | 结论 |
|---|---|---|---|---|---|
| **GDPval** | **S：ICLR 2026 主会 Poster**（[official](https://iclr.cc/virtual/2026/poster/10008039)） | 完整集 1,320 题、公开 gold 220 题；44 职业、9 行业；任务由平均 14 年经验的行业专家制作与多轮审核 | human/model pairwise + 公共自动评分；公开 gold、rubric 和 reference deliverable 带来反复优化泄漏风险 | 冻结 external transfer | **最高权威锚点；不做高频主演化 reward** |
| **PRBench Finance** | **S：ACL 2026 主会 Long Paper**（[paper](https://aclanthology.org/2026.acl-long.1958/)） | 总计 1,100 个 Finance/Law 任务；Finance 600、Finance-Hard 300；182 名持 CFA/JD 或至少 6 年经验的专业人士参与 | rubric 与代码公开；主要依赖 LLM judge，不是 deterministic verifier | finance reasoning confirm | **强保留；不能单独证明 agentic tool/workspace 能力** |
| **FINCH / FinWorkBench** | **A：ACL 2026 Findings**，不是 ACL main（[paper](https://aclanthology.org/2026.findings-acl.523/)） | 172 个 composite workflows、384 个任务、1,710 张 spreadsheets、约 2,700 万 cells；真实企业 workspace + 700+ 小时专家标注 | 数据、reference、预处理和 GPT-judge pipeline 公开；自动评分仍有 judge variance | 低频真实工作流 promotion | **最接近 enterprise finance/accounting workflow** |
| **QFBench** | **B：NeurIPS 2026 submission，未核实录用**（[paper](https://qfbench.com/qfbench_paper_v0.pdf)） | 截至调查时约 87 个 practitioner-authored quant tasks，覆盖 derivatives、risk、market microstructure、factor research、credit 等；不是银行内部数据 | Harbor/Docker + pytest；headline reward 严格 `0/1`；tests/oracle 公开，需 evaluator firewall | 高频主演化 | **工程核心首选；用其他 benchmark 补足学术权威** |
| **BankerToolBench (BTB)** | **B+：arXiv + 非存档 workshop poster**，不是顶会主会（[paper](https://arxiv.org/abs/2604.11304)） | 100 个投行端到端任务；502 名现/前 banker 参与整体研究，其中 172 人直接创题/审题；背景包括 BofA、Citi、GS、JPM、MS、UBS 等 | weighted criterion score；Gandalf 可打开 Excel/PPT 并检查产物，但核心仍是 agentic verifier | 低频 banking core/checkpoint | **最接近“大行经验来源”，但不是大行内部数据** |
| **DSBench ModelOff 分支** | **S：ICLR 2025 主会**（[paper](https://proceedings.iclr.cc/paper_files/paper/2025/hash/50e9ad960ae78b741a6b4fea533f2eaf-Abstract-Conference.html)） | 466 个 analysis 任务来自 ModelOff/Eloquence challenge；另有 74 个 Kaggle modeling 任务，后者不能全部算 finance | 答案比较、语义 judge 与运行 metric 混合；第三方数据权利需单独审计 | 候选 analysis baseline/control，尚未在当前仓库完成可审计 run | **条件保留；不替代 quant 主线** |
| **MBABench** | **B：arXiv preprint，未核实正式录用**（[paper](https://arxiv.org/abs/2605.22664)） | end-to-end finance workbook，来源包括 ModelOff、FMWC、Wall Street Prep | composite = Accuracy 50% + Formula 35% + Format 15%；包含 LLM judge；第三方数据许可不由代码 MIT 自动覆盖 | Excel modeling secondary | **先限于权利清楚、与 DSBench 去重的 ModelOff 子集** |

#### B. 降级、辅助或暂不进入 optimize 的候选

| Benchmark | 决定 | 主要证据与原因 |
|---|---|---|
| **APEX-Agents IB** | **从 optimize 池剔除** | IB 有 160 题/10 worlds，且有大行背景专家参与；但官方 data card 明确 worlds 为 hypothetical/simulated，并限定 exclusively for evaluation，禁止 training、fine-tuning、parameter fitting。reward-driven scaffold selection 存在明显用途风险；无书面许可时只做一次性 confirm。[data card](https://huggingface.co/datasets/mercor/apex-agents) |
| **BigFinanceBench** | **blind/hosted confirm** | 928 题、52 名 finance SMEs、12 名 reviewer；只使用 public sources。当前仅公开 50 题且完整暴露 gold/rubric，剩余 held-out 题更适合作最终盲测。[paper](https://arxiv.org/abs/2606.03829) |
| **Hedge-Bench** | **confirm / watchlist** | 102 个任务来自专业 hedge-fund analysts 的推理讨论，但机构和分析师匿名；论文强调 expert steps，发布 grader 实际仍使用 semantic judge，不能称完全 deterministic。[paper](https://arxiv.org/abs/2606.03918) |
| **SpreadsheetBench** | **机制控制组** | NeurIPS 2024 Datasets & Benchmarks Track；912 个真实 Excel forum 问题与 OJ-style evaluator 很可靠，但不是 finance 数据，不能进入 Finance Overall Reward。[paper](https://proceedings.neurips.cc/paper_files/paper/2024/hash/ac840df270ac537dd74530a15c332684-Abstract-Datasets_and_Benchmarks_Track.html) |
| **FinMCP-Bench** | **routing 诊断轴** | 613 samples、65 tools；当前 scorer 主要检查工具名称/序列，tool arguments 与最终财务结果验证不足，不能代表完整 task success。[paper](https://arxiv.org/abs/2603.24943) |
| **OccuBench** | **robustness 辅助轴** | 100 个跨行业场景，通过 LLM world model 注入 timeout、字段缺失、隐式数据退化；适合测恢复能力，但不是 finance-specific，且 simulator/verifier 均有模型依赖。[paper](https://arxiv.org/abs/2604.10866) |
| **FinVault** | **finance safety gate** | 适合测攻击、越权和 benign over-refusal；低 attack success 不等于高任务完成率，不能把 `1-ASR` 当总 reward。[repo](https://github.com/aifinlab/FinVault) |
| **From Tasks to Teams / M-SAEA** | **multi-agent safety audit** | ACL 2026 Findings，但它对已完成 trajectory 做 post-hoc 风险评分，不是让 worker 执行金融任务的 benchmark。[paper](https://aclanthology.org/2026.findings-acl.1934/) |
| **WorkspaceBench / 已核验的 MarketBench 版本** | **移出 finance 主表** | workspace 或 market 机制可借鉴，但任务内容不足以代表 quant/finance 专业能力。 |

#### C. “大银行数据”的事实边界

**本轮未找到由 Goldman Sachs、JPMorgan、Morgan Stanley 等大型银行授权发布的内部交易、客户、模板或真实 deal-room 数据集。** 可成立的表述是：

| Provenance 类型 | Benchmark | 可声称 | 不可声称 |
|---|---|---|---|
| 大行背景从业者参与 | BTB、APEX-Agents | banker-authored / banker-validated | 使用其前雇主的内部数据 |
| 真实企业 workspace | FINCH | 来自真实企业 spreadsheet、email、PDF 等 artifacts | 大银行正式发布的内部数据 |
| 专家按工作实践构造 | GDPval、PRBench | 由资深专业人士基于 representative workflows 制作 | 输入必然来自真实客户项目 |
| 公共金融来源 | BTB、BigFinance、Hedge-Bench、QFBench | SEC、IR、公开市场或 benchmark 冻结数据 | Bloomberg、FactSet、CapIQ 或银行私有系统数据 |
| 专业比赛 | DSBench、MBABench | ModelOff/FMWC 等专业建模案例 | 真实生产 banking workflow |

BTB 的准确表述应为：**“Banker-authored and banker-validated, using public or standardized financial data.”** 其早期稿约 175 名 banker、任务 1–8 小时；当前扩展版为 502 名参与者、最长 21 小时。后续实验必须 pin paper/dataset 版本，不能把两版统计混用。

### 1.4 案例研究 / Case Study

#### Case A — GDPval：顶会权威不等于可演化 headroom

GDPval 现在拥有本候选集中最强的 publication authority 之一，但 QEA 的实测已经显示它不适合作高频主演化池：

| GDPval worker | mean multimodal / gated | 解释 |
|---|---:|---|
| weak：prompt 缩成一行 + bare shell | **0.791 / 0.771** | worker 在 episode 内自行恢复通用解题套路 |
| full | **0.797 / 0.772** | 与 weak 几乎相同 |
| recoverable gap | **约 0** | 没有足够可恢复差距供 evolver 证明升级 |

相反，FAB 删除 SEC retrieval bindings 后从 full **0.618** 降到 weak **0.388**，出现 **0.230** 的真实工具能力 gap（本地证据见 [`BASELINES`](../BASELINES.md)）。

这个对照证明：**benchmark 的论文权威性回答“值得信吗”，headroom 回答“能演化吗”；两者必须分别验证。** 因此 GDPval 被保留为 frozen transfer，而不是被淘汰。这里仅声称 FAB 存在 headroom；完整 scored evolution 当时在 candidate evaluation 前暂停，尚不能声称已自动恢复该 gap。

#### Case B — BTB：银行从业者 provenance 不等于银行内部数据

BTB 是“银行行业真实性”最强的候选，但如果只看到 Goldman/JPM/MS 等机构名称，容易错误写成“大银行数据”。进一步核验后，正确链路是：

```text
大行背景 banker 参与 survey / task analysis / authoring / review
       +
真实上市公司、SEC filings、标准化 market-data/VDR
       ->
模拟真实 junior-banker workflow 的 benchmark
```

论文明确不包含 internal templates、真实 deal-room archive、机密交易或客户 PII。因此 BTB 可作为 high-fidelity banking checkpoint，却不能作为“银行官方内部数据”证据。该例说明：**专家 provenance 与底层数据 provenance 必须拆开写。**

### 1.5 当前证据能回答什么、仍需验证什么 / What the Evidence Resolves and What Remains Open

本轮筛选已经回答了“每个 benchmark 更接近测什么”，但还没有回答“哪一种 benchmark 组织方式最适合驱动演化”。现有证据只能支持以下能力地图：QFBench 更接近确定性的 quant coding、risk、factor、backtesting 与多文件产物执行；FINCH 更接近企业财务与 accounting workflow；BTB 更接近投行业务交付物；GDPval/PRBench 更适合作为专业任务上的迁移观察。这里的定位不等于已经确定它们必须组成同一个 suite。

#### 单一 benchmark 演化：归因更清楚，但能力范围可能较窄

如果主演化只使用一个 benchmark，reward 定义、grader、任务格式和成本都更容易控制，也更容易判断一次 worker 修改是否真的改善了同一种任务分布。它的局限是：即使分数提高，也可能只能说明 worker 更适应该 benchmark，而不能说明 quant、企业财务 workflow 和 banking deliverable 等多种能力同时提高。

#### 多 benchmark 演化：可以探索多能力，但解释更复杂

如果同时使用多个 benchmark，可以把研究问题扩展为：同一个 evolver 能否改善多种能力，例如 QFBench 所代表的 quant 执行能力、FINCH 所代表的企业财务 workflow，以及 BTB 所代表的投行业务交付能力。与此同时，综合结果也可能受到 routing、benchmark 权重、grader 类型和输出格式差异影响。因此，多 benchmark 分数变好不一定等于底层能力普遍变好，需要通过逐 benchmark 结果和迁移测试拆开解释。

#### held-out 测试：单 benchmark 与多 benchmark 都需要明确边界

对于单一公开 benchmark，反复使用同一批任务进行演化容易把 benchmark-specific 适配误写成泛化，因此是否建立按 task family 或 workflow lineage 隔离的 held-out 测试，是首先要决定的方法学问题。对于多 benchmark，还需要进一步判断：每个 benchmark 是否都要保留自己的 held-out 部分，以及未参与主演化的另一个 benchmark 能否作为 cross-benchmark transfer test。当前报告只提出这些设计选项，不提前给出结论。

#### 多 benchmark 的两种候选组合

一种思路是选择任务类别相近的 benchmark，例如 GDPval Finance 与 FINCH，以观察同一大类专业 finance workflow 上的演化与迁移；另一种思路是选择能力互补的 benchmark，例如 QFBench、FINCH 与 BTB，分别覆盖 quant、企业财务 workflow 和 banking deliverable。前者更容易比较，后者覆盖面更广。具体采用哪一种，应由小规模 pilot 的实际效果决定。

**证据边界：** 本轮尚未运行上述单 benchmark / 多 benchmark 对照，也没有测得跨 benchmark transfer、统一 reward、adapter 兼容性或综合演化收益。以上内容是下一步实验需要检验的假设，不是已经成立的结果。

---

## 3. 问题与困难（待讨论）/ Problems & Open Questions

1. **应该使用单一 benchmark 演化，还是使用多个 benchmark 演化？** 如果使用多个 benchmark，是否可以有意识地演化多种能力，例如 QFBench 对应的 quant 分析与执行能力、FINCH 对应的企业财务 workflow，以及 BTB 对应的 banking deliverable 能力？
2. **不同演化方案应如何设计测试边界？** 如果使用单一 benchmark，是否必须设置 held-out 测试，以区分真正的泛化与 benchmark-specific 优化？如果使用多个 benchmark，它们应该来自相同或相近类别，例如 GDPval Finance 与 FINCH，还是应该覆盖互补能力？

---

## 4. 下周计划 / Next Week's Plan

> 以下是待讨论的初步计划；目标是先用最小实验观察实际效果，再决定是否扩大接入。

1. **初步敲定 benchmark 方案。** 选出一个单 benchmark 方案和一个多 benchmark 候选方案，明确各自希望观察的能力与最小任务集合。
2. **运行小规模测试。** 每个方案只选少量有代表性的任务，先比较演化前后的分数、完成情况和失败类型，不立即扩展到完整 benchmark。
3. **检查提升发生在哪里。** 区分提升只出现在主演化任务内，还是也能迁移到 held-out task 或另一 benchmark；同时记录结果是否稳定，而不只看一次均分。
4. **根据实际效果再做决定。** 如果小测能显示清楚的可恢复提升，再细化 benchmark、held-out 和后续接入方案；如果没有明显效果，先调整 benchmark 选择或任务组合。

**当前状态 / Current status：benchmark 方案尚未最终敲定；下一步只进行小规模效果测试，不开展 license audit 或大规模接入。**
