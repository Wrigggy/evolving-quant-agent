# QEA v0 — PLAN (locked, awaiting final go)

> Evolving Quant Agent (QEA) v0。状态：**方案已按 review 调整完毕，等你最后 go 才写代码**。
> 目标：复用已复现的 AHE `evolve -> falsify -> rollback` 回路，组件层换成 quant 语义，打一个 task family
> （**真实 GDPval Econ/Finance/Accounting**），做机制验证。成败看 §7 的机制信号，不看绝对分数。
>
> 本文档中文 + 英文术语；代码 / 注释 / 标识符 / README / ROADMAP 用英文（CLAUDE.md）。

---

## 0. 锁定决策 / Locked decisions（review 后）

| # | 决策 |
|---|---|
| 复用方式 | **(A) 轻量移植**：新建独立 `qea/` 包，搬走 AHE 的纯逻辑，**不引入 NexAU/harbor/E2B** |
| 任务族 | **真实 GDPval Econ/Finance/Accounting**（"Finance and Insurance" 板块 5 类职业），接真数据 |
| 实验形式 | **2-arm ablation**（见 §3.6）：Arm1 evolve-A→transfer-B（铁律2干净基线）；Arm2 evolve-A+B（B 软信号进回路，铁律2放松） |
| A 堆硬 verifier | 结构化输出 `{metric: value}` + 从 `rubric_json` 抽/重算 answer key + perturbation probe；真 A 堆太薄的 subtype 用同类合成任务补信号量 |
| B 堆 verifier | 真 GDPval + soft LLM-judge；Arm1 仅冻结后 transfer，Arm2 额外进回路 |
| real 跑规模 | **小规模冲烟级**：A 堆 ~6-10 task、3-4 iter、k=2；B 堆 transfer ~10-15 task、judge 1 次 |
| 模型 | `quant_agent` / `evolve_agent` / judge **都用 `deepseek-v4-pro`**（OpenRouter，provider.order pin、402/429 backoff、并发<=10） |
| worker 改名 | `code_agent` -> **`quant_agent`**（财务工作可能异于 coding） |
| 七 slot | 命名/颗粒度保留：`tool / middleware / skill / prompt / validator / memory / router` |
| SkillOpt | 最小：rejected-edit buffer（无语义去重，仅精确/归一化匹配）+ edit budget=1；**不上** cosine 调度 |
| selection split | **不做**（v0）。防过拟合/OOS 信号改由 perturbation probe + B 堆 transfer 承担 |
| mock | 仍保留为零-API-key 冒烟测试；real 模式新增 |
| 文档语言 | README / ROADMAP 英文 |

---

## 1. 探索结论（依据）/ What grounds this

- AHE 回路是真的，但「无 headroom 钉死平台期」（Case A 证因果连通 + falsification 正确；Case B 证空转 churn，正是 rejected-edit buffer 要治的病）。
- `evaluate_changes` verdict 引擎 + iteration-diff + 三层 observability + change-manifest schema **纯 Python 零耦合** -> 可搬。
- 重耦合只在 eval（harbor/E2B/terminal-bench）与 ADB（adb CLI）两处 -> 替换/包装掉。
- GDPval：公开 ungated 数据集 `openai/gdpval`，220 gold，含 "Finance and Insurance" 板块 25 行财务/会计任务，确认有摊销表（$559,377.61）、NPV/IRR/WACC=9%、美式期权定价等数值内核。**但无任何原始任务自带硬 verifier**（评分=LLM-judge/专家配对）-> A 堆硬信号需自建（见 §4）。
- SkillOpt（arXiv:2605.23904，MIT）三机制有代码级细节；v0 只取 rejected-edit buffer + edit budget。

---

## 2. 复用图 / Reuse map

### 直接搬（reuse as-is，搬运+轻改写，逻辑不变）
| 来源 | -> QEA | 说明 |
|---|---|---|
| `evolve.py:2245` `evaluate_changes` | `qea/falsify.py` | EFFECTIVE/PARTIALLY/MIXED/INEFFECTIVE/HARMFUL verdict，纯函数 |
| `evolve.py:836` `compute_iteration_diff` | `qea/falsify.py` | flipped/regressed（数值版：subtype 分数升降） |
| `evolve.py:749-833` task history / stability | `qea/observability.py` | 稳定性 / 去噪 |
| `evolve.py:563-602` `pass_at_k_est` 思路 | `qea/verifier.py` | 改造成 numeric k-repeat 去噪（铁律 3） |
| `change-manifest-schema.json` | `qea/manifest.py` | change-manifest schema **原样复用**（标注 subtype + arm） |
| iteration_NNN 三层目录布局 | `qea/observability.py` | eval / manifest / workspace 三层落盘 |
| `code_agent_simple` 单-tool-其余空 种子理念 | `qea/seed.py` | minimal seed（归因纯净） |
| `evolve.py:115-174` config 继承 / env 解析 | `qea/loop.py` | 轻量保留 |

### 包装（wrap）
- eval 入口（harbor/E2B/terminal-bench）-> `qea/verifier.py` 确定性数值 verifier（本地 exec + timeout）。
- ADB（adb CLI）-> `qea/agents.py::diagnose()` 轻量 trace->root-cause（real=LLM，mock=脚本）。
- agent 调用（harbor 拉 NexAU）-> `qea/agents.py` 的 `quant_agent` / `evolve_agent`，直连 OpenRouter + mock。
- LLM client -> `qea/llm.py`：OpenRouter client + `MockLLM`。

### 替换（replace）
- terminal-bench -> 真实 GDPval Econ/Finance/Accounting（A 硬 / B 软）。
- pass@k 二值 -> 数值「容差内匹配」+ per-subtype 分数。
- ADB QC 分类 -> quant 失败分类：`Hardcoding / WrongFormula / MissingEdgeCase / BadFormat / InsufficientCapability`（+ `LookAhead` 占位）。
- 单一聚合 -> **per-subtype** OOS（option_pricing / amortization / audit_metric / valuation）。

### 不引入（v0）
NexAU、harbor、E2B、adb CLI、terminal-bench、多 family 路由、deliverable 解析器（用结构化输出绕开）、selection split、SkillOpt 的 L_t 调度。

---

## 3. 架构 / Architecture

### 3.1 七组件池（NexAU 风格 slot，quant 语义）
5 继承 + 2 quant 原生。种子只 `tool` 非空（一个确定性 code-execution sandbox 跑 quant_agent 的解），其余六空：

| QEA slot | 对应 AHE | 种子 |
|---|---|---|
| `tool` | tools | **唯一非空**：code-execution sandbox |
| `middleware` | middleware | 空（含 look-ahead guard slot） |
| `skill` | skills | 空 |
| `prompt` | system_rules | 仅最小种子指令 |
| `memory` | long_term_memory | 空 |
| **`validator`** | （新增） | 空 — 硬 verifier / perturbation probe / integrity guard |
| **`router`** | （新增） | 单族两路：A->硬 verifier，B->软 judge |

### 3.2 verifier router
task 进来 -> 判 pile（A/B）-> 路由：A 走确定性硬 verifier，B 走 soft LLM-judge。**硬 verifier 驱动回路；软 judge 仅在 Arm1 transfer 或 Arm2 进回路时使用**。

### 3.3 integrity guard（quant 旗舰组件）
1. **perturbation probe（v0 主力，在 verifier 里）**：扰动参数重算，要求解仍正确。hardcode 常数过 base、过不了 probe。**因为不做 selection split，probe 就是 A 堆的主防过拟合/OOS 信号**（held-out 参数空间）。
2. **look-ahead data-access middleware（slot 占位 + stub）**：时序族硬拦读 t 之后数据；v0 数值任务无时间轴不触发，建好 slot，标 ROADMAP。

### 3.4 falsification + verdict + rollback（**无 selection split**）
- **gate**：full-eval（含 perturbation probe）的 per-subtype 分数**严格改进**才算 EFFECTIVE；平局/不升 = reject。沿用 EFFECTIVE/PARTIALLY/MIXED/INEFFECTIVE/HARMFUL。
- **k-repeat 去噪**（铁律 3）：数值 verifier 虽干净，仍走 k=2 路径以泛化到 B 堆软信号（软 judge 必须多 repeat）。
- **rejected-edit buffer（SkillOpt a）**：非 EFFECTIVE 的 edit 入 buffer（`{edit_text, target, verdict, score_before/after, failure_pattern}`），下轮渲染进 proposer 上下文「已证伪，别再提」。**不做 embedding/语义去重**；mock 用精确字符串匹配演示拦截。
- **edit budget（SkillOpt c）**：固定 `L_t = 1 edit/iter`。
- **rollback**：reject 还原到上一 best/incumbent（保留 best vs current 双轨）。
- ⚠️ Arm2 的 B 堆进回路 = 软 judge 当主信号 = 放松铁律 2，且 B 堆无 probe 护栏 -> 故必须有 Arm1 干净基线对照。

### 3.5 per-subtype task-delta（铁律 4）
manifest 标注 subtype + arm；OOS 按 subtype 分别记。抬一压一必须可见、不自动保留。

### 3.6 2-arm ablation（核心实验）
- **Arm 1（基线，铁律2干净）**：种子 harness 在 **A 堆**（硬 verifier）evolve N iter -> 冻结 -> 在 **B 堆**（软 judge）做 transfer 评测。另记种子 harness 直接打 B 堆作 baseline。
- **Arm 2（B 进回路）**：种子 harness 在 **A+B 全集** evolve（A 硬 / B 软，软信号进 verdict）-> 同样 transfer 评测。
- **对比**：Arm2 vs Arm1 的 (i) A 堆 in-domain 单调性、(ii) B 堆 transfer 分数、(iii) verdict 稳定性 -> 回答「B 软信号进回路帮还是害」。
- mock 模式两臂都跑（脚本化、零成本）；real 模式按小规模跑。

---

## 4. GDPval adapter / 任务

接真实数据，两个 loader，回路与 verifier 接口对 real/synthetic/未来数据都不变：

- `load_gdpval_a_pile()` -> A 堆硬任务（驱动 evolve）：
  - 真 GDPval finance 数值任务：quant_agent 被要求输出 `{metric: value}` JSON；硬 verifier 比对从 `rubric_json` 抽取/重算的 answer key（如摊销 $559,377.61、NPV@WACC=9%、期权价）+ 不变式（如 `Begin+Adds-Amort=End`、`variance==0`）+ perturbation probe。**免解析 .xlsx/.pdf**。
  - 合成补足：真 A 堆太薄的 subtype（option_pricing/amortization/audit_metric/valuation）用同类合成任务补到 ~6-10，保证信号量（治薄集方差）。每个合成任务 docstring 引真实 GDPval task_id 标血缘（c7d83f01… / 7d7fc9a7… / b78fd844…）。
- `load_gdpval_b_pile()` -> B 堆软任务（transfer + Arm2 in-loop）：
  - 真 GDPval finance 主观交付物（advisory memo / 估值报告 / 策略）；软 judge 按 `rubric_pretty` 打 0-1 偏好/达标率。

每个 A-task 暴露：`prompt`、`inputs`、`reference(inputs)->expected`（纯函数）、`verify(answer, expected, tol)`（round-to-cent / 1e-6）、`perturbation_probe()`。

---

## 5. 文件清单 / File list（bias to fewer files, runnable）

```
evolving-quant-agent/
├── README.md / ROADMAP.md / PLAN.md
├── pyproject.toml            # 极简：numpy、pyyaml、(可选) pandas+pyarrow 读 GDPval parquet、(可选) openai
├── .env.example              # OpenRouter 接线 + MOCK_LLM 开关；3 路都 deepseek-v4-pro
├── run.py                    # 一条命令入口：`python run.py --mock` / `--real --arm both`
├── qea/
│   ├── __init__.py
│   ├── loop.py               # evolve->falsify->rollback 驱动 + iteration 编排 + config + 2-arm 调度
│   ├── harness.py            # 七 slot harness 对象、minimal seed、clone/apply-edit/rollback、verifier router
│   ├── falsify.py            # verdict 引擎（搬 evaluate_changes）+ iteration-diff + 严格 gate + rejected-edit buffer + edit budget
│   ├── verifier.py           # HardVerifier(数值+perturbation probe) + SoftJudge(LLM) + k-repeat 去噪
│   ├── tasks.py              # load_gdpval_a_pile() / load_gdpval_b_pile() + reference 纯函数 + 真数据 loader + task_id 血缘
│   ├── agents.py             # quant_agent(产出解) + evolve_agent(读 trace 提 1 edit) + diagnose()(轻量 ADB)
│   ├── llm.py                # OpenRouter client(provider pin/backoff/并发<=10) + MockLLM + 脚本化 mock edits
│   └── observability.py      # 三层 trace/score/manifest 落盘 + per-subtype 分数 + 稳定性 + ablation 汇总
└── tests/
    └── test_smoke.py         # 断言 mock 两臂跑出 §7 三信号
```

---

## 6. mock 模式（零 API key 冒烟）/ Mock design
确定性「世界模型」把 harness 状态映射到 per-subtype 分数。脚本化 4 次 edit：
1. **iter1 EFFECTIVE**：往 `validator` 加 `integrity_guard` -> 逼参数化解 -> 某 subtype 分严格升 -> keep。
2. **iter2 HARMFUL**：改坏 `tool`(code-exec) -> 全 error -> 掉分 -> rollback -> 入 buffer。
3. **iter3 overfit**：加只记忆/hardcode base 输入的 edit -> base 过但 **perturbation probe 挂** -> verdict HARMFUL/INEFFECTIVE -> rollback（演示 probe 杀过拟合，替代 selection split 的角色）。
4. **iter4 repeat**：重提 iter2/3 的 edit -> **rejected-edit buffer 评估前拦下**。
两臂都跑；打印逐 iter per-subtype 分数、每 edit verdict、B 堆 transfer、final headroom verdict。

---

## 7. 验收 / Acceptance（机制级；mock 跑即可达成，real 佐证）
1. 四 stage 真实且因果连通（同 Case A）：trace 里追同一 root cause 从 eval -> diagnose -> workspace -> verdict。
2. 选定族 OOS **单调上升**（铁律 1 headroom）；此处 OOS = perturbation-probe-robust 的 per-subtype 分数 + B 堆 transfer 分。
3. falsification 正确 rollback 过拟合 / 退化算子 edit（iter2/3/4 演示）。
4. （ablation 产出）Arm2 vs Arm1 的对比结论：B 软信号进回路是帮是害，有数有 verdict 稳定性对比。
`tests/test_smoke.py` 断言 1-3 在 mock 两臂成立。

---

## 8. 我会 stub 的东西（ROADMAP 标注）
- deliverable 解析器（用结构化输出绕开）；OpenAI 官方软评分器（用自建 soft judge 代）。
- look-ahead middleware（建 slot+stub，numeric 不触发）。
- 多 family 路由（router 单族两路）。
- 真 ADB（用轻量 `diagnose()` 代）。
- sandbox 隔离（`subprocess`/`exec`+timeout，不上 E2B）。
- **selection split**（v0 不做，ROADMAP）；SkillOpt L_t cosine 调度；buffer 语义去重。

**ROADMAP.md（NOT-in-v0）核心实验均按「fitness vs verifier-call-budget 曲线」对照 Life-Harness 全迭代 baseline + AHE 文件编辑 baseline 设计**：
(1) prioritized/credit-assigned harness search（PUCT-like VOI）；
(2) multi-fidelity verifier（先证 cheap proxy 与 full verifier 秩相关再 successive-halving）；
(3) entropic/risk-seeking pruning（保高方差 late-bloomer）；
(4) offline-amortized base + online-per-instance adaptation；
(5) **selection split 回归 + 跨时间窗/跨 regime 切分**（治非平稳）。

---

## 9. 待你最后 go / Final sign-off
方案已按 review 全部锁定（§0）。流程上：你 go 之后我先建**骨架 + mock 两臂闭环**（零成本、零 API），跑绿 `test_smoke.py`；**真实 OpenRouter 跑（约 <$10、一两小时）我会在跑之前再确认一次**，不擅自花预算。
