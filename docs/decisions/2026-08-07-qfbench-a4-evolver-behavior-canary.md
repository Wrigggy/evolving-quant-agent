# 2026-08-07 — QFBench A4 Evolver Behavior Canary

Status: **completed; behavioral gate failed and multi-round evolution is not ready**.

This decision supersedes only the immediate raw-versus-indexed post-A3
experiment in
[the self-hosted discovery decision](2026-08-07-self-hosted-model-configurable-quant-discovery.md).
It preserves A1–A3 and the failed infrastructure attempts as historical
evidence. The raw/indexed debugger ablation is deferred until one indexed A4
run demonstrates that the Evolver itself can complete the intended discovery
loop.

## Conclusion

A4 is a single-proposal behavioral canary, not another multi-iteration
evolution run. It asks whether one model-configured Evolver can turn broad,
answer-free execution evidence into a causal hypothesis, an admissible harness
intervention, and a falsifiable prediction. Candidate task reward is a
secondary directional signal. The primary object is the Evolver's observable
behavior.

The canary starts from the exact worker in the completed five-repetition
baseline. It does not continue the post-A3 candidate ancestry. A1–A3 established
that structural components can be recombined and activated; A4 deliberately
returns to the measured seed in order to study general discovery on several
repeatable baseline failures rather than one skill-translocation episode.

## Train-only selection

The completed 85-task baseline is a sampling source, but only tasks in the
frozen 30-task evolution-train split are eligible for Evolver evidence.
Validation, authoritative test, and diagnostic task identities, outcomes,
traces, finals, artifacts, and verifier information remain excluded.

Target eligibility requires all of the following in the five baseline
repetitions:

1. official reward is zero in all five repetitions;
2. verifier exit code is zero in all five repetitions;
3. answer-free official passed/failed test counts are present and non-empty in
   all five repetitions.

Eligible targets are ranked by minimum repetition-level pass fraction, then
mean pass fraction, then task ID. Ranking by the minimum rather than the best
or a single repetition avoids selecting a lucky near-pass whose other runs
collapsed. The first three tasks are:

| Role | Task | Domain | Five-repeat public outcome |
|---|---|---|---|
| target | `swap-curve-bootstrap-ois` | rates/FX/macro | reward 0/5; 17/19 tests in every repetition |
| target | `earnings-surprise-calculator` | data engineering | reward 0/5; 4/8 tests in every repetition |
| target | `corporate-action-adjustment` | data engineering | reward 0/5; 3/7 tests in every repetition |

Protection tasks must have reward 1 in all five repetitions, normal verifier
execution, and non-empty tests. The selector prefers distinct domains not
represented among targets, then larger minimum official test count. The two
protections are:

| Role | Task | Domain | Five-repeat public outcome |
|---|---|---|---|
| protection | `brinson-sector-attribution` | systematic strategy | reward 5/5; 42/42 tests every time |
| protection | `bs-greeks-pde` | derivatives | reward 5/5; 39/39 tests every time |

The exact source hashes, worker digest, selection facts, and panel are frozen in
`data/qfbench/MANIFEST_A4_EVOLVER_BEHAVIOR.json` and re-derived before evidence
construction. Any drift fails closed.

## Evidence and debugger relationship

The debugger is a deterministic indexer in the Evolver's read-only evidence
workspace, not a second root-cause agent and not a privileged verifier. A4 uses
one Evolver with one coherent context containing:

- the five-repetition train-only selection statistics;
- a fresh current-runtime seed execution for all five selected tasks;
- structured worker tool calls and results, final responses, and process
  summaries;
- worker-produced text artifacts in full up to 192 KiB, with head/tail previews
  and exact hashes for larger text artifacts;
- a task index and anomaly overview that state observed facts and unresolved
  questions but do not name a component or cause;
- the complete writable candidate harness and bounded NexAU reference surface
  already provided by the Evolver runtime.

This design makes code construction, commands, outputs, artifacts, component
bindings, and candidate contents legible to the Evolver. It directly measures
the previously noted side observation that evidence is useful only when the
agent actually accesses it. Exact evidence access, task coverage, raw-trace
access, query operations, and grounded citation are recorded.

Official tests, official solutions, reference data, raw private verdicts,
credentials, and all non-train evidence remain outside the corpus. Large files
are previewed for legibility, not silently dropped. Every copied text surface
is credential-scrubbed and the immutable tree is content-addressed before use.

## Evolver contract

The Evolver uses QEA's model-neutral full-harness profile in the self-hosted
rootless Docker environment. The exact model, provider, and supported
deliberation request are bound at run time. E2B is forbidden for A4.

The coordinator does not prescribe a component. Before writes unlock, the
Evolver must inspect exact evidence, compare at least two mechanisms, record
counterevidence and uncertainty, define a discriminating probe, select one of
the nine component roles, and state task/process predictions. The final report
must agree with the unlock record and the actual changed component.

A4 does not require the edit to avoid prompts or skills. Such a requirement
would merely replace a skill prior with another artificial prior. Instead, a
prompt or skill edit passes only if exact evidence supports it over competing
components and the intervention is reachable, bounded, and aligned with its
prediction. Tools, tool descriptions, validator, memory, middleware, routing,
and agent configuration remain equally available.

## Frozen model control

The A4 main run is a single-model closed loop. The five-repeat sampling
baseline, fresh seed-evidence workers, Evolver, and admitted-candidate workers
all use the official DeepSeek route for
`deepseek/deepseek-v4-flash-0731`, pinned to the DeepSeek provider with
fallbacks disabled. The Evolver requests the route-supported `high` reasoning
effort; the deterministic debugger/indexer makes no model call. This keeps the
model family and release fixed while the evidence-to-intervention mechanism is
observed.

One already-started `deepseek-v4-pro` proposal may be retained only as
engineering evidence that the self-hosted discovery path executes. Because
that Pro route is not the formal release selected for A4, its behavior,
candidate, and any score are excluded from the A4 main conclusion and are
never pooled with the Flash run. A Pro/Flash difference is not interpreted as
a mechanism effect.

## Execution schedule

The maximum schedule is deliberately one step:

1. evaluate the pinned seed once on the five selected train tasks to obtain
   current structured traces;
2. build and authorize the indexed A4 evidence bundle;
3. request exactly one Evolver proposal;
4. admit and smoke-check the candidate;
5. if admitted, evaluate the candidate once on the same five tasks;
6. audit discovery behavior first and score deltas second.

This is ten worker task attempts plus one Evolver call when the candidate is
admitted. It is not a multi-round loop, does not update an incumbent, and does
not make a statistical performance claim.

## Primary behavioral audit

The fixed engineering audit requires:

- an admitted, non-empty candidate;
- successful write unlock after multiple hypotheses and counterevidence;
- a falsifiable prediction and consistent final mechanism/component report;
- exact evidence access covering at least two selected tasks and at least two
  raw traces;
- grounded-citation ratio of at least 0.8;
- agreement between the declared component and the actual diff.

The threshold is a practical canary gate, not a paper metric. A manual causal
audit still checks whether the hypothesis is substantively supported, whether
the diff truly tests it, and whether predicted process changes appear in the
candidate trace. Passing the automated gate therefore yields
`manual_causal_audit_required`, not automatic multi-round readiness.

Task deltas report target gains/regressions and protection regressions
separately. A score gain cannot rescue a failed discovery process; a strong
process with no one-pass gain is useful negative mechanism evidence. Only a
coherent process plus a plausible falsification result justifies designing a
multi-round successor.

## Claim boundary

A4 can support only an engineering statement about whether the configured
Evolver completed a legible evidence-to-intervention loop on this panel. It
cannot establish debugger uplift, multi-round improvement, statistical
significance, causal truth, transfer to hidden tasks, or publication-level
novelty. A later debugger ablation should compare matched raw and indexed
evidence after a viable model route and successful indexed A4 proposal exist.

## Measured result

The frozen Flash main run completed on the self-hosted backend. The Evolver
accessed all five raw task traces and 30/44 evidence members, recorded three
competing mechanisms with counterevidence, and produced an admitted candidate.
The actual diff changed only `systemprompt.md`.

The fixed automated process gate failed because the unlock-time and final
selected-mechanism strings were not exact matches. Manual review found the two
descriptions conceptually aligned, but the candidate's more important causal
prediction failed: it activated first-call workspace inventory on all five
tasks, while target tool calls, errors, and turns increased and every target
and protection score remained unchanged. The mechanism is falsified on this
panel, and A4 is not ready to extend into multiple evolution iterations.

The previously started Pro proposal remains engineering-only evidence and is
not pooled with the main result. Full measurements, costs, run IDs, the proxy
audit correction, and the next identifiability/abstention recommendation are in
the [A4 report](../reports/2026-08-07-qfbench-a4-evolver-behavior-canary-report.md).
