# 2026-08-07 — QFBench A4 Evolver Behavior Canary Report

Status: **completed engineering canary; not ready for multi-round evolution**.

## Headline

The A4 instrumentation worked, but the discovered intervention did not.

With one model fixed end to end, the Evolver inspected all five selected task
traces, accessed 30 of 44 exact evidence members, considered three competing
mechanisms, recorded counterevidence and uncertainty, unlocked writes, emitted
an admissible candidate, and made falsifiable process and task predictions.
The candidate changed only `systemprompt.md`.

The predicted first-call workspace inventory appeared on all five candidate
tasks. The more consequential predictions did not: target task tool calls,
tool errors, and turns increased in aggregate, and all five public test-count
and reward vectors were exactly unchanged. The fixed automated behavior gate
also failed because the unlock-time and final mechanism strings were not exact
matches. Manual review found the two descriptions conceptually aligned, so
that specific failure is best interpreted as contract/serialization drift,
not a conceptual pivot. The observed process and score result nevertheless
falsifies the proposed mechanism on this run.

This is useful negative evidence. A4 demonstrates a legible
evidence-to-hypothesis-to-intervention loop, but it does not demonstrate that
the current discovery policy can identify a productive component edit. Do not
start multi-round evolution from this mechanism yet.

## Frozen main condition

The main result is a single-model closed loop:

| Role | Model route | Provider | Deliberation |
|---|---|---|---|
| five-repeat sampling baseline | `deepseek/deepseek-v4-flash-0731` | DeepSeek | baseline configuration |
| fresh five-task seed evidence | `deepseek/deepseek-v4-flash-0731` | DeepSeek | worker configuration |
| Evolver | `deepseek/deepseek-v4-flash-0731` | DeepSeek | `high` |
| candidate workers | `deepseek/deepseek-v4-flash-0731` | DeepSeek | worker configuration |

Provider fallbacks were disabled. A bounded route probe resolved the requested
Flash route to `deepseek/deepseek-v4-flash-20260731` on DeepSeek, returned
generation ID `gen-1786084455-LcLq9PXL8OF09MkmFkse`, and exposed 16 reasoning
tokens. The probe cost was USD 0.00001946.

The deterministic debugger/indexer made no model call. E2B was not used. All
Evolver and worker execution ran in the self-hosted rootless Docker runtime.

## Panel and evidence

The frozen train-only panel was:

| Role | Task | Five-repeat baseline | Fresh seed |
|---|---|---:|---:|
| target | `swap-curve-bootstrap-ois` | reward 0/5; 17/19 every run | 17/19, reward 0 |
| target | `earnings-surprise-calculator` | reward 0/5; 4/8 every run | 4/8, reward 0 |
| target | `corporate-action-adjustment` | reward 0/5; 3/7 every run | 3/7, reward 0 |
| protection | `brinson-sector-attribution` | reward 5/5; 42/42 every run | 42/42, reward 1 |
| protection | `bs-greeks-pde` | reward 5/5; 39/39 every run | 39/39, reward 1 |

The fresh seed pass completed all five tasks with 44 completed model requests,
423,000 tokens, and USD 0.0260037624. Its result vector exactly reproduced the
selection facts. The authorized evidence bundle contained 44 members and had
SHA-256
`a521ca9de68a88e115bbcf18abbec9a66163e7f99a4892a2ae981539217f414a`.
It included the five public worker traces, finals, process summaries, and
bounded artifact contents, but no validation/test task material, official
tests, solutions, private verdict text, reference answers, or credentials.

## Main Evolver behavior

Exact run ID:
`qfbench-a4-discovery-deepseek-v4-flash-0731-high-20260807-r2`.

The run completed with zero service restarts and no residual exact-run
containers or networks. The proposal used 19 completed model requests plus two
provider-accounted `downstream_delivery` records whose caller completed and
published the bounded proposal. Those request identities remain denied across
attempts. Total accounted usage was 1,807,812 tokens and USD 0.0550246536.

Measured discovery behavior:

| Measure | Result |
|---|---:|
| exact evidence members accessed | 30/44 (0.6818) |
| selected tasks accessed | 5/5 |
| raw worker traces accessed | 5/5 |
| debugger/index files accessed | 2/2 |
| grounded cited evidence | 13/13 (1.0) |
| competing hypotheses recorded | 3 |
| writes unlocked | yes |
| candidate admitted | yes |
| changed components | `systemprompt` only |
| automated contract score | 0.9091 |
| automated process gate | failed |

The three mechanisms considered were:

1. a system-prompt process policy addressing workspace inventory,
   specification extraction, independent re-derivation, and shell-error
   discipline;
2. an output validator/middleware hypothesis for formatting or numerical
   interpretation;
3. a deterministic input-inventory tool hypothesis.

The Evolver rejected the formatting hypothesis because the public artifacts
matched the written schemas and the protection tasks used similar writers. It
rejected the dedicated inventory tool because `bs-greeks-pde` also recovered
from a bad initial path and still passed. It selected the broader system-prompt
policy because the target traces appeared to use one-sided verification and
contained path or shell errors.

This is materially better diagnosis behavior than the earlier A1–A3
translocation path: the component was not prescribed, the Evolver checked
multiple component families, and it stated counterevidence and a falsifiable
probe. It still selected a prompt-only intervention.

### Automated gate failure

Every fixed check passed except `final_mechanism_consistent`. The unlock record
and final report used different strings for the selected mechanism. Manual
review found both descriptions refer to the same system-prompt protocol, so the
strict string comparison overstates the conceptual inconsistency. It still
correctly detects failure to preserve an exact machine-readable contract and
keeps the run fail-closed for multi-round readiness.

## Candidate outcome

Exact run ID: `qfbench-a4-candidate-eval-20260807-r2`.

The admitted candidate changed only `systemprompt.md`. Its five-task evaluation
completed with zero service restarts, 47 completed model requests, 582,622
tokens, USD 0.0373550464, and no residual exact-run containers or networks.

| Task | Seed | Candidate | Delta |
|---|---:|---:|---:|
| `swap-curve-bootstrap-ois` | 17/19, reward 0 | 17/19, reward 0 | 0 |
| `earnings-surprise-calculator` | 4/8, reward 0 | 4/8, reward 0 | 0 |
| `corporate-action-adjustment` | 3/7, reward 0 | 3/7, reward 0 | 0 |
| `brinson-sector-attribution` | 42/42, reward 1 | 42/42, reward 1 | 0 |
| `bs-greeks-pde` | 39/39, reward 1 | 39/39, reward 1 | 0 |

There were zero target gains, zero target regressions, and zero protection
regressions.

### Falsifiable process prediction

The candidate did cause the first tool call to inventory `/app`, `/app/data`,
and `/app/output` on all five tasks. That confirms the prompt intervention was
active. It did not deliver the predicted reduction in tool errors and turns:

| Scope | Metric | Seed | Candidate | Direction |
|---|---|---:|---:|---:|
| three targets | tool calls | 27 | 30 | +3 |
| three targets | tool errors | 6 | 7 | +1 |
| three targets | turns | 23 | 25 | +2 |
| all five tasks | tool calls | 49 | 56 | +7 |
| all five tasks | tool errors | 15 | 17 | +2 |
| all five tasks | turns | 44 | 47 | +3 |

Target wall time also increased from 259.093 to 400.083 seconds. Across the
full panel it increased from 545.338 to 749.357 seconds. These timings are
descriptive single executions, not stable latency estimates, but their
direction agrees with the increased tool/turn counts.

The predeclared mechanism allowed a hygiene-only outcome if errors and turns
fell while task counts stayed flat. That did not happen. The first-call
inventory subprediction passed, but the broader process and task prediction
failed. The mechanism is therefore falsified on this panel rather than merely
"not yet proven."

## Engineering-only Pro run

An already-started `deepseek-v4-pro` proposal is retained only as engineering
evidence. It is excluded from the main result because Pro was not the formal
model release selected for A4, and it was neither pooled with Flash nor scored.

The Pro Evolver accessed 27/44 evidence members and all five raw traces,
recorded two hypotheses, achieved a 1.0 automated discovery contract score,
and also selected a `systemprompt`-only edit. Its runtime then failed closed
during proxy-audit validation because the producer emitted the legitimate
`failure_class="downstream_delivery"` state but the audit validator did not
enumerate it. The proposal artifacts were retained, the candidate passed a
read-only deterministic admission check, and quarantine prevented all three
bounded service retries from reopening a paid request. No Pro task evaluation
was launched, and its provider cost is not available from a canonical audit.

The proxy contract was corrected before the Flash main run:

- `downstream_delivery` is now a valid quarantined audit tuple;
- its request identity remains denied across attempts;
- a successful Evolver caller may publish its bounded proposal because the
  proposal itself confirms delivery at the experiment boundary;
- worker attempts retain their stricter fatal treatment;
- accounted downstream-delivery token and cost fields are included in the
  proposal report.

The exact remote regression set passed 76 tests with one skip before the Flash
main run. Final local verification passed 96 A4/discovery/sandbox tests and 58
model-proxy loopback tests; `git diff --check` and Python compilation also
passed.

## Cost and claim boundary

The audited known cost of the Flash main path was USD 0.1184029224:

- route probe: USD 0.00001946;
- fresh seed evidence: USD 0.0260037624;
- Flash Evolver proposal: USD 0.0550246536;
- candidate evaluation: USD 0.0373550464.

One earlier Flash probe attempt produced no publish-once artifact and is not
included in that audited total. The Pro proposal cost is also unavailable.
Therefore USD 0.1184029224 is an evidence-backed lower bound for the work in
this report, not an account-billing total.

A4 supports these conclusions:

- the self-hosted, single-model discovery path can expose and record a much
  richer Evolver investigation than A1–A3;
- the Evolver can autonomously compare component mechanisms and produce an
  admissible, activated, falsifiable intervention;
- on this run, richer evidence access did not prevent convergence to a
  prompt-only edit and did not improve any selected task;
- the selected prompt mechanism was falsified by its own process and task
  predictions;
- the present mechanism is not ready for multi-round evolution.

A4 does **not** establish debugger uplift, evidence-exposure causality,
statistical significance, hidden-task transfer, model-independent behavior,
or publication-level novelty. Evidence access is descriptive because there is
no matched raw-versus-indexed ablation in A4.

## Next mechanism decision

Do not spend the next budget on more iterations of this Evolver. The next
canary should improve discovery selectivity before scale:

1. allow an explicit `insufficient_identifiability`/abstain outcome when the
   public evidence does not distinguish a causal intervention;
2. require the selected mechanism to have an observable signature that is
   present in failures and survives explicit protection-task counterexamples;
3. have the deterministic debugger expose executable, answer-free
   discriminating probes and process deltas rather than only more trace text;
4. require the Evolver to execute the discriminating probe or a unit-style
   candidate check before write unlock;
5. keep `deepseek-v4-flash-0731` fixed for the next matched canary so the
   mechanism change, not a model change, is the experimental variable.

The deferred raw-versus-indexed debugger ablation becomes informative only
after this identifiability/abstention gate can produce either a coherent
intervention or a justified no-change decision.

## Exact artifacts

- frozen panel: `data/qfbench/MANIFEST_A4_EVOLVER_BEHAVIOR.json`
- evidence builder: `scripts/build_qfbench_a4_evidence.py`
- fixed audit: `scripts/audit_qfbench_a4_behavior.py`
- main proposal run:
  `/home/julius/qea/runs/qfbench-a4-discovery-deepseek-v4-flash-0731-high-20260807-r2`
- candidate run:
  `/home/julius/qea/runs/qfbench-a4-candidate-eval-20260807-r2`
- behavior audit:
  `qfbench-a4-discovery-deepseek-v4-flash-0731-high-20260807-r2/a4-behavior-audit.json`
- exact release: `/home/julius/qea/deploy/releases/a4-b4fa7c3-c91be14`
