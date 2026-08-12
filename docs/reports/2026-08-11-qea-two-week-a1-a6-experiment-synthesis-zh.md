# QEA 近两周 A1-A6 实验综合报告

> **Scope。** 本报告覆盖 2026-07-30 至 2026-08-11 的主要 QFBench experiments：
> self-hosted rootless backend canary、85x5 baseline、第一轮 full-harness evolution，
> 以及 A1-A6 discovery mechanism sequence。它面向研究结论与实验决策，不复述 tool-call、
> restart、package hash 或逐次 repair 细节；这些细节继续保存在各 dated report 和 machine record。

## 结论先行

近两周的实验完成了三层递进：

1. **Execution foundation 已建立。** self-hosted rootless Docker、offline verifier、
   evaluator firewall、exact-ID lifecycle、monitor/mirror 和大规模 baseline 都完成了真实验证。
2. **Full-harness evolution 的瓶颈被定位。** 第一轮 evolution 只产生 `systemprompt.md`
   edits；A1-A3 证明 component 可以被注册、translocate 和 activate，但 routing 仍不够精准；
   A4-A5 进一步证明 richer evidence、更多 hypotheses 和 probes 仍不自动产生正确 intervention。
3. **Discovery control mechanism 已经可用，但 productive ACT 尚未证明。** A6 最终实现了
   multi-epoch exploration、real probes、reload-verified checkpoints、bounded repair、
   immutable decision 与 truthful calibrated `ABSTAIN`。不过没有一轮 A6 产生 legal `ACT`、
   non-empty full-harness diff、candidate validation、admission 或 candidate panel。

因此，当前最准确的 program status 是：

> **Execution and discovery-control mechanism PASS；calibrated ABSTAIN PASS；
> productive ACT-to-candidate evolution 尚未得到证明。**

这不是“evolution 没用”的证据。已测得的结论是：当前瓶颈已从 infrastructure、route、
context 和 control flow，迁移到 **evidence sufficiency、semantic identifiability 与 component
localization**。下一步不应继续增加 blind iterations，而应直接验证一个具备足够 public
evidence、same-task semantic discriminator 和 matched-success contrast 的合法 `ACT`。

## 实验内术语与判定规则

以下术语是本 program 的 operational definitions，不应直接等同于日常语言中的“行动”“拒绝”
或“检查点”。它们描述的是 Evolver 在 evidence、mutation 与 evaluation 之间所处的 protocol
state。

| Term | 本实验中的具体含义 |
|---|---|
| `ACT` | Evolver 判断现有 evidence 足以支持一个 selected hypothesis，并愿意提出 bounded intervention。它是一种 structured decision，不等于 candidate 已经有效，也不等于 reward 已经提高。A5 的 `failure_only ACT` 使用的是较早、较宽松的 A5 contract。 |
| `legal ACT`（A6） | 通过 A6 local verifier 的严格 ACT：必须绑定 real current-epoch probe；selected hypothesis 的 typed expectation 为 true，至少一个 eliminated competitor 为 false；相关 public evidence 已实际访问并通过 content/access binding；ready checkpoint reload 验证通过；immutable decision 与 checkpoint 精确一致。它只解锁 candidate write，仍不是 experiment success。 |
| `CONTINUE` | 非终局 checkpoint branch。表示当前 evidence 还不足以 ACT/ABSTAIN，需要保存本 epoch 的 verified state、unverified memory 与 next question，再进入下一轮 exploration。它不会解锁 candidate write。 |
| `ABSTAIN` | Evolver 明确声明现有 evidence 不足以安全选择 intervention。A6 中它必须绑定 real probe、给出 bounded insufficiency reason，并保持 candidate writes locked。它不是 timeout、provider error、empty response 或程序 crash。 |
| `calibrated ABSTAIN` | 一个通过 local verifier、checkpoint/decision binding 与 truthful terminal gate 的合法 ABSTAIN。它表示机制正确识别了 uncertainty；属于 control-mechanism success，但不是 harness-benefit success。 |
| `probe` | 对 answer-free public evidence 执行的 bounded diagnostic。`schema-1 probe` 可以记录一般 observation，足以支持 CONTINUE 或 ABSTAIN；`schema-2 probe` 必须在同一 task 上连接 `public contract clause <-> manifested artifact <-> trace phase`，并对 competing hypotheses 给出 typed expectations，才可能支持 A6 legal ACT。 |
| `checkpoint` | 持久化并可 reload-verify 的 discovery state，绑定 probe result、evidence refs、hypothesis universe、candidate tree hash 与 validation snapshot。`ready checkpoint` 只是进入 immutable decision 的前置条件；checkpoint 本身不是 candidate，也不是 performance result。 |
| `full-harness diff` | candidate workspace 相对 frozen seed 的真实、non-empty 修改；允许覆盖 prompt、tools、bindings、skills、middleware、validator、memory 或 routing。它不表示必须同时修改所有 components，但不能只是文字 proposal。 |
| `validation` / `admission` | `validation` 检查 diff、tree binding、declared components、write restrictions 与必要的 smoke/inspect signals；`admission` 决定该 candidate 是否满足进入 measured panel 的 policy。两者都通过后，仍需 evaluation 才能讨论 gain。 |
| `candidate panel` | legal ACT candidate 通过 validation/admission 后才允许启动的最多四个 relevant/risk tasks 小型 evaluation。它是 engineering feasibility check，不是 formal generalization study。 |
| `semantic identifiability` | public evidence 是否足以区分 selected mechanism 与 plausible competitors，并能把 mechanism 连接到具体 component intervention。更多 traces、hypotheses 或 probes 本身不保证 identifiability。 |

> **阅读关键。** A5 确实产生过一个符合 A5 contract 的 `ACT`，但它的 primary prediction 被
> falsify；A6 尚未产生符合更严格 A6 contract 的 `legal ACT`。ME7 与 ME10 的
> `calibrated ABSTAIN` 则是有效的 mechanism outcome，但没有产生 candidate gain。

## 实验路线总览

| Stage | Main question | Measured outcome | Status |
|---|---|---|---|
| Rootless canary | self-hosted backend 能否保持 evaluator isolation | historical verifier parity PASS；fresh model route 被 HTTP 403 中断 | infrastructure partial PASS |
| 85x5 baseline | fixed Flash worker 的稳定 performance 是什么 | 425 official scores；77-task primary domain macro `0.3697` | baseline established |
| First evolution | 现有 Evolver 能否改进 full harness | 4/10 iterations；0 candidate kept；只编辑 prompt | exposure/manipulation negative |
| A1 | prescribed skill 是否可注册并真实 activate | final trace run `3/3` activation | reachability PASS |
| A2 | generic translocation 能否迁移有用 component | candidate admitted；`2/4` activation；task mean `0.25` | partial mechanism PASS |
| A3 | debugger-guided selection 能否改善 activation | candidate admitted；`4/4` activation；task mean `0.7083` | routing over-broad |
| A4 | richer evidence 能否产生可证伪 intervention | 访问全部 5 traces；candidate active；5-task reward vector unchanged | mechanism falsified |
| A5 | failure types、probes 与 success contrast 能否改善 decision | `failure_only=ACT` 但 prediction 失败；`contrastive=ABSTAIN` | calibration advanced |
| A6 | semantic evidence 与 bounded multi-epoch control 能否形成 safe ACT | control path 最终 PASS；ME7/ME10 valid ABSTAIN；0 legal ACT | feasibility still open |

## Foundation 0A - Self-hosted rootless backend canary

**Purpose**

验证共享 `bc-server` 上的 self-hosted rootless Docker，能否在不削弱 evaluator firewall 的
前提下，复现 QFBench worker-to-artifact-to-offline-verifier 的关键执行链路。

**What we did**

- 构建 immutable base、worker 和 verifier images；
- 将 official tests/reference 固定在独立、`--network none` 的 verifier container；
- 检查 worker egress、read-only root、bounded tmpfs、cgroup、force-kill、exact-ID reaper 与
  resume；
- 对一个 historical artifact 执行 official verifier parity，并启动一个 fresh worker canary。

**Measured data**

- historical artifact parity：reward `1.0`，`12/12` tests passed；
- offline verifier 的 DNS、TCP、HTTP、HTTPS 与 package access 全部被拒绝；
- fresh paid request：一次 provider request，HTTP 403，未生成 worker artifact 或 official score；
- cleanup 后 managed containers/networks 均为零；fresh request 的 cost 为 unknown，不是零。

**Conclusion**

rootless backend 已证明 isolation、artifact-only handoff、deterministic verification 和 lifecycle
能力，但该 canary 没有完成 fresh model-to-score 闭环。它是 backend engineering PASS 的重要
前置证据，不是 performance comparison。

## Foundation 0B - 85x5 fixed-worker baseline

**Purpose**

在固定 `deepseek/deepseek-v4-flash-0731`、固定 seed worker 与 rootless runtime 下，建立后续
evolution 可以比较的 repeated baseline，并分开 primary tasks 与 copy-oracle diagnostics。

**What we did**

- 对 85 tasks 执行 5 independent repetitions，共 `425 official scoring attempts`；
- primary panel 使用 77 tasks；8 个 copy-oracle tasks 只作为 diagnostic，不并入 headline；
- worker/verifier concurrency 固定为 `12/3`，provider fallback disabled；
- 所有 task-level results、replacement manifests 和 lifecycle artifacts 均持久化。

**Measured data**

- primary 77-task repeat domain macro：mean `0.3697`，95% CI `[0.3340, 0.4054]`；
- primary repeat task mean：`0.4385`，95% CI `[0.3915, 0.4856]`；
- five repetitions 全部完成，`425/425` official scores；
- 8-task diagnostic domain macro：`0.3478`，与 primary 分开报告。

**Conclusion**

这是当前 fixed-worker 的 canonical repeated baseline。它说明单次 task vector 有明显 sampling
variation，因此后续 improvement 不能只看一次 task mean；同时必须保持 panel-matched、
domain-macro 和 task-level vectors 分开。

## Foundation 0C - 第一轮 full-harness evolution

**Purpose**

验证当 Evolver 获得现有 candidate workspace 与 feedback 后，能否在 10 iterations 内产生并
保留一个优于 fixed seed 的 full-harness candidate。

**What we did**

- 使用 30 train、15 validation、40 test 的 train/validation/test schedule；
- 计划 10 iterations，实际完成 4 iterations 后冻结；
- admission policy 允许修改 prompt、tools、middleware、skills、validator、memory 与 routing；
- 对每个 candidate 执行 official scoring、validation gate、keep/rollback 与 exact resume。

**Measured data**

- 完成 `225 official scores`，4 个 iterations，`0 candidate kept`；
- iterations 1-3 只编辑 `systemprompt.md`，分别因 domain regression 被 rollback；
- iteration 4 返回 empty diff，却仍消耗 45 official scoring attempts；
- incumbent 从未 advance；seed train/validation/test domain macro 分别为
  `0.3889 / 0.2500 / 0.4570`；
- provider ledger：`3,462 model requests`，78,480,049 tokens，USD `3.3472`；
- observed effective worker concurrency `5.13`，低于配置 12；provider HTTP 402 在 iteration 4
  后终止 run。

**Conclusion**

这轮结果应被解释为 **exposure/manipulation failure**，而不是“full-harness evolution 无效”。
Evolver 虽然技术上能够写多种 component，却只被 prompt 与 guide 引导到
`systemprompt.md`；`smallest coherent change` incentive 也强化了 prompt-only behavior。
这直接推动了 A1-A6：先验证 component reachability，再改善 evidence-to-intervention policy。

## A1 - Prescribed skill activation

**Purpose**

验证一个明确指定的 `spec-driven-deliverables` skill，能否被正确注册、加载，并在真实 worker
trace 中出现 activation；该实验只测 reachability，不测 autonomous discovery。

**What we did**

- 将 skill 接入 NexAU worker；
- 在三个 QFBench tasks 上执行 trace-based worker runs；
- 通过 exact activation token 检查是否真的调用了 skill，而不是只检查配置文件存在。

**Measured data**

- final trace run：`3/3` tasks activated `spec-driven-deliverables`；
- task rewards：`evt-pot-var=0.5`、`fomc-tone-event-study=1.0`、
  `historical-var-data-prep=1.0`；task mean `0.8333`；
- `37 completed requests`，515,349 tokens，USD `0.02642598`。

**Conclusion**

skill registration、binding 和 runtime activation 都可达。A1 证明“component 可以被使用”，
但因为 intervention 是 prescribed 的，不能据此声称 Evolver 能自主找到正确 component。

## A2 - Generic component translocation

**Purpose**

验证 Evolver 是否能从一个 source parent 抽取 component，并通过 generic translocation operator
迁移到 backbone candidate，而不是依赖手工指定全部修改。

**What we did**

- 提供 source/backbone parents、task vectors 和 operator contract；
- 允许 Evolver 修改 `agent.yaml`、skill、system prompt 与 tool description；
- 对生成 candidate 执行 admission、四任务 evaluation 和 trace activation audit。

**Measured data**

- candidate 通过 admission，并迁移 `spec-driven-deliverables` skill；
- activation：`2/4` tasks；
- task rewards：`credit-migration-matrix=0`、`evt-pot-var=0`、
  `fomc-tone-event-study=0`、`realized-vol-estimators=1`；task mean `0.25`，
  domain macro `0.1667`；
- `40 completed requests`，526,245 tokens，USD `0.0299028408`。

**Conclusion**

generic translocation 和 admission 工作，但 activation 只覆盖一半 tasks，而且没有形成稳定
performance improvement。A2 证明 component transfer 可行，问题转向 task-conditional routing
与 source behavior 的正确抽取。

## A3 - Debugger-guided selection

**Purpose**

测试 deterministic debugger/indexer 提供历史 candidate、task vectors 和 positive/negative
clusters 后，Evolver 是否能更好地选择并绑定 component。

**What we did**

- 汇总 seed 与历史 candidates 的 task-level outcomes；
- 让 debugger 生成 answer-free selection evidence；
- Evolver 重新生成 candidate，并在四任务 panel 上审核 admission、activation 与 reward。

**Measured data**

- candidate admitted，`4/4` tasks 全部 activate skill；
- task rewards：`credit-migration-matrix=1.0`、`evt-pot-var=0.8333`、
  `fomc-tone-event-study=0`、`realized-vol-estimators=1.0`；
- task mean `0.7083`，domain macro `0.4722`；
- `91 completed requests`，1,897,501 tokens，USD `0.0777959896`。

**Conclusion**

debugger evidence 提高了 structural selection 与 activation coverage，但 skill 在 `4/4` tasks
上都 activate，说明 routing 仍然过宽。A3 证明 wiring/reachability 不再是主要问题；真正瓶颈是
如何从 behavior evidence 推断 task-specific causal mechanism。

## A4 - Evidence-to-hypothesis behavior canary

**Purpose**

测试一个 model-bound Evolver 在看到 raw traces、process summaries、artifacts 与 deterministic
index 后，能否完成 grounded evidence to competing hypotheses to component to prediction 的闭环，
并产生一个可证伪 intervention。

**What we did**

- 冻结 3 个 repeated failures 和 2 个 stable protections；
- fresh seed 收集五个 tasks 的 traces、finals、process summaries 和 bounded artifacts；
- Evolver 自主比较 system prompt、validator/middleware 与 deterministic tool hypotheses；
- admission 后，对同一五任务 panel 执行 candidate evaluation 和 process prediction audit。

**Measured data**

- Evolver 访问 `30/44` evidence members、`5/5` raw traces，记录 3 competing mechanisms；
- candidate admitted，只修改 `systemprompt.md`；
- 五个 tasks 的 test-count 与 reward vectors 全部 unchanged；target gains `0`，
  protection regressions `0`；
- candidate 确实让 `5/5` tasks 首次调用先 inventory workspace，但三个 targets 的
  tool calls `27 -> 30`、tool errors `6 -> 7`、turns `23 -> 25`；
- known Flash-path cost 至少 USD `0.1184029224`；seed、Evolver、candidate 合计至少
  2,813,434 tokens，另有 route probe。

**Conclusion**

instrumentation 和 evidence-to-hypothesis loop 工作，但 selected mechanism 被自身 prediction
falsify。richer evidence 没有阻止 Evolver 收敛到 prompt-only edit；因此不应从 A4 candidate
继续 multi-round evolution。下一步需要 `ABSTAIN`、identifiability gate 和 executable probes。

## A5 - Failure types、probes 与 contrastive calibration

**Purpose**

测试 Evolver 是否能把多个 failures 归纳为 recurring failure types，生成 competing hypotheses，
执行 answer-free probes，并通过 success counterfactual 判断应当 `ACT` 还是 `ABSTAIN`。

**What we did**

- 使用 6 个 repeatable failure targets 和 5 个 stable protections；
- matched comparison：`failure_only` 允许缺少 success counterfactual，`contrastive` 要求
  counterfactual 或显式 `insufficient_contrast`；
- 两个 arms 使用相同 evidence 与 constrained probe interface；
- 仅对 `failure_only` 的 ACT candidate 执行 11-task evaluation。

**Measured data**

- 四个 valid model runs：`334 completed requests`、12,857,239 tokens、
  USD `0.3953654432`；
- `failure_only`：17 hypotheses、6 probes、eliminated 12，选择 `ACT`，修改
  `systemprompt` + `tool description`；
- `contrastive`：6 success counterfactuals，其中 3 个 `insufficient_contrast`，3 probes，
  选择 `ABSTAIN`，writes locked；
- ACT candidate 的 11-task binary vector 完全 unchanged：6 targets 仍为 0，5 protections
  仍为 1；task mean `5/11=0.4545`；primary zero-coupon prediction 被 falsify；
- `localvol-barrier` 从 timeout 变为 completed `0/7`，但 paired tasks 的 mean turns、tool calls、
  tool-error rate 与 wall time 都上升。

**Conclusion**

A5 首次证明 discovery harness 可以真实执行 type induction、hypothesis competition、probes 与
`ACT/ABSTAIN` decision。最强结论是 calibration，不是 reward gain：failure-only 产生了
evidence-rich 但错误的 ACT；contrastive 用 success-side uncertainty 避免 unsupported mutation。
下一步需要 semantic public-contract evidence，而不是更丰富的 narrative。

## A6 - Expanded semantic discovery 与 bounded control

**Purpose**

在 16-task frozen panel 上，区分 raw evidence、indexed evidence 与 evidence-plus-public-contract
representations，并验证一个安全、multi-epoch、checkpoint-bound 的 discovery mechanism 能否
产生 legal `ACT` 或 calibrated `ABSTAIN`。

**What we did**

- panel：6 repeatable failures、8 stable protections、2 volatile sentinels；
- 初始 matched arms：`A6-R`、`A6-E`、`A6-EC`；
- 保持 `deepseek/deepseek-v4-flash-0731`、DeepSeek、high reasoning、no fallback、
  answer-free evaluator firewall 与 rootless isolation 固定；
- 初始 arms 未能到达共同 terminal decision 后，使用 fresh IDs 执行 ME mechanism sequence，
  逐步加入 structured progress、probe/checkpoint persistence、verified navigation、compact
  projection、pre-wire guards、case-safe IDs 和 immutable decision；
- candidate evaluation 始终 gated，只有 legal ACT + non-empty diff + validation + admission
  才能开启。

**Measured data**

- 初始 R/E/EC：60 wire attempts、59 logical calls、59 HTTP 200、1 safe HTTP 429，
  5,092,626 tokens，USD `0.1645248976`；三个 arms 都没有 valid decision、proposal 或 diff；
- ME1-ME10 sequence：174 wire attempts、172 logical requests、170 HTTP 200、
  1 HTTP 400、2 safe HTTP 429、1 HTTP 520；known accepted usage 至少
  5,798,107 tokens，known cost 至少 USD `0.3520366696`；
- 仅合计 R11 proposal-only + ME mechanism sequence：至少 10,890,733 known tokens，
  至少 USD `0.5165615672`；这不包含更早的 A6 seed/infrastructure attempts；
- ME7 与 ME10 产生 valid terminal calibrated `ABSTAIN`；
- ME10：22/22 HTTP 200，1,101,540 tokens，USD `0.0718470312`，三个 exploration epochs、
  三个 probes、三个 checkpoints、immutable ABSTAIN decision、clean exit；
- 全部 A6 experiments：legal ACT `0`、non-empty candidate diff `0`、candidate validation `0`、
  admission `0`、candidate panel `0`。

**Conclusion**

A6 不能支持 R/E/EC representations 的 scientific comparison，因为初始三 arms 没有到达共同
decision boundary。ME sequence 的有效结论是 control mechanism 已经通过 live validation：
route、context、multi-epoch state、compaction、probe、checkpoint、bounded repair、immutable
ABSTAIN、accounting 与 cleanup 都能 end-to-end 工作。剩余问题不是 terminal plumbing，而是
ACT 所需的 semantic evidence sufficiency。

## 跨实验结论

### 已经得到验证

- rootless execution、offline verifier、evaluator firewall 与 lifecycle cleanup 可用；fixed Flash
  baseline 也已量化 repetition variation；
- Evolver 能修改并 activate prompt、skills 与 tool descriptions；deterministic debugger 能改善
  evidence organization 和 component reachability，但 routing 仍可能过宽；
- richer evidence、更多 hypotheses/probes 不保证 causal correctness；success counterfactual 与
  `insufficient_contrast` 对 calibrated `ABSTAIN` 有实际价值；
- A6 bounded discovery control mechanism 已通过真实、truthful terminal `ABSTAIN`。

### 尚未得到验证

- legal `ACT` 能产生 non-empty、validated、admitted full-harness improvement；
- candidate 能带来 reward/task mean/domain-macro gain，或 A6-R/E/EC 存在 representation advantage；
- 当前结果可以 transfer，或 A4/A5/A6 的 failure phenotype 是 reward-causal truth。

## 下一实验边界

下一轮不应再做 blind multi-iteration search，也不需要继续改写 terminal mechanism。应使用
fresh successor，直接验证一条最小 legal ACT path：

1. 实际访问至少两个 declared failure targets，以及一个 matched success 的
   `public_evaluation` 与 task evidence；
2. 执行 same-task schema-2
   `public clause <-> manifested artifact <-> trace phase` discriminator，支持 selected
   hypothesis 并排除至少一个 competitor；
3. 只有 legal ACT 产生 non-empty diff 且通过 validation/admission，才启动最多四个
   relevant/risk tasks 的 candidate panel；
4. causal bridge 仍弱时保留 `insufficient_contrast` 与 calibrated `ABSTAIN`，不强迫写入。

成功标准不再是“model 写出了 proposal”，而是：

> **legal ACT -> non-empty full-harness diff -> validation -> admission -> <=4-task candidate panel。**

**Evidence boundary。** 本报告只引用 frozen public experiment summaries、pilot reports、
provider accounting 与 dated reports，不重新解释 official tests、private verifier inputs 或
hidden outcomes。详细 A6 ME repair chain 继续保存在 ME1-ME10 appendix。
