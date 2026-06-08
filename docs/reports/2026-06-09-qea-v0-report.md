# 实验报告 / Experiment Report — Evolving Quant Agent (QEA) v0

> 日期 / Date: 2026-06-09 · 项目 / Project: Evolving Quant Agent v0 · 仓库 / Repo: `github.com/Wrigggy/evolving-quant-agent` (private)
> 状态 / Status: v0 机制验证完成（mock 全绿）；real GDPval 实验跑通但结论受噪声限制（inconclusive）。

---

## 1. 实验过程与结果 / Process & Results

### 目标 / Goal
在已复现的 AHE `evolve -> falsify -> rollback` 回路之上，把组件层换成 quant 语义，构建一个**最小可跑**的 evolutionary harness agent v0，打**一个** task family（GDPval finance/accounting）。v0 是**机制验证**，不是性能跑分——成败看「闭环是否真的工作」，而非绝对分数。

### 设计思路 / Build Thinking
继承自 AHE 复现 [[project_ahe_deepseek_repro]] 的**四条铁律**约束整个设计：

1. **Headroom**：task 必须落在「harness 是真瓶颈」区间（process-limited，非 capability-limited），否则只会重演 70% 平台期。
2. **硬 verifier 入回路**：`evolve->falsify->rollback` 只吃确定性硬信号，绝不用 LLM-judge 当主信号（软 verifier = 「falsification 建在沙上」）。
3. **task-aware 去噪**：edit 用 k-repeat 评估，看分布不看单次。
4. **无单一聚合指标**：per-subtype / per-occupation 记 delta，「抬一压一」必须可见。

**架构**：7-slot harness（5 个继承自 AHE：`tool/middleware/skill/prompt/memory` + 2 个 quant 原生：`validator`/`router`）；**minimal seed** 只填 `tool`（一个 code-execution sandbox），其余六空——逼每个组件靠实测 delta 挣位置（归因纯净）。**复用** AHE 的 `evaluate_changes` verdict 引擎（EFFECTIVE/PARTIALLY/MIXED/INEFFECTIVE/HARMFUL）、change-manifest schema、三层 observability；**移植** SkillOpt 三机制（rejected-edit buffer、strict gate、edit budget）。quant 旗舰组件 = **integrity guard = perturbation probe**（扰动输入重算，hardcode 能过 base 过不了 probe）。

**项目结构 / Structure**（纯 stdlib core，mock 零依赖；1956 LOC）：

| 模块 | LOC | 职责 |
|---|---|---|
| `qea/loop.py` | 442 | evolve->falsify->rollback 驱动 + 2-arm ablation + `run_gdpval_soft` + 并发 eval + resume/checkpoint |
| `qea/tasks.py` | 468 | A-pile（合成数值 + reference 纯函数 + probe）/ B-pile / `load_gdpval_finance`（真 GDPval + rubric_json 解析） |
| `qea/verifier.py` | 283 | HardVerifier（数值 + perturbation probe）+ SoftJudge（per-criterion rubric 评分）+ sandbox |
| `qea/agents.py` | 233 | quant_agent + evolve_agent（scripted mock / real LLM）+ diagnose (ADB-lite) |
| `qea/falsify.py` | 169 | verdict 引擎（搬 `evaluate_changes`）+ diff + strict gate + noise-aware gate + rejected-edit buffer |
| `qea/harness.py` | 144 | 7-slot Harness、minimal seed、clone/apply/rollback、to_state/from_state |
| `qea/llm.py` | 82 | OpenRouter client（provider pin + 超时 + 退避重试）+ MockLLM |
| `qea/observability.py` | 63 | 三层 trace/score/manifest 落盘 |
| `qea/manifest.py` | 61 | change-manifest（HARNESS.md v1.0 schema）|

入口 `run.py`（`--mock` / `--real [--resume] [--core]`），测试 `tests/test_smoke.py`（**17/17 通过**）。开发跨 13 个 commit（`6639359` → `063a18b`）。

### 数据与结果 / Data & Results
四组实验，按时间顺序：

| # | 实验 | 配置 | headline 结果 |
|---|---|---|---|
| **E1** | Mock 机制验证 | 离线脚本、硬 verifier、2-arm | **四条验收信号全 PASS**；17/17 测试；`HEADROOM CONFIRMED (MOCK)` |
| **E2** | 合成 A-pile real | deepseek-v4-pro，7 合成 A + 12 真 B，4 iter | seed 4/7；模型能力充足；4 个 edit 全 HARMFUL/INEFFECTIVE → flat → NOT CONFIRMED |
| **E3** | GDPval-soft (pro) | pro worker+judge，30 真 GDPval，4 iter | seed mean **0.618**（19/30≥0.6）；2 个 edit 抬升聚合（0.651/0.645）却被旧 strict gate 回滚 |
| **E4** | GDPval-soft (flash/pro) | **flash worker + pro evolve** + pro judge，30 真，8 iter（6+resume 2）| seed ~**0.60**，noise floor **0.0276**，**0/8 kept** → `SOFT HEADROOM NOT OBSERVED`（噪声限制，inconclusive）|

**E1 mock 2-arm**：Arm1（A-only）OOS 轨迹 `0→6→6→6→6`；Arm2（A+B 软信号进回路）`0→9→9→9→9`，eval-signal 方差 **0.0 vs 0.00031**（干净复现「软信号进回路更吵」）。四信号：①因果连通 ②OOS 单调上升 ③正确 rollback（HARMFUL+INEFFECTIVE+buffer-blocked）④capability-wall 永不被修。

**E4 per-occupation pass rate**（关键数据，两种估计——其差距本身就是噪声证据）：

| 职业 / occupation | pass rate（6-eval 平均，稳）| pass rate（最终单样本）| mean rubric |
|---|---|---|---|
| Personal Financial Advisors | 100% | 100% | 0.82 |
| Real Estate Brokers | 86.7% | 100% | 0.76–0.82 |
| Financial and Investment Analysts | 66.7% | 80% | 0.60–0.65 |
| Financial Managers | 56.7% | 40% | 0.49–0.56 |
| Securities/Commodities Sales | 43.3% | 60% | 0.49–0.53 |
| **Accountants and Auditors** | **13.3%** | **0%** | **0.25–0.31** |

### 案例研究 / Case Study

**Case A — 闭环确实在工作（mock，6/6 审计级）。** iter1：diagnose 给出 root cause tag `Hardcoding`（"6 个 A-task 过 base 但 fail perturbation probe"）→ change_manifest 的 `root_cause` 同样写 `Hardcoding` → workspace 落盘显示 `validator` slot 新增 `integrity_guard` → verdict `EFFECTIVE`、OOS `0→6`。**同一 root cause 贯穿 EVAL→DIAGNOSE→WORKSPACE→VERDICT 四层**（落在 `results/.../iteration_001/{diagnosis,change_manifest,workspace}.json`）。紧接着 iter2 把 `tool:code_exec` 改坏 → 全 task error → verdict `HARMFUL` → **正确 rollback**；iter4 重提 iter2 的 edit → 被 **rejected-edit buffer 在评估前拦下**。这正是 §5.4 三条机制信号的直接证据。real 模式也佐证：E2 里真实 evolve_agent（deepseek）**自己诊断出了 sandbox 的 import bug**，并尝试加一个 `import_restorer` middleware 去修（虽判 HARMFUL 回滚）——说明回路真的在读 eval+诊断并据此行动，而非空转。

**Case B — 闭环在哪里卡住（real GDPval，§2/3 的核心）。** E3 里 evolve_agent 提的两个 edit（`skill:financial_computation_skill`、`middleware:variable_pay_middleware`）**真的把聚合分抬了**（0.618→0.651、→0.645，oos 19→22/21）——但都被回滚。原因：旧 strict gate「只要有任何未预测的 task 掉分就判 MIXED」，而**软 rubric judge 每次评测都重新生成交付物+重新打分**，必然产生 1–2 个随机掉分 → 净正的 edit 被误杀。这把铁律 2 的代价具体化了。据此加了 **noise-aware gate**（只 credit 超过噪声底的聚合提升）；E4 进一步显示：即使有 noise-aware gate，**single-sample incumbent + 软噪声**仍盖过 edit 效应（8 个 edit 的 delta 全在 ±0.0276 噪声带内，0/8 kept）。

---

## 2. 分析 / Analysis

- **机制是真的、且忠实复现。** E1 在硬 verifier 下让四条信号全部点亮（含可审计的 Case-A 因果链），E2–E4 证明回路能在**真实 LLM + 真实 GDPval 数据**上端到端跑通。falsification/rollback/buffer 全程按预期工作。
- **「无 headroom」出现了两种不同性质的形态**：(a) **能力充足型**（E2 合成 A-pile）——deepseek-v4-pro 把 well-specified 数值任务做得很好（BS=10.4506 精确、NPV+IRR 收敛到 1e-13），harness 无从发力，正是铁律 1；(b) **噪声受限型**（E3/E4 GDPval soft）——这是铁律 2 的代价被实测出来：软信号下 falsification **分辨不出** edit 的真实效果，于是要么误杀净正 edit（E3 strict gate），要么一个都 credit 不了（E4 noise-aware gate + 单样本噪声）。
- **E2 的初始结论曾被我误判**：一开始把 3 个失败归因为 "eval 非确定性"，per-task 诊断后发现真因是**我自己的 task-authoring bug**（supplement task 的 prompt 写「Same contract as A_opt_01」，而每次 solve 是独立 LLM 调用、看不到 A_opt_01 → 模型幻觉出无关问题 → KeyError/TypeError）。修正后模型其实很强。**这条提醒：诊断要落到 per-task 证据，别从聚合轨迹脑补根因。**
- **flash worker + pro evolve（E4）是正确的 ablation 设计**（弱执行器有 process-headroom + 强 evolve agent），但结论 inconclusive ——**不是**「evolve 没用」，而是软信号噪声（噪声底 0.0276 与 edit 幅度同量级）+ 单样本 incumbent 回归均值，使 gate 无法分辨。
- **per-occupation 给出可行动信号**：Accountants/Auditors 在两种估计下都是明显短板（~0–13%；flash 在会计/审计这类数值+格式重任务最弱），Advisors/Real-Estate 接近天花板。这比单一聚合分有用得多（铁律 4 的价值）。

---

## 3. 问题与困难（待讨论）/ Problems & Open Questions

**已解决的工程坑（均已 commit）：**
- `safe_exec_solve` 白名单挡掉 `import math` → 全 ImportError（`28c3fed` 加白名单 import）。
- IRR 容差 bug：`tol=1.0` 套到无量纲 IRR（±643% 放水）→ 改 per-metric tol；未归因 regression 能混过 EFFECTIVE → 统一降级 + 收紧 gate；edit signature 120 字符截断碰撞 → hash 全文。
- **2.4 小时死锁**：OpenAI client 无请求超时，经 SOCKS 代理的连接 stall 后永久阻塞（重试只在抛异常时触发）→ 加 `timeout=90s` + max_retries=0 + 并发 eval + 单任务失败降级（`836a277`）。
- SOCKS 代理需 `socksio`；`--resume` + 每轮 checkpoint（`resume.json`）让中断可续跑（`fa489ba`）。

**待讨论的开放问题（想听你意见）：**
1. **去噪 vs 成本（THE blocker）**：软回路要可定论，必须把 eval 噪声压下去——最直接是**对 worker 交付物 k 次采样取中位**（让 incumbent/candidate 均分稳定）。tradeoff：flash worker 便宜，k=3 成本可控，但 eval 调用翻 3 倍。要不要上？
2. **软信号到底值不值得继续**：原始 GDPval 无硬 verifier，用软 rubric 驱动回路是**主动放松铁律 2**。是继续在软信号上做去噪，还是**换一个自带硬 verifier 的 family**（如 FinRL-Meta 带摩擦回测）来拿干净的 iron-law-2 闭环？
3. **官方 grader 不可用**：OpenAI GDPval 官方 grader 是 GPT-5-high pairwise-vs-human-gold，**无公开 API**（只有网页表单、且实测不可提交）。当前用 deepseek 自评 rubric_json（偏宽松、循环偏置）。要不要换更强/中立的 judge model 做校准？
4. **文本交付物 = 下限**：worker 只产 text，format/layout rubric 条目必挂 → 0.60 是 lower bound。是否优先做 **.xlsx/.pptx 真实文件生成**（顺带把 ~37% 客观条目变回确定性硬检查）？
5. **worker/task 配对的 headroom**：flash 偏弱、pro 能力充足——需要一个**真正 process-limited** 的 model+task 配对，evolve 才有发力空间。

---

## 4. 下周计划 / Next Week's Plan

1. **worker 交付物 k-sample 去噪**（最高优先，#1 blocker）：每个交付物生成 k=3 次取 median，稳定 incumbent/candidate 均分；重跑 flash/pro 8-iter，**拿到能定论的 soft-headroom 判定**。预期：噪声底显著下降，若 pro 的 edit 有真实效果即可被 credit。
2. **`.xlsx/.pptx` 真实文件生成 + 格式条目确定性检查**：worker 改为写 `openpyxl`/`python-pptx` 代码经 sandbox 生成真文件；机械条目（文件数/页数/可打开）走确定性硬检查 → 抬升 0.60 文本下限、部分找回铁律 2。
3. **硬 verifier family 对照**：接 FinRL-Meta（带摩擦回测、防泄漏 train-test-trade）做一个**真硬信号**的 evolve 闭环，与软 GDPval 对照——直接回答「软信号到底拖累了多少」。
4. **judge 升级 / 校准**：复现版 pairwise-vs-gold judge 指向更强模型（gpt-5 via OpenRouter），并周期性手动提交官方 grader 做 calibration。
5. **（ROADMAP）四个优化方向**逐一做 *fitness vs verifier-call-budget* 曲线（prioritized harness search / multi-fidelity verifier / risk-seeking pruning / offline+online adaptation），对照 Life-Harness 全迭代 + AHE 文件编辑 baseline。

> 依赖 / Blocked-on：#1–#4 需联网 + OpenRouter 余额；官方 grader 校准被「无 API」阻塞，只能人工网页提交。
