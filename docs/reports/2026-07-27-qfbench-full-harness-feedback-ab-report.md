# 实验报告 / Experiment Report — QFBench Full-Harness Feedback A/B

> 日期 / Date: 2026-07-27
> 覆盖区间 / Reporting window: 2026-07-25 previous report → 2026-07-27 completed A/B
> Benchmark: QFBench commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a`
> Runs: `qfbench-30x5-full-control-20260727-024921eb` and `qfbench-30x5-full-rich-20260727-024921eb`

**结论先行 / Bottom line.** Rich feedback 已经证明“让 evolver 看到 optimize-task 的 public goal、public rubric、worker-observable trajectory 与 sanitized criterion evidence”能够改变搜索过程，并在一次 matched 30-task × 5-iteration 实验中找到一个被 gate 接受的 candidate：optimize domain-macro 从 `0.564583` 提升到 `0.720139`，adaptation gain 为 `+0.155556`；Control gain 为 `0.000000`。但是这仍是 **one paired run 的 point estimate**，不是稳定 causal/generalization claim：Rich held-out 反而 `-0.083333`，而 worker 完全未改变的 Control held-out 却 `+0.166667`，直接显示 model-sampling noise 仍然足以主导 10-task transfer panel。工程层面，answer-free firewall、deterministic offline verifier、checkpoint/resume、exact-ID cleanup 和 full-harness admission 均完成 live validation；费用与 token totals 仍未被 artifact 记录。

## 1. 实验过程与结果 / Process & Results

### 1.1 目标与变更链 / Goal and Change Timeline

本阶段的研究问题是：**在不暴露 official tests、reference answers 或 held-out information 的前提下，提高 evolver 对真实工作目标和 worker 工作轨迹的可见度，是否能提高 optimize-task 上的 harness evolution 能力？**

从上一份 [2026-07-25 30×5 report](2026-07-25-qfbench-30x5-comparison-report.md) 到本报告，完成了四组工作：

1. **Verifier repair.** 7 月 25 日 run 中 14 个 scores 被三个未正确 warm 的 `if uvx ...` verifier templates 污染。7 月 26 日发布了 delta-hedging、swap-curve 和 Form 4 的 corrected identities，并在无网络 E2B canary 中执行全部 `27 + 19 + 7 = 53` 个 official tests。旧 run 保持 immutable，没有回写历史分数。
2. **Full-harness feedback contract.** Control 只看到 scalar/coarse answer-free feedback；Rich additionally 看到 optimize-only public instruction、environment data、public rubric、worker final/trace/artifacts、sanitized public criterion evidence 和 prior candidate outcomes。两者都看不到 official tests、expected values、solutions、credentials 或任何 held-out content/outcome。
3. **Secure evolver and admission.** Evolver 被移入 isolated E2B sandbox，使用 restricted egress 和 external credential injection；evidence 只读、candidate output 可写。Admission 对 prompt、tool descriptions、agent bindings、middleware、skills、validator、memory 和 routing 执行 allowlist/schema/security validation。Import canary 与 paid Rich canary 均通过；paid canary 还实际留下并由 exact-ID reaper 清理了一个 interrupted evolver sandbox。
4. **Matched paid A/B.** Control 和 Rich 使用相同 20 optimize + 10 held-out panel、五轮 schedule、model、seed digest、task/template/verifier identities、concurrency 8、global E2B cap 12、`noise_floor=0.02` 和 zero domain-regression gate。唯一预注册差异是 feedback contract。

实验数据流如下：

```text
Control corpus ----\
                    > isolated E2B evolver -> admitted full-harness candidate
Rich corpus -------/                                  |
                         20 optimize workers -> offline verifiers
                            -> gates -> final held-out evaluation
```

### 1.2 固定实验配置 / Fixed Configuration

| Item | Value |
|---|---|
| Optimize / held-out | 20 / 10 tasks, six domains |
| Outer iterations | 5 |
| Official scores | 140 per arm |
| Model | `deepseek/deepseek-v4-pro` |
| Seed worker | `qea/worker_gdpval_weak` |
| Worker runtime | NexAU 0.3.9, isolated E2B task sandbox |
| Verifier | Independent E2B sandbox, official pytest reward, no network, no LLM judge |
| Gates | gain ≥ `0.02`; no domain regression below `0.0` |
| Parallelism | worker concurrency 8; account-wide E2B cap 12 |
| Identity invariants | Same benchmark, task manifest, templates, verifier mapping, model, seed and admission policy; feedback digest differs by design |

### 1.3 Primary Results

| Metric | Control | Rich |
|---|---:|---:|
| Optimize seed | 0.612500 | 0.564583 |
| Optimize final incumbent | 0.612500 | **0.720139** |
| Adaptation gain | 0.000000 | **+0.155556** |
| Kept / rolled back | 0 / 5 | **1 / 4** |
| Held-out seed | 0.583333 | 0.666667 |
| Held-out final | 0.750000 | 0.583333 |
| Held-out delta | **+0.166667** | -0.083333 |
| Evidence records read | 94 | **203** |
| Evolver tool errors | 11 | 21 |
| Worker timeouts | 7 | 9 |
| Recorded execution seconds | 48,872.566 | 56,485.222 |
| Worker / verifier / evolver lifecycles | 140 / 133 / 5 | 140 / 131 / 5 |
| Unique lifecycle IDs, all clean | 278 / 278 | 276 / 276 |

The comparison audit reconstructs held-out task, domain and overall scores directly from all 20 official held-out score records per arm, then requires the stored summaries to match. It also enumerates the historical contaminated records as six delta-hedging, six swap-curve and two Form 4 checkpoints; there is no hard-coded count fallback.

The preregistered point estimate is:

```text
RichFeedbackGain
= Rich adaptation gain - Control adaptation gain
= 0.155556 - 0.000000
= 0.155556
```

Rich 的 accepted incumbent 改善了 `bollinger-backtest-aapl`、`credit-migration-matrix` 和 `crypto-funding-rate-basis-carry`（各 `+1.0`），同时 `evt-pot-var` 为 `-0.166667`、`prediction-markets-cross-venue-dislocation` 为 `-0.05`，其余 15 个 optimize tasks 不变。按 domain 看，accepted candidate 在 execution/microstructure、risk/credit、systematic strategy 上分别为 `+0.475000`、`+0.208333`、`+0.250000`，其余 domains 不变。

### 1.4 五轮 Gate 行为 / Iteration Decisions

| Iteration | Candidate score | Decision | Why |
|---:|---:|---|---|
| 1 | 0.601389 | Rollback | `risk_credit -0.041667` |
| 2 | 0.543750 | Rollback | `data_engineering -0.333333`, `risk_credit -0.041667` |
| 3 | **0.720139** | **Keep** | `+0.155556`, no domain regression |
| 4 | 0.762897 | Rollback | Overall higher, but `execution_microstructure -0.076786` |
| 5 | 0.559722 | Rollback | Execution `-0.462500`, risk `-0.250000`, systematic `-0.250000` |

Iteration 4 is important: the safety gate rejected a candidate whose overall score exceeded the kept incumbent because one domain regressed. This is expected falsification behavior, not a lost win.

### 1.5 Case Studies

#### Case A — Rich iteration 3: evidence exposure produced a useful prompt edit

Rich iteration 3 read 36 evidence records and converted the one-line seed prompt into a short, structured operating procedure: read the full task and inputs, write one self-contained script, debug the actual traceback, verify every required artifact, and follow exact schema/numerical conventions. The resulting candidate improved three domains with no domain regression and was kept at `0.720139`.

This case supports a narrow but useful mechanism claim: **answer-free process evidence can help the evolver synthesize a better general execution policy without reading hidden answers.** The edit was still prompt-only; the full harness *could* mutate tools, middleware, skills, validator, memory and routing, but this run did not demonstrate those mutation classes.

#### Case B — Rich iteration 5: more evidence did not guarantee a better candidate

Iteration 5 read 38 records, including task-specific public evaluations and worker traces for `13f-amendment-aware-crowding`, `localvol-barrier`, `yield-curve-bond-immunization`, `evt-pot-var` and other failures. It explicitly added planning, intermediate assertions, edge-case handling, exact schema checks and named numerical-method conventions. Nevertheless, `localvol-barrier` still timed out, yield-curve work reached verification without producing a passing result, 13F remained at zero, and three domains regressed sharply. The gate correctly rolled it back.

This is evidence against the simplistic hypothesis “more visibility always improves the next proposal.” Rich evidence improves diagnosability and search capacity, but the evolver can still overgeneralize, add prompt overhead, or choose interventions that do not solve task-specific bottlenecks.

#### Case C — unchanged Control worker exposes held-out noise

Control kept no edits, so its seed and final worker digest were identical. Yet held-out rose from `0.583333` to `0.750000`, with binary FX and option-audit tasks changing outcome. Rich held-out fell by `0.083333`. Therefore the final held-out difference cannot be attributed only to the worker candidate in this single pair. Increasing from two to ten held-out tasks reduced granularity, but did not estimate independent model-sampling variance.

## 2. 分析与判断 / Analysis

### 2.1 What is now demonstrated

- **The full harness path is real, not a mock.** Public evidence was mounted read-only into an isolated evolver, a candidate was emitted, validated, scored with 20 official optimize tasks, and kept/rolled back by deterministic gates.
- **Rich exposure changed useful adaptation behavior.** It doubled evidence reads (`203` vs `94`) and produced the only kept candidate. The observed difference-in-adaptation gain is substantial relative to the `0.02` noise gate.
- **Evaluator isolation held.** Official tests and reference data existed only in independent no-network verifier sandboxes. Proposer-surface leak scans passed. The verifier did not use an LLM judge; it ran official deterministic tests and parsed their reward.
- **Recovery and cleanliness held.** The Rich run was paused and resumed from checkpoint without duplicating completed content-addressed scores. Across the two full arms, 554 sandbox lifecycle IDs were recorded and cleaned, with zero pending exact IDs.

### 2.2 What is not yet demonstrated

- **No stable causal effect size.** The two arms share a protocol but contain independently sampled worker trajectories; the different seed scores (`0.612500` vs `0.564583`) show the initial draws were not coupled. `causal_comparison=true` in the artifact means the intended treatment identity was isolated, not that one pair supplies statistical significance.
- **No transfer gain.** Rich held-out did not improve. This may be regression or ordinary sampling noise; the present design cannot distinguish them.
- **No broad full-harness mutation result.** All ten admitted proposals across both arms were prompt-only or no-change. Tool, middleware, skill, validator, memory and routing evolution remain untested in live scoring.
- **No cost-efficiency conclusion.** Rich evolver time was `2,724.293 s`, versus `1,019.346 s` for Control (`2.67×`); total recorded execution time was 7,612.656 s (`15.6%`) higher. Token usage and provider/E2B monetary cost were not exposed, so cost per gain is unknown.

### 2.3 Relation to the 2026-07-25 result

The 7 月 25 日 run remains useful as engineering and gate evidence but is not a causal arm and contains 14 verifier-contaminated zeros. The new A/B did **not** rewrite those records; it used the corrected verifier identities from the start and supplies new, complete 140-score arms. Therefore current adaptation analysis should use the Control/Rich pair, while the old run remains historical context only.

## 3. 问题与困难（待讨论）/ Problems & Open Questions

1. **How many repetitions are enough?** At least three matched Control/Rich pairs with independent preregistered model seeds are needed before treating `+0.155556` as a stable treatment estimate. Report the distribution and paired confidence interval, not only the mean.
2. **How should trajectories be coupled?** Same seed digest did not force identical stochastic seed evaluations. We need either replayable model sampling, repeated seed evaluations, or a paired common-randomness design that does not leak held-out outcomes.
3. **Rich feedback is more resource-intensive in recorded wall time.** It read 2.16× as many evidence records and used 2.67× evolver wall time. Without token and billing telemetry, we cannot determine whether the gain is economical.
4. **Long-tail task latency remains operationally dominant.** `localvol-barrier` and yield-curve tasks can occupy the final slot for roughly 30–40 minutes. Higher concurrency speeds the bulk but cannot remove the iteration tail. Per-task runtime distributions and timeout reasons need durable reporting.
5. **Exposure boundary remains a research variable.** Current Rich reveals public rubric and worker-observable traces but not hidden answers/tests. Future ablations should separate public goal/rubric, raw worker trajectory, and prior-candidate history instead of treating Rich as one indivisible treatment.
6. **Mutation diversity is low.** Prompt edits may be the easiest admissible move. We need to determine whether the evolver lacks evidence for tool/skill edits, whether admission/tool ergonomics discourage them, or whether prompt-only is genuinely optimal for this worker.
7. **Historical contaminated scores remain intentionally unrepaired.** They no longer block the new A/B evidence, but may be repaired as a separately identified superseding artifact if historical score comparability is worth the spend.

## 4. 下周计划 / Next Week's Plan

1. **Repeat the matched A/B across independent seeds.** Keep the same 30-task panel, five-iteration schedule, corrected verifier identities, model and gates. Run at least three pairs; preregister how arm order and sampling seeds are assigned.
2. **Add cost telemetry before more full runs.** Persist per-attempt model calls/tokens/cost when exposed, sandbox wall time, role-attributed lifecycle duration, provider billing fields and a run-level cost ledger. Unknown values must stay explicitly `null`, never be estimated as measured spend.
3. **Analyze evidence-to-edit causality.** For each proposal, record which evidence paths were read, the stated hypothesis, changed harness slots, targeted failure classes and realized task/domain deltas. This will distinguish useful feedback from generic prompt expansion.
4. **Run a mutation-surface canary.** Use a non-scoring admission test to confirm that a safe tool-description or skill edit can be generated, validated and executed end to end; do not force such edits into the paid benchmark merely to increase variety.
5. **Pilot sandbox alternatives without changing benchmark conclusions.** Keep E2B as the official reference. Implement Daytona Linux VM first for API/resource parity and run Vercel as the first matched cost pilot; no provider receives official tests until hard no-egress and lifecycle gates pass.
6. **Retain the current Rich iteration-3 worker as an experimental candidate, not the canonical default.** Promotion requires repeated optimize gain plus a transfer result that exceeds measured sampling uncertainty.

主要 artifacts / Primary artifacts: [A/B comparison](../../results/qfbench_feedback_ab/20260727-024921eb/comparison.md) · [Control result](../../results/qfbench/qfbench-30x5-full-control-20260727-024921eb/result.json) · [Rich result](../../results/qfbench/qfbench-30x5-full-rich-20260727-024921eb/result.json) · [Verifier repair decision](../decisions/2026-07-26-qfbench-verifier-template-repair.md) · [Feedback A/B design](../superpowers/specs/2026-07-27-qfbench-full-harness-rich-feedback-ab-design.md) · [Result decision](../decisions/2026-07-27-qfbench-full-harness-feedback-ab-result.md) · [Sandbox provider decision](../decisions/2026-07-27-sandbox-provider-selection-and-parity-plan.md).
