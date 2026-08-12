# QuantCode-Bench 最终 harness 外部泛化候选筛选报告

> 日期：2026-08-09
>
> 性质：primary-source desk audit + 本地只读静态审计
>
> 目标：判断 QuantCode-Bench 能否在 QFBench harness 演化完成后，作为 seed/final-only 的外部泛化测试
>
> 本轮未做：模型调用、付费评测、市场数据下载、benchmark 得分运行、gold/hidden solution 读取、adapter 或 evaluator 修改

---

## 0. 结论

**精确身份已确认：这里的“QuantCodeBench”指 Lime / LimexAILab 发布的 [QuantCode-Bench](https://arxiv.org/abs/2604.15151)，而不是 QuantCodeEval 或 QuanBench。**

最终判定分成两个层次：

| 拟议用途 | 判定 | 原因 |
|---|---|---|
| 在 QFBench 上完成 harness 选择后，对固定模型的 seed harness 与 final harness 做一次冻结的外部迁移比较 | **CONDITIONAL GO** | 任务接口与 QFBench 明显不同，400 个英文自然语言到 Backtrader 策略代码的任务可以检验 harness 是否迁移到新的 API、单文件输出和执行反馈环境 |
| 作为唯一的最终 blind benchmark，证明无污染的广义 finance / quant 泛化 | **NO-GO** | 全部 400 个 prompt 和 evaluator 已公开，无 hidden split；392 个任务来自公开网站；与 QFBench 的 SMA、momentum、Bollinger、backtest 等主题存在近域重合；预训练污染无法排除 |
| 不改上游代码，直接把官方分数当作本项目 publication-grade evaluator 结果 | **NO-GO** | 当前 evaluator 在同一 Python 环境执行不可信代码，允许运行时下载市场数据，judge 有 heuristic fallback 和 fail-open 路径，依赖及市场数据均未锁定 |
| 使用隔离、fail-closed、数据冻结后的 evaluator，作为“QuantCode-Bench-derived hardened protocol” | **CONDITIONAL GO** | 需要先通过本文第 8 节的本地 canary 与冻结门；改变 evaluator 后必须与“官方 leaderboard reproduction”分开命名、分别报告 |

因此，QuantCode-Bench 最合适的角色是：

> **一个公开但在组织流程中严格封存、只在 harness 选择完成后使用的近域 external transfer benchmark。它能补充 QFBench，但不能替代真正 hosted/hidden 的最终盲测。**

它测试的是“能否把系统化交易描述转换成可执行 Backtrader 策略，并满足一个宽松语义 judge”，不是策略盈利能力、风险稳健性、真实 alpha，也不是宽泛的金融工作流能力。

### 证据状态标签

本文严格区分以下四类陈述：

| 标签 | 含义 |
|---|---|
| **[source-audited]** | 来自官方论文、项目网站、官方仓库或依赖项目的第一方文档 |
| **[measured-static]** | 对固定官方 commit 的本地只读静态统计或代码审计；没有运行模型或 benchmark |
| **[proposed]** | 为 evolving-quant-agent 提出的实验协议或安全加固，尚未实现 |
| **[not tested]** | 当前不能从 source audit 推断成立，必须通过 canary、模型运行或人工核验解决 |

---

## 1. Benchmark 身份、版本与来源

### 1.1 精确身份

**[source-audited]** 官方论文全名为 *QuantCode-Bench: A Benchmark for Evaluating the Ability of Large Language Models to Generate Executable Algorithmic Trading Strategies*，作者为 Alexey Khoroshilov、Alexey Chernysh、Orkhan Ekhtibarov、Nini Kamkia、Dmitry Zmitrovich，作者单位为 Lime。论文 [arXiv:2604.15151](https://arxiv.org/abs/2604.15151) 的 v1 提交日期为 2026-04-16；另有[官方项目页](https://limexailab.github.io/QuantCode-Bench/)与[官方 GitHub 仓库](https://github.com/LimexAILab/QuantCode-Bench)。

**[measured-static]** 本轮核验时官方仓库 `main` 指向：

```text
f8bda951addb409a81aa316c00401dbde60774ae
```

仓库当时没有 release tag。因此后续实验不能只写“main”；必须 pin 上述 commit 或另一个经重新审计的完整 commit。

名称相近但不属于本报告对象的项目包括 QuantCodeEval（论文量化研究代码复现任务）和 QuanBench（量子代码 benchmark）。如果后续用户所指并非 Lime 的 QuantCode-Bench，应重新做 identity screen，不能沿用本报告结论。

### 1.2 官方发布物与许可

| 项目 | 审计结果 |
|---|---|
| 代码仓库 | **[source-audited]** 官方仓库以 [MIT License](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/LICENSE) 发布 |
| 论文 | **[source-audited]** arXiv 页面标注 CC BY 4.0 |
| dataset hosting | **[measured-static]** dataset JSON 直接包含在 GitHub 仓库；审计时没有官方 Hugging Face dataset card |
| 独立 hosted/hidden evaluator | **[measured-static]** 未发现；仓库中公开的是完整 400 题 JSON 和本地 evaluator |
| 数据条目 provenance | **[measured-static]** 每题有来源类别，但没有逐题 URL、抓取日期、原内容许可或 attribution 字段 |
| 市场数据 | **[source-audited]** 不随仓库发布；运行前通过 yfinance 下载并缓存 |

官方仓库的 MIT 许可足以说明仓库代码的许可，却**不能自动替代**以下两类权利判断：

1. 392 个来源于 Reddit、TradingView、StackExchange、GitHub 的任务文本，其逐条来源与许可没有在 dataset 中给出，无法独立复核 downstream redistribution 条件；
2. yfinance 项目明确提示其面向研究/教育用途，Yahoo 数据的实际使用权仍受 Yahoo 条款约束，见 [yfinance 官方仓库](https://github.com/ranaroussi/yfinance)。

这是一项 provenance / 使用范围 caveat，不是法律结论。正式发布 benchmark 镜像或市场缓存之前仍需单独权利审查。

### 1.3 固定源码摘要

**[measured-static]** 以下 SHA-256 来自上述 commit 的本地只读 clone，可作为后续 freeze manifest 的起点：

| 文件 | SHA-256 |
|---|---|
| `data/benchmark_tasks_multiframe.json` | `b197e0271779f332c6808ea40167615e3b90061563544b8bdf3c48237a9f17d3` |
| `data/task_data_requirements.json` | `7bc4039cfe971ec04de3618c652eca268c95ce07030c5f597c594209344f38b9` |
| `requirements.txt` | `a2839970e22a7ada6a03fb85a50856e38d87738280ed170356abbf3390ac8777` |
| `quantcode_bench/reward.py` | `4a97ae9df7f3368cb2c14db305f7a7b30f1bff66f35b884a6710de4c38abf069` |
| `quantcode_bench/judge.py` | `d9d485776f46c58c0a02ceeead800a7af907b5f6cd428c6bf900da029d4076a5` |
| `quantcode_bench/generator.py` | `818524f79f1f628e9a1ca3d2ce4f87b1dae7e4a2d219e48ff4d87c72433e0cd0` |
| `quantcode_bench/data_cache.py` | `2f92cf5aced6020f95cb18c32a6906b86903f588701d80164495e66028a07cb9` |
| `scripts/build_cache.py` | `565d98c5dba581b65d82054b5750d3ac6b44abe3c0a5fc934ab44de2efa01f61` |
| `scripts/run_all_models.sh` | `17291c6185101c89f96e308b845e74c66a7d9f721ab9cdb997909e699f6c4101` |
| `run_single_shot.py` | `c770958ad3acd668561a6e770628680e9e4604f4e4a0d8e56e435f200508d999` |
| `run_agentic.py` | `f20f01ee75185bb8fb3cb0526f0fa18361821095fb44388a6e105692ce4ba188` |
| `README.md` | `8f395f72776f5f2945e5cbcaec1ccc11bdb0a6b9d525b995c491bb7dabda73a4` |
| `LICENSE` | `f06e6e29b500ee161eb31a5d83dfce382ea294c142e6538509bd7658a39d2fca` |

---

## 2. 任务面、语言、输入输出与 agent 接口

### 2.1 官方任务定义

**[source-audited]** [官方 README](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/README.md)和论文定义了 400 个英文任务：模型读取自然语言的系统化交易策略描述，输出一段可执行的 Python / Backtrader strategy code。来源和难度分布为：

| 维度 | 分布 |
|---|---|
| 来源 | Reddit 183、TradingView 100、StackExchange 90、GitHub 19、synthetic 8 |
| 难度 | easy 197、medium 116、hard 87 |
| 语言 | 英文 |
| 主要输出 | 一段 Python 源码、一个 `bt.Strategy` 子类 |
| 官方交互 | single-turn；或最多 10 轮、每轮收到结构化执行反馈的 agentic 模式 |

它不是终端中的多文件 mini-project，也不要求 spreadsheet、报告、检索结果或组合式 deliverable。官方 runner 是一个 OpenAI-compatible API generator，而不是 NexAU 或通用 shell agent。接入本项目时，需要定义一个很薄的 worker adapter：仅把任务描述和统一公开输出 contract 交给同一个固定 worker/harness，并收回一个 `strategy.py` artifact。

### 2.2 本地只读数据统计

**[measured-static]** 对固定 JSON 的审计得到：

| 项目 | 统计 |
|---|---:|
| 任务行数 / 唯一 ID | 400 / 400 |
| `reformulated_task` 完全重复 | 0 |
| `was_reformulated=false/true` | 389 / 11 |
| 唯一 yfinance symbol | 24 |
| 唯一 symbol × timeframe | 39 |
| timeframe | 1d 211、5m 83、15m 36、1h 35、1m 32、30m 3 |
| 任务描述字符数 | min 298、median 1299、p90 2850、max 4334、mean 1542.6 |
| 任务描述词数 | min 54、median 209、p90 470、max 722、mean 251.5 |

数据虽然包含 24 个 yfinance symbol，但有效分布高度集中：AAPL 占 360/400（90%），SPY 占 6/400，其余 symbol 只占很小部分。因此“跨 diverse market instruments”是上游设计意图，不能直接当作本数据分布均衡的实证表述。

`task_data_requirements.json` 与 400 个任务 ID 完全对齐，静态 metadata 显示：

| 兼容性标记 | 数量 |
|---|---:|
| `data_available=true` | 400 |
| `has_hardcoded_prices=true` | 41 |
| `needs_reformulation=true` | 1 |
| `requires_external_data=true` | 29 |
| `requires_multi_asset=true` | 17 |
| `requires_session_timing=true` | 106 |

这些标记目前只被 cache build 逻辑用于准备数据 pair，并未被官方 runner 用作任务排除或专门评分规则。与此同时，[官方 generator prompt](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/quantcode_bench/generator.py)把 worker 限制为单一 `self.data`、不使用日期/时间戳、只使用一组指定指标，并鼓励把复杂任务简化为能产生交易的策略。因而上面 29/17/106/41 项是否都能在同一 public contract 下得到忠实实现，**[not tested]**；不能仅凭 metadata 认定它们无效，也不能在正式得分前忽略这个 compatibility gap。

为避免将 benchmark 内容泄漏给 Evolver，本报告没有复制任何实际任务文本。

### 2.3 是否存在 public/hidden tests、solution 或 reference

**[measured-static]**

- 仓库公开完整 400 个任务描述；
- 没有 train/dev/test 划分；
- 没有 hosted hidden test；
- 没有目标 strategy solution、gold code 或 reference implementation；
- evaluator、judge prompt、生成 prompt 和运行脚本全部公开；
- 官方示例与 generator system prompt 包含通用 SMA crossover 模板。

这意味着不存在“worker 读取官方 solution”的直接风险，但存在更广泛的 benchmark/task-template 暴露和训练污染风险。组织上把数据封存，只能阻止本次 evolver 的自适应使用，不能证明基础模型在预训练或后训练阶段没有见过公开来源或发布后的 benchmark。

---

## 3. 评分器、partial credit 与 evaluator 放宽问题

### 3.1 官方四阶段评分

**[source-audited]** 官方定义是四个嵌套阶段：

1. compilation / structure；
2. 在指定历史数据上成功 backtest；
3. 至少产生一笔交易；
4. LLM judge 判定实现与任务语义一致。

最终 `reward.py` 返回严格的二元 `0.0/1.0`；没有原生 partial credit。Compilation、Backtest、Trade 和 Judge Pass rate 可以作为阶段诊断，但官方 primary success 需要所有阶段同时通过。论文报告的最佳 single-turn Judge Pass 为 75.8%，最佳最多十轮的 agentic 结果为 97.5%；这些是**上游发表结果，不是本项目复现值**。

论文也明确说明该 reward 不评估盈利、risk-adjusted return、out-of-sample robustness 或经济意义。技术阶段本身可以被通用“总会产生交易”的模板利用，因此作者增加了语义 judge。由此可见：

> 对这个 benchmark，“放宽 evaluator”可以作为诊断性 sensitivity analysis，但不宜把进一步放宽后的分数作为主成功指标；否则很容易把通用 Backtrader 模板适配误写成任务语义泛化。

### 3.2 当前实现与论文描述之间需要注意的差异

**[measured-static]** 对 [`reward.py`](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/quantcode_bench/reward.py)、[`judge.py`](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/quantcode_bench/judge.py) 和 runners 的代码审计发现：

- 所谓 compilation gate 实际先做字符串/正则结构检查：要求出现 Backtrader import、`bt.Strategy` 子类和 `next(self)`；它不是独立的 AST 或 `py_compile` gate。后续语法错误通常会落入 subprocess/backtest failure；
- wrapper 只装载一个 `PandasData`，初始资金 10,000，commission 0.001，并运行发现的第一个 strategy 子类；
- 不可信 strategy 被拼接到 wrapper，随后通过 `[sys.executable, "-c", test_code]` 在当前主机/环境的 subprocess 里执行，120 秒超时；
- subprocess 没有容器、网络禁用、credential scrubbing、只读文件系统、cgroup 资源限制或进程组 reaper；
- judge prompt 明确要求对复杂任务的合理简化保持宽松，只有明显忽略主逻辑时才判 0；
- judge API 出错时会退回基于代码长度、类名和常见 indicator 词的 heuristic；
- judge 初始化失败或上层 judge call exception 时存在保持 `judge_aligned=True` 的 fail-open 路径；
- runner 汇总时会把“有交易但 judge 没有被调用”的结果计入 judge pass。

因此，官方 release 的可执行性与语义评分代码目前不满足本项目既定的 evaluator firewall，也不能在共享 judge credential 的环境中运行不可信生成代码。尤其不能让 strategy subprocess 继承 provider key 或允许任意 egress。

### 3.3 建议的 evaluator 分层

**[proposed]** 正式报告应同时保存以下不可互相替代的结果：

| 层 | 指标 | 用途 |
|---|---|---|
| Stage 1 | structure / syntax | 诊断输出 contract 与基本代码有效性 |
| Stage 2 | isolated execution | 诊断 Backtrader/API/runtime 能力 |
| Stage 3 | at least one trade | 诊断策略是否在冻结数据上激活 |
| Stage 4 | fail-closed semantic judge | 主成功指标的一部分 |
| Primary | 四阶段全通过的 task mean | seed/final 的主要 paired comparison |

如果要探索 evaluator relaxation，推荐预注册两个 secondary sensitivity：

1. 只报告 `(structure, execution, trade, semantic)` 的阶段向量，而不是把前三阶段加权成另一个模糊总分；
2. 对同一冻结输出，用“strict semantic rubric”和“上游 lenient rubric”各 adjudicate 一次，明确标为 sensitivity，不能用更有利者做事后主结论。

不建议把“能运行并交易”直接视为成功，也不建议在看到 seed/final 结果后修改 judge prompt、阈值或排除任务。

---

## 4. 市场数据、依赖、复现性与成本

### 4.1 动态市场数据

**[source-audited]** 仓库不包含 `data/cache/`。官方 [cache builder](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/scripts/build_cache.py)通过 yfinance 准备 39 个 symbol × timeframe：

| interval | 上游窗口 |
|---|---|
| 1d | 2020-01-01 至 2025-12-31 |
| 1h | 运行时最近 730 天 |
| 1m | 运行时最近 7 天 |
| 5m / 15m / 30m | 运行时最近 60 天 |

日线窗口看似固定，但供应商修订、复权和依赖版本仍可能改变内容；所有 intraday 窗口更会随下载日期滚动。更重要的是，[`reward.py`](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/quantcode_bench/reward.py)在项目 cache 缺失时会实时下载，并会复用不带内容摘要的系统临时文件名。

**[proposed]** 正式实验必须：

- 在 trusted staging 中只下载一次 39/39 cache；
- 对每个 cache 文件记录 SHA-256，以及规范化后的 row count、columns/dtypes、index/timezone、first/last timestamp 和内容 hash；
- seed 与 final 只读挂载完全相同的 cache slice；
- evaluator 运行时关闭网络与 download fallback，任何 pair 缺失都 fail closed 为基础设施 missing；
- 每个 attempt 使用独立容器和临时目录，不能复用未验证的 `/tmp/qcb_*.pkl`；
- 在许可审查完成前，不公开分发冻结的 Yahoo 市场数据。

### 4.2 运行环境未锁定

**[source-audited]** [`requirements.txt`](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/requirements.txt)只有 lower bounds，包括 Backtrader、OpenAI SDK、yfinance、pandas、aiohttp 等；没有 Python pin、lockfile、wheel hash、Dockerfile、base image digest 或 CI parity fixture。

**[proposed]** 在运行任何 scored task 前，需要冻结：

- Python 版本与解释器 build；
- base image digest；
- Backtrader、pandas、yfinance、OpenAI SDK 及全部 transitive wheels 的版本和 hash；
- locale、timezone、CPU architecture 与线程设置；
- adapter、wrapper、parser、judge prompt 和 retry policy 的 digest；
- 每个阶段的 wall-clock、CPU、memory、PIDs 和 output-size 上限。

### 4.3 Judge 与调用预算

**[source-audited]** 官方 [batch script](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/scripts/run_all_models.sh)目前通过 OpenRouter 把 judge 配为 `openai/gpt-5.4`，judge temperature 为 0；generator 单次最大输出 64,000 tokens，agentic 模式最多 10 轮。论文没有提供 judge 的 human agreement、重复判定稳定性或完整 calibration 结果，也没有固定 provider snapshot。

**[proposed]** 若完整 400 题、seed/final 两个 harness、3 次独立 paired repetitions：

```text
400 tasks × 2 harnesses × 3 repetitions
= 2,400 worker attempts
+ at most 2,400 semantic adjudications
```

若把上游最多 10 轮的 evaluator feedback 用作 primary，最坏会膨胀到 24,000 次 generator/judge attempt，并且上游最佳结果已经达到 97.5%，headroom 和归因都会显著恶化。因此 primary 应为一次 worker episode、一次 sealed adjudication；10-turn repair 只能是另行标记的 secondary diagnostic。

每个 backtest 的上游 timeout 是 120 秒，因此 2,400 个 attempt 的理论最坏 serial execution 约 80 CPU-hours，尚未包含生成与 judge。实际 token 成本和金额**当前未知**：必须等模型/provider/route、平均输入输出 token、judge调用数和价格快照固定后再估算，不能从上游仓库推断一个权威成本。

---

## 5. 与 QFBench 的互补性、重合与污染

### 5.1 能力与接口对照

| 维度 | 当前 QFBench 主线 | QuantCode-Bench |
|---|---|---|
| 任务规模 | pinned snapshot 下约 86 个异质 mini-project | 400 个单框架 strategy generation |
| 输出 | 文件/项目产物，可能多文件 | 单段 Python / strategy class |
| evaluator | 以确定性 pytest 为主，72 binary + 14 partial | backtest + trade gate + LLM semantic judge，最终 binary |
| 任务范围 | derivatives、risk、factor、microstructure、backtest、credit 等 | Backtrader 系统化交易策略 |
| 公开 oracle 风险 | public tests/solutions，需要 verifier firewall | 无 solution，但全部 prompt/evaluator 公开 |
| 市场数据 | benchmark artifact / test fixture | yfinance 动态 cache，必须另行冻结 |
| 最适合角色 | harness 发现、局部化与受控演化 | 演化完成后的近域 external transfer |

QuantCode-Bench 的价值来自新的 output contract、Backtrader API、单文件 agent interface 和不同 evaluator，而不是来自完全不同的金融领域。

### 5.2 已知概念重合

**[source-audited + measured-static]** QFBench 中已有与 Bollinger、momentum、SMA crossover、AAPL/SPY backtest 等相关任务；QuantCode-Bench 的 task family 与 generator 例子也包含这些常见系统化交易模式。因此：

- 迁移提升可能代表共享策略模板、Backtrader API 或“确保产生交易”的适配；
- 它仍然是有价值的 near-domain transfer；
- 但它不能单独支持“跨金融领域的广义泛化”。

**[not tested]** 本轮没有在 verifier-only surface 中运行两套 benchmark 的规范化文本、代码 fingerprint 或来源 URL exact-overlap scan。也没有完成 QuantCode-Bench 五位作者与 QFBench 全体贡献者的穷尽身份消歧。因此当前只能说“存在明确概念重合，未发现官方声明的直接仓库关系”；不能声称 exact overlap 或 author overlap 为零。

**[proposed]** 正式运行前必须由 trusted verifier 做 overlap gate：

- 比较 normalized task text、n-gram/embedding near-duplicate、关键实体和策略模板；
- 比较 QFBench public solution / fixture fingerprint，但绝不把 solution 内容交给 worker 或 Evolver；
- 输出只能是 excluded task IDs、重合类型、数量和扫描器/config digest；
- 排除清单必须在任何 QuantCode scored model call 之前冻结。

### 5.3 模型训练污染与 freshness

**[source-audited]** benchmark 自身于 2026-04 公开，发布较新；但 392/400 的原始来源来自公开网站，dataset 没有逐题日期，且 389 个任务标记为未 reformulate。所有 400 个 prompt 现在也已公开。

因此 contamination 结论必须写成：

- benchmark 发布后污染：可通过模型训练 cutoff/数据声明部分评估，但当前未解决；
- 原始网页内容污染：高概率存在一般性暴露，无法由 benchmark 新发布日期消除；
- 本次 evolver 自适应泄漏：可以通过 seed/final-only 封存和 firewall 控制；
- “基础模型从未见过任务”：不能证明。

如果正式模型仍是 DeepSeek V4 Flash，其[官方 model card](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash)没有给出足以排除 QuantCode-Bench 或其来源页面的训练 cutoff / dedup 证明。故污染状态是 **unresolved**，不是 clean。

最终论文若需要强 blind claim，应保留另一个 hosted hidden benchmark；QuantCode-Bench 只能作为公开 external confirm。

---

## 6. 推荐的 seed/final-only 泛化协议

### 6.1 实验问题与独立变量

**[proposed]** 目标问题应限定为：

> 在固定基础模型、provider/route、解码、任务、数据、runtime、worker adapter、预算和 evaluator 的条件下，只把 seed harness 替换为最终经 QFBench 选择的 harness，QuantCode-Bench 的四阶段成功率是否在重复实验中稳定提高？

唯一计划改变的独立变量是 harness version。以下项目必须相同：

- 模型精确 ID、provider、route、reasoning/temperature、max tokens；
- task panel、任务顺序或配对调度、并发 epoch；
- worker adapter、可用工具与 episode budget；
- container image、CPU/memory/PIDs/time limit；
- 市场 cache；
- judge model/route/prompt/parser/temperature；
- retry、missingness 和 resume policy。

### 6.2 对 Evolver 的零接触

QuantCode-Bench bundle 应存放在 worker/evolver repo 之外的 trusted evaluator root。正式 final selection 完成前：

- 不把 prompt、metadata、source/difficulty、cache、evaluator code、阶段分数、错误 trace、judge rationale 或 seed 结果交给 Evolver；
- 不用 QuantCode score 决定任何 candidate 的 keep/rollback、routing 或 prompt 修改；
- 不在中间 iteration 运行 QuantCode；
- 不让任务 worker 把跨 episode memory 写回最终 harness；
- 对 proposer/evolver 输入与 artifact 做 leak scan；
- seed 结果写入 sealed score store，直到 final harness 完全冻结后才统一解封分析。

公开 benchmark 经过这种组织封存后，可以被称为“selection-held-out”或“externally sealed”，不能称为 cryptographically hidden 或 contamination-free。

### 6.3 Primary 与 secondary setting

**Primary：**

- 完整冻结 panel，默认 400 题减去预注册 overlap/compatibility exclusions；
- 每个 task 只给英文任务描述与 benchmark-wide public output contract；
- worker 生成一个 strategy artifact；
- worker 不接触历史数据 cache、backtest结果或 judge反馈；
- isolated verifier 和 judge 在 episode 结束后一次性评分；
- 至少 3 次独立 stochastic paired repetitions；预算允许时 5 次；
- 报告 task-level paired delta、均值、置信区间/cluster bootstrap、difficulty/source slice、四阶段 rates 与 missingness；
- 明确检查 hard/source slice 是否有实质回归。

**Secondary：**

- 上游最多 10 轮的 structured-feedback agentic repair；
- evaluator relaxation sensitivity；
- 不同 judge 的 agreement；
- compatibility-flag 子集分析；
- 这些结果不参与 final harness 选择，也不替换 primary。

若需要先验证固定模型是否存在 headroom，只能预注册并“牺牲”一个小 pilot subset；该 subset 永久排除出最终 primary panel。不能先看完整 panel 再决定协议。

### 6.4 Missingness 与重试

**[proposed]**

- worker 在固定 episode budget 内 timeout、输出错误或工具失败：计 task failure；
- cache 缺失、容器启动失败、judge/provider outage、sealed-store failure：标为 infrastructure missing，不自动计模型失败；
- infrastructure missing 只允许重跑完全相同的缺失 evaluator step；
- 已经接受的模型调用不得因结果不好而 resample；
- 每次调用保存 attempt ID、provider request ID、token/cost、cache hash、image digest、开始/结束时间与退出原因；
- 并发批次必须对 seed/final 配对，避免 provider 或负载时间漂移与 harness 混淆。

---

## 7. 必需的 evaluator 隔离架构

上游实现把生成代码、cache、judge client 和环境放在同一 Python 进程体系内，不适合直接使用。建议的最小信任边界为：

```text
sealed coordinator
  ├─> ephemeral worker container
  │     input: task description + public output contract
  │     egress: fixed model provider only
  │     output: strategy.py
  │
  ├─> offline execution verifier
  │     input: strategy.py + exactly one read-only frozen cache slice
  │     network: none
  │     secrets: none
  │     output: structure / execution / trade stage record
  │
  └─> trusted semantic-judge service
        input: task description + generated code only
        egress: judge provider allowlist only
        secrets: judge credential, never inherited by generated code
        output: signed/hashed binary adjudication + metadata

sealed score store -> released only after final harness freeze
Evolver          <- no QuantCode content, trace, score, or outcome
```

**[proposed]** execution verifier 应使用 rootless container、read-only root filesystem、独立 tmpfs、无网络/DNS、无环境 secret、bounded CPU/memory/PIDs/output、process-group kill、精确 task-ID cleanup。只挂载该任务所需的冻结 cache slice，不挂载完整 benchmark、repo、host home 或 Docker socket。

**[proposed]** semantic judge 必须 fail closed：

- judge 初始化/API/parser 失败都记 infrastructure missing；
- 禁止 heuristic fallback；
- 禁止“judge 未调用即 pass”；
- judge credential 与 provider网络永远不进入 strategy execution container；
- 保存 judge provider/route/model snapshot、prompt hash、parser hash、temperature 和 request ID；
- 用非 benchmark-gold 的合成 fixture 做 repeated agreement 和人工 calibration。

**[not tested]** 本项目已有 QFBench rootless backend 经验，但 QuantCode 特定的 Backtrader、pickle cache、process tree、resource limits 和 judge split 尚未通过 parity/isolation canary，不能从 QFBench 结果直接外推为已通过。

如果 hardening 改变了上游运行或判定语义，应采用两个名字：

- **Official-compatible score**：只有在严格复现上游 evaluator 时使用；
- **QuantCode-Bench-derived hardened score**：使用隔离、fail-closed 和冻结数据的本项目主结果。

二者可以同时报告，但不能合并或把 hardened score 直接与官方 leaderboard 数字比较。

---

## 8. 在任何 scored model run 前必须通过的 canary

| Gate | 无模型 canary / 审计 | 通过标准 |
|---|---|---|
| 身份与 schema | commit、文件 hash、400 ID、字段、source/difficulty 计数 | 全部与 freeze manifest 一致 |
| 数据完整性 | trusted staging 构建 39/39 cache；两次 fresh-container parity | 所有规范化内容 hash 相同，无空/退市 pair |
| 离线性 | 删除/阻断 runtime download fallback | 缺 cache 明确 fail closed，零网络请求 |
| 依赖锁定 | lockfile、wheel hash、image digest | fresh rebuild 一致 |
| 正向 fixture | 手写、非 benchmark solution 的简单 Backtrader fixture | 四阶段按预期通过 |
| 负向 fixture | 语法错、runtime错、零交易、语义错 | 分别落在预期阶段，不交叉误判 |
| rootless 隔离 | 读取 host/env/credential、network/DNS、fork/child、timeout、磁盘/内存压力 | 全部被阻断；process tree 和容器精确清理 |
| judge fail-closed | 无 key、provider 5xx、timeout、malformed response、parser failure | 全部 infrastructure missing，绝不 pass |
| judge calibration | 合成 matched/mismatched pairs；重复 adjudication；人工 sample | 预注册 agreement/误差门通过 |
| compatibility | 审核 29 external、17 multi-asset、106 session-time、41 hardcoded 标记 | 排除/保留规则在得分前冻结 |
| overlap | trusted QFBench ↔ QuantCode exact/near-duplicate scanner | 只输出排除 ID/计数/hash，清单冻结 |
| firewall | worker/evolver mounts、prompts、logs、artifacts leak scan | QuantCode 内容对 Evolver 零可见 |
| no replay | attempt ledger、resume、provider request ID | 已接受调用不 resample |
| cost authority | 任务数、repetition、最大 calls/tokens/time、judge budget | 预算预注册并可审计 |

任何需要模型的 headroom/judge calibration pilot 都必须使用事先牺牲的 subset，不得污染正式 final panel。

---

## 9. GO / NO-GO 门与可发表 claim 边界

### 9.1 从 CONDITIONAL GO 升为 GO 的必要条件

只有同时满足以下条件，才建议启动完整 seed/final run：

1. commit、dataset、cache、dependency image、adapter、judge 和预算全部固定；
2. final harness 已在 QFBench 协议内冻结，不再因 QuantCode 结果调整；
3. Evolver zero-contact 与 artifact firewall 通过；
4. rootless execution、cache parity、resource reaper 通过；
5. judge fail-closed、重复稳定性和人工 calibration 达到预注册门；
6. overlap 与 compatibility exclusions 在得分前冻结；
7. paired repetitions、missingness、resume 与 cost ledger 已具备；
8. 论文中同时保留一个 hosted/hidden confirm，若要提出 blind generalization claim。

### 9.2 立即 NO-GO 的触发条件

- 任一 QuantCode task、score、trace 或 judge反馈进入 Evolver，或影响 candidate selection；
- seed/final 使用不同 yfinance fetch、cache、dependency、model route、judge或预算；
- 使用上游 heuristic judge fallback 或任何 judge fail-open；
- generated strategy 获得 credential、host filesystem 或非必要网络；
- exact/near overlap 未处理，却声称独立 cross-benchmark generalization；
- 在观察结果后修改 task exclusions、judge prompt 或 pass rule；
- 把该 benchmark 结果写成真实盈利、alpha、风险稳健性或广义 finance workflow 证据；
- 把公开完整 panel 写成 contamination-resistant blind final。

### 9.3 成功后可以与不可以声称什么

若按本文协议得到稳定正向 paired delta，可以谨慎声称：

> 在固定模型和预算下，经 QFBench 选择的 final harness 相对于 seed harness，把改进迁移到了一个在选择过程中封存、接口不同但仍属于系统化交易代码生成的公开 benchmark；提升体现在冻结数据和 fail-closed semantic evaluator 下的四阶段任务成功率。

仍然不能由此声称：

- 基础模型没有见过 benchmark 或其网页来源；
- 改进泛化到所有 quant、finance 或真实投研工作流；
- 生成策略有盈利能力、稳健 alpha 或可部署价值；
- hardened score 与官方 leaderboard 完全可比；
- harness 本身而非共享模板、路由或未控制的 evaluator 漂移导致提升，除非 paired controls 支持该因果解释。

---

## 10. 当前状态与建议下一步

### 当前已经完成

- **[source-audited]** benchmark 身份、论文、项目页、官方仓库、许可、任务与评分定义；
- **[measured-static]** 固定 commit、dataset/schema/counts、symbol/timeframe 分布、compatibility flags、文件 digest；
- **[measured-static]** evaluator subprocess、judge fallback/fail-open、dynamic cache、依赖与 runner 配置审计；
- **[proposed]** seed/final-only、rootless split、fail-closed judge、freeze manifest、重复与统计协议。

### 当前没有完成

- **[not tested]** 39 个市场 cache 的可获取性与内容 parity；
- **[not tested]** rootless Backtrader evaluator；
- **[not tested]** judge calibration / agreement；
- **[not tested]** QFBench exact/near overlap；
- **[not tested]** fixed model 的 headroom、seed/final score、实际 token/cost；
- **[not tested]** dataset逐项许可与原始来源追溯；
- **[not tested]** QuantCode-Bench 五位作者与 QFBench contributor 的完整身份消歧。

### 建议顺序

1. 先把 QuantCode-Bench 登记为“最终近域 external transfer 候选”，不让 Evolver 接触；
2. 在完全不调用模型的情况下实现 cache freeze、dependency lock、rootless execution 和 fail-closed judge canary；
3. 在 trusted surface 做 overlap 与 compatibility gate，冻结正式 panel；
4. 只有在 final harness 已锁定后，按相同模型与预算运行 paired seed/final；
5. 将 QuantCode 结果与另一个 hosted/hidden benchmark 共同构成最终泛化证据，而不是单独承担 blind claim。

---

## Primary sources

- [QuantCode-Bench arXiv abstract and paper](https://arxiv.org/abs/2604.15151)
- [QuantCode-Bench official project page](https://limexailab.github.io/QuantCode-Bench/)
- [Official repository, pinned commit `f8bda951…`](https://github.com/LimexAILab/QuantCode-Bench/tree/f8bda951addb409a81aa316c00401dbde60774ae)
- [Pinned README and benchmark description](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/README.md)
- [Pinned reward implementation](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/quantcode_bench/reward.py)
- [Pinned semantic judge implementation](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/quantcode_bench/judge.py)
- [Pinned generator and public prompt contract](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/quantcode_bench/generator.py)
- [Pinned market-cache builder](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/scripts/build_cache.py)
- [Pinned official batch configuration](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/scripts/run_all_models.sh)
- [Pinned dependency requirements](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/requirements.txt)
- [Pinned MIT license](https://github.com/LimexAILab/QuantCode-Bench/blob/f8bda951addb409a81aa316c00401dbde60774ae/LICENSE)
- [yfinance official repository and data-use notice](https://github.com/ranaroussi/yfinance)
- [DeepSeek-V4-Flash official model card](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash)

---

## Account-exit handoff

- Source audit 已完成；恢复入口是本报告 `docs/reports/2026-08-09-quantcodebench-generalization-screen.md`，上游官方源码固定为 commit `f8bda951addb409a81aa316c00401dbde60774ae`。
- 当前边界：**CONDITIONAL GO** 作为 final harness 冻结后的 seed/final-only 近域 external transfer；**NO-GO** 作为唯一 blind / contamination-resistant final，或原样使用上游 fail-open evaluator 提出 publication-grade claim。
- 本轮没有下载市场数据，没有调用模型，没有付费或 scored benchmark run，也没有启动外部基础设施动作。
- 下一步仅做 hardened protocol canaries：冻结 cache/dependency、rootless 离线执行、judge fail-closed、overlap/compatibility gate、firewall 与 cost ledger。在 final harness freeze 之前，QuantCode task、metadata、cache、trace、score 和 judge outcome 必须继续对 Evolver 保持 zero-contact。
