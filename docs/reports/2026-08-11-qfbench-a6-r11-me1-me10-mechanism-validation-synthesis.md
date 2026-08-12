# QFBench A6 R11 ME1–ME10 Engineering Mechanism Validation Synthesis

> **Claim boundary.** This report begins immediately after the frozen
> [R11 three-arm engineering discovery negative](2026-08-10-qfbench-a6-r11-engineering-discovery-negative.md)
> and covers every subsequent ME1–ME10 mechanism-validation experiment,
> including provider-zero infrastructure attempts and deterministic
> source/package/preflight gates. It is an engineering synthesis, not a formal
> A6 result, statistical comparison, causal-benefit claim, or publication-grade
> benchmark conclusion.

## Outcome first

The ME sequence moved the A6 discovery Evolver from a terminal/tool-interface
failure to a real, bounded, evidence-bound terminal mechanism. ME7 produced the
first valid checkpoint-bound `ABSTAIN`; ME10 reproduced a stronger valid
`ABSTAIN` after closing navigation, compact-state, pre-wire guard, and
hypothesis-ID interoperability failures. ME10 is the strongest mechanism result:
three exploration epochs, three real probes, three reload-verified checkpoints,
bounded repair, an immutable decision, exact accounting, truthful completion,
locked candidate writes, and clean resource closure all worked in the live paid
path.

The user-defined A6 engineering success bar is nevertheless **not met**. No run
produced a legal `ACT`, a non-empty full-harness diff, candidate validation,
admission, or a separately identified candidate panel of at most four tasks.
No candidate was evaluated and no harness benefit was measured. The honest
result is:

> **Terminal mechanism PASS / calibrated ABSTAIN PASS / ACT-to-candidate
> engineering feasibility not demonstrated.**

The bottleneck has moved. It is no longer route health, context capacity,
multi-epoch rollover, checkpoint persistence, compact-state capacity, or
terminal `ABSTAIN` control flow. It is now evidence sufficiency and semantic
identifiability for a safe ACT: matched-success evidence, task-bound public
outcomes, and a same-task public-clause–manifested-artifact–trace discriminator.

## Reporting boundary and common execution contract

The prior R11 R/E/EC three-arm report is the baseline and is not double-counted
below. ME1–ME10 retained the same engineering-only boundary:

- model: `deepseek/deepseek-v4-flash-0731`;
- required provider: DeepSeek;
- fallback: disabled;
- reasoning effort: high;
- immutable formal R10 source release unchanged;
- same-ID zero-model preflight before every launch;
- candidate evaluation disabled during discovery;
- candidate panel permitted only after legal ACT, non-empty diff, successful
  validation, and admission;
- answer-free public evidence only; gold, official tests/solutions, raw private
  verdicts, trusted criteria, credentials, and held-out evaluator material
  remained outside the Evolver surface.

Each final ME identity passed `preflight_complete` with
`model_request_count=0`, exact runtime/evidence/scheduler identities, inactive
service/timer, zero scoped containers/networks, and no model-boundary/request/
audit/proposal/candidate artifacts before its paid attempt. Deterministic test
counts below are versioned gates, not additive independent observations; the
related suite and many focused regressions repeat across generations.

## Cumulative provider accounting

| Item | ME1–ME10 total |
|---|---:|
| Wire attempts | **174** |
| Logical requests | **172** |
| HTTP-200 accepted responses | **170** |
| HTTP 400 | **1** — ME2 |
| Safe not-accepted HTTP 429 | **2** — ME7 |
| HTTP 520 | **1** — ME8 |
| Known accepted input tokens | **5,407,027** |
| Known accepted output tokens | **391,080** |
| Known accepted total tokens | **5,798,107** |
| Known provider cost | **USD `0.3520366696`** |

The token and cost totals are lower bounds, not billing upper bounds. ME2's
HTTP-400 row and ME8's HTTP-520 row have null provider request ID, usage, and
cost. Those fields are **unknown**, not zero. Excluding ME2 alone leaves 167
wire attempts, 165 logical requests, 164 HTTP-200 responses, 5,626,876 known
accepted tokens, and USD `0.3448526536`, but that subtotal remains a lower bound
because it still contains ME8's unknown HTTP-520 row. The fully reconciled
accepted-usage subset excluding both ME2 and ME8 contains 158 wire attempts,
156 logical requests, 156 HTTP-200 responses, two safe not-accepted ME7 HTTP
429 attempts, 5,404,760 accepted tokens, and USD `0.3306656304`.

ME5 is a separately proven provider-zero attempt: it failed before sandbox and
proxy construction, generated no request/usage/cost artifact, and incurred no
model cost.

## Experiment-by-experiment record

### ME1 — multi-epoch rollover without structured progress

- Run ID: `qfbench-a6-discovery-e-flash-high-20260810-r11-me1`
- Source gates: 23 focused + 65 related tests.
- Accounting: 24/24 HTTP 200; 874,396 input + 28,697 output =
  903,093 tokens; USD `0.0341954704`.
- Mechanism state: three exploration epochs, 24 exploration calls, zero probe,
  zero checkpoint, zero decision, zero diff.

ME1 proved that the 1M-advertised Flash route, live 510,125-token canary,
multi-epoch rollover, compact prompts, one-shot paid-boundary marker, rootless
isolation, accounting, watchdog, additive mirror, and exact cleanup all worked.
It did not prove discovery progress. Ordinary access-log growth reset the
generic progress fingerprint, so the model consumed all 24 exploration calls
without creating a probe or checkpoint.

The failure-time 60 access records and 24 distinct paths were live-observed;
the host failure path did not durably copy that runtime log. The immutable
evidence tree's empty `access_log.jsonl` must not be confused with the runtime
observation. Frozen machine record SHA-256:
`ab90fb3e66a52f130adcf120a70b6a57f815d3c6e97c70dd2316592c3fa2bae9`.

### ME2 — hard cadence met a provider tool-choice incompatibility

- Run ID: `qfbench-a6-discovery-e-flash-high-20260810-r11-me2`
- Source gates: 33 focused + 70 related tests.
- Accounting: seven wire/logical requests; six HTTP 200 and one HTTP 400;
  accepted 166,962 input + 4,269 output = 171,231 tokens; known cost at
  least USD `0.007184016`.
- Mechanism state: six exploration calls, one checkpoint-repair request, zero
  probe/checkpoint/decision.

ME2 correctly stopped treating ordinary reads as structured progress and
reached the bounded repair surface. The first repair request used
`tool_choice=required`; DeepSeek thinking mode rejected it with
`Thinking mode does not support this tool_choice`. This was a provider-interface
negative, not a verdict on the checkpoint mechanism. Frozen machine record
SHA-256: `d7108f2877b0de79a9c3afb9c5ebbba0442d9114e4776b24fc16700487a3d08a`.

### ME3 — thinking-compatible repair produced a probe but swallowed checkpoint errors

- Run ID: `qfbench-a6-discovery-e-flash-high-20260810-r11-me3`
- Source gates: 39 focused + 70 related tests.
- Accounting: 10/10 HTTP 200; 239,492 input + 29,856 output = 269,348
  tokens; USD `0.017214512`.
- Mechanism state: one real schema-1 probe, zero checkpoint, zero decision.

ME3 switched to provider-compatible `tool_choice=auto`, restricted the repair
tool surface, scrubbed invalid response forms, and force-continued bounded
repairs. It persisted the first real probe. Calls 8–10 then appeared to be valid
`checkpoint_memory` calls at the middleware boundary but appended no checkpoint
and produced no durable validation error. Pinned NexAU validates schema outside
the tool implementation but converts implementation exceptions into ordinary
error results; ME3 validated tool names, not checkpoint parameters or returned
execution status.

The exact rejected arguments were not retained, so the diagnosis is based on
the frozen terminal/command path and successor replay, not a byte-exact request
reconstruction. Terminal SHA-256:
`8edd2a1d9fa120efc4c55fc9c9f0ea838809d73d23d144bdb9f62be57643f6f4`;
proxy audit SHA-256:
`09b97a6de02e1b866192822381bd421d2f2c53ca143d8f69ddb50b604b75f328`.

### ME4 — exact checkpoint feedback worked, but the monolithic interface remained unusable

- Run ID: `qfbench-a6-discovery-e-flash-high-20260810-r11-me4`
- Source gates: 49 focused + 70 related tests.
- Accounting: 11/11 HTTP 200; 212,705 input + 29,243 output = 241,948
  tokens; USD `0.01689282`.
- Mechanism state: one real schema-1 probe, zero checkpoint, four durable
  checkpoint errors, zero decision.

ME4 added read-only checkpoint payload normalization before `Tool.execute`,
scrub-before-persist behavior, exact current error in compact state, and bounded
post-tool execution status. Those controls worked: four distinct errors were
durably visible. The model nevertheless cited prose as an evidence path,
referenced undeclared state, and attached forbidden intervention fields to
CONTINUE/ABSTAIN payloads. The large nested checkpoint interface exhausted all
repairs without an append.

Raw rejected arguments were not retained; the four error classes are exact,
but successor tests are class replays rather than byte-exact request replays.
Terminal SHA-256:
`5de34860526d63364872eb35b5b2d602246a9d6d090c6d46cb4a3f18f4c36483`;
proxy audit SHA-256:
`eb4761d87c914435f53b978fa052cf8ac39534ae1d6d54bc2207be2e96922810`.

### ME5 — branch-minimal mechanism passed locally but the live attempt was provider-zero

- Run ID: `qfbench-a6-discovery-e-flash-high-20260811-r11-me5`
- Source gates: 51 focused + 70 related tests, including a real NexAU
  checkpoint→decision→non-empty edit→validation/admission path and a real
  ABSTAIN write-lock path.
- Accounting: zero wire requests, zero tokens, zero model cost.

ME5 replaced the monolithic checkpoint API with branch-separated derived-state
tools and a small decision adapter. The live launch did not exercise it. The
resource lease failed before sandbox/provider construction because measured
`load_1m=82.001953125` exceeded the unchanged `56.0` threshold. A scheduled
restart was blocked by the durable model-boundary marker. This validates
pre-provider lease failure, marker containment, and cleanup only; it is not a
mechanism outcome. Attribution to competing host jobs was an operator
observation and is unnecessary for the exact `ResourceLeaseTimeout` conclusion.
Incident record SHA-256:
`190df5f657cb63dc7b054c378c81ffc96366aa1d1b5c1ab066f6eec3cf8b246e`.

### ME5B — first repeated probe/checkpoint persistence, but no terminal decision

- Run ID: `qfbench-a6-discovery-e-flash-high-20260811-r11-me5b`
- Mechanism bytes: identical to ME5 under a fresh identity.
- Accounting: 25/25 HTTP 200; 993,640 input + 70,234 output =
  1,063,874 tokens; USD `0.064557136`.
- Mechanism state: three probes, three probe-bound CONTINUE checkpoints; first
  two advanced epochs, final checkpoint non-ready; zero decision/diff/
  validation/admission.

ME5B demonstrated real checkpoint persistence and exact bounded repair: a
malformed `next_hypothesis_ids` subset was rejected, surfaced, and repaired.
The final checkpoint left every hypothesis open. The final-epoch gate then
raised, NexAU attempted another call entry, and the one-shot guard blocked it
before provider I/O. ME5B was a substantial mechanism advance but remained an
engineering negative. Frozen [single-run report](2026-08-11-qfbench-a6-r11-me5b-engineering-negative.md)
and machine record SHA-256:
`c1ef8407f8f86be43b5949b1249d0a53a2b6b52bebdf14d01a0d1df0df38f769`.

### ME6 — explore text/no-tool exposed a false-success terminal path

- Run ID: `qfbench-a6-discovery-e-flash-high-20260811-r11-me6`
- Source gates: 66 focused + 70 related tests.
- Accounting: 14/14 HTTP 200; 325,632 input + 27,206 output = 352,838
  tokens; USD `0.0217533344`.
- Mechanism state: two real probes, two non-ready CONTINUE checkpoints, zero
  decision/diff.

Call 14 returned a text-only synthesis during ordinary exploration. ME6 enforced
structured response contracts in repair and decision phases, not explore, so
NexAU treated the no-call response as a natural agent finish before the next
rollover. Middleware correctly wrote `phase=invalid` and `complete=false`, but
the immutable pilot runner unconditionally wrote `status=complete` and exited
zero. The systemd success was therefore a false-success control-flow outcome.
Frozen [single-run report](2026-08-11-qfbench-a6-r11-me6-engineering-negative.md)
and machine record SHA-256:
`da08afdd395b747511a8a12551f72a649fe51c5c447eccb470d6fdb2c5f2aba0`.

### ME7 — first end-to-end terminal ABSTAIN mechanism pass

- Run ID: `qfbench-a6-discovery-e-flash-high-20260811-r11-me7`
- Source gates: 83 focused + 70 related tests.
- Accounting: 23 wire attempts for 21 logical requests; 21 HTTP 200 plus two
  safe not-accepted HTTP 429 attempts; 439,112 input + 45,030 output =
  484,142 accepted tokens; USD `0.0338504544`.
- Mechanism state: three probes, two non-ready CONTINUE checkpoints, one ready
  ABSTAIN checkpoint, immutable checkpoint-bound ABSTAIN, final
  `after_agent complete=true`, unchanged candidate.

ME7 was the first complete terminal mechanism pass. It added structured
response enforcement to exploration/mutation, exact phase-narrow tool sets,
final-epoch ACT/ABSTAIN-only surfaces, and a runner gate binding the last
terminal event to the outer report.

Its scientific rationale contained an important false inference. The model
reported contracts and artifacts absent, but the authorized evidence tree was
complete. A directory-style `contracts/**` glob returned no files under the
remote tool runtime, and compaction lost exact member navigation from the prior
map. ME7's ABSTAIN was honest for its accessed state, but source absence was
false. It is a terminal/control pass, not a causal-evidence conclusion. Frozen
[single-run report](2026-08-11-qfbench-a6-r11-me7-engineering-terminal-abstain.md)
and machine record SHA-256:
`1bd5fde052d05281a3109d7b6b287a108c1aebbac88b951935deeb783f0d4839`.

### ME8 — verified navigation worked until an external HTTP 520 interruption

- Run ID: `qfbench-a6-discovery-e-flash-high-20260811-r11-me8`
- Source gates: 96 focused + 70 related tests.
- Accounting: nine wire attempts; eight HTTP 200 and one HTTP 520; accepted
  211,435 input + 10,681 output = 222,116 tokens; known cost at least USD
  `0.0141870232`.
- Mechanism state: one real probe, one probe-bound non-ready CONTINUE
  checkpoint, zero decision/diff.

ME8 introduced a trusted pre-model identity for the exact 177-member answer-free
evidence inventory and a deterministic verified-navigation capsule. The live
mechanism advanced normally into epoch 1 before DeepSeek returned HTTP 520 on
the ninth request. The failed row has null provider ID, usage, and cost; this is
a provider-interrupted negative, not a mechanism verdict. Frozen
[single-run report](2026-08-11-qfbench-a6-r11-me8-provider-negative.md)
and machine record SHA-256:
`1eef2824581f3fe26c4d64ee814977e90d3933447daa7b5dcdaea76e2bff61e7`.

### ME8B — navigation passed, then compact state overflowed by 407 bytes

- Run ID: `qfbench-a6-discovery-e-flash-high-20260811-r11-me8b`
- Mechanism bytes: identical to ME8 under a fresh identity.
- Accounting: 15/15 HTTP 200; 570,103 input + 45,433 output = 615,536
  tokens; USD `0.0388147256`.
- Mechanism state: one schema-1 probe, one schema-2 public-clause/artifact/trace
  probe, one non-ready checkpoint, zero decision/diff.

Immediately before call 15, compact state occupied 65,492/65,536 bytes.
Rejecting call 15's malformed CONTINUE added exact error and validation state,
requiring 65,943 bytes—407 above the cap. NexAU swallowed the next
`before_model` exception and attempted another call entry; the wrap guard
blocked attempted call 16 before provider I/O. ME8B proved verified navigation
under a complete run and exposed a deterministic compact/pre-wire boundary.
Frozen [single-run report](2026-08-11-qfbench-a6-r11-me8b-compact-overflow-negative.md)
and machine record SHA-256:
`33f6959e6f59d229f76d2e85acc2b75644241e4fb51c9a39c7d516657e392b75`.

### ME9 — compact repair passed live, then uppercase hypothesis IDs could not reach decision

- Run ID: `qfbench-a6-discovery-e-flash-high-20260811-r11-me9`
- Source gates: 106 focused + 70 related tests.
- Accounting: 14/14 HTTP 200; 341,345 input + 31,096 output = 372,441
  tokens; USD `0.0315401464`.
- Mechanism state: one probe, one reload-verified ready ABSTAIN checkpoint,
  zero persisted decision/diff.

ME9 recursively removed duplicated access bindings from the model-prompt copy
of navigation, retained durable evidence state unchanged, raised the local
compact cap to 131,072 bytes with worst-state tests, and revalidated compact/
identity state inside the wrap before provider I/O. The final live state was
53,594/131,072 bytes; the compact and pre-wire repair passed.

The next interface boundary failed. Probe/checkpoint state legally persisted
uppercase hypothesis IDs such as `H1_artifact_shape_failure`, but provider-facing
CONTINUE and decision schemas accepted lowercase IDs only. Two checkpoint echoes
and four decision attempts were rejected by NexAU before the adapter/immutable
validator. Frozen [single-run report](2026-08-11-qfbench-a6-r11-me9-uppercase-id-schema-negative.md)
and machine record SHA-256:
`ae97eb53e8ab64c1a9cd97e8c3eedc45dc039c926ef701ce687c920fd0b095a3`.

### ME10 — case-safe immutable decision and calibrated ABSTAIN

- Run ID: `qfbench-a6-discovery-e-flash-high-20260811-r11-me10`
- Source gates: 109 focused + 70 related tests.
- Accounting: 22/22 HTTP 200, retry index zero; 1,032,205 input + 69,335
  output = 1,101,540 tokens; USD `0.0718470312`.
- Exact wire phases: 16 explore + 2 checkpoint repair + 3 decision + 1 final.
- Mechanism state: exploration epochs 0/1/2 with two rollovers; three probes;
  three checkpoints; final checkpoint ready; immutable ABSTAIN decision; two
  semantic validation errors repaired; candidate unchanged; diff/write/
  candidate-validation/evaluation all zero.

ME10 applied one case-capable grammar,
`^[A-Za-z][A-Za-z0-9_-]{0,63}$`, across probe expectation keys, checkpoint
universes, provider echoes, and decision inputs. Equality remained case-sensitive
with no normalization or autofill. Provider-shaped IDs were prevalidated before
NexAU could erase the causal schema error, and incomplete terminal state used a
distinct non-success exit that systemd would not restart.

The key live fix passed: uppercase IDs entered the immutable decision adapter.
The first two decision attempts were then rejected for genuine semantic reasons,
not interface faults: missing accessed matched-success public evaluation/task
evidence, and a failure hypothesis lacking a success counterfactual or explicit
`insufficient_contrast`. The third decision correctly recorded ABSTAIN. The
observed early `/app/<file>` path mismatch recurred in 3/5 readable targets and
0/2 reward-1 protections, but recovery still preceded failure for one target,
other targets lacked the marker, matched-success evidence was incomplete, and
no schema-2 discriminator supported a causal intervention.

The final compact was 65,288/131,072 bytes; service exited zero without restart;
run-scoped containers/networks/leases were zero; the health timer and local
watchdog/mirror were unloaded after final additive sync. Frozen
[single-run report](2026-08-11-qfbench-a6-r11-me10-terminal-valid-abstain.md)
and machine record SHA-256:
`43ba405a9e9d4335ede551698b3f88c95cf079c0ee17d83dd291703ca8df0f08`.

## Causal repair chain

```text
R11 terminal/tool interoperability negative
  -> ME1 multi-epoch rollover, but access falsely counted as progress
  -> ME2 hard cadence, but thinking mode rejected tool_choice=required
  -> ME3 thinking-compatible auto/narrowed tools, but tool errors were swallowed
  -> ME4 exact parameter prevalidation/feedback, but nested checkpoint API failed
  -> ME5 branch-minimal derived interfaces; live lease failed before provider
  -> ME5B real repeated checkpoints, but no final ready decision
  -> ME6 final branch, but explore text/no-tool caused false outer success
  -> ME7 structured exploration + truthful terminal: first valid ABSTAIN
  -> ME8 verified navigation, interrupted by provider HTTP 520
  -> ME8B navigation + schema-2 probe, then deterministic compact overflow
  -> ME9 compact/pre-wire repair passed, uppercase decision echo failed
  -> ME10 case-safe exact universe + immutable calibrated ABSTAIN
```

This is not evidence that success arose by merely increasing call count. Each
fresh run moved a source-audited boundary: epoch control, structured progress,
provider tool compatibility, argument validation, checkpoint ergonomics, final
commit, truthful terminal state, navigation, compact/pre-wire safety, identifier
interoperability, and finally semantic decision sufficiency.

## What the sequence establishes

Measured engineering conclusions:

- The base Flash-0731/DeepSeek/no-fallback route and native long context are not
  the limiting factors for this mechanism.
- Multi-epoch state, compaction, real probes, reload-verified checkpoints,
  bounded repair, immutable ABSTAIN decisions, exact accounting, rootless
  isolation, restart markers, additive evidence mirroring, and cleanup all work
  end-to-end.
- ME7 and ME10 are valid terminal ABSTAIN mechanism passes; ME10 is stronger
  because navigation, compact capacity, pre-wire guards, and case-safe IDs are
  all live-validated.
- Strict semantic validation rejected unsupported ACT-like claims and accepted
  a repaired ABSTAIN without unlocking candidate writes.
- Failures and provider interruptions remained separately classified; no
  missingness, null usage, or false source absence was silently converted into
  success.

Not measured and not claimable:

- legal ACT;
- non-empty full-harness mutation;
- candidate validation or admission;
- candidate-panel execution or score;
- reward, transfer, or harness benefit;
- a scientific difference among R/E/EC representations;
- a formal A6 or statistical conclusion;
- causal truth for the ME10 path-mismatch phenotype.

## Next experimental boundary

Another terminal-plumbing rewrite is not currently justified by the measured
sequence. A future fresh successor, if authorized, should target the remaining
ACT prerequisites without weakening ABSTAIN:

1. Access `public_evaluation` and task evidence for at least two declared target
   members.
2. If matched-success tasks are declared, access each task's public evaluation
   and task evidence and require protection role plus reward 1; sentinels cannot
   silently serve as strict protections.
3. Execute at least one same-task schema-2 public-clause–manifested-artifact–
   trace discriminator whose typed expectations support the selected hypothesis
   and eliminate a competitor.
4. Preserve explicit `insufficient_contrast` and calibrated ABSTAIN when the
   causal bridge remains weak.
5. Start a candidate panel of at most four relevant/risk tasks only after a
   legal ACT creates a non-empty diff that passes validation and admission.

Until that path exists, the correct program status is:

> **A6 bounded discovery control mechanism validated through calibrated
> ABSTAIN; full ACT-to-candidate engineering feasibility remains open.**

## Frozen evidence and companion records

- Consolidated machine record:
  `output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me10-continuation/r11-me1-me10-mechanism-validation-synthesis-20260811.json`
- ME10 machine record:
  `output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me10-continuation/r11-me10-engineering-terminal-abstain-20260811.json`
- ME10 zero-model preflight evidence:
  `output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me10-continuation/r11-me10-live-zero-model-preflight-20260811.json`
- Canonical additive project memory: `docs/PROJECT_MEMORY.md`

Every ME run ID is frozen and non-resumable. This synthesis authorizes no new
model call, provider request, candidate evaluation, release, merge, or formal
claim.
