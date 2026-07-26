# 实验报告 / Experiment Report — QFBench 30-Task × 5-Iteration E2B Evolution

> 日期/Date: 2026-07-25 · 实验/Experiment: `qfbench-30x5-20260725` · Benchmark commit: `024921eb507fcc0c4ffe3e0a96802724be1ae84a`

## 1. 实验过程与结果 / Process & Results

- **目标 / Goal**：把 QFBench 从 3 optimize / 2 held-out 的小 pilot 扩展到预注册的 20 optimize / 10 held-out，并用 5 轮真实 E2B evolution 检查 reward firewall、resume 和更低的单题敏感度。
- **结论 / Headline**：工程链路完成 140/140 个 official score records，五个 candidate 全部被正确 rollback；但 3 个 verifier templates 的 offline cache 缺陷污染了 14 个 attempts，因此 performance score 只能视为 provisional，不能声称 evolution gain。

### 方法与过程 / Method & Process

```text
30-task manifest (20 optimize + 10 held-out, 6 domains)
        -> seed optimize + seed held-out
        -> 5 × proposer edit + 20-task candidate evaluation
        -> domain-regression gate + 0.02 noise-floor gate
        -> final held-out on the surviving incumbent
```

配置固定为 `deepseek/deepseek-v4-pro`、`concurrency=8`、global E2B cap 12。Worker 可访问受限的 model-provider endpoint；official tests/test reference data 只进入独立、无网络的 verifier sandbox；未上传或运行 official solutions。共享 base 被复用；60 个 task-role templates 中 10 个复用、50 个在 05:21–05:43 UTC 发布。完整命令和 resume 规则见 runbook。

调度为 `20 + 10 + 5×20 + 10 = 140`。从首个 attempt artifact 到最终 lifecycle cleanup 的实测跨度约 5 h 17 min。140 个 worker 中 4 个 timeout 后按预注册规则记 0 并跳过 verifier，因此实际生成 136 个 verifier、合计 276 个 sandbox lifecycles；最终 276/276 均 `cleaned_up=true`，exact-ID reaper dry-run 为 0 pending。模型 token、provider cost 与 E2B billing total 未写入 artifact，故记为 **not measured**。

### 数据与结果 / Data & Results

Observed optimize incumbent 为 0.500000，五轮没有 keep：

| Iter | Candidate overall | 关键 domain delta | Gate result |
| ---: | ---: | --- | --- |
| 1 | 0.490278 | `risk_credit -0.083333` | rollback：domain regression |
| 2 | 0.418452 | `systematic_strategy -0.500000` | rollback：domain regression |
| 3 | 0.465278 | `risk_credit +0.041667`, `systematic_strategy -0.250000` | rollback：domain regression |
| 4 | 0.529167 | `derivatives +0.333333`, `systematic_strategy -0.250000` | rollback：domain regression |
| 5 | 0.513194 | 全部 domain 非负；净增益 `+0.013194` | rollback：未超过 `0.020000` noise floor |

Held-out observed domain macro 从 0.666667 降到 0.583333（`-0.083333`），task mean 从 0.7 降到 0.6（`-0.1`）。最终变化来自 `fx-forward-cross-rate: 1→0`；其余可评分 held-out 题保持不变。`form4` 的 seed/final 都受 offline cache 污染，不能据此判断真实表现。

与 2026-07-24 pilot 的比较如下。两个 run 的 overall 使用不同 panel，只能作 contextual comparison，不是 paired estimate：

| Metric | 3-task pilot | 30-task run |
| --- | ---: | ---: |
| Optimize / held-out tasks | 3 / 2 | 20 / 10 |
| Iterations / official scores | 3 / 16 | 5 / 140 |
| Optimize seed→final | 1.0000→1.0000 | 0.5000→0.5000 |
| Held-out domain macro | 1.0000→0.5000 | 0.6667→0.5833 |
| Keep / rollback | 0 / 3 | 0 / 5 |
| One binary held-out task 对 task mean 的影响 | 0.5 | 0.1 |

Shared optimize tasks 中，`historical-var-data-prep` 和 `momentum-backtest` 都是 1.0；`evt-pot-var` 从旧 pilot 的 1.0 变为新 seed 的 0.833333。Shared held-out 中，旧 pilot 的 option audit 为 `1→0`、FX 为 `1→1`；新 run 为 option `0→0`、FX `1→0`。这再次显示 model sampling variance 并未因题量扩大而消失。

### 案例研究 / Case Study

**Case A — firewall 确实工作。** Iteration 4 的 overall 从 0.500000 提升到 0.529167，derivatives、execution 和 risk_credit 分别提高 0.333333、0.050000、0.041667；但 systematic_strategy 下降 0.25。`resume.json` 因此记录 `kept=false` 和 `domain regression: systematic_strategy`。这是“aggregate improvement 不得掩盖 domain harm”的端到端证据。

**Case B — offline isolation 成立，但 cache preflight 不完整。** 3 个官方脚本写成 `if uvx ...`，发布时 parser 只识别裸 `uvx ...`，对应 manifests 的 `verifier_uvx_warm_command` 为 `null`。无网络 verifier 随后无法从 registry 补齐 pytest，14 个 attempts 得到 `reward=0, tests_passed=0, tests_failed=0`。受影响的是 delta hedging 6 次、swap bootstrap 6 次、form4 2 次。根因已用 RED→GREEN test 修复，本轮授权没有包含额外 template rebuild 或 score repair。

## 2. 分析 / Analysis

1. **扩大题量显著改善了分辨率，但没有估计 stochastic variance。** Held-out task mean 的单个 binary task 步长从 0.5 降到 0.1；不过同一 seed worker 的 FX 仍出现 `1→0`，所以 30 题不能替代 independent model seeds。
2. **双 gate 提供了有意义的安全约束。** Iteration 4 证明 domain firewall 会拒绝“总分上涨但局部受损”；Iteration 5 证明无 domain regression 时，低于 0.02 的小增益仍不会晋升。
3. **没有 evolution gain。** 五轮均 rollback，final worker 与 seed 相同，optimize trajectory 只有 0.500000。Held-out 下降是对同一 worker 的独立采样，不是已接受 mutation 的 regression。
4. **当前 score 不是正式 authority claim。** 14 个 infrastructure zeros 横跨 optimize 与 held-out。它们在 observed table 中是固定 0，但 counterfactual official rewards 未知，可能改变 candidate delta 或 held-out level；因此只能保留工程与 gate 行为结论。
5. **主要成本风险来自 task-specific long tail。** `localvol-barrier` 可接近 2400 s，`yield-curve-bond-immunization` 多次接近 1800 s；提高 concurrency 无法消除轮末等待。应按 task 记录 runtime distribution 和 budget，而不是统一缩短 timeout。

## 3. 问题与困难（待讨论）/ Problems & Open Questions

1. **如何修复已完成 run 的统计身份？** 建议发布 3 个新 verifier identities，并在新授权下只修复 14 个 contaminated scores；需要决定是生成 superseding repair run，还是在保留原始 artifacts 的前提下重算同一 schedule。
2. **infra failure 是否应进入 reward？** 已完成 run 中，shell 可写 `reward.txt=0` 且 exit 0，即使 CTRF 从未生成。Local trusted parser 现已对明确的 offline dependency-resolution error fail closed；仍需决定其他“expected CTRF missing”路径应记录可恢复的 `verifier_error`，还是直接中止 checkpoint。
3. **需要多少 seed repetition？** 10 个 held-out tasks 降低了 panel granularity，但 FX 的 `1→0` 表明至少还需固定 panel 的多次 independent seed run，才能估计 uncertainty/noise floor。
4. **费用可观测性仍缺失。** 50 builds、140 worker scores 与 136 verifier lifecycles 已执行，但实际 E2B 和 provider 金额无法从 artifact 复核。

## 4. 下周计划 / Next Week's Plan

1. **固化 verifier preflight hardening。** Local code 已识别 `if uvx`、对未知 `uvx` wrapper fail closed，并拒绝明确的 offline dependency-resolution zero；下一步把 30-task manifest preflight 纳入 CI 和 paid-publication checklist。
2. **申请最小 paid repair authorization。** 只重建 delta/swap/form4 的 3 个 verifier templates，先做无模型的 offline cache canary，再修复 14 个受污染 scores；不上传 official solutions。
3. **生成 superseding comparison。** 修复后重算五轮 gate、held-out delta 和与旧 pilot 的 shared-task table；旧 run 保持 immutable，并由新 decision 明确 supersede。
4. **估计模型方差。** 对固定的代表性 optimize/held-out 子集运行至少 3 个 independent seeds，分开报告 task-panel variance 与 model-sampling variance。
5. **补齐 cost telemetry。** 在 attempt/run manifest 中持久化 provider usage、token/cost（若 API 提供）和 E2B lifecycle duration/billing metadata；未知值继续明确标为 not measured。

主要 artifacts：`results/qfbench/qfbench-30x5-20260725/resume.json`、`result.json`、`validity-audit.json`、`comparison-to-pilot-3.{json,md}`、`data/qfbench/MANIFEST_30.json` 和 `output/qfbench-e2b-images/20260725_30x5_024921eb/`。
