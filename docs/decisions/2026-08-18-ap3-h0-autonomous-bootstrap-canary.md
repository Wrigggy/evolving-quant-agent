# Streamlined AP-2M and AP-3 H0 autonomous bootstrap canary

Status: accepted speed-first experiment sequence, 2026-08-18

## Measured prerequisite

The R3 Evolver-produced candidate harness has now produced a fresh T26 Worker
artifact that passed all 17 official properties and received reward 1.  The run
started from the public task rather than a repaired seed artifact.  This is a
fresh candidate-harness binary success, but the experimenter designed the AP-1
probe and manually promoted the candidate.  It therefore does not by itself
establish a complete autonomous exploration loop or autonomous bootstrap from
H0.

## AP-2M: minimum warm-history autonomy canary

AP-2M replaces the heavier immediate AP-2A platform build.  It uses:

- one pre-AP-1 experience catalog;
- two Evolver decision rounds;
- one intermediate Worker probe authored by the Evolver;
- one independent final T26 evaluation;
- full-harness mutation;
- ordinary JSON evidence files rather than a new durable experiment platform.

Round one receives the objective, an unranked pre-AP-1 experience catalog, raw
optimize evidence, the full harness workspace, and a fixed resource budget.  It
must submit a candidate plus an `experiment_spec` containing its own choice of:

- repair or from-scratch mode;
- historical seed experience, or none;
- Worker instruction;
- Worker iteration budget within the external cap;
- prediction;
- observation that would change its decision.

The experimenter does not select the artifact, failure class, prompt, search
operator, component, or promotion direction.  The coordinator executes exactly
one valid experiment specification and returns its artifact, trace, official
optimize properties, runtime, requests, tokens, and cost.

Round two sees the complete result and may retain, refine, roll back, compose,
submit, or ABSTAIN.  If it edits the candidate, the independent final T26 Worker
is the second real observation; there is no second intermediate probe.  Report
separately whether the loop was legally completed, whether round two was caused
by round-one feedback, whether the self-selected component helped, and whether
the independent final score improved.

For the engineering canary, use concurrency one, one bounded 10--12 iteration
probe, a shorter feedback turn, a normal-budget final Worker only for a legal
non-regressing candidate, and a total paid cap of $0.25.  Reuse the current
provider-flexible DeepSeek route.  Defer additional probes, a generalized
experience service, formal ablation, transfer, QFBench, and scheduling.

## AP-3: minimum autonomous bootstrap from H0

AP-2M success proves experience-guided autonomy only.  AP-3 reuses the same
coordinator, decision protocol, probe executor, feedback handoff, and final
verifier, but changes the initial state:

- the only harness seed is shell-only H0;
- the only task evidence comes from one fresh H0 Worker created inside AP-3;
- no historical high-scoring artifact is available;
- no R3 or AP-1 candidate is available;
- no AP-1 repair instruction or expert root-cause summary is available;
- no task-specific component recommendation is available.

The ordered AP-3 flow is:

1. Run one fresh H0 Worker on public T26 and persist its artifact, trace,
   runtime failures, answer-rich optimize diagnostic, score, runtime, and cost.
2. Give only that run-local evidence and the H0 full-harness workspace to
   Evolver round one.
3. Require the Evolver to choose the first hypothesis, component mutation, and
   experiment specification; allow any full-harness edit or grounded ABSTAIN.
4. Execute one real bounded Worker experiment and return all run-local results.
5. Give the result to Evolver round two; record whether its retain, refine,
   rollback, compose, submit, or ABSTAIN decision is explicitly grounded in the
   observed result.
6. Independently evaluate the frozen final candidate with one fresh normal-
   budget T26 Worker and the unchanged official verifier.

## Claim gates

AP-3 reports four gates without collapsing them:

1. `bootstrap_loop_feasible`: H0 evidence leads to a legal self-selected
   experiment and a feedback-grounded second decision.
2. `component_activated`: the selected prompt, tool, middleware, memory,
   validator, routing, or composition actually affects Worker execution.
3. `bootstrap_helpful`: the final independent T26 property count is above the
   fresh H0 reference, or an explicitly predicted runtime failure is repaired
   without a property regression.
4. `binary_helpful`: the final independent score is 17/17 and reward 1.

One AP-3 success supports only a T26 H0-bootstrap feasibility claim.  Repeat
from the exact H0 harness with a fresh Evolver sample before claiming initial
stability.  Test a second task with a different failure mechanism before
claiming broader autonomous bootstrap.  Full-benchmark scheduling and formal
held-out reporting remain later work.
