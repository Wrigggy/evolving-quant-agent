# QFBench A5 Failure-Type and Probe Discovery Report

Date: 2026-08-08  
Status: **measured engineering canary; not a paper-grade causal result**

## Executive conclusion

A5 made the Evolver's discovery behavior materially more explicit: both arms
induced a recurring failure type, generated competing causal hypotheses,
executed answer-free probes, recorded counterevidence, and ended in an explicit
`ACT` or `ABSTAIN` decision. The comparison also supports the user's concern
that producing a useful success hypothesis is difficult.

The strongest result is calibration rather than reward improvement:

- `failure_only` generated 17 hypotheses, eliminated 12 with six probes, and
  chose `ACT`. It edited `systemprompt.md` and the shell tool description under
  one declared mechanism. The candidate changed worker behavior, but the
  11-task binary reward vector was exactly unchanged and its primary
  zero-coupon prediction was falsified.
- `contrastive` generated six minimal success counterfactual records, but had
  to mark three as `insufficient_contrast`. It eliminated three of six
  hypotheses and chose `ABSTAIN`, leaving candidate writes locked. Its reason
  was that the surviving explanation depended on task-specific numeric or
  oracle conventions that authorized evidence could not identify safely.

Therefore, this single matched canary does **not** show that success hypotheses
directly discover a better intervention. It does show a plausible, useful role:
when a failure explanation cannot imply an observable success-side contrast,
that difficulty should lower confidence in `ACT` instead of being hidden by a
plausible narrative. Because there is only one stochastic Evolver sample per
arm, the contrast cannot yet be attributed causally to the contract.

## Question and frozen design

The experiment asked whether the Evolver should reason from multiple failures
into one or more recurring types, generate competing causal hypotheses, probe
them, and use minimal success counterfactuals to decide when evidence justifies
an edit.

The two arms received the same answer-free evidence and deterministic
constrained probe interface:

- `failure_only`: success counterfactuals were optional.
- `contrastive`: every causal hypothesis required a minimal observable success
  counterfactual or an explicit `insufficient_contrast` marker.

The shared train-only panel contained six repeatable baseline failures and five
stable successes/protections:

- targets: `swap-curve-bootstrap-ois`, `earnings-surprise-calculator`,
  `corporate-action-adjustment`, `zero-coupon-bootstrapping`,
  `13f-amendment-aware-crowding`, and `localvol-barrier`;
- protections: `brinson-sector-attribution`,
  `credit-spread-decomposition`, `bs-greeks-pde`,
  `merton-jump-diffusion`, and `momentum-backtest`.

One shared fresh seed run supplied both evidence bundles. The bundles contained
92 data members plus their arm-specific contract; excluding `contract.json`,
the payloads were byte-identical. The failure-only bundle digest was
`ead47cfda2a879a0b150ca67f76501fcb87c089ace7512944025cd19850afc1b`;
the contrastive digest was
`9ca2e42457c589928b78612063989b84f9cf171ff6b5d77c6da6951f4ccfc270`.

## Setup and QFBench comparability

Every valid model run used `deepseek/deepseek-v4-flash-0731`, provider
`deepseek`, fallbacks disabled. The Evolver used the route-supported `high`
reasoning setting. Pro was not used in the A5 conclusion.

The worker matched the exact formal baseline seed digest
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`:

- 200,000 context tokens;
- `max_iterations=60`;
- 32,000 maximum tokens per response;
- temperature 0.2;
- one shell tool;
- worker/verifier concurrency 12/3.

The official benchmark commit was
`024921eb507fcc0c4ffe3e0a96802724be1ae84a`. The task image-set digest was
`36be1ec027aa50fbeb6c177c4429bcc0467b096bf982193d60f949911321c51c`;
the manifest digest was
`7c32910b75408908cbc01a25b9a67670e42d408f1c8b1b1c5695ed9ac124012c`.
Public task resources and offline verifier identities remained fixed, and no
E2B resource was used.

This matches the project's measured formal worker loop. QFBench defines task
resources and evaluates real agents that can inspect, write, execute, and
iterate, but does not prescribe one universal conversation-turn cap across all
supported agents. Matching our measured seed worker is therefore the relevant
loop control; this is an inference from the official
[QFBench repository](https://github.com/QF-Bench/QuantitativeFinance-Bench),
not a claim that 60 is an upstream-mandated number.

## Run ledger and cost

| Run | Role | Result | Requests | Tokens | Cost (USD) |
| --- | --- | --- | ---: | ---: | ---: |
| `qfbench-a5-seed-evidence-20260808-r1` | shared fresh evidence | complete; target 0/6, protection 5/5 | 141 | 3,236,841 | 0.1486857624 |
| `qfbench-a5-discovery-failure-only-flash-high-20260808-r1` | failure-only Evolver | complete; `ACT` | 31 | 4,917,153 | 0.0686826504 |
| `qfbench-a5-discovery-contrastive-flash-high-20260808-r1` | first contrastive attempt | infrastructure collision; zero model requests; excluded | 0 | 0 | 0 |
| `qfbench-a5-discovery-contrastive-flash-high-20260808-r2` | valid sequential contrastive replacement | complete; `ABSTAIN` | 20 | 1,966,940 | 0.0447995072 |
| `qfbench-a5-candidate-eval-20260808-r1` | evaluate failure-only ACT candidate | complete; binary vector unchanged | 142 | 2,736,305 | 0.1331975232 |

The four valid model runs used 334 completed requests, 12,857,239 total tokens,
and **$0.3953654432** in recorded provider cost. They had no non-completed
provider requests and no missing cost or token records. The zero-request failed
attempt is preserved as infrastructure evidence and excluded from the total.

The first contrastive attempt exposed an engineering limitation: two Evolver
runs launched concurrently used the same hard-coded container name
`qea-proxy-evolver-iteration-1`. The systemd restart was stopped after one
repeat collision, and a fresh sequential run ID was used. No result or evidence
from the failed attempt was pooled into the valid arm.

## Discovery behavior

| Metric | `failure_only` | `contrastive` |
| --- | ---: | ---: |
| Terminal decision | `ACT` | `ABSTAIN` |
| Exact evidence members accessed | 41/93 | 39/93 |
| Worker trace files accessed | 10 | 6 |
| Recurring failure types | 1 | 1 |
| Failed tasks assigned to type | 2 | 5 |
| Hypotheses considered | 17 | 6 |
| Hypotheses eliminated | 12 | 3 |
| Probes | 6 | 3 |
| Success counterfactual records | 0 | 6 |
| `insufficient_contrast` records | 0 | 3 |
| Types with matched success | 0 | 1 |
| Grounded citation ratio | 1.0 | 1.0 |
| Changed components | system prompt + tool description | none; writes locked |

### Failure-only ACT

The arm induced a two-task type, `schema_completeness_gap`, from
`zero-coupon-bootstrapping` and `13f-amendment-aware-crowding`. It explicitly
excluded the other four target failures rather than forcing all failures into
one type. The selected mechanism claimed that workers completed the underlying
calculation but wrote artifacts that omitted or misordered parts of the full
public deliverable contract.

The admitted candidate coherently edited two component roles:

- `systemprompt.md`: contract-first artifact construction and final on-disk
  re-read verification;
- `tool_descriptions/run_shell_command.tool.yaml`: the same verification
  discipline at the tool-use surface.

This is broader than the earlier skills-only behavior, although it still did
not localize the intervention to implementation code, a validator, middleware,
or routing. The candidate's decisive prediction was falsifiable:

- zero-coupon should add the omitted grid keys and move from 1/6 tests toward
  at least 4/6;
- 13f schema-bound checks should improve.

### Contrastive ABSTAIN

The arm induced a five-task type described as artifacts that appear consistent
with the public schema but diverge on task-specific numeric conventions. It
matched the type against `brinson-sector-attribution` and
`momentum-backtest`, while excluding the no-trace `localvol-barrier` timeout as
a disjoint phenotype.

Its three probes eliminated schema mismatch, a structural artifact defect, and
a shared convention-substitution explanation. Of six required minimal success
counterfactual records, three could not form a usable contrast and were
explicitly marked `insufficient_contrast`. The surviving explanation depended
on unobservable, task-specific oracle conventions. The arm therefore chose
`ABSTAIN`; admission was not applicable and candidate writes remained locked.

This is the concrete answer to whether success hypotheses are easy: in this
sample they were feasible but difficult. A 50% insufficient-contrast rate is
not itself a quality score, but it exposed that the Evolver could not justify a
general intervention from the available evidence.

## Candidate outcome

The only `ACT` candidate was evaluated on the same 11-task panel.

- Seed task mean: 5/11 = 0.45454545; reported domain-weighted overall:
  0.53333333.
- Candidate task mean: 5/11 = 0.45454545; reported domain-weighted overall:
  0.53333333.
- Target reward gains: 0.
- Target reward regressions: 0.
- Protection regressions: 0.
- All six targets remained reward 0; all five protections remained reward 1.

The main zero-coupon prediction failed: the task remained at 1/6 tests, not the
predicted at least 4/6. This directly falsifies the ACT arm's strongest causal
claim for this sample.

Two secondary observations moved without changing binary reward:

- `13f-amendment-aware-crowding` moved from 41/51 to 45/51 tests. This is a
  descriptive +7.843 percentage-point pass-fraction change, not a stable gain;
  historical baseline repetitions varied on this task.
- `localvol-barrier` changed from a seed worker timeout with no trace or test
  count to normal verifier completion at 0/7. Seed used 43 requests and
  1,859,984 tokens before timeout; candidate used 27 requests and 984,065
  tokens, produced a trace and six artifacts, but still scored 0.

Panel-wide candidate cost and tokens were lower than the seed
($0.1331975232 versus $0.1486857624; 2,736,305 versus 3,236,841 tokens), but
completed request counts were 142 versus 141. This does not establish a general
efficiency improvement.

## Observable harness-capability change

The capability audit treats the seed timeout as explicit missingness rather
than inventing a trace. Ten tasks had traces on both sides and support paired
process deltas; `localvol-barrier` supplies a separate
`worker_timeout -> complete` status transition.

| Paired metric, candidate minus seed | Delta |
| --- | ---: |
| First-turn workspace inventory rate | +0.30 |
| Validation-behavior rate | +0.30 |
| Independent-crosscheck rate | +0.10 |
| Output-inspection rate | +0.00 |
| Mean turns | +1.70 |
| Mean tool calls | +2.60 |
| Tool-error rate | +0.038836 |
| Mean wall time | +40.3622 seconds |
| Mean artifact-file count | +0.00 |

Across the ten paired tasks, the candidate added 17 turns, 26 tool calls, ten
tool errors, and 403.622 seconds. Coverage improved from ten normal completions
and one timeout to 11 normal completions, and trace availability moved from
10/11 to 11/11.

The correct interpretation is mixed: the worker became more systematic and
completed the previously timed-out task, but it also became more verbose,
slower, and more error-prone across comparable tasks. More visible checking is
not automatically better harness behavior.

## What A5 establishes

Measured engineering evidence supports these limited conclusions:

1. The implemented discovery harness can make a Flash Evolver induce
   cross-task types, preserve exclusions, generate competing hypotheses,
   execute answer-free probes, and choose `ACT` or `ABSTAIN`.
2. A single failure-only Evolver can produce a coherent multi-component edit
   rather than modifying only skills. The actual changed roles were still
   prompt-level surfaces, so broad code/component discovery is not solved.
3. The failure-only arm produced a confident, evidence-rich ACT whose primary
   prediction failed. More probes and more eliminated hypotheses did not imply
   causal correctness.
4. Requiring minimal success counterfactuals exposed identifiability gaps and
   coincided with a calibrated abstention. In this sample, success-side
   reasoning was more useful as a confidence gate than as a solution generator.
5. Separately measuring worker behavior revealed a real process change that
   official binary reward alone would miss, including both improved completion
   coverage and increased process cost.

## What A5 does not establish

- No causal conclusion from the arm comparison: one Evolver sample per arm is
  confounded by model stochasticity.
- No statistically significant score result from 11 tasks.
- No held-out transfer, independent model repetition, multi-round evolution, or
  retained incumbent gain.
- No conclusion about free versus constrained probes; both arms used the same
  constrained interface.
- No conclusion that a success hypothesis must always be present. An honest
  `insufficient_contrast` marker was part of the useful behavior.
- No proof that the contrastive arm's surviving explanation was true. Its
  calibrated action was to avoid claiming that it was identifiable.

## Next mechanism change

The next discovery improvement should not ask for a richer success story. It
should strengthen semantic identifiability:

1. expose each task's exact **public** instruction/contract as a separately
   indexed, answer-free evidence object;
2. add typed probes that compare a cited public contract clause with an exact
   artifact field and with the corresponding trace phase;
3. require every ACT mechanism to cite both sides of that comparison: one
   public requirement and one worker-observable fact that contradicts or
   supports it;
4. treat missing success contrast as an uncertainty penalty, while continuing
   to allow `insufficient_contrast` and `ABSTAIN`;
5. repeat the frozen contrastive contract before trying free-form AI probes or
   multi-round evolution.

The motivation comes directly from the failed ACT. The current probe primitive
can profile files and traces, but it does not reliably adjudicate the semantic
meaning of a public task instruction. The failure-only arm inferred that
interpolated keys were required; candidate evaluation showed that adding a
generic contract checklist did not repair the task. A contract-clause-to-
artifact probe would make that claim testable before mutation.

## Evidence and source identities

Implementation verification after the audit refinements completed with
`1065 passed, 1 skipped` in the full repository test suite using the
dependency-complete NexAU environment. JSON parsing, Python compilation,
`git diff --check`, and the explicit evidence-contract firewall flags also
passed. The first sandboxed full-suite attempt could not bind loopback test
ports; all 58 model-proxy tests passed when rerun with loopback permission.

After the final additive mirror, all five exact run roots were present locally,
the A5-only Mac monitor was unloaded, and all five remote A5 health timers were
disabled. The zero-request failed service state was reset only after its files,
logs, and run record were preserved. The global QFBench `caffeinate` agent was
left running for other work. No experiment artifact or unit definition was
deleted.

Canonical local artifacts:

- seed: `results/bc-mirror/qfbench-a5-seed-evidence-20260808-r1/`;
- failure-only discovery:
  `results/bc-mirror/qfbench-a5-discovery-failure-only-flash-high-20260808-r1/`;
- failed zero-request contrastive attempt:
  `results/bc-mirror/qfbench-a5-discovery-contrastive-flash-high-20260808-r1/`;
- valid contrastive replacement:
  `results/bc-mirror/qfbench-a5-discovery-contrastive-flash-high-20260808-r2/`;
- candidate evaluation and capability audit:
  `results/bc-mirror/qfbench-a5-candidate-eval-20260808-r1/`.

The seed used remote release
`/home/julius/qea/deploy/releases/a5-521591460048`, archive digest
`521591460048986ad53e89f2e6d5a53036581b4d85c7b5a84f46f2c1431d1ea2`.
Discovery and candidate evaluation used
`/home/julius/qea/deploy/releases/a5-33472c3c61f8`, archive digest
`33472c3c61f8aa9b4a905fe11053e1a0fc25c7435f055cd8c2d8c8ae0a0c6301`.
The timeout-aware offline audit was subsequently refined locally to preserve
explicit missingness and avoid JSON `NaN`; that later audit-only source did not
change any paid run, model input, or score.
