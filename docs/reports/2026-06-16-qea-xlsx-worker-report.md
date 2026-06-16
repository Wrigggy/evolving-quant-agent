# 实验报告 / Experiment Report — QEA 本 session 实验线:重构 → 发现 format basin → file-producing worker (v0.1)
> 日期/Date: 2026-06-16 · 仓库/Repo: `github.com/Wrigggy/evolving-quant-agent` · 分支/Branch: `main`(重构已合)+ `qea/xlsx-producing-worker`(v0.1) · 模型: quant+evolve `deepseek-v4-pro`, judge `qwen3.7-max`(OpenRouter)

> 名词 / Quick glossary（首次出现先解释一句）:
> **QEA** = 演化一个 quant agent "harness"(外骨骼)的实验框架,机制是 `evolve→falsify→rollback`。
> **harness/组件** = worker 的 7 个槽(tool/middleware/skill/prompt/validator/memory/router),evolve_agent 每轮改一个组件。
> **B-pile** = 真实 GDPval 金融/会计开放式 deliverable 任务(~30 个);**grader** = LLM judge 按 `rubric_json` 逐条打分,聚合成连续 rubric %;**gate** = `decide_keep_soft`(候选平均分超 incumbent 超 noise floor 才 keep)。
> **observation firewall** = 把 rubric ground-truth 只喂给 diagnosis、不漏给 proposer 的设计(防 proposer 抄答案/修幻觉失败)。
> **format basin** = proposer 反复只提"格式型"edit、出不来的退化态。

---

## 0. 实验线索 / The line（本 session 全貌,出发点串起来）

这一段把本 session 做完的工作连成一条**因果线**——每一步的"出发点"都是上一步的发现:

```
[出发点 0] 上一阶段发现(memory: proposer_observation_space):
  B-pile 写作任务被喂了 A-pile debugger 语义 → proposer 修"幻觉失败",8/8 harmful、0/7 kept
        │  → 动机:重做观测 + 决策层
        ▼
[Step 1 · 工程] 重构 QEA(本 session,已合 main):
  grader/evaluator 拆分 · 删 PairwiseJudge → decide_keep_soft(连续 rubric %)
  · firewalled B-pile debugger(per-criterion verdicts + answer-free critic → sanitized payload)
  · 通用 leakage guard · Benchmark 抽象 · 删 A-pile/ablation(synthetic --mock)· iron law 2 → observation firewall
        │  → 出发点 1:重构有没有修好"修幻觉失败"?
        ▼
[Exp 1 · loop_test_2026-06-16] 重构后首个真实 run(10 iters):
  ✅ keep rate 脱离 0(3/10 kept,headroom OBSERVED 0.609→0.662)→ observation-space 修复落地
  ⚠️ 但发现 FORMAT BASIN:10/10 edit 全是格式型;Accountants/Auditors 卡在 0.282
        │  → 出发点 2:为什么 proposer 出不来?
        ▼
[诊断] 根因 = 进化的是 TEXT 不是 CODE:worker 物理上产不出 rubric 要的 .xlsx 工件
        │  → 出发点 3:给 worker 加"产 .xlsx"能力(框架 seed,不是 evolve)
        ▼
[Step 2 · 工程] v0.1 file-producing worker(本 session,16 commits/40 tests):
  seed tool:xlsx_writer · subprocess exec_artifact · render 桥接 → grader 能 credit 工件
        │  → 出发点 4:工件真能产吗?尾部能拉起来吗?
        ▼
[Exp 2 · xlsx_test_2026-06-16] v0.1 真实 run(3 iters,跑完):
  ✅ 机制成立:全程产出 17 个真 .xlsx / 8 个任务(含能对平的会计摊销表);seed 分 0.609→0.660(+0.05)
  ❌ 但单靠"产文件"不够:headroom NOT observed(0.660→0.659 平);Accountants 尾部 0.292 ≈ 没动;3/3 edit 仍全是格式型
        │  → 下一层 = 内容正确性 + 忠实评分(file-aware grader),非"能产文件"
        ▼
[下一步] sub-project 3 忠实 grader(.xlsx→图片→多模态 / cell-level 硬验证)成为关键路径;并把这条线接到双 benchmark 路线(§5)
```

**一句话**:重构修好了"proposer 修幻觉失败"(Exp 1 keep 脱离 0)并暴露 **format basin**;诊断指向"进化只动 text、worker 产不出工件";v0.1 给 worker seed 了 xlsx 能力——**Exp 2 证实工件能端到端产出、seed 提分 +0.05,但"能产文件"本身没拉起会计尾部、也没让 proposer 逃出 basin**:下一层瓶颈是**内容正确 + 忠实评分**,正好接到 §5 的"file-output + 硬验证"路线。

---

## 1. 实验过程与结果 / Process & Results

### 目标 / Goal
本 session 两个实验串成一条线:**(Exp 1)** 验证刚合入的重构(firewalled B-debugger + decide_keep_soft)是否修好了上一阶段的 proposer-observation 缺陷,并观察下一个瓶颈;**(Exp 2)** 针对 Exp 1 暴露的 format basin,验证假设——**会计尾部上不去是因为 worker 物理上产不出 .xlsx 工件**,做法是 v0.1 给 worker seed "产 .xlsx"能力,看 (a) 工件能否端到端产出、(b) 尾部能否拉起、(c) proposer 能否逃出 basin。

### 方法与过程 / Method & Process
- **Step 1 工程(apparatus,已合 main commit `0dd68ad`)**:重构 QEA——grader/evaluator 拆分、删 PairwiseJudge → `decide_keep_soft`、**firewalled B-pile debugger**(per-criterion rubric verdicts + answer-free critic → sanitized payload,proposer 拿不到答案)、leakage guard、Benchmark 抽象、删 A-pile/ablation(synthetic `--mock`)、iron law 2 → observation firewall。**动机**:修上一阶段 `proposer_observation_space` 缺陷(A-pile debugger 语义喂 B-pile 写作任务 → 修幻觉失败,旧 run 0/7 kept)。
- **两次真实 run 对照**,同模型(quant + evolve = `deepseek-v4-pro`,judge = `qwen3.7-max`,均经 OpenRouter),同 30 个 GDPval finance 任务,同 gate `decide_keep_soft`:
  - **Exp 1 — `loop_test`(无 xlsx,= 重构验证 + 发现)**:`results/loop_test_2026-06-16/`,10 iters,跑完。它**不是单纯 baseline**——是重构后的首个真实 run,既验证 B-debugger 修复,又暴露 format basin。
  - **Exp 2 — `xlsx_test`(有 xlsx,v0.1)**:`results/xlsx_test_2026-06-16/`,3 iters(iter 1 已完成 + 10 工件;iters 2–3 正 resume,**本报告时点未完**)。
- **Step 2 工程 = v0.1 实现**(16 commits,6 个 TDD task,40 tests green;spec/plan 见 `docs/superpowers/specs|plans/2026-06-16-xlsx-producing-worker*`):
  - `qea/sandbox.py::exec_artifact` —— **subprocess 沙箱**(`python script.py` 跑在一次性 temp work_dir,scrubbed env 抹掉密钥,超时杀进程;借鉴 AHE `LocalSandbox` 的纯 stdlib 切片)。
  - `qea/artifacts.py` —— `extract_openpyxl_code`(从 worker LLM 输出里抓 openpyxl 代码块)+ `render_xlsx`(把产出的 .xlsx 渲染成忠实文本:文件名 + sheet + 单元格值 + 公式串)+ `assemble_artifact_deliverable`(extract→exec→落盘→render,**永不抛异常**)。
  - seed 新增 `tool:xlsx_writer`;real B worker 检测到该 tool 就在 prompt 里告知"可产 workbook",并把产出走渲染管道。`EvalSummary.deliverables` 仍是 `str`(narrative + 渲染文本),所以 grader / 防火墙 / leakage-guard 全不动。
  - **关键设计点**:openpyxl 写出的公式没有计算值,故 v0.1 只渲染**公式串 + 字面值**,不算公式结果(留给 sub-project 3)。

### 数据与结果 / Data & Results

**三条结论:(1) Exp 1 —— 重构修复落地:keep rate 脱离 0(3/10,headroom OBSERVED),对比旧 run 的 0/7。(2) Exp 2 —— xlsx 机制成立:v0.1 真实模型下端到端跑通,全程产出 17 个真 .xlsx;seed 分 +0.05(artifact criteria 现在可 credit)。(3) 但 —— "能产文件"本身不够:Exp 2 headroom NOT observed(0.660→0.659 平),Accountants 尾部 0.292 ≈ 没动,3/3 edit 仍全格式型。** 对照数据:

| 指标 | Exp 1: `loop_test` 无 xlsx (10 iters) | Exp 2: `xlsx_test` 有 xlsx (3 iters,完整) |
|---|---|---|
| seed mean rubric % | **0.6088** | **0.6604**(+0.052,= xlsx 能力效应) |
| 工件产出 (.xlsx / 任务) | 0 | **17 / 8** |
| 已 keep edit | 3/10(脱离 0;旧 run 0/7) | 1/3 |
| 轨迹 ms_traj | 0.609 → 0.662 | 0.660 → **0.659（平,headroom NOT observed)** |
| Accountants/Auditors mean | **0.282** | **0.292(≈ 没动,.xlsx 墙仍在)** |
| proposer edit 是否逃 basin | 否(10/10 格式型) | **否(3/3 仍格式型:format_specialist / structured_formatter / format_enforcer)** |
| noise floor | 0.0237 | **0.010**(cache 把同-incumbent 噪声压成 judge-only → floor 触底) |

**per-occupation 对照(两 run 终态,incumbent 不同,仅指示):** Accountants 0.282→0.292、Fin Managers 0.655→0.659、Analysts 0.728→**0.825**、Advisors 0.882→0.874、Real Estate 0.835→0.787、Securities 0.593→0.516。→ **seed 的 +0.05 没落在会计尾部**(它仍 0.29),而是散在本就有工件任务、且未触底的 occupation 上;**会计尾部真正缺的是内容正确 + 能判内容的 grader,不只是"有没有 .xlsx"。**

**Exp 1 暴露的 format basin（关键发现)—— 10/10 个 edit 全是格式型:**

| iter | edit | verdict |
|---|---|---|
| 1 | skill:**output_format**_validator | rollback (MIXED) |
| 2 | prompt:**format**_instructions | **keep** |
| 3 | prompt:**output_schema**_instruction | rollback (HARMFUL) |
| 4 | skill:output_**autoformatter** | rollback (MIXED) |
| 5 | skill:llm_answer_**formatter** | **keep** (PARTIALLY_EFFECTIVE) |
| 6 | validator:**format**_compliance | rollback (MIXED) |
| 7 | router:**format**_reminder | **keep** |
| 8–10 | dynamic_**format_schema** / **format**_enforcer / output_**sanitizer** | rollback (HARMFUL ×3) |

per-occupation(Exp 1 终态):Advisors 0.882 / Real Estate 0.835 / Analysts 0.728 / Fin Managers 0.655 / Securities 0.593 / **Accountants 0.282(.xlsx 墙)**。

### 案例研究 / Case Study —— worker 真的产出了一份会计工作簿

任务 `7d7fc9a7…`(GDPval prepaid amortization schedule,正是 Accountants 尾部)。**之前(text-only)**:worker 只能写文字 → rubric 的"提交为 .xlsx 工作簿"类 criteria 永远 fail → 0.282。**现在(v0.1)**:worker emit 了 openpyxl 代码,`exec_artifact` 跑出真文件 `Aurisic_Prepaid_Schedule.xlsx`,`render_xlsx` 把它渲染进 deliverable。渲染节选(真实产出):

```
[ARTIFACT FILE: Aurisic_Prepaid_Schedule.xlsx]
Sheet "..." : A11:'Monthly Activity Summary'
  A12:'Month' B12:'Beginning Balance' C12:'Additions' D12:'Amortization Expense' E12:'Ending Balance'
  A13:'January'  B13:0          C13:622721.83  D13:103786.97  E13:518934.86
  A14:'February' B14:518934.86  C14:13830.29   D14:106092.02  E14:426673.13
Sheet "Prepaid Insurance" (18x15): A1:'Aurisic' A2:'Prepaid Insurance (Account #1251)' ...
```

这是一份**多 sheet、能对平的**摊销表(`0 + 622721.83 − 103786.97 = 518934.86` ✓)。GDPval 该任务 rubric 的核心就是"Begin + Adds − Amortization = End、variance == 0"——现在 grader 能从渲染文本里 credit "提交了 .xlsx / 有这些 sheet 与列"这类**结构**criteria。**这就是机制证据:从"结构上不可能满足"到"产出真工件并被渲染打分"。** ⚠️ 但注意(§2.4):该任务终态仍 0.292——结构可 credit 了,**内容是否正确(抽样规则全覆盖、数值对不对)现有文本 grader 判不了**,要等 sub-project 3 的忠实/cell-level grader,这正是 Exp 2 的关键负面结论。

---

## 2. 分析 / Analysis

### 2.1 format basin 的根因 = "进化的是 text,不是 code"
**Exp 1 的 10/10 格式型 edit 不是 proposer 笨,是它的 action space 只有文字。** 看代码就清楚 QEA 到底进化什么:
- `Component.content` 是 **`str`**;evolve_agent 提的 `Edit` 也只带一个 `content` 字符串。
- 这些 content 怎么被消费?`harness.assemble_system_prompt()` 只把 **prompt / skill / memory / validator** 四个槽的 content 拼进 worker 的 **system prompt**(纯文本)。`tool / middleware / router` 槽**根本不注入** worker。
- worker 的**执行**(A-pile 的 `safe_exec_solve`、B-pile 的一次 `llm.complete`、现在的 `exec_artifact`)是**固定的框架代码**,不在演化面上。

**结论:QEA 进化的是 TEXT(prompt 片段),从不进化可执行 code。** "tool" 组件只是 inert 文字描述,真实行为硬编码在框架里。所以当 proposer 看到"缺 .xlsx",它**唯一能做的就是改 prompt 文字**(加格式指令)→ 但文字永远把 text 变不成 .xlsx → basin。这是 scaffold(可演化文字)vs substrate(固定代码)的边界。

### 2.2 为什么 xlsx 必须 seed,而不是等它演化出来
"产 .xlsx"是 **substrate 能力**(要真跑 openpyxl、写文件),不是一段 prompt。proposer 在 scaffold 上工作,够不到 substrate。所以正确做法是**框架层 seed 这个能力**(v0.1 做的),然后让演化在上面做流程优化(何时用、放哪些 sheet)。这也符合 iron law 1:harness 修流程瓶颈,capability gap 该由框架补。

### 2.3 横向对比 AHE 的 harness 进化
AHE(`/Users/kevinwu/Coding/agentic-harness-engineering`,QEA 的来源)进化的是**真 agentic harness**;QEA 是它的极简化:

| 维度 | **QEA(本仓库)** | **AHE(原版)** |
|---|---|---|
| 进化对象 | 7 槽里的 **text prompt 片段**(只有 prompt/skill/memory/validator 真进 worker) | 真 agent 的**文件**:code / config / skills / prompts |
| evolve 动作 | 写一个 prose 组件(`Edit.content: str`) | 用 `multiedit_tool`/`apply_patch` **patch 文件** |
| worker | 一次 `llm.complete` → text(+ 固定 exec substrate) | **agentic**:NexAU sandbox 上的 tool loop(`run_code_tool`/shell/file/web) |
| tools | **inert 文字描述**(code_exec/xlsx_writer 行为框架硬编码) | **真可执行工具模块** |
| 产工件 | 无 →（v0.1 才 seed 了 xlsx,经框架 `exec_artifact`) | 有(worker 跑 shell/python 原生产文件) |
| falsification | `evaluate_changes` verdict taxonomy + gate + rejected-edit buffer（**从 AHE/SkillOpt port**) | 同源(AHE 是出处) |
| 取舍 | 干净、便宜、确定性、可归因的机制 check——但进化的是"玩具" harness | 真实 agentic harness——但进化起来重、贵、noisy |

**v0.1 的 xlsx 工作 = 把 AHE substrate 的一个最小切片(`exec_artifact` ≈ 纯 stdlib 的 LocalSandbox)seed 进 QEA**,让 worker 能产真工件——朝 AHE 靠了一步,但是 seed(框架写)而非 evolve(proposer 写)。完整方向("让 evolve_agent 自己造可执行工具")= tool synthesis,记在 [Track 2 / future](../superpowers/specs/2026-06-16-xlsx-producing-worker-design.md)。

### 2.4 这次 xlsx 数据怎么读(诚实版,Exp 2 已跑完)
三层结论,前两层正面、第三层是关键的负面发现:
- **✅ 机制成立(强证据)**:全程产出 **17 个真 .xlsx / 8 个任务**(会计摊销表、MSCI 相关性矩阵、Roth 转换表、payroll、P&L 等),被 grader 渲染读到。单元测试覆盖不到的集成路径,在真实模型下确实跑通。
- **✅ seed 提分(中证据)**:seed mean 0.6088→0.6604(+0.05),方向符合"artifact criteria 现在可 credit"。
- **❌ 但"能产文件"本身没解决问题(关键负面)**:(a) 演化在上面 **headroom NOT observed**(0.660→0.659 平,1/3 kept 且那一个 keep 落在跨-resume 重采样噪声里);(b) **Accountants 尾部 0.292 ≈ 没动**——seed 的 +0.05 散在别的占位,没落在会计墙;(c) **proposer 仍困 format basin**(3/3 edit 全格式型)。

**为什么 "产文件" 不够 → 指向下一层**:interim grader 是把 .xlsx **渲染成文本**喂现有 LLM judge——它能 credit "是 .xlsx / 有 sheet X / 用了公式"这类**结构/存在**criteria(故 seed 提了 +0.05),但**判不了内容是否正确**(抽样逻辑对不对、摊销表是否真对平、数值是否准)。会计尾部 rubric 的核心恰恰是内容正确。所以 v0.1 证明了"产文件"这一半,**剩下一半是"内容正确 + 能判内容的忠实 grader"(sub-project 3)**——这也正是 §5 双 benchmark 路线里"file-output + 硬验证(AFC cell-level verifier)"的动机。同时 proposer 仍只提格式 edit,说明**它的观测(critic note / tag)仍被格式主导**,需要让 critic surface 内容缺陷而非格式。

---

## 3. 问题与困难（待讨论）/ Problems & Open Questions

1. **[已解决] never-raise 纪律**:worker 现写代码会产坏文件/超时/损坏 .xlsx;`exec_artifact`(超时杀进程)+ `assemble_artifact_deliverable`(render/copy 都 guard、temp dir 在 finally 清理)保证任何情况只降级不崩。corrupt-xlsx 有回归测试。
2. **[已解决] 安全**:worker 代码跑子进程,env 抹掉 `*_API_KEY/*_TOKEN/OPENROUTER*`,子进程内 assert 验证拿不到 `OPENROUTER_API_KEY`。
3. **[关键负面,Exp 2 已证] "产文件" ≠ 解决尾部**:v0.1 让 worker 产了 17 个真 .xlsx、seed +0.05,但 Accountants 尾部 0.292 没动、headroom 平、proposer 仍只提格式 edit。**根因**:interim grader 只把 .xlsx 渲染成文本判**结构/存在**,判不了**内容正确**。**讨论点**:这把 **sub-project 3(忠实 file-aware grader / cell-level 硬验证)从"锦上添花"升级为"关键路径"**——不上它,file-output 维度拿不到真梯度。
4. **[待讨论] 噪声地板触底**:Exp 2 noise floor = **0.010**(deliverable cache 把同-incumbent 两次 eval 压成 judge-only 噪声 → floor 撞 `max(0.01,…)` 下限);而跨 `--resume` 重启重采样摆动 ~0.017(iter1 的 keep 就落在里面)。→ **floor 低估了真噪声,部分 keep 是噪声驱动**。**讨论点**:noise floor 应在 worker 也重采样的条件下估,或对 incumbent k-sample。
5. **[待讨论] 公式只渲染串、不算值(v0.1 限制)**:"用公式且数值正确"类 criteria judge 只能心算。**讨论点**:并入 sub-project 3 的 LibreOffice 重算 + 多模态,还是 interim 先加 `formulas`/`pycel`(pip)。
6. **[待讨论] proposer 观测仍格式主导**:即便能产文件,B-debugger 的 critic note / tag 仍让 proposer 只提格式 edit(2 个 run 共 13/13 格式型)。**讨论点**:critic 是否要被迫 surface **内容缺陷**(抽样逻辑错、未对平)而非格式,才能让 proposer 提实质 edit。
7. **[待讨论] provider 摇摆**:停 OpenRouter 改 DashScope Anthropic 网关失败(token 被拒 401/403 `invalid api-key`,两 header 都试),已 rollback;`AnthropicLLM` backend 已就位(token 一设自动切)。**讨论点**:长期算力走哪家——代码 provider-无关,换家只改 `.env`。

---

## 4. 下周计划 / Next Week's Plan

**(Exp 2 已跑完,判定:xlsx 机制成立但"产文件"没解尾部 → 下一步重排序)**
1. **【关键路径】sub-project 3 — 忠实 file-aware grader**(Exp 2 把它从可选升为必做):.xlsx → LibreOffice headless 渲染 → 图片 → 多模态 judge(AHE `read_visual_file` 是参考),顺带公式重算(问题 5);并对 **AFC 类任务先做 cell-level 确定性 verifier**(§5.3.4),让 file-output 维度真正拿到内容梯度。
2. **修噪声地板**:worker k-sample / 跨 resume 用稳态分数,让 floor 反映真噪声(问题 4)——否则 keep 信号不可信。
3. **让 critic surface 内容缺陷**:改 B-debugger 观测,使 proposer 能提实质 edit 而非 13/13 格式型(问题 6)。
4. **sub-project 2 — gold-file 获取**:fetch+缓存 GDPval `deliverable_file_urls` 后的人工 gold 文件,为 vs-gold 忠实评分铺路。
5. **双 benchmark 路线启动(§5)**:**发起 FAB private validation 450 的 license 申请**(§5.4 待决第 1 项,组内确认后);搭 baseline harness 做进化种子;GDPval 作 held-out。
6. **Track 2 / provider**:tool synthesis(`exec_artifact` 已是纯 stdlib 前置)按需单开;算力 provider 定盘后改 `.env` 即可。
6. **算力 provider 定盘**(问题 5):给一个有效 key,`.env` 切换即可,无需改代码。

---

## 5. 后续路线 / Research Roadmap — 多模态输出 × 双 benchmark 进化
> 来源:一次技术讨论纪要(2026-06)。**⚠️ 本节所有 benchmark 数字均来自公开来源、为讨论时点值,正式引用前务必复核最新 leaderboard / 样本量(出处见 §5.6)。** 与本 session 的关系:v0.1 的 file-producing worker 正是这条路线的第一块砖(file-output 能力 + §5.4 的"文件输出 + 硬验证"桥梁)。

**目标重定:让 QEA 在 finance 域内,从一个(近)无工具 agent 进化成能覆盖 file-output 与文本 QA 两类任务的 finance agent;但"对着两个 benchmark 一起进化成通用 agent"这一原始表述有结构性问题,需重构(§5.3)。**

### 5.1 核心技术结论:多模态 I/O 的硬约束 → fitness landscape 不连续
- **输出端**:LLM 前向只产 token;**xlsx 是 zip 二进制,单次 LLM 调用稳定产不出**。产 xlsx 必须有一层"执行/序列化"(谱系:最小 = 模型吐 JSON/代码 + 宿主 `df.to_excel()`;最大 = 带文件系统的 agentic harness)。标准模式恒为 **模型写代码 → 代码产文件**(openpyxl/pandas)——这正是 v0.1 `exec_artifact` 做的。
- **输入端(对称)**:xlsx 也非原生输入模态。两条路:(A)预先 `read_excel` → CSV/MD/JSON 文本进 prompt(结构固定时首选);(B)给 code-exec 工具让模型自己 `pd.read_excel`。厂商"文件上传"本质是托管版路径 B。
- **对 QEA 的关键含义**:file-output 任务上,真·无工具 agent 得分硬性 ≈ 0(交不出文件),**该维度梯度是平的**——进化必须在早期跨过"获得 code execution"这道**不连续的坎**。对比文本 QA(FAB)无工具仍能凭记忆给非零答案,**landscape 连续**。两 benchmark 的进化轨迹形状因此显著不同,需分别处理。

### 5.2 两个 benchmark 对比（已 web 复核 2026-06;✓ = 已确认,出处见 §5.5)
| 维度 | GDPval(finance 子集) | FAB v2(Vals AI) |
|---|---|---|
| 输出形态 | **真实文件** ✓(documents/slides/diagrams/spreadsheets/multimedia) | **纯文本答案 + 数字,无文件** ✓ |
| 评分 | blind pairwise **win-rate** ✓(官方:专家盲比模型 vs 人类交付;Artificial Analysis 出 GDPval-AA Elo 版)——one-shot/主观/慢/贵 | **dealbreaker 门控加权 partial credit + All-Pass** ✓(可程序化硬验证) |
| 工具/harness | 开放、**官方 agent harness 未开源**;但 OpenAI 开了 `evals.openai.com` 自动评分服务 ✓ | **固定六工具** ✓(`edgar_search`/`web_search`/`parse_html_page`/`retrieve_information`/`calculator`/`price_history`),已开源;每题 2h(纪要,未单独复核) |
| 规模 | **1320 全集 / 220 gold 开源 ✓;Finance&Insurance gold = 25 题 ✓** | **927 ✓ = public 27 / private validation 450(可 license ✓)/ test 450;成绩只报 test 防过拟合 ✓** |
| 自动 fitness 信号 | **无**(需自建 grader) | **有**(但 public 仅 27) |
| 能否进 QEA loop | **否**(win-rate/Elo 非 hard verifier) | **是**(注意样本量) |
| 顶格成绩 | 顶级模型 win-rate vs 人类专家**多数仍 <50%**,确切区间以 GDPval / GDPval-AA leaderboard 为准(原"47–70%"未精确复核) | partial credit **Gemini-3.5-Flash 57.86 / Fable-5 56.31 / Opus-4.8 53.92 ✓;All-Pass 全 <46% ✓** |

- FAB 九类中 **Financial Modeling(如 Ralph Lauren 困境收购 Capri 评估 + DCF)与 Precedents top out 仅 23% ✓**(对比:Earnings/General-Quant/General-Qual 70%+、Disclosure/Market 60s%)→ **Financial Modeling 是最高 headroom 方向**。
- GDPval 代表性 xlsx 任务 = **反金融犯罪风险审计(AFC,Accountants & Auditors)**:`Population.xlsx` 进 → 按 90% 置信/10% 误差算抽样量、J 列环比方差、按多条件规则在 K 列标记抽样 → 产 `Sample.xlsx`(两 tab)。**xlsx-in/xlsx-out 且抽样逻辑有确定答案** → 可写 cell-level 确定性 verifier(§5.3.4 关键)。

### 5.3 方案重构(可行性判断)
1. **评分形态不兼容 → 一个进 loop,一个 held-out**:铁律"hard verifier only in loop"直接排除 GDPval(Elo 主观)。**FAB-style 可验证任务进 evolution loop 当 fitness;GDPval 作 held-out 泛化测试,仅结束时评一次。** 叙事增益:"在可验证任务上进化的 harness 能否迁移到文件输出任务"本身是干净的研究问题。
2. **fitness 数据量 = 比架构更先决的瓶颈**:FAB public 仅 27 → 直接进化必过拟合,test 私有报不了;GDPval 220 无 grader。**方向(倾向已定,待组内确认)**:in-loop fitness 倾向 **(a) license FAB private validation 450**(已确认该 set 可申请 license);备选 (b) 自建数百~上千道程序化可验证 SEC QA。**此决策定下来前,进化算法与 harness 接口都是空中楼阁** → 已列为待办第 1 项申请 license。
3. **"从零工具进化"的预算风险 → baseline harness 做种子**:头 ~80% 提升来自已知 scaffolding(code-exec/EDGAR/calculator);QEA 卖点是 **harness 源码进化**,越过 table-stakes 才有意义。**用合理 baseline harness 做进化种子,把预算投到非显然部分。**(与本 session 的"capability 该 seed、process 才 evolve"判断一致。)
4. **AFC 审计任务 = file-output + 硬验证的桥梁**:其抽样量公式/方差列/规则覆盖可写成 cell-level 确定性 verifier,不依赖 Elo。**行动:找/造一小批"文件输出 + 可程序化校验"任务,把 file-output 维度纳入 hard-verifier loop**,让进化在多模态输出上真正拿到梯度,而非只在纯文本上进化、指望白白迁移。(= 本 session sub-project 2/3 的硬验证版延伸。)
5. **成功判据重构**:不以绝对 SOTA / "通打"为目标(学生项目难刷榜首)。**改为:进化出的 harness vs 强手工 baseline harness 在同 benchmark 上的相对增益,逐 category 拆 delta。** 覆盖范围**初步定为全 9 类(做尽量通用型)**,但仍逐类报 delta——这样既保通用性,又能把最高 headroom 的 **Financial Modeling**(及 Precedents)当 headline 子 claim(如"harness 进化把 Financial Modeling pass rate 从 X 提到 Y"),通用性与可发表/可证伪兼得。

### 5.4 待决 / 已定问题
**仍待决(优先级序):**
1. **in-loop fitness 数据(最高优先级)**:**倾向 license FAB private validation 450**(已确认可申请),**待组内讨论确认**;备选自建可验证 SEC QA。决定后续全部设计 → **行动:发起 license 申请**。
2. **种子 harness**:进化起点是真·无工具还是 baseline harness?报告里怎么处理"不连续坎"?(§5.1 / §5.3.3)
3. **baseline 对照**:强手工 harness 的具体配置(算相对增益用)。

**已定(本轮讨论拍板):**
- **GDPval 接入**:GDPval 作 held-out win-rate/Elo 一次性评测 **+** 为 AFC 类"文件输出 + 可硬验证"任务自建 cell-level verifier 子集(§5.3.1 + §5.3.4)。
- **category 粒度**:**初步覆盖全 9 类,做尽量通用型**,逐类报 delta,Financial Modeling(+ Precedents)为 headline 子 claim。

### 5.5 出处(已 web 复核 2026-06)
- **GDPval** ✓:OpenAI GDPval 论文 [`arXiv:2510.04374`](https://arxiv.org/abs/2510.04374);[OpenAI 官方页](https://openai.com/index/gdpval/) + 自动评分 `evals.openai.com`;[Epoch AI](https://epoch.ai/benchmarks/gdpval);amaarora 复现博客(SmolAgents harness,含 AFC 审计任务 prompt 原文)。**已确认**:1320 全集 / 220 gold / Finance&Insurance gold 25 题 / 文件型交付 / blind pairwise win-rate。
- **FAB v2** ✓:[Vals AI 官方页](https://www.vals.ai/benchmarks/fabv2);论文 [`arXiv:2508.00828`](https://arxiv.org/abs/2508.00828);[GitHub `vals-ai/finance-agent-v2`](https://github.com/vals-ai/finance-agent-v2)。**已确认**:927(27/450/450,test-only 计分)/ 六工具(v1.1 四工具 + calculator + price_history)/ partial-credit 57.86·56.31·53.92 / All-Pass <46% / Financial Modeling & Precedents top out 23% / 九类。
- 仍**待复核**:GDPval 文件交付占比的精确百分比与 SOTA win-rate 区间;FAB"每题 2h"时限。
