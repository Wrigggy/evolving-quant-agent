# T26 Answer-Rich Evolver Mechanism Experiment

**Date:** 2026-08-16

**Status:** Designed; implementation and live run not yet started

**Benchmark:** QuantCodeEval

**Search level:** A — reusable transfer

## Question

Can the Evolver use answer-bearing, item-level T26 diagnostics to convert a
specific Worker failure into a reusable harness component that improves a new
blind Worker, without copying T26 answers into the Worker or persistent
component?

This is a mechanism-localization experiment. It is not intended to establish a
paper-level QuantCodeEval gain.

## Evidence already available

Do not rerun old attempts merely to create the feedback packet:

| T26 state | Type A | Type B | Total | Interpretation |
|---|---:|---:|---:|---|
| shell-only H0 | 5/7 | 8/10 | 13/17 | retained baseline attempt |
| first clause-semantic candidate | 6/7 | 8/10 | 14/17 | one-point improvement with component activation |
| repeated candidate | 5/7 | 7/10 | 12/17 | activation repeated but benefit was unstable |

The same candidate's T19 protection attempt scored 18/18, while its static
T26-oriented audit reported irrelevant failures. This is why the general
read/validate/revise workflow and the task-specific assertions must be
separated rather than promoted as one component.

## Minimal implementation

Add one explicit feedback mode, tentatively named `answer_rich_evolver`.
After official scoring of an optimization attempt, the trusted coordinator
creates an `optimization-diagnostic.json` visible to the Evolver projection and
absent from the Worker projection.

The packet should contain only information useful for diagnosis:

- attempt identity and prior candidate change;
- rubric criterion or tested property;
- expected behavior or answer;
- observed behavior and minimal counterexample when available;
- relevant public interface, Worker action, and artifact observation;
- before/after item status across H0, first candidate, and repeat.

The complete optimization rubric may be available for Evolver drill-down if
the compact packet is insufficient. Raw checker implementation is not needed
for the first canary.

Store two experience views:

- an Evolver-private episode containing the answer-bearing T26 evidence;
- a reusable component record containing only the abstract failure mechanism,
  component edit, predicted behavior, activation, scores, repeat/protection/
  transfer results, and rejection lesson.

The Worker receives the public task and candidate harness only. It never
receives either the expected answers or the diagnostic packet.

## Evolver assignment

Give the Evolver the 13/17, 14/17, and 12/17 contrast and ask it to:

1. distinguish task-specific failed properties from the reusable missing
   capability;
2. inspect the existing full harness and choose the component locus itself;
3. choose `REFINE`, `SPLIT`, `SYNTHESIZE`, or `ABSTAIN`;
4. implement and smoke-test a reachable component when acting;
5. predict which T26 properties should change and what should happen on T19
   and T27.

The mutation surface remains the full harness. Do not prescribe a finalizer,
checker, middleware, prompt edit, or repair ledger. The experiment is testing
whether evidence is sufficient for autonomous component selection as well as
whether the selected component helps.

## Lightweight admission

Admit a candidate when it has:

- a legal decision and non-empty harness change;
- a small component-level smoke or preflight;
- a reachable integration path used by the Worker;
- no copied T26 task ID, expected constant/output, reference implementation,
  or fixed assertion that can only apply to T26 in the reusable artifact.

Multi-file changes are allowed and expected when the component requires state,
tools, routing, or middleware. The final condition is a simple research review,
not a new defensive subsystem.

## Stop-gated live sequence

1. Run one Evolver activation using the retained evidence.
2. Stop if it returns calibrated `ABSTAIN`, produces no candidate, fails its
   local smoke, or cannot be admitted.
3. Run one fresh blind T26 Worker with the admitted candidate.
4. Continue only if it improves over the retained 13/17 H0 attempt.
5. Run one independent blind T26 repeat. Continue only if that repeat also
   exceeds 13/17.
6. Run T19 answer-free protection with unchanged code. Continue only if it
   preserves the current 18/18 reference result.
7. Measure T27 transfer with one shell-only H0 Worker and one unchanged-code
   candidate Worker under the same task/model/budget setup. Do not expose T27
   answers to the Evolver before this comparison.

If the first T26 result improves but the repeat does not, retain the candidate
as an unstable optimization branch and do not spend T19/T27 calls. If T27 is
used to guide another edit, relabel it development/protection data from that
point onward.

The T27 official golden 18/18 setup check is not a Worker baseline. A matched
shell-only Worker attempt is required before interpreting candidate transfer.

## Outcomes

Record the outcomes separately:

- `discovery_positive`: Evolver consumes the new evidence, selects a component
  locus, writes an admitted component, and that component activates as
  predicted;
- `target_positive`: both fresh T26 attempts exceed the retained 13/17 H0;
- `protected_candidate`: target-positive and T19 remains 18/18;
- `reusable_candidate`: protected and T27 is preserved or improved relative to
  its matched shell-only Worker baseline with unchanged candidate code;
- `optimization_only`: T26 improves but transfer does not;
- `insufficient_or_unstable`: no admitted candidate or no repeated target gain.

Do not collapse these into one success label. A discovery-positive result can
still have zero score benefit, and a target-positive result can still fail the
reusability hypothesis.

## Evidence and cost envelope

Retain the feedback mode and task roles, diagnostic packet, Evolver decision
and diff, smoke output, Worker trace and artifact, property vector, score, model
requests, cost, wall time, and every stop-gate decision. This is enough to
reconstruct the engineering experiment; no new digest or exhaustive runtime
contract is required.

The maximum gated path is six model executions: one Evolver, two T26 Workers,
one T19 Worker, and two T27 Workers. Based on prior canaries, use a proposed
run-level cap of **$0.25**, report actual usage, and stop earlier whenever a
gate fails. This document does not authorize or launch the paid run.

## Interpretation and fallback

One positive component is not evidence of stability. If this component passes
the target repeat and protection/transfer checks, test a second, genuinely
different component hypothesis before making a reusable-transfer claim.

If two distinct, activated components repeatedly improve their optimization
tasks but fail answer-free transfer, follow
[`2026-08-16-transfer-first-and-closed-benchmark-fallback.md`](2026-08-16-transfer-first-and-closed-benchmark-fallback.md):
record the negative transfer result and switch to benchmark-wide adaptive
optimization rather than repeating the same held-out experiment indefinitely.
