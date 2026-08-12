# QFBench A6 R11 ME1-ME10 Engineering Mechanism Validation 综合报告

> **Claim boundary。** 本报告紧接已经冻结的
> [R11 three-arm engineering discovery negative](2026-08-10-qfbench-a6-r11-engineering-discovery-negative.md)，
> 覆盖之后全部 ME1-ME10 mechanism-validation 实验，包括 provider-zero
> infrastructure attempts，以及 deterministic source/package/preflight gates。
> 这是一份 engineering synthesis，不是 formal A6 result、statistical comparison、
> causal-benefit claim，也不是 publication-grade benchmark conclusion。

## 结论先行

ME 系列将 A6 discovery Evolver 从 terminal/tool-interface failure，推进成了一个真实、
bounded、evidence-bound 的 terminal mechanism。ME7 首次产生合法、与 checkpoint 绑定的
`ABSTAIN`；ME10 在修复 navigation、compact-state、pre-wire guard 和 hypothesis-ID
interoperability 后，再次得到更强的合法 `ABSTAIN`。ME10 是目前最强的 mechanism result：
三个 exploration epochs、三个 real probes、三个 reload-verified checkpoints、bounded
repair、immutable decision、exact accounting、truthful completion、candidate write lock 和
clean resource closure 都在真实 paid path 中正常工作。

但是，用户定义的 A6 engineering success bar 仍然**没有达到**。所有实验中都没有出现合法
`ACT`、非空 full-harness diff、candidate validation、admission，或者单独识别出的、最多四个
任务的 candidate panel。没有 candidate 被评估，也没有测得 harness benefit。因此，诚实的
结论是：

> **Terminal mechanism PASS / calibrated ABSTAIN PASS / ACT-to-candidate
> engineering feasibility 尚未得到证明。**

bottleneck 已经迁移。它不再是 route health、context capacity、multi-epoch rollover、
checkpoint persistence、compact-state capacity 或 terminal `ABSTAIN` control flow；
现在的瓶颈是安全 `ACT` 所需的 evidence sufficiency 与 semantic identifiability：
matched-success evidence、task-bound public outcomes，以及 same-task
public-clause-manifested-artifact-trace discriminator。

## Reporting boundary 与共同 execution contract

此前的 R11 R/E/EC three-arm report 作为 baseline，本报告不重复计入。ME1-ME10 一直保持
相同的 engineering-only boundary：

- model：`deepseek/deepseek-v4-flash-0731`；
- required provider：DeepSeek；
- fallback：disabled；
- reasoning effort：high；
- immutable formal R10 source release 保持不变；
- 每次 launch 之前执行 same-ID zero-model preflight；
- discovery 期间禁用 candidate evaluation；
- 只有在 legal ACT、non-empty diff、successful validation 和 admission 全部完成后，才允许
  candidate panel；
- Evolver 只能访问 answer-free public evidence；gold、official tests/solutions、raw private
  verdicts、trusted criteria、credentials 与 held-out evaluator material 始终不进入 Evolver
  surface。

每个最终 ME identity 都先通过 `preflight_complete`，其中 `model_request_count=0`，
runtime/evidence/scheduler identities 精确一致，service/timer 处于 inactive，scoped
containers/networks 为零，并且在 paid attempt 前不存在 model-boundary、request、audit、
proposal 或 candidate artifacts。下文的 deterministic test counts 是 versioned gates，
不是可以相加的独立 observations；不同 generation 会重复执行 related suite 和部分 focused
regressions。

## 累计 provider accounting

| Item | ME1-ME10 total |
|---|---:|
| Wire attempts | **174** |
| Logical requests | **172** |
| HTTP-200 accepted responses | **170** |
| HTTP 400 | **1 - ME2** |
| Safe not-accepted HTTP 429 | **2 - ME7** |
| HTTP 520 | **1 - ME8** |
| Known accepted input tokens | **5,407,027** |
| Known accepted output tokens | **391,080** |
| Known accepted total tokens | **5,798,107** |
| Known provider cost | **USD `0.3520366696`** |

token 与 cost 合计是 lower bounds，不是 billing upper bounds。ME2 的 HTTP-400 row 和 ME8
的 HTTP-520 row 都没有 provider request ID、usage 和 cost；这些字段是**未知**，不是零。
如果完全排除 ME2，剩余 167 wire attempts、165 logical requests、164 HTTP-200 responses、
5,626,876 known accepted tokens 和 USD `0.3448526536`；但因为仍包含 ME8 usage/cost 未知的
HTTP-520 row，这一 subtotal 依然只是 lower bound。完全可核对的 accepted-usage subset
同时排除 ME2 与 ME8，包含 158 wire attempts、156 logical requests、156 HTTP-200
responses、两次 ME7 safe not-accepted HTTP 429 attempts、5,404,760 accepted tokens 和
USD `0.3306656304`。

ME5 是单独证明的 provider-zero attempt：它在 sandbox 和 proxy 构建之前失败，没有产生
request/usage/cost artifact，也没有发生 model cost。

## 逐实验记录

### ME1 - multi-epoch rollover 已工作，但没有 structured progress

- Run ID：`qfbench-a6-discovery-e-flash-high-20260810-r11-me1`
- Source gates：23 focused + 65 related tests。
- Accounting：24/24 HTTP 200；874,396 input + 28,697 output = 903,093 tokens；
  USD `0.0341954704`。
- Mechanism state：三个 exploration epochs、24 exploration calls、零 probe、零 checkpoint、
  零 decision、零 diff。

ME1 证明 1M-advertised Flash route、真实 510,125-token canary、multi-epoch rollover、
compact prompts、one-shot paid-boundary marker、rootless isolation、accounting、watchdog、
additive mirror 和 exact cleanup 都能够工作。但它没有证明 discovery progress。普通的
access-log 增长重置了 generic progress fingerprint，因此 model 用完 24 exploration calls，
仍没有生成 probe 或 checkpoint。

failure 时的 60 access records 和 24 distinct paths 来自 live observation；host failure path
没有持久复制该 runtime log。immutable evidence tree 中空的 `access_log.jsonl` 不能被误解为
runtime 没有访问。Frozen machine record SHA-256：
`ab90fb3e66a52f130adcf120a70b6a57f815d3c6e97c70dd2316592c3fa2bae9`。

### ME2 - hard cadence 遇到 provider tool-choice incompatibility

- Run ID：`qfbench-a6-discovery-e-flash-high-20260810-r11-me2`
- Source gates：33 focused + 70 related tests。
- Accounting：七次 wire/logical requests；六次 HTTP 200、一次 HTTP 400；accepted
  166,962 input + 4,269 output = 171,231 tokens；known cost 至少 USD `0.007184016`。
- Mechanism state：六次 exploration calls、一次 checkpoint-repair request，零
  probe/checkpoint/decision。

ME2 正确停止把普通 reads 当作 structured progress，并进入 bounded repair surface。第一次
repair request 使用 `tool_choice=required`；DeepSeek thinking mode 返回
`Thinking mode does not support this tool_choice`。这是 provider-interface negative，
不是 checkpoint mechanism 的结论。Frozen machine record SHA-256：
`d7108f2877b0de79a9c3afb9c5ebbba0442d9114e4776b24fc16700487a3d08a`。

### ME3 - thinking-compatible repair 生成 probe，但 checkpoint errors 被吞掉

- Run ID：`qfbench-a6-discovery-e-flash-high-20260810-r11-me3`
- Source gates：39 focused + 70 related tests。
- Accounting：10/10 HTTP 200；239,492 input + 29,856 output = 269,348 tokens；
  USD `0.017214512`。
- Mechanism state：一个 real schema-1 probe，零 checkpoint、零 decision。

ME3 改用 provider-compatible `tool_choice=auto`，限制 repair tool surface，scrub invalid
response forms，并通过 force-continue 执行 bounded repairs。它持久化了第一个 real probe。
Calls 8-10 在 middleware boundary 上看似合法的 `checkpoint_memory` calls，却没有 append
checkpoint，也没有 durable validation error。Pinned NexAU 在 tool implementation 外做 schema
validation，但会把 implementation exceptions 转成普通 error results；ME3 只验证 tool names，
没有验证 checkpoint parameters 或 execution status。

由于 rejected arguments 没有保留，诊断来自 frozen terminal/command path 与 successor replay，
而不是 byte-exact request reconstruction。Terminal SHA-256：
`8edd2a1d9fa120efc4c55fc9c9f0ea838809d73d23d144bdb9f62be57643f6f4`；
proxy audit SHA-256：
`09b97a6de02e1b866192822381bd421d2f2c53ca143d8f69ddb50b604b75f328`。

### ME4 - exact checkpoint feedback 生效，但 monolithic interface 仍不可用

- Run ID：`qfbench-a6-discovery-e-flash-high-20260810-r11-me4`
- Source gates：49 focused + 70 related tests。
- Accounting：11/11 HTTP 200；212,705 input + 29,243 output = 241,948 tokens；
  USD `0.01689282`。
- Mechanism state：一个 real schema-1 probe、零 checkpoint、四个 durable checkpoint errors、
  零 decision。

ME4 在 `Tool.execute` 之前加入 read-only checkpoint payload normalization，同时加入
scrub-before-persist、compact state 中的 exact current error，以及 bounded post-tool execution
status。这些 controls 正常工作：四个不同 errors 被持久化并可见。但 model 仍把 prose 当作
evidence path、引用 undeclared state，并在 CONTINUE/ABSTAIN payload 中附加 forbidden
intervention fields。大型 nested checkpoint interface 用完全部 repairs，仍未 append。

raw rejected arguments 没有保留；四类 error 是精确的，但 successor tests 是 class replay，
不是 byte-exact request replay。Terminal SHA-256：
`5de34860526d63364872eb35b5b2d602246a9d6d090c6d46cb4a3f18f4c36483`；
proxy audit SHA-256：
`eb4761d87c914435f53b978fa052cf8ac39534ae1d6d54bc2207be2e96922810`。

### ME5 - branch-minimal mechanism 本地通过，但 live attempt 为 provider-zero

- Run ID：`qfbench-a6-discovery-e-flash-high-20260811-r11-me5`
- Source gates：51 focused + 70 related tests，包括真实 NexAU
  checkpoint-to-decision-to-non-empty edit-to-validation/admission path，以及真实 ABSTAIN
  write-lock path。
- Accounting：零 wire requests、零 tokens、零 model cost。

ME5 用 branch-separated derived-state tools 和 small decision adapter 替代 monolithic
checkpoint API。live launch 没有执行到该 mechanism：resource lease 在 sandbox/provider
construction 之前失败，因为 `load_1m=82.001953125` 高于未修改的 `56.0` threshold。计划中的
restart 被 durable model-boundary marker 拦截。这只验证了 pre-provider lease failure、marker
containment 和 cleanup，不是 mechanism outcome。将原因归于其他 host jobs 只是 operator
observation，不是精确 `ResourceLeaseTimeout` 结论所必需。Incident record SHA-256：
`190df5f657cb63dc7b054c378c81ffc96366aa1d1b5c1ab066f6eec3cf8b246e`。

### ME5B - 首次重复持久化 probe/checkpoint，但没有 terminal decision

- Run ID：`qfbench-a6-discovery-e-flash-high-20260811-r11-me5b`
- Mechanism bytes：使用 fresh identity，与 ME5 byte-identical。
- Accounting：25/25 HTTP 200；993,640 input + 70,234 output = 1,063,874 tokens；
  USD `0.064557136`。
- Mechanism state：三个 probes、三个 probe-bound CONTINUE checkpoints；前两个推进 epoch，
  final checkpoint non-ready；零 decision/diff/validation/admission。

ME5B 证明了真实 checkpoint persistence 与 exact bounded repair：不合法的
`next_hypothesis_ids` subset 被拒绝、反馈并成功修复。final checkpoint 让所有 hypotheses 保持
open。final-epoch gate 随后抛错，NexAU 尝试再次进入 call，而 one-shot guard 在 provider I/O
之前拦截。ME5B 是显著的 mechanism 进步，但仍是 engineering negative。Frozen
[single-run report](2026-08-11-qfbench-a6-r11-me5b-engineering-negative.md) 和 machine record
SHA-256：
`c1ef8407f8f86be43b5949b1249d0a53a2b6b52bebdf14d01a0d1df0df38f769`。

### ME6 - explore text/no-tool 暴露 false-success terminal path

- Run ID：`qfbench-a6-discovery-e-flash-high-20260811-r11-me6`
- Source gates：66 focused + 70 related tests。
- Accounting：14/14 HTTP 200；325,632 input + 27,206 output = 352,838 tokens；
  USD `0.0217533344`。
- Mechanism state：两个 real probes、两个 non-ready CONTINUE checkpoints、零 decision/diff。

Call 14 在普通 exploration 中返回 text-only synthesis。ME6 只在 repair 和 decision phases
强制 structured response contracts，explore 没有，因此 NexAU 在下一次 rollover 前把 no-call
response 当成 agent 自然结束。Middleware 正确写入 `phase=invalid` 和 `complete=false`，但
immutable pilot runner 无条件写入 `status=complete` 并 exit zero。因此 systemd success 实际是
false-success control-flow outcome。Frozen
[single-run report](2026-08-11-qfbench-a6-r11-me6-engineering-negative.md) 和 machine record
SHA-256：
`da08afdd395b747511a8a12551f72a649fe51c5c447eccb470d6fdb2c5f2aba0`。

### ME7 - 第一个 end-to-end terminal ABSTAIN mechanism PASS

- Run ID：`qfbench-a6-discovery-e-flash-high-20260811-r11-me7`
- Source gates：83 focused + 70 related tests。
- Accounting：23 wire attempts 对应 21 logical requests；21 次 HTTP 200，加两次 safe
  not-accepted HTTP 429 attempts；439,112 input + 45,030 output = 484,142 accepted tokens；
  USD `0.0338504544`。
- Mechanism state：三个 probes、两个 non-ready CONTINUE checkpoints、一个 ready ABSTAIN
  checkpoint、immutable checkpoint-bound ABSTAIN、最终 `after_agent complete=true`、
  candidate unchanged。

ME7 是第一个完整 terminal mechanism PASS。它为 exploration/mutation 增加 structured
response enforcement，使用 exact phase-narrow tool sets，在 final epoch 只暴露 ACT/ABSTAIN，
并让 runner gate 将最后一个 terminal event 绑定到 outer report。

但它的 scientific rationale 包含一个重要 false inference。model 报告 contracts 和 artifacts
不存在，而 authorized evidence tree 实际是完整的。directory-style `contracts/**` glob 在
remote tool runtime 下没有返回文件，compaction 又丢失了 prior map 中的 exact member
navigation。ME7 的 ABSTAIN 对它实际访问到的 state 是诚实的，但 source absence 是错误的。
因此，它是 terminal/control PASS，不是 causal-evidence conclusion。Frozen
[single-run report](2026-08-11-qfbench-a6-r11-me7-engineering-terminal-abstain.md) 和 machine
record SHA-256：
`1bd5fde052d05281a3109d7b6b287a108c1aebbac88b951935deeb783f0d4839`。

### ME8 - verified navigation 生效，随后被外部 HTTP 520 中断

- Run ID：`qfbench-a6-discovery-e-flash-high-20260811-r11-me8`
- Source gates：96 focused + 70 related tests。
- Accounting：九次 wire attempts；八次 HTTP 200、一次 HTTP 520；accepted 211,435 input +
  10,681 output = 222,116 tokens；known cost 至少 USD `0.0141870232`。
- Mechanism state：一个 real probe、一个 probe-bound non-ready CONTINUE checkpoint、
  零 decision/diff。

ME8 为精确的 177-member answer-free evidence inventory 加入 trusted pre-model identity 和
deterministic verified-navigation capsule。live mechanism 正常推进到 epoch 1，之后 DeepSeek
在第九次 request 返回 HTTP 520。失败 row 的 provider ID、usage、cost 均为 null；这是
provider-interrupted negative，不是 mechanism verdict。Frozen
[single-run report](2026-08-11-qfbench-a6-r11-me8-provider-negative.md) 和 machine record
SHA-256：
`1eef2824581f3fe26c4d64ee814977e90d3933447daa7b5dcdaea76e2bff61e7`。

### ME8B - navigation 通过，compact state 超出上限 407 bytes

- Run ID：`qfbench-a6-discovery-e-flash-high-20260811-r11-me8b`
- Mechanism bytes：使用 fresh identity，与 ME8 byte-identical。
- Accounting：15/15 HTTP 200；570,103 input + 45,433 output = 615,536 tokens；
  USD `0.0388147256`。
- Mechanism state：一个 schema-1 probe、一个 schema-2
  public-clause/artifact/trace probe、一个 non-ready checkpoint、零 decision/diff。

Call 15 之前，compact state 已占用 65,492/65,536 bytes。拒绝 call 15 的 malformed CONTINUE
后加入 exact error 和 validation state，需要 65,943 bytes，比 cap 多 407。NexAU 吞掉下一次
`before_model` exception 并尝试再次进入 call；wrap guard 在 provider I/O 前拦截 attempted
call 16。ME8B 证明了 complete run 下的 verified navigation，同时暴露 deterministic
compact/pre-wire boundary。Frozen
[single-run report](2026-08-11-qfbench-a6-r11-me8b-compact-overflow-negative.md) 和 machine
record SHA-256：
`33f6959e6f59d229f76d2e85acc2b75644241e4fb51c9a39c7d516657e392b75`。

### ME9 - compact repair live PASS，但 uppercase hypothesis IDs 无法进入 decision

- Run ID：`qfbench-a6-discovery-e-flash-high-20260811-r11-me9`
- Source gates：106 focused + 70 related tests。
- Accounting：14/14 HTTP 200；341,345 input + 31,096 output = 372,441 tokens；
  USD `0.0315401464`。
- Mechanism state：一个 probe、一个 reload-verified ready ABSTAIN checkpoint，
  零 persisted decision/diff。

ME9 从 model-prompt copy 的 navigation 中 recursively 移除重复 access bindings，保持 durable
evidence state 不变，将 local compact cap 提高到 131,072 bytes 并加入 worst-state tests，
同时在 provider I/O 之前由 wrap 再次验证 compact/identity state。最终 live state 为
53,594/131,072 bytes；compact 与 pre-wire repair 均通过。

随后失败的是下一个 interface boundary。Probe/checkpoint state 合法持久化了
`H1_artifact_shape_failure` 等 uppercase hypothesis IDs，但 provider-facing CONTINUE 与
decision schemas 只接受 lowercase IDs。两次 checkpoint echoes 和四次 decision attempts
都在 adapter/immutable validator 之前被 NexAU 拒绝。Frozen
[single-run report](2026-08-11-qfbench-a6-r11-me9-uppercase-id-schema-negative.md) 和 machine
record SHA-256：
`ae97eb53e8ab64c1a9cd97e8c3eedc45dc039c926ef701ce687c920fd0b095a3`。

### ME10 - case-safe immutable decision 与 calibrated ABSTAIN

- Run ID：`qfbench-a6-discovery-e-flash-high-20260811-r11-me10`
- Source gates：109 focused + 70 related tests。
- Accounting：22/22 HTTP 200，retry index 为零；1,032,205 input + 69,335 output =
  1,101,540 tokens；USD `0.0718470312`。
- Exact wire phases：16 explore + 2 checkpoint repair + 3 decision + 1 final。
- Mechanism state：exploration epochs 0/1/2，包含两次 rollovers；三个 probes；三个
  checkpoints；final checkpoint ready；immutable ABSTAIN decision；修复两个 semantic
  validation errors；candidate unchanged；diff/write/candidate-validation/evaluation 全部为零。

ME10 在 probe expectation keys、checkpoint universes、provider echoes 和 decision inputs 上
统一使用 case-capable grammar `^[A-Za-z][A-Za-z0-9_-]{0,63}$`。equality 保持
case-sensitive，不做 normalization 或 autofill。provider-shaped IDs 在 NexAU 抹掉 causal
schema error 之前完成 prevalidation；incomplete terminal state 使用独立 non-success exit，
systemd 不会对此 restart。

关键 live fix 通过：uppercase IDs 成功进入 immutable decision adapter。前两次 decision
attempts 随后因为真实 semantic reasons 被拒绝，而不是 interface faults：第一，缺少已经访问的
matched-success public evaluation/task evidence；第二，failure hypothesis 缺少 success
counterfactual 或显式 `insufficient_contrast`。第三次 decision 正确记录 ABSTAIN。观察到的早期
`/app/<file>` path mismatch 在 3/5 readable targets 与 0/2 reward-1 protections 中复现，但
其中一个 target 在 recovery 后仍失败，其他 targets 没有该 marker，matched-success evidence
不完整，也没有 schema-2 discriminator 支持 causal intervention。

final compact 为 65,288/131,072 bytes；service exit zero 且没有 restart；run-scoped
containers/networks/leases 为零；final additive sync 后 health timer 与 local watchdog/mirror 均已
unloaded。Frozen
[single-run report](2026-08-11-qfbench-a6-r11-me10-terminal-valid-abstain.md) 和 machine record
SHA-256：
`43ba405a9e9d4335ede551698b3f88c95cf079c0ee17d83dd291703ca8df0f08`。

## Causal repair chain

```text
R11 terminal/tool interoperability negative
  -> ME1 multi-epoch rollover，但 access 被错误计为 progress
  -> ME2 hard cadence，但 thinking mode 拒绝 tool_choice=required
  -> ME3 thinking-compatible auto/narrowed tools，但 tool errors 被吞掉
  -> ME4 exact parameter prevalidation/feedback，但 nested checkpoint API 失败
  -> ME5 branch-minimal derived interfaces；live lease 在 provider 前失败
  -> ME5B 真实重复 checkpoints，但没有 final ready decision
  -> ME6 final branch，但 explore text/no-tool 导致 false outer success
  -> ME7 structured exploration + truthful terminal：首次 valid ABSTAIN
  -> ME8 verified navigation，被 provider HTTP 520 中断
  -> ME8B navigation + schema-2 probe，随后 deterministic compact overflow
  -> ME9 compact/pre-wire repair 通过，但 uppercase decision echo 失败
  -> ME10 case-safe exact universe + immutable calibrated ABSTAIN
```

这不是“只要增加 call count 就会成功”的证据。每个 fresh run 都推进了一个经过 source audit 的
boundary：epoch control、structured progress、provider tool compatibility、argument validation、
checkpoint ergonomics、final commit、truthful terminal state、navigation、compact/pre-wire
safety、identifier interoperability，以及最后的 semantic decision sufficiency。

## 这一序列已经证明什么

Measured engineering conclusions：

- base Flash-0731/DeepSeek/no-fallback route 与 native long context 不是该 mechanism 的限制因素。
- Multi-epoch state、compaction、real probes、reload-verified checkpoints、bounded repair、
  immutable ABSTAIN decisions、exact accounting、rootless isolation、restart markers、additive
  evidence mirroring 和 cleanup 已经能够 end-to-end 工作。
- ME7 与 ME10 是合法的 terminal ABSTAIN mechanism PASS；ME10 更强，因为 navigation、
  compact capacity、pre-wire guards 和 case-safe IDs 都通过了 live validation。
- strict semantic validation 拒绝 unsupported ACT-like claims，并在不 unlock candidate writes
  的情况下接受 repaired ABSTAIN。
- failures 与 provider interruptions 被分开分类；missingness、null usage 或 false source
  absence 都没有被静默转成 success。

Not measured and not claimable：

- legal ACT；
- non-empty full-harness mutation；
- candidate validation 或 admission；
- candidate-panel execution 或 score；
- reward、transfer 或 harness benefit；
- R/E/EC representations 之间的 scientific difference；
- formal A6 或 statistical conclusion；
- ME10 path-mismatch phenotype 的 causal truth。

## 下一实验边界

目前的 measured sequence 不支持再做一轮 terminal-plumbing rewrite。如果未来授权 fresh
successor，应在不削弱 ABSTAIN 的前提下，直接针对剩余 ACT prerequisites：

1. 对至少两个 declared target members，实际访问 `public_evaluation` 与 task evidence。
2. 如果声明 matched-success tasks，实际访问每个 task 的 public evaluation 与 task evidence，
   并要求 protection role + reward 1；sentinels 不能静默充当 strict protections。
3. 至少执行一个 same-task schema-2 public-clause-manifested-artifact-trace discriminator；
   typed expectations 必须支持 selected hypothesis，并排除一个 competitor。
4. causal bridge 仍弱时，保留显式 `insufficient_contrast` 与 calibrated ABSTAIN。
5. 只有在 legal ACT 产生 non-empty diff，并通过 validation 与 admission 后，才启动最多四个
   relevant/risk tasks 的 candidate panel。

在这条路径实现之前，正确的 program status 是：

> **A6 bounded discovery control mechanism 已经通过 calibrated ABSTAIN 得到验证；
> 完整 ACT-to-candidate engineering feasibility 仍然开放。**

## Frozen evidence 与 companion records

- Consolidated machine record：
  `output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me10-continuation/r11-me1-me10-mechanism-validation-synthesis-20260811.json`
- ME10 machine record：
  `output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me10-continuation/r11-me10-engineering-terminal-abstain-20260811.json`
- ME10 zero-model preflight evidence：
  `output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me10-continuation/r11-me10-live-zero-model-preflight-20260811.json`
- Canonical additive project memory：`docs/PROJECT_MEMORY.md`

每个 ME run ID 都已经冻结且 non-resumable。本 synthesis 不授权新的 model call、provider
request、candidate evaluation、release、merge 或 formal claim。
