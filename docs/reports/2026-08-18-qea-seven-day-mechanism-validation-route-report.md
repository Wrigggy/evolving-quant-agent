# 实验报告 / Experiment Report — Harness Evolution 机制验证路线

> 日期 / Date: 2026-08-18
> 覆盖范围 / Scope: 2026-08-11 至 2026-08-18
> Benchmarks: QFBench、QuantCodeEval
> 报告边界 / Boundary: engineering mechanism validation，不是 benchmark-wide 或论文级最终结果

## 结论先行 / Executive Summary

过去一周已经把系统从“Evolver 能不能完成一次合法决策”推进到“Evolver 产生的多组件 harness 能不能让 fresh Worker 得到 official binary reward”。目前最强结果是：R3 Evolver 产生并通过 admission 的 candidate harness，在一次从 public T26 task 开始的 fresh Worker 中达到 **17/17、reward 1**。这证明了候选 harness 可以产生实际二元收益，但还没有证明完整的 autonomous search：AP-1 的 repair probe、候选晋级和最终确认仍由实验者组织。

因此，当前结论不是“已经完成全自主进化”，而是：

> **控制闭环、full-harness mutation、runtime experience、component activation、answer-rich attribution 和 fresh binary success 均已有实验证据；剩余核心门槛是 Evolver 自主选择实验、消费实验反馈，以及从 shell-only H0 自主 bootstrap。**

整体机制路线如下：

```text
合法 ACT / ABSTAIN
  -> full-harness component mutation
  -> component smoke + Worker activation
  -> runtime experience retained across rounds
  -> domain-specific state localization
  -> answer-rich optimize feedback to Evolver, blind Worker execution
  -> component-level repair and official score
  -> autonomous experiment choice (AP-2M, next)
  -> autonomous bootstrap from H0 (AP-3, next)
```

## 1. 机制验证路线与实验结果 / Mechanism Validation Route

报告按机制依赖组织，而不是逐日列出 run。每个节点回答：机制是什么、要验证什么、什么数据能够验证、实际得到什么、现在处于什么状态。

### 节点 1 — Evolver 能否诚实完成搜索闭环

**Mechanism。** A6 ME1–ME10 建立 bounded exploration、probe、checkpoint 和 terminal `ACT/ABSTAIN` 协议，使证据不足时可以合法停止，而不是被迫生成 candidate。

**Question。** Evolver 能否在真实 provider path 中累计证据、执行 probe、保存 checkpoint，并以与证据一致的 terminal decision 结束？

**Validation signal。** 合法 terminal decision；decision 与 checkpoint 绑定；candidate write lock 在 `ABSTAIN` 时保持关闭；若 `ACT`，则必须出现非空 harness diff、admission 和 candidate evaluation。

**Evidence and result。** ME7 首次完成端到端合法 `ABSTAIN`；ME10 在三个 exploration epochs、三个 real probes、三个 reload-verified checkpoints 后再次得到更强的 calibrated `ABSTAIN`。ME1–ME10 共记录 172 logical requests、170 个 HTTP-200 responses、至少 5,798,107 tokens 和 USD 0.3520366696。整个系列没有产生合法 `ACT`、non-empty diff 或 candidate score。

**Status。** **Terminal mechanism validated；harness benefit not tested。** 瓶颈从 control flow 转移到 evidence sufficiency 与 semantic identifiability。

**Next dependency。** 必须让 Evolver 能操作真实 harness component，并让后续轮次看到之前的成功与失败。

### 节点 2 — 搜索对象能否从 prompt 扩展到完整 harness，并保留跨轮历史

**Mechanism。** QuantCodeEval adapter 将 mutation surface 扩展为 NexAU full harness，包括 `systemprompt`、tools、tool descriptions、agent configuration、skills 和 middleware；每轮保留 prior candidate、diff、decision、component smoke 和 score outcome。

**Question。** Evolver 是否能看到上一轮改动及其结果，从 prompt-only mutation 转向 executable component，并根据历史 refine、rollback 或 abstain？

**Validation signal。** 下一轮实际读取 prior entry 和 candidate source；产生非 prompt-only diff；component 可调用；完整 admission 通过；candidate 在 Worker 中被触发。

**Evidence and result。**

- 初始五轮 PGBHS 都只修改 `systemprompt.md`。T16 始终作为保护任务，T24 多次没有 artifact；第 5 轮把 T24 从 59 requests 后无 artifact 改为 10 个 T24 requests 内产生可评分 artifact，并达到 15/17，但所有 candidate 最终 rollback，官方 incumbent 仍为 H0 `[1, 0]`。五轮 search 共 200 requests、6,152,505 tokens、USD 0.1532859160。
- v2 deterministic canary 证明 round 2 能读取 round 1 的 rejected patch，改为新增 executable tool、tool description 和 agent registration，并在达到 fixture target 后提前停止，不再固定运行五轮。
- real r1–r4 逐步修复 role attribution、history projection 和 decision schema 后，r4 首次完成合法 full-harness ACT 与 admission。r8 随后生成并激活四文件 quant audit component；T24 从 H0 15/17 提升到 16/17、T16 保持 18/18，但 binary vector 未变。
- r9 继续扩大 static audit 后，T16 降到 3/18，T24 无 artifact；该负结果否证了“继续堆叠静态规则”作为主要搜索方向。

**Status。** **Full-harness manipulation and cumulative history validated。** 早期 fixed five-iteration prompt search 已完成其工程验证作用，不是当前方法本体。

**Next dependency。** 历史不仅要可见，还要能帮助 Evolver排除错误机制、定位可复用的 quant state。

### 节点 3 — Runtime experience 能否定位真正有辨识力的 quant state

**Mechanism。** 将 Worker trace、artifact、public-definition retrieval、probe outcome 和 prior component result保存为 answer-free runtime experience；同时引入 declarative quant invariant，把 public quantity vocabulary 绑定到实际 operation。

**Question。** 累计 history 是否能帮助 Evolver发现“Worker 自己写的 probe 虽然通过，但并不区分正确与错误解释”？domain component 是否能通过显式 state binding 修复该问题？

**Validation signal。** Evolver 能指出 prior probe 对成功/失败样本无区分力；新的 component 对错误/正确语义产生不同观察；fresh Worker score 改善并在 protection task 不退化。

**Evidence and result。** 两次 autonomous activation 都读取了历史，但分别在 23 和 22 requests 后 calibrated `ABSTAIN`。历史对比显示四个 T12 分支的 free-form probe 最终都通过，而 official result 从 8/16 到 16/16 不等，说明该 probe 是 self-confirming。实验者随后 seed 了 declarative invariant：初版仍允许“文字说 average、工具算 additive sum”，只得 8/16；将 `average_return`、`cumulative_return` 和 `additive_sum` 绑定到公开定义后，两次独立 T12 Worker 都得到 16/16，T19 protection 得到 18/18。该节点合计 137 requests、5,102,462 tokens、USD 0.1547955976。

**Status。** **Runtime localization and component viability validated；final invariant was not autonomously discovered。**

**Next dependency。** Evolver 必须能 reuse/refine component，也要能在历史否证某个 intervention 后停止重复它。

### 节点 4 — Evolver 能否利用负反馈 refine component，并处理组件交互

**Mechanism。** Component ledger 记录 `activated / unsupported / pending / supported`；下一轮读取上一轮 exact intervention、Worker activation 和 official outcome，选择 `REUSE / REFINE / COMPOSE / ABSTAIN`。

**Question。** Evolver 是否会因为真实负结果改变下一轮决策？它能否区分“quant component 无效”“component hook 不可达”和“多组件相互干扰”？

**Validation signal。** 不重复已证伪 intervention；对证据不足的分支 calibrated `ABSTAIN`；用 runtime reachability falsify 错误 hook；修复后在真实 Worker 中触发；组合后的 score 单独解释。

**Evidence and result。**

- T18：Evolver 自主提出 warmup-boundary skill，fresh Worker 确实加载 skill、执行 exactly-120 fixture 并改变 implementation，但 T18 仍为 16/18。下一轮读取这一结果后明确排除该机制，并因 percentile/NaN conventions 无法由 public evidence 区分而合法 `ABSTAIN`。两轮分别使用 USD 0.0656560688 和 USD 0.0492410744。
- T24 delivery：第一版 `after_model` guard 属于正确 component family，但 installed runtime 在 hook 前已经抛错，因此不可能触达；第二轮改为 reachable `wrap_model_call` middleware，并在真实 Worker 中连续恢复两次 empty response，使 Worker 最终交付 artifact。组合后的 quant score 却从 prior 16/17 降到 11/17，说明“delivery recovery 有效”不等于“整体 harness score 提升”。该阶段 142 requests、11,733,043 tokens、USD 0.178233636。

**Status。** **Feedback-driven refine、reachability diagnosis 和 real middleware recovery validated；component composition benefit not validated。**

**Next dependency。** 需要跨 benchmark 的共同 experience interface，同时避免把 task-specific checker 当成通用 component。

### 节点 5 — 同一搜索接口能否跨 QFBench 与 QuantCodeEval 工作

**Mechanism。** Thin cross-benchmark adapter 共享 task cards、runtime experience、component cards 和 search operators；Worker contract 与 official verifier 仍由各 benchmark 自己执行。

**Question。** 同一 Evolver interface 能否在 evidence 不足时对 QFBench abstain，又在 QuantCodeEval 有足够 runtime contrast 时自主合成 component，而不是强制复用同一个模板？

**Validation signal。** 不同 benchmark 上产生与证据匹配的不同决策；QuantCodeEval candidate 是 multi-file executable mutation；Worker 实际调用 component；target repeat 与 protection 单独报告。

**Evidence and result。** Zero-model preflight 建立了 QFBench 四个 task cards 和 QuantCodeEval T26/T27 可执行环境，14 个 focused tests 通过，未产生模型费用。live breadth 中，QFBench `swap-curve-bootstrap-ois` 的 task-only 与 history-enabled arms 都因 public evidence 无法区分 forward definition 与 valuation convention 而 semantic `ABSTAIN`。T26 H0 为 13/17；Evolver 自主生成五文件 public-clause audit/revision component；两个 candidate Workers 都调用 component 三次，但分数分别为 14/17 和 12/17，收益不稳定；T19 protection 为 18/18。整组 live experiment 使用 183 requests、8,231,008 tokens、USD 0.2101171912。

**Status。** **Cross-benchmark navigation、autonomous ACT 和 real activation validated；stable benefit not validated。** Task-specific assertions 没有解释 T19 的表现，较可能有用的是 read-contract、independent-check、revise、re-audit workflow。

**Next dependency。** 对 optimize task 给 Evolver 更精确的 post-run diagnostic，同时保持 Worker blind，以提高 attribution 分辨率。

### 节点 6 — Answer-rich Evolver 能否定位可复用组件，而不把答案交给 Worker

**Mechanism。** 对声明为 optimize 的 T26，trusted coordinator 在评分后向 Evolver 提供 item-level answer-rich diagnostic；fresh Worker 仍只看到 public task、data 和 candidate harness。答案可帮助 Evolver 归因，但不得写入 reusable component。

**Question。** 更精细的错误对比能否让 Evolver从宽泛 static rules 转向具体 quant-contract component，并使 predicted properties 在 blind Worker 中改善？

**Validation signal。** Evolver 自主选择 component locus；candidate 不包含 expected values；Worker 真实调用 component；Evolver 预测的 properties 改为 PASS；独立 repeat 保持结果。

**Evidence and result。** Evolver 从 retained 13/17、14/17、12/17 attempts 归纳 declared-formula-realization 问题，新增 quant-contract auditor、tool registration 和 revise/re-audit workflow。第一名有效 blind Worker 调用 auditor 14 次并达到 16/17；独立 repeat 调用相关 component 12 次，再次达到 16/17。两次均通过全部 Type B，Evolver 明确预测的 B5/B9 均从失败转为 PASS；A10 numeric identity 仍失败。完整 retained lineage 使用 139 requests、5,841,009 tokens、USD 0.2923158504。

**Status。** **Answer-rich attribution、blind-Worker boundary 和 repeated property benefit validated；binary gain remained open at this node。**

**Next dependency。** 必须区分“最终数值不一致”的表象与 estimator pipeline 中真正错误的 state transition。

### 节点 7 — Quant-specific state semantics 能否解释 residual binary failure

**Mechanism。** 将 CV split membership、moment-estimation membership、fold-local scaling、first/second moment 和 runtime output shape视为显式 quant state，而不是继续扩充长列表式 failure taxonomy。

**Question。** A10 的 residual mismatch 是 grid resolution、formula surface，还是 sample-set/state propagation 错误？static semantic checks 是否足以保证 Worker artifact 稳定？

**Validation signal。** Causal ablation 能单独区分竞争假设；official verifier 从 16/17 变为 17/17；新的 autonomous component 在 blind Worker 中不产生新的 runtime crash。

**Evidence and result。**

- Grid-only change仍为 16/17，否证了“更多 grid points 足以解决 A10”。
- Causal ablation 找到真正原因：CV complement 的非连续月份集合被下游用首尾日期重建成连续区间，held-out fold 因此重新进入 moment estimation；同时 fold-local quantities 复用了 full-sample state。修复 set membership、fold-local scaling、population covariance 与 grid 后，trusted zero-model replay 得到 17/17、reward 1。这个结果证明 root cause，但不是 fresh autonomous lineage。
- 8 月 18 日 R3 autonomous estimator candidate 的 synthetic contrasts 仍有 false rejection；generalized R4 repair 使 fresh Worker 达到 15/17。R5 再扩充 first/second-moment 与 public-scope static checks，虽然 synthetic pairs 全部通过，但 blind Worker 因 multi-output OLS shape mismatch 只得 3/17，十一项 property crash。由此可见 static semantic localization 不能替代 executable runtime probe。
- Provider recovery 同期确认 reasoning-only SSE empty response 可以被识别，但 full-budget serial fallback 会超过 downstream timeout；最终实现改为一次 bounded low-reasoning recovery。它已通过 focused tests，尚未在新的 paid Worker 中验证。

**Status。** **Causal estimator-state root cause validated；static-check stability refuted；fresh autonomous binary still not closed at this node。**

**Next dependency。** 与其继续人工枚举 failure class，应让 Evolver 能发起一个真实、短程 Worker experiment，并依据 artifact、trace、score、runtime 和 cost 自己更新 candidate。

### 节点 8 — Evolver-produced harness 是否已经产生 official binary benefit

**Mechanism。** AP-1 使用同一个 3/17 failed artifact，分别交给 parent harness 和 R3 Evolver-produced candidate harness做短程 repair；随后把 candidate harness用于一次从 public task 开始的 fresh Worker。

**Question。** Candidate bundle 是否在实际 Worker repair 中有帮助？它能否在不是 seed-artifact repair 的 fresh run 中产生 17/17？

**Validation signal。** Paired repair 中 candidate 相对 parent 有 property gain；fresh Worker 从 public task 产生新 artifact；official verifier 达到 17/17；同时明确区分“harness有效”与“实验选择完全自主”。

**Evidence and result。** Paired repair 的 parent 与 candidate 各使用 11 requests。Parent 得到 12/17，candidate 得到 14/17，property delta 为 +2；candidate 更慢、更贵，因此是 `score-helpful`，不是 `efficiency-helpful` 或 `binary-helpful`。随后 fresh candidate run 使用 59 requests、3,284,491 tokens、USD 0.120627420 和 1,766.607 秒，得到 Type A 7/7、Type B 10/10、总计 **17/17、reward 1**。所有请求均走 DeepSeek，configured fallback 未触发。

**Status。** **Fresh candidate-harness binary success validated once。Complete autonomous search not yet validated。** AP-1 的 seed、repair instruction、promotion 与 final evaluation 仍由 experimenter 组织；static auditor 对 14/17 artifact 仍有 false negatives，所以收益应归于整个 workflow bundle，不能归因于 auditor accuracy。

### 案例研究 / Case Study

**正向案例：candidate harness 从 paired repair 走到 fresh 17/17。** 同一个 3/17 artifact 在 shell-only parent 下修到 12/17，在 R3 candidate harness 下修到 14/17，说明 candidate workflow 能给 Worker 带来额外修复能力。随后不再提供 seed artifact，而是让相同 candidate harness 面对 public T26 task 从头工作；Worker 在 59 turns 中完成 76 次 tool calls，最终 artifact 在 official verifier 中通过全部 17 个 properties。这个案例证明 harness benefit 可以跨越“修旧 artifact”和“从 public task 生成新 artifact”两种工作模式；它尚未证明 experiment selection 自主，因为 paired probe 与 promotion 由实验者决定。

**负向案例：static contrasts 全通过，fresh Worker 仍从 15/17 降到 3/17。** R5 component 能区分 synthetic first/second-moment 与 public-scope wrong/correct pairs，也接受 retained 17/17 repair；但 fresh Worker 写出的 multi-output OLS helper 使用不兼容 array shapes，导致十一项 property crash。这个案例直接否证“component smoke PASS 就代表 Worker integration 稳定”，并给出下一步机制要求：Evolver 的 probe 必须能够执行 public entry points、检查 output shape/finiteness/no-crash，并把真实 traceback 带回下一轮，而不是只扩大 static rule set。

## 2. 跨节点分析 / Analysis

### 2.1 已经验证的不是单一 prompt trick，而是一条 component lifecycle

证据已经覆盖完整生命周期：Evolver 能提出 multi-file component、通过 smoke/admission、让 Worker 真正调用、观察 score 与 runtime outcome、把失败保留到下一轮，并在证据不足时停止。r8、T18、T24 delivery、T26 breadth 和 answer-rich refinement分别验证了这一链条的不同部分。

### 2.2 Runtime experience 的价值主要是排除和定位，不保证自动发现最终答案

T18 历史使 Evolver 不再重复 warmup-boundary；T12 历史揭示 free-form probe 无区分力；T24 reachability history 把错误 hook 改成可达 middleware。这些都是有效 learning-from-runtime。另一方面，T12 的 public-quantity binding 和 T26 的 CV set semantics 仍先由实验者因果定位，说明当前缺口是 **Evolver 自己设计有辨识力的实验**，而不是“看不到上一轮”。

### 2.3 Domain specialization 应表达为可扩展 state map，而不是穷举答案

有效的 quant abstraction 是 `sample membership`、`moment scope`、`unit state`、`temporal endpoint`、`artifact lifecycle` 和 `runtime shape` 等 pipeline state。它们指导 Evolver 选择检查或实验，但不把 T26 property answer编码进 Worker。R5 的 3/17 负结果表明，仅有更长的 static failure map 会产生 false confidence；domain map 必须连接到 executable observation。

### 2.4 当前最强 performance 结果与最强 autonomy 结果仍是两条证据

- Performance：R3 candidate harness 的 fresh Worker 已达到一次 17/17。
- Autonomy：Evolver 已能自主选择并实现 component，也能使用历史 refine/abstain；但尚未自主选择 AP-1 类型的 probe、读取 probe 结果后再决定 final candidate。

下一步 AP-2M 的作用就是把这两条证据连接起来；AP-3 再检验能否从 H0 起步。

## 3. 当前问题与结论边界 / Open Questions and Claim Boundary

1. **完整自主性仍未验证。** 目前不能声称 Evolver 已能自主完成 `history search -> experiment design -> feedback update -> final submission`。
2. **17/17 只出现一次 fresh candidate run。** 它证明可行性，不证明稳定性；但当前优先级应先验证自主闭环，再决定是否重复。
3. **Component attribution 仍不充分。** AP-1 的 bundle 有效，但 static auditor 本身仍误报；真正贡献可能来自 contract reading、revision discipline、runtime probe 或它们的组合。
4. **Static smoke 不能代表 Worker integration。** R5 synthetic tests 通过而 fresh Worker 3/17，是当前最明确的反例。
5. **Cross-task generalization 尚未建立。** T19 是 protection，不是 matched positive transfer；QFBench arms验证了 semantic abstention，但没有 score gain。
6. **大规模 scheduler 暂缓。** 长尾 task 与异步成本调度是后续 scaling 问题；在自主闭环尚未跑通前实现复杂 scheduler 会稀释主要机制问题。

## 4. 下一步实验计划 / Next Experiment Plan

下一步不再新增一轮人工 failure-class mutation，而是先验证 Evolver 是否拥有完整、最小的自主实验能力。

### P1 — 实现 AP-2M minimum closed loop

**What。** 在现有 QuantCodeEval runner 上增加两个 Evolver decision rounds 和一个 Evolver-authored `experiment_spec`。Round 1 自己选择 history、artifact 或 from-scratch mode、Worker instruction、component、probe budget、prediction，以及什么 observation 会改变决策；coordinator 只执行一次合法 probe；Round 2 收到 artifact、trace、official optimize properties、runtime、requests、tokens 和 cost 后，选择 retain、refine、rollback、compose、submit 或 `ABSTAIN`。

**Why。** 这是当前唯一缺失的最小机制：Evolver 不仅看到历史，而且能自己选择下一条真实 observation，并用 observation 更新 harness。

**Implementation boundary。** 复用现有 runner、candidate workspace、Worker executor 和 verifier；使用普通 JSON 记录，不先建立通用 experience service，不实现 scheduler，不扩展到多个 benchmark。

**Local validation。** 用 deterministic fake 验证：Round 1 能写合法 experiment；coordinator 能执行；Round 2 能读取真实结果并改变决策；final candidate 能独立评分；`ABSTAIN` 始终合法。只覆盖 happy path 和已经观察过的 malformed decision/empty artifact。

### P2 — 运行一次 AP-2M warm-history autonomy canary

**Setup。** 使用 pre-AP-1 history catalog；两轮 Evolver；一个 10–12 iteration Worker probe；一个合法 candidate 的 independent final T26 Worker；concurrency 1；建议总 provider cap USD 0.25。当前 17/17 candidate 作为 experimenter-side reference，不把 AP-1 prompt 或 expert root-cause summary写进 Evolver assignment。

**Primary gates。**

- `autonomy_feasible`：Evolver 完成 self-selected experiment 和 second decision；
- `feedback_driven`：Round 2 明确依据 Round 1 observation 改变、保留或回滚；
- `component_helpful`：self-selected component 改善 property、修复 predicted runtime fault，或以更低成本达到同等结果；
- `benchmark_helpful`：independent final candidate 相对其选定 parent 有 official property gain；17/17 单独标记 binary success。

AP-2M 不需要超过当前已知 17/17 上限。它的首要结论是“自主 experiment loop 是否成立”；若它自主选择较弱 parent 并最终达到或保持 17/17，这是很强的机制结果。grounded `ABSTAIN` 是合法 autonomy outcome，但不是 performance success。

### P3 — AP-2M 成立后运行 AP-3 H0 autonomous bootstrap

**Setup。** 只提供 shell-only H0 和 AP-3 内部 fresh H0 Worker 产生的 run-local artifact、trace、optimize diagnostic、score、runtime 与 cost；禁止使用 R3/AP-1 candidate、历史高分 artifact、人工 repair prompt 和 expert root-cause summary。复用 AP-2M 的两轮协议与一个 intermediate probe。

**Gates。**

- `bootstrap_loop_feasible`：H0 evidence 导致 self-selected experiment 与 feedback-grounded second decision；
- `component_activated`：新 component 实际影响 Worker execution；
- `bootstrap_helpful`：final score 高于 fresh H0，或 predicted runtime fault 修复且无 property regression；
- `binary_helpful`：final independent T26 为 17/17、reward 1。

### P4 — 只有 AP-3 positive 后才扩展稳定性与 breadth

按以下顺序扩展：

1. 对 AP-3 positive lineage 做一次 fresh Evolver repeat；
2. 选择一个 failure mechanism 明确不同的第二个 QuantCodeEval task；
3. 再运行一个 QFBench canary，验证同一自主实验接口能否在另一种 artifact contract 下工作；
4. 最后才实现渐进式、异步、成本感知 scheduler，并在冻结 candidate 上运行较大 test set。

## 最终判断 / Current Verdict

过去一周已经获得了机制论文所需的一条清晰正向链路：系统从合法 `ABSTAIN` 发展到 full-harness ACT、runtime-history refinement、quant-specific component activation、repeated 16/17 property repair，最终出现一次 fresh 17/17 binary success。负结果也直接推动了机制设计：T18 否证无效 boundary hypothesis，T24 暴露 hook reachability 与 component interaction，R5 证明 static semantic checks 不足以保证 runtime stability。

现在不应继续把主要预算投入人工枚举更多 failure classes，也不应提前建设大规模 scheduler。最小且决定性的下一步是 AP-2M：让 Evolver 自己选 probe、看到结果并更新 candidate。AP-2M 成立后，AP-3 才能回答最终的工程问题——系统是否能够从 shell-only H0 自主进化出有二元收益的 quant harness。
