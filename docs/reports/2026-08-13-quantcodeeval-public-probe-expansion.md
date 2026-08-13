# QuantCodeEval public behavior-probe expansion

Date: 2026-08-13

Status: measured engineering canary; investigator-authored mechanism; not a
formal benchmark estimate

## Outcome

The four-task public-data expansion is operational and produced a useful
mechanism-localization result. An investigator-authored worker added two
components to the ordinary shell worker:

- a `quant-contract-arbitration` skill for distinguishing competing finance
  definitions; and
- a `probe_public_behavior` tool that imports the draft strategy in a fresh
  temporary directory and executes independently calculated assertions using
  only public task inputs.

The final fresh four-task run scored `T01=0, T12=0, T18=0, T19=1`, for a task
mean of `0.25`. This matches the binary vector obtained by transferring the
autonomous r8 static-audit candidate, but it does not imply the two mechanisms
are equivalent. The behavior probe was activated on T01, T12, and T19; T18
exhausted one long generation path before writing a candidate. A separate T18
retry wrote a candidate, activated the probe, and still reproduced H0's
`16/18` property result.

The strongest result is therefore not a universal score gain. It is a
localization result:

1. Public executable probes can change generated quantitative definitions and
   can produce a fully correct candidate on T12 in one sample.
2. The same T12 mechanism is not stable: a fresh panel sample passed `12/16`,
   not `16/16`.
3. T01 and T18 did not improve even when the mechanism was available or fully
   activated.
4. T19 passed under both the autonomous r8 static audit and the manual public
   behavior probe, making it the current positive transfer task but not yet
   identifying which component is necessary.

## Experimental sequence

All worker calls used `deepseek/deepseek-v4-flash-0731` through DeepSeek with
no fallback. The rootless worker, verifier, and model-proxy setup was unchanged
within these comparisons. H0 was sampled before the candidate mechanisms; its
saved artifacts were replayed through the corrected verifier without model
calls.

| Stage | T01 | T12 | T18 | T19 | Requests | Tokens | Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| H0 replay | 2/17 | 14/16 | 16/18 | 16/18 | 121 sampling requests | 2,890,386 | $0.1000396712 |
| autonomous r8 transfer | 2/17 | 8/16 | 16/18 | 18/18 | 62 | 1,233,285 | $0.0569713984 |
| manual probe v1, T12 only | - | 7/16 | - | - | 13 | 203,616 | $0.0105279832 |
| manual probe v2, T12 only | - | 16/16 | - | - | 22 | 460,404 | $0.0174447056 |
| manual probe v2, fresh panel | 2/17 | 12/16 | no artifact | 18/18 | 68 | 1,776,058 | $0.0833991200 |
| manual probe v2, T18 retry | - | - | 16/18 | - | 24 | 921,144 | $0.0352327584 |

The fractions are property passes, not partial official rewards. QuantCodeEval
uses an all-properties gate, so only the two `18/18` T19 rows and the
single-task `16/16` T12 row have official reward 1. The H0 sampling count
includes the original expansion run plus the T19 retry; verifier replay used
zero additional model requests.

The four manual-mechanism runs together used 127 requests, 3,361,222 tokens,
and `$0.1466045672`. They are distinct diagnostic samples and must not be
pooled as repeated formal benchmark trials.

## What activated

The final fresh panel retained complete traces:

| Task | Probe trace mentions | Skill trace mentions | Worker outcome |
| --- | ---: | ---: | --- |
| T01 | 9 | 5 | candidate written; 2/17 |
| T12 | 2 | 5 | candidate written; 12/16 |
| T18 | 0 | 0 | no candidate after long responses |
| T19 | 9 | 5 | candidate written; 18/18 |

The T18 retry recorded 10 probe mentions and 5 skill mentions, wrote a valid
candidate, and passed 16/18. This separates two effects: missing-artifact
completion is sampling-sensitive, while the unchanged T18 property result is
not explained by lack of component activation in the retry.

T12 also separates availability from reliability. The successful v2 sample
implemented an arithmetic prior-year average; the fresh panel sample selected
a geometric prior-period return and passed only 12/16. The skill exposed the
competing definitions and the tool ran, but the worker did not consistently
bind its asserted public basis to the implementation it finally submitted.
The next mechanism needs component state that preserves this decision and
checks candidate/probe consistency, not another longer prose reminder.

## Comparison with the autonomous r8 component

r8 was genuinely autonomous: the Evolver used accumulated answer-free history,
selected a static unit/structure audit, changed agent configuration, prompt,
tool description, and executable tool code, then passed component smoke and
candidate admission. Its expansion transfer improved T19 to 18/18 but regressed
T12 from 14/16 to 8/16.

The public-probe worker was investigator-authored to test a different causal
hypothesis after r9 falsified continued static-audit growth. It also passed
T19, had no effect on T01, reproduced H0 on the T18 retry, and showed a
high-variance T12 benefit. This makes the project-specific search problem more
concrete: components have conditional value, and successful search must learn
activation scope and retained decision state rather than globally accumulating
rules.

## Next autonomous experiment

Use the manual worker only as a diagnostic search parent, not as an official
incumbent. Give the Evolver the complete answer-free four-task contrast:

- T19: activated positive example;
- T01: activated but unchanged negative example;
- T12: one full pass followed by a 12/16 fresh sample, showing definition-state
  instability;
- T18: missing artifact in the panel, then activated 16/18 retry, separating
  completion from quant correctness.

Keep the full harness mutation surface open. The Evolver must compare at least
two mechanisms and choose the component itself. Plausible component locations
include conditional `routing`, persistent decision `memory`, executable
candidate/probe consistency validation, and early-draft completion state, but
these are investigator hypotheses rather than instructions to implement a
specific finalizer. Evaluate a candidate first with its own local component
smoke, then on this four-task panel. Preserve every rejected or scored attempt
in the existing history so subsequent rounds can read exact prior changes and
outcomes. Search remains variable-length and should stop on no new information,
calibrated abstention, a working mechanism, or budget—not an arbitrary five
rounds.

## Evidence and validation

The complete generated evidence is mirrored additively under:

- `results/bc-mirror/qce-expansion-h0-replay-fixed-20260813-r4/`
- `results/bc-mirror/qce-expansion-r8-candidate-20260813-r1/`
- `results/bc-mirror/qce-manual-public-probe-t12-20260813-r1/`
- `results/bc-mirror/qce-manual-public-probe-t12-20260813-r2/`
- `results/bc-mirror/qce-manual-public-probe-expansion-20260813-r1/`
- `results/bc-mirror/qce-manual-public-probe-t18-retry1-20260813/`

The final two services exited successfully. After each run, the remote host
reported zero experiment containers and zero experiment networks. The focused
adapter, candidate, replay, and retained-output suite passed `16 passed, 21
deselected` after the run.

## Autonomous contract-audit round

Status: measured one-round autonomous engineering search and four-task
candidate evaluation; no new solved task

Run identities:

- activation: `qce-public-probe-autonomous-activation-20260813-r1`
- candidate panel: `qce-public-probe-autonomous-candidate-20260813-r1`

The Evolver read 31 of 43 evidence members exactly, including all four task
instructions, the current answer-free outcomes, the independent T12 16/16
comparison, and traces or process facts from every task. It compared three
hypotheses and selected a missing real-data contract-audit mechanism. The
candidate changed three files across the full harness rather than making a
prompt-only mutation:

- `tools/public_behavior_probe.py`: added an executable `contract_checks`
  interface that calls required functions on public data and checks declared
  columns, index kind, row count, and value domain;
- `tool_descriptions/probe_public_behavior.tool.yaml`: exposed that interface
  to the worker; and
- `systemprompt.md`: required workers to derive and run the checks before
  submission.

The final tool import smoke and independent harness admission passed. The
activation used 45 model requests, 2,662,056 tokens, and `$0.0471596608`.
This establishes a real Evolver-generated executable component change, not a
conceptual proposal or another prompt-only search.

The candidate was then sampled once on the same four-task panel:

| Task | diagnostic parent | autonomous candidate | property change | official reward |
| --- | ---: | ---: | ---: | ---: |
| T01 | 2/17 | 3/17 | +1 | 0 |
| T12 | 12/16 | 15/16 | +3 | 0 |
| T18 | 16/18 | 16/18 | 0 | 0 |
| T19 | 18/18 | 18/18 | 0 | 1 |

The binary vector remained `0,0,0,1` and task mean remained `0.25`. The
candidate panel used 136 requests, 6,250,275 tokens, and `$0.1638542808`.
All requests completed on the pinned DeepSeek Flash route without fallback;
the service exited successfully and left zero experiment containers and zero
experiment networks.

This is a useful negative localization result. The new mechanism improved
several public property outcomes and preserved the positive T19 protection
task, but it did not close any new task. On T01 the worker reported every
self-declared contract check and independent probe as passing, while the
official answer-free result was only Type-A `3/7` and Type-B `0/10`. Therefore
the missing step is not merely executing more checks on real data: a worker
can construct an internally consistent check for an incorrect interpretation
of the public instruction. T18 also spent a long generate-audit-repair loop
and remained 16/18. The stronger component increased worker effort without a
corresponding solved-task gain.

The next autonomous round should start again from the diagnostic parent, not
promote or cumulatively layer this candidate. It should receive the exact
candidate diff, component tests, answer-free per-task outcomes, and rollback
reason as searchable history. Its search question is now narrower: how to
translate a public finance instruction into an independently checkable
semantic contract, or otherwise discriminate between competing definitions,
instead of trusting the worker's own declared contract. The Evolver still
chooses the component and must compare this explanation with at least one
alternative; the investigator does not prescribe a finalizer or fixed routing
implementation.

The complete new evidence is mirrored additively under:

- `results/bc-mirror/qce-public-probe-autonomous-activation-20260813-r1/`
- `results/bc-mirror/qce-public-probe-autonomous-candidate-20260813-r1/`

## Autonomous parameter-identity round

Status: measured autonomous search with accumulated candidate history; one
sampling-sensitive solved task, so the candidate is not promoted

Run identities:

- failed activation attempts:
  `qce-public-probe-autonomous-activation-20260813-r2` and
  `qce-public-probe-autonomous-activation-20260813-r2-retry1`;
- successful activation:
  `qce-public-probe-autonomous-activation-20260813-r2-toolfirst`;
- four-task candidate panel:
  `qce-public-probe-autonomous-candidate-20260813-r2-toolfirst`; and
- T12 repeat:
  `qce-public-probe-autonomous-candidate-20260813-r2-t12-repeat1`.

The first two activation attempts ended before a candidate because a long
model response returned no usable content. They were provider/NexAU response
failures rather than Evolver abstentions or benchmark outcomes. Their completed
proxy records contain 17 requests and `$0.0369052712`, then 14 requests and
`$0.0190436848`. A minimal Evolver control change required the first response
to inspect the candidate and map the evidence, followed by incremental tool
use instead of a full silent investigation. The tool-first retry then completed
normally. This repair changes search observability and response pacing; it does
not alter benchmark answers.

The successful Evolver read the exact prior scored candidate entry and diff,
all four current answer-free outcomes, the independent T12 comparison, task
instructions, AST/process facts, and relevant public paper text. It compared
three explanations: incorrect library parameterization after reading the
paper constants, a worker/checker environment mismatch, and failure to read
the quantitative conventions. Same-harness T19 and historical T12 successes
rejected the environment explanation; the T01 AST already containing 261, 60,
0.4, and 12 rejected the missing-reading explanation. The selected cause was a
parameter-identity gap: constants can look correct while `com`, `span`,
`halflife`, annualization, window endpoints, or return alignment remain wrong.

The candidate modified the `quant-contract-arbitration` skill and the system
prompt. It requires workers to write the paper identity before selecting a
library argument and validate the mapping on a small independently computed
fixture. The skill was explicitly loaded twice in component smoke and the
full-harness admission passed. This was an Evolver-selected skill intervention,
but its file-level mutation remained guidance-only rather than executable
Python code. Activation used 39 requests, 2,294,526 tokens, and
`$0.0346782856`.

The fresh four-task panel produced:

| Task | diagnostic parent | prior candidate | parameter-identity candidate | official reward |
| --- | ---: | ---: | ---: | ---: |
| T01 | 2/17 | 3/17 | 5/17 | 0 |
| T12 | 12/16 | 15/16 | 16/16 | 1 |
| T18 | 16/18 | 16/18 | 16/18 | 0 |
| T19 | 18/18 | 18/18 | 18/18 | 1 |

The binary vector was `0,1,0,1`, raising the single-panel task mean from
`0.25` to `0.50` while preserving T19. T01's Type-A improved to `4/7` and its
previously untouched Type-B improved to `1/10`; T18 remained exactly
Type-A `2/4`, Type-B `14/14`. The panel used 104 completed requests,
3,266,600 tokens, and `$0.1133131552`, with no fallback or infrastructure
failure.

This initially looked like a working local mechanism, but T12 had previously
produced an isolated H0 `16/16`, so one fresh full pass was not enough for
promotion. A direct T12 candidate repeat used the same candidate and runtime
without resampling H0. It passed only `8/16` (Type-A `4/8`, Type-B `4/8`) and
returned reward 0. The repeat used 16 completed requests, 320,141 tokens, and
`$0.0170303784`. An earlier zero-request repeat preflight mistakenly omitted
the bound panel and was rejected before generation; it has no model cost and
is not a measurement.

Therefore this candidate is retained as a useful but rejected search branch,
not promoted as the incumbent. Accumulated history worked as intended: the
second Evolver saw what the first changed and why it failed, changed causal
hypothesis, selected a different component, and produced different worker
behavior. The remaining bottleneck is reliability across independent worker
samples. More prose is unlikely to solve it. The next search should favor an
executable competing-definition component that materializes alternative
parameter mappings, runs discriminating fixtures, and binds the selected
definition to submitted code. Candidate admission should include a small
repeatability probe when an apparent binary gain occurs, while retaining T19
as the protection task.

The complete new evidence is mirrored additively under:

- `results/bc-mirror/qce-public-probe-autonomous-activation-20260813-r2/`
- `results/bc-mirror/qce-public-probe-autonomous-activation-20260813-r2-retry1/`
- `results/bc-mirror/qce-public-probe-autonomous-activation-20260813-r2-toolfirst/`
- `results/bc-mirror/qce-public-probe-autonomous-candidate-20260813-r2-toolfirst/`
- `results/bc-mirror/qce-public-probe-autonomous-candidate-20260813-r2-t12-repeat1/`

## Autonomous executable-audit round

Status: measured mechanism success but benchmark negative; executable component
was Evolver-selected, activated, and locally evaluated, but it did not improve
T12 and is not promoted

Run identities:

- terminal-protocol failure: `qce-public-probe-autonomous-activation-20260813-r3b`;
- final-smoke rejection: `qce-public-probe-autonomous-activation-20260813-r3c`;
- recovered passed activation: `qce-public-probe-autonomous-activation-20260813-r3d`; and
- local candidate panel: `qce-public-probe-autonomous-candidate-20260813-r3d-local`.

The third search round received three scored experiences, including the same
parameter-identity candidate's T12 pass and immediate repeat failure. It
explicitly compared worker/code-sampling variance, implementation defects,
and environment differences. The environment was held fixed; the answer-free
AST facts showed different submitted structures across samples, while a prior
worker's internally green probes still failed official properties. The
Evolver therefore selected an executable public-behavior audit rather than
another prompt-only parameter rule.

This round also exposed and repaired three concrete controller problems. The
terminal middleware did not recognize `quant_property_v2` decisions, causing
r3b to exhaust its terminal calls after a real ACT and tool implementation.
After that fix, r3c completed but was rejected because its last tool edit came
after its last component smoke. The exact rejected source and reason were
imported for r3d. R3d then reused the mechanism, performed a final tools smoke,
and completed a legal unscored activation. Its history append failed because
component-test records were keyed only by candidate code, even though the same
candidate can have different attempt evidence. Component checks are now scoped
to the history entry. Since the full r3d candidate, ACT, proxy audit, admission,
and final smoke had already completed, the activation was recovered without a
second model run and marked `recovered_after=history_append_failure`.

The candidate modified two files: executable
`tools/public_behavior_probe.py` and its tool description. It added an optional
structural pre-audit that imports the generated strategy in an isolated
temporary directory and invokes named public functions against the real public
data before bespoke assertions. The final tools component smoke and independent
full-harness admission passed. During the official T12 worker run, the new
runner was observed executing with the generated strategy, real `/app/data`,
probe, and audit inputs, so this is an activated executable intervention rather
than a dormant code edit.

The focused official panel produced:

| Task | diagnostic parent | executable-audit candidate | official reward |
| --- | ---: | ---: | ---: |
| T12 | 12/16 | 9/16 (Type-A 4/8, Type-B 5/8) | 0 |
| T19 | 18/18 | 18/18 (Type-A 7/7, Type-B 11/11) | 1 |

The panel used 65 completed model requests, 2,833,409 tokens, and
`$0.0733250952`, with no fallback and clean completion. The r3d activation used
26 completed requests, 1,448,502 tokens, and `$0.0291706968`. R3c used 35
completed requests, 2,289,760 tokens, and `$0.0390771472`; it is a rejected
component attempt, not a benchmark score. R3b is retained as an infrastructure
failure and was not evaluated.

The result falsifies the current audit mechanism as a T12 improvement. It
proves the broader evolution mechanism can accumulate positive and negative
evaluations, retrieve a failed candidate's exact source, autonomously choose
executable code, activate it in a worker, and pass component/admission checks.
But an audit whose contract is still declared by the same worker can remain
self-confirming, and adding more repair effort can make a sampled solution
worse. The next useful search target is not more prompt prose or a larger
panel. It is an externally materialized public-definition fixture or a
candidate finalization/state mechanism that forces the chosen definition into
submitted code and can discriminate it independently. T19 remains the
protection task. T12 should be the first local target; expand only after a gain
survives a focused repeat.

The evidence is mirrored additively under:

- `results/bc-mirror/qce-public-probe-autonomous-activation-20260813-r3b/`
- `results/bc-mirror/qce-public-probe-autonomous-activation-20260813-r3c/`
- `results/bc-mirror/qce-public-probe-autonomous-activation-20260813-r3d/`
- `results/bc-mirror/qce-public-probe-autonomous-candidate-20260813-r3d-local/`

## Interpretation boundary and next competing directions

The r3 controller repairs and the next harness hypotheses must not be merged
into one claim. The `quant_property_v2` terminal-reserve bug was an observed
controller compatibility failure: the Evolver had already recorded ACT and
written its tool, but the end-of-round middleware recognized only older
decision schemas and incorrectly requested ABSTAIN until its terminal-call
budget was exhausted. Fixing this made a valid QuantCodeEval decision visible
to the controller. It did not improve the Worker, discover a quant solution,
or contribute a benchmark score.

There are now two distinct candidate directions for the Worker harness:

- **Direction A — independent public-definition fixture.** Materialize a small
  expected-behavior test from the public instruction, public paper, and public
  data schema, independently of the Worker implementation, then use it to
  distinguish competing definitions before submission. The Evolver did partly
  discover the underlying problem: it observed that a worker-authored contract
  can be internally green while official answer-free properties remain wrong.
  However, the external fixture mechanism is an investigator extension of that
  diagnosis; it has not yet been autonomously proposed and validated by the
  Evolver.
- **Direction B — decision-state retention/finalization.** Preserve a selected
  quantitative definition and its passing local evidence across later repair
  edits, then check that final submitted code still implements that state. This
  could live in memory, a checkpoint, regression state, or completion
  middleware; it need not be a hard-coded artifact finalizer. This is currently
  an investigator hypothesis motivated by long rewrite trajectories and T12
  instability. We have not yet observed a trace proving that an intermediate
  correct implementation was later overwritten, so it is weaker than A and
  must not be reported as an Evolver finding.

The immediate autonomous search should therefore keep the full harness surface
open and expose the complete accumulated history without prescribing A or B.
If the Evolver remains stuck, a second hypothesis-seeded round may present A
and B as competing explanations while allowing another mechanism or ABSTAIN.
Only after that should an investigator-authored A control be used to separate
"the mechanism can work" from "the Evolver can discover it." Start on T12,
retain T19 as the protection task, and require an apparent T12 solve to survive
one focused repeat before expansion. The search is variable-length and stops
on a working repeated mechanism, no new information, calibrated abstention, or
the declared budget; it is not intrinsically a five-iteration experiment.
