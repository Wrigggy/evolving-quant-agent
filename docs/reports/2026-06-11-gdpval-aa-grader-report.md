# 实验报告 / Experiment Report — GDPval-AA Pairwise Grader：协议迁移、A/B 校验与 8 轮演化实验

> 日期 / Date: 2026-06-11 · 项目 / Project: Evolving Quant Agent v0 · 仓库 / Repo: `github.com/Wrigggy/evolving-quant-agent`
> 关联报告：`2026-06-09-qea-v0-report.md`（v0 机制与第一次 soft 实验）

**一句话 / TL;DR**：把评分器从「自建 rubric 均分 + 噪声门」**整体迁移到 Artificial Analysis 的 GDPval-AA 盲配对协议**（blind pairwise + Bradley-Terry Elo），用 judge A/B 验证了评分器本身的可靠性，然后跑了 8 轮演化实验。结果是一个**干净的阴性**：0/7 edit 通过门控，其中 4 个是决定性惨败——并且找到了惨败的机理根因：**diagnosis 层在用 A-pile 硬验证器的语义描述 B-pile 软任务，evolve agent 一直在修不存在的故障**。门控本身从此可信；瓶颈被精确定位到了 proposer 的观测空间。

---

## 1. 背景与动机 / Why

v0 第一次 soft 实验（见上一篇报告）的结论是 inconclusive：均分门控下 0/8 edit 保留，但**全部淹没在 ±0.0276 的评分噪声里**——分不清「edit 没用」和「信号太糙」。两条出路：去噪（k 采样），或者换一个**更敏锐的信号**。我们选了后者，理由是官方权威已经给出了答案：

- OpenAI GDPval 官方评分 = pairwise 盲评（模型交付物 vs 人工 gold），**无公开 API**；
- **Artificial Analysis 的 GDPval-AA**（Intelligence Index v4.0 起收录）= 模型 vs 模型的**盲配对锦标赛**，输出 Bradley-Terry Elo——方法论公开（artificialanalysis.ai/methodology/intelligence-benchmarking），这是本次迁移的蓝本。
- 相对判断（A 和 B 谁更好）天然比绝对打分（A 值多少分）方差小——这正是均分门控卡死的地方。

## 2. GDPval-AA 协议与我们的实现 / Protocol fidelity

AA 官方协议（公开部分）与本仓库实现的对照：

| 协议要素 | AA 官方 | 本实现 | 偏差说明 |
|---|---|---|---|
| 匿名化 | 随机匿名为 Submission A/B（防位置/身份偏置） | 同；每次重复独立随机序（按 (task, repeat) 稳定哈希，可复现） | 一致 |
| 评判问题 | 「哪个更好地回应了任务」，可平局 | 同 | AA 的 grader prompt 原文**未公开**，我们的是按其描述重建 |
| 平局处理 | **平局剔除**，只用胜负 | 同 | 一致 |
| 聚合 | Bradley-Terry MLE，GPT-5.1 锚定 1000 | 2 玩家特例（= 胜负比），**冻结 seed 锚定 1000**，Haldane +0.5 平滑 | 我们只有两名"选手"（候选 vs 在位者 / vs seed） |
| Judge | Gemini 3.1 Pro Preview，多模态读文件 | **qwen3.7-max**（无 Gemini 权限；锁 Alibaba 官方 provider） | 文本-only；judge 可换（见 §4 A/B） |
| 任务/数据 | openai/gdpval gold 220 题 | 同源，**本地 fork**（`data/gdpval/`，SHA256 清单，可推 HF），取 30 题金融/会计 6 职业 | rubric 留作诊断信号 |

在演化循环里的接法：**keep/rollback 门 = 候选 vs 在位者逐题盲配对**，剔除平局后 win share 必须 > 0.5 + null margin；**轨迹 = 在位者 vs 冻结 seed** 的 win rate 与 Elo。null margin 不是拍的：每次跑 seed 自比（两份独立 seed 样本互比），实测「同一 harness 的再生成+judge 噪声」会产生多大的伪胜率偏移。

**复现门（replication gate，本次新增）**：候选首轮胜出后，**重新生成**其全部交付物再比一轮，两轮皆胜才 keep。动机见 §4——我们实测到单样本胜出不可复现。

## 3. 实验时间线 / What actually ran

| # | 实验 | 配置 | 结果 |
|---|---|---|---|
| R1 | aa_qwen_test（2 轮冒烟） | judge=qwen3.7-max, k=2, n=30 | null margin 0.0652；iter1 拒（0.261）、**iter2 keep（0.609）**；Elo 1015.8 |
| R2 | judge A/B v1 | deepseek-pro vs qwen3.7-max | **作废**：代理故障致 C1 生成大面积为空（86 次 worker 错误） |
| — | （插曲） | — | DeepSeek 官方 provider 上游 402 "Insufficient Balance" 故障 ~3h；恢复探测 watchdog 自动重启实验 |
| R3 | judge A/B v2（干净） | 同上，0 空文档/0 剔除 | 见 §4：两 judge 高度一致；**R1 的 keep 不可复现** |
| R4 | aa_run8（8 轮主实验） | + 复现门，fresh seed | 见 §5：0/7 keep，干净阴性 |

## 4. Judge A/B：评分器自身的校验 / Is the grader trustworthy?

**设计**：同一批冻结文本（S0 = R1 的 seed 锚本，S1 = seed 新样本，C1 = R1 保留版 incumbent 新样本），相同的匿名顺序，分别让 deepseek-v4-pro（与 worker 同家族 → 自评）和 qwen3.7-max（跨家族）独立评判——**一切分歧只能归因于 judge 本身**。

| | deepseek-v4-pro | qwen3.7-max |
|---|---|---|
| null S1-vs-S0（应≈0.5） | 0.381（margin 0.119） | 0.455（margin 0.05） |
| effect C1-vs-S0 | 0.400（Elo 933） | 0.458（Elo 972） |
| keep 判定 | False | False |

- **一致率**：双方都判出胜负的 match 上，null 93.8%、effect 87.5%；方向硬翻转合计仅 3 例，绝大多数分歧是「判胜负 vs 判平」。
- **结论 1：自评偏置不是主要误差源**。便宜 ~3 倍的 deepseek judge 可用；qwen null 偏移更小，保留为默认。
- **结论 2（更重要）：R1 的那次 keep 是采样噪声**。0.609 = 14/23 decided，二项 95% CI ≈ [0.41, 0.78]；换一批新生成样本后两个 judge 都判它输给 seed。单样本、n=30、k=2 的配对胜出**不构成 keep 证据** → 引入复现门。
- 同场对照：rubric 诊断分当时也判该 edit 变差（0.533→0.517）——两个独立信号事后对齐了。

## 5. 主实验：8 轮 AA 门控演化 / The 8-iteration run

**设置**：worker=deepseek-v4-flash，evolve=deepseek-v4-pro，judge=qwen3.7-max（全部锁官方 provider：deepseek=DeepSeek、qwen=Alibaba），k=2，n=30（6 金融职业 × 5 题），fresh seed，含复现门。耗时 2h40m（match_set 已并行化：每组 30 match ~5 分钟，此前 ~30 分钟）。

**Null 校准**：seed-vs-seed = 11W/11L/8T → win share 恰好 0.500，**margin 取下限 0.050**（门槛 0.550）。rubric 噪声地板 0.0417（诊断用）。

**逐轮明细**（核心表）：

| iter | diagnosis tag | edit（slot:组件） | W/L/T | win share | rubric Δ(cand−inc) | 预言命中 | verdict |
|---|---|---|---|---|---|---|---|
| 1 | BadFormat | prompt:output_format_prompt | 0/28/2 | **0.000** | −0.192 | 0/9 | HARMFUL |
| 2 | WrongFormula | （无有效 edit 解析出） | — | — | — | — | BLOCKED |
| 3 | InsufficientCapability | skill:financial_calculations | 11/15/4 | 0.423 | −0.033 | 0/9 | HARMFUL |
| 4 | WrongFormula | validator:financial_sanity_validator | 3/19/8 | **0.136** | −0.067 | 2/9 | MIXED |
| 5 | InsufficientCapability | memory:financial_knowledge_base | 9/10/11 | 0.474 | −0.075 | 0/9 | HARMFUL |
| 6 | InsufficientCapability | router:financial_occupation_router | 13/13/4 | 0.500 | −0.058 | 0/9 | HARMFUL |
| 7 | InsufficientCapability | prompt:enable_code_exec_for_calculations | 5/16/9 | **0.238** | −0.058 | 1/9 | MIXED |
| 8 | InsufficientCapability | tool:fin_knowledge_retrieve | 12/11/7 | 0.522 | −0.042 | 0/9 | INEFFECTIVE |

**读法与观察**：

1. **0/7 keep，复现门一次都没触发**（没人过得了第一道门）。轨迹平在 win rate 0.5 / Elo 1000。
2. **4/7 是决定性惨败**（win share ≤0.42，远超噪声能解释的范围）——这不是「测不出来」，是「edit 把交付物改坏了」。和上一代均分门控的「全部困在噪声里」有本质区别。
3. **两个独立信号 7/7 方向一致**：每一轮 rubric 均分变化（Δ）都为负，与配对判负同向。评分器内部自洽。
4. **proposer 的预言命中率 3/63 ≈ 4.8%**（falsification 引擎逐轮对账 predicted_fixes）。这量化了 proposer 的失效程度。
5. iter1 的惨案有代表性：给写 memo/邮件的任务强加「只输出 JSON」的格式 prompt → 30 局输 28 局。

### 5.1 根因：diagnosis 层的语义错位（本报告最重要的发现）

为什么一个还不错的模型（deepseek-v4-pro）连续 8 轮提出伤害性 edit？查 `results/aa_run8/.../diagnosis.json` 和 `change_manifest.json` 发现所有诊断都长这样：

> "All failures show **base=False and probe=False** with no exception, likely because the agent's output format did not conform to the expected structure…"

而 `qea/agents.py:_diagnose_real` 把每个失败任务渲染成 `base={bool} probe={bool} err={...}`，tag 集合也是 A-pile 的（Hardcoding/BadFormat/ToolBroken…）。**这是硬验证器（A-pile）的观测语义**：B-pile 软任务没有 probe、没有解析失败、没有 code_exec——`base_pass=False` 只是「rubric 分 <0.5」的别名。于是 Agent Debugger 把「写作质量不够好」系统性地误读成「输出不可解析 / 缺计算工具」，proposer 顺着幻觉开药：强制 JSON 格式（iter1）、强制 code_exec（iter7）、加计算 skill（iter3）……每一个都在伤害自由写作的质量，然后被配对门控正确击毙。

**含义**：①「evolve agent 是瓶颈」这个 AHE 式结论在这里要修正为「**proposer 的观测空间是瓶颈**」——换 GPT-5.4 级 proposer 大概率也会被同样的错误观测带偏；②修复成本低：给 B-pile 写专属诊断渲染（occupation、rubric 逐条 miss、配对判负时 judge 的理由），tag 集合换成写作域的（MissingCriteria / WrongRegister / ShallowAnalysis / MissingArtifact…）。这是下一个实验前的必做项。

### 5.2 Per-occupation（终态=seed，rubric 诊断口径）

| 职业 | pass(≥0.6) | mean | 备注 |
|---|---|---|---|
| Personal Financial Advisors | 5/5 | 0.900 | 近天花板 |
| Real Estate Brokers | 5/5 | 0.700 | |
| Financial and Investment Analysts | 4/5 | 0.600 | |
| Financial Managers | 3/5 | 0.550 | |
| Securities/Commodities Sales | 3/5 | 0.500 | |
| Accountants and Auditors | 1/5 | **0.100** | 能力墙：题面要求产出 .xlsx 等真实文件，文本 worker 结构性失分 |

职业排序与历史三次跑完全稳定（铁律 4 的分桶记分再次给出唯一稳定信号）。会计尾部不是 harness 问题——8 个中间件 edit 无一触及——需要 worker 具备文件产出能力（ROADMAP）。

## 6. 工程与运维记录 / Ops

- **match_set 并行化**：线程池复用 `QEA_MAX_CONCURRENCY`(=8)，每 5 个 match 报进度，单 match 失败降级为平局；30-match 一组从 ~30 分钟 → ~5 分钟，整轮实验 2h40m。
- **Provider 锁定（用户规则：一切走官方）**：`llm.py` 改为「模型前缀 → 官方 provider」映射（deepseek=DeepSeek、qwen=Alibaba），`allow_fallbacks=false`，可用 `QEA_PROVIDER_MAP` 扩展。期间实测：账号级 Allowed Providers 白名单需在 OpenRouter 后台放行 Alibaba。
- **故障与自愈**：①首跑被后台任务 ~2h 时限静默杀死 → checkpoint `--resume` 全量恢复（pw_margin/seed 锚本/buffer 均还原）；②DeepSeek 官方 provider 上游 402 故障 ~3h → 恢复探测 watchdog（10 分钟一探，恢复即自动重启实验）；③运行 watchdog：进程死→自动 resume，日志 >45 分钟不动→kill+resume（阈值高于配对静默期）。
- **成本**：A/B v2 + 8 轮主跑合计 ~$18.7（OpenRouter 用量 $54.0→$72.8）；账户余额尚余 ~$27。
- **测试**：25 个单测全过（新增：配对去匿名正确性、平局/坏输出兜底、BT-Elo 锚定、门控边界、并行 match_set 故障降级、provider 映射、mock 端到端、本地 fork 优先）。

## 7. 有效性威胁 / Threats to validity

1. **Judge ≠ AA 官方**（qwen3.7-max vs Gemini 3.1 Pro Preview），且 grader prompt 是按公开描述的重建——绝对 Elo 不可与 AA 榜单互比，但协议结构（盲配对/平局剔除/BT）一致，相对结论（keep/rollback、方向）经 A/B 显示对 judge 不敏感。
2. **文本-only**：AA 多模态读文件；我们的 worker 不产文件 → 会计类任务结构性低估，per-occupation 绝对值是下界。
3. **n=30、k=2**：单轮 match 的 win share CI 很宽（±0.2 量级）；本实验靠「多数惨败远离 0.5」与复现门弥补，但接近门槛的判定（如 iter8 的 0.522）只能算无证据，不能算证伪。
4. **单一 worker/evolve 家族**（deepseek）：diagnosis 错位的放大效应可能因模型而异。
5. seed 锚本是单次抽样：Elo 的锚有抽样误差（null 校准部分覆盖此项）。

## 8. 结论与下一步 / Conclusions & next

**结论**：
1. **GDPval-AA 配对门控迁移完成且可信**——干净的 null（0.500）、决定性判别（0.000–0.522 全谱）、与 rubric 诊断 7/7 同向、judge A/B 显示对评判者不敏感、复现门兜底单样本噪声。评分器这条线收尾。
2. **演化没有产生改进，且原因明确**：diagnosis 层把 A-pile 语义喂给了 B-pile 实验，proposer 全程在修幻觉故障。「干净阴性 + 机理定位」比上一轮的 inconclusive 前进了一大步。
3. v0 总图景更新：硬 A-pile（数值题）worker 能力已饱和、无 harness 余量；软 B-pile（真实 GDPval 交付物）有分数余量（seed 仅 0.56），但吃下它需要 **(a)** B-pile 专属诊断 + **(b)** 文件产出能力，而不是更多中间件。

**下一步（按杠杆排序）**：
1. **B-pile 专属 diagnosis**（低成本高确定性）：渲染 rubric 逐条 miss + 配对判负理由给 proposer，换写作域 tag 集合；重跑 8 轮看 keep 率是否脱离 0。
2. **会计尾部攻坚**：worker 加 .xlsx/.pdf 产出（LibreOffice/openpyxl 沙箱），正面解决 mean 0.100 的能力墙。
3. （可选）judge 升级：拿到 Gemini 权限后一键切换 `QEA_JUDGE_MODEL` 对齐 AA 官方；或用 deepseek judge 省 3 倍成本跑更多轮次。

**Artifacts**：`docs/RESULTS_aa_pairwise_qwen_test.md`、`docs/RESULTS_ab_judge.md`、`docs/RESULTS_aa_run8.md`；原始数据 `results/aa_qwen_test/`、`results/ab_judge_v2/`（含全部被评文本）、`results/aa_run8/`（8 轮三层 trace + checkpoint）；评分器实现 `qea/verifier.py:PairwiseJudge`、门控 `qea/falsify.py:decide_keep_pairwise` + 复现门 `qea/loop.py`；数据 fork `data/gdpval/` + `scripts/fork_gdpval.py`；A/B 脚本 `scripts/ab_judge.py`。
