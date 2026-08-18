# AP-2 autonomous runtime-experience search

Status: accepted next experiment order, 2026-08-18

## Decision

AP-1 showed that an Evolver-produced harness bundle was score-helpful under an
experimenter-designed paired repair probe: 14/17 versus the parent harness's
12/17 on the same 3/17 T26 artifact.  Because the experimenter selected the
artifact, supplied the runtime symptom, wrote the repair instruction, and
defined promotion, AP-1 is not evidence of a complete autonomous exploration
loop.

AP-2A will test the stronger mechanism.  The Evolver receives generic access
to historical runtime experience and bounded experiment execution, but no
selected artifact, prescribed failure class, repair prompt, target component,
or promotion recommendation.  It must search, experiment, update, and submit a
candidate or ABSTAIN without intermediate human intervention.

## Responsibility boundary

The experimenter fixes only:

- T26 as the optimize task;
- the cold-history evidence cutoff;
- the model route, concurrency, time, request, and cost budgets;
- the generic experiment actions;
- Worker/verifier information separation;
- independent scoring and final claim interpretation.

The Evolver owns:

- which histories to inspect;
- whether to start from a harness, artifact, or empty task;
- the working diagnosis and any competing explanation;
- the content of a probe or repair instruction;
- which harness components to add, remove, or compose;
- when to call component smoke, Worker, or optimize evaluation;
- whether to retain, refine, compose, rollback, submit, or ABSTAIN.

The Worker receives public task inputs and Evolver-authored instructions.  It
does not receive checker answers, expected values, reference solutions, or the
Evolver's answer-rich optimize diagnostics.

## Ordered execution

1. Finish and freeze the already-running fresh T26 confirmation.  Record its
   outcome, but do not rewrite AP-2's initial instruction around that outcome.
2. Build a simple run-based experience index over pre-AP-1 evidence.  Include
   Worker artifacts and traces, candidate changes, optimize scores, runtime and
   cost, and earlier Evolver decisions.  Do not include the AP-1 handcrafted
   repair instruction or its expert root-cause summary.
3. Add benchmark-neutral actions for experience search and inspection,
   full-harness candidate editing, component smoke, bounded Worker experiments,
   optimize evaluation, run comparison, candidate submission, and ABSTAIN.
   A Worker experiment may optionally take a seed artifact and instruction,
   but both choices come from the Evolver.
4. Persist an Evolver-readable experiment notebook.  Each iteration records
   evidence inspected, current hypothesis, selected parent and components,
   experiment request, observed runtime/score/cost, decision, and next question.
   The next iteration can retrieve the complete previous record.
5. Test only the mechanism plumbing with deterministic fakes: actions are
   callable, a first experiment is recorded, a second iteration can read it and
   choose a different action, a candidate can be submitted, and ABSTAIN remains
   legal.  These tests are not autonomous-performance evidence.
6. Run a no-model rootless preflight for roles, images, action availability,
   output locations, budget counters, and final candidate evaluation.
7. Execute one paid AP-2A canary.  Use DeepSeek V4 Flash with the existing
   provider fallback route, concurrency one, at most three Evolver iterations,
   and at most three Worker experiments of 8--12 agent iterations each.  The
   total paid cap is $0.40.  Do not intervene between iterations.
8. Freeze the Evolver's submitted candidate before independent evaluation.
   Run one fresh normal-budget T26 Worker and the unchanged official verifier.
   Treat T26 as an optimize result, not held-out transfer.
9. If the final result is 17/17, repeat the entire autonomous run from a fresh
   Evolver start before making a stable binary-gain claim.  If it is 16/17 or
   improves at least one property, retain the trajectory as mechanism-positive
   and localize which autonomous decision produced the gain.  If the loop runs
   but does not improve, diagnose retrieval, experiment design, component
   manipulation, feedback use, and final selection separately.  A grounded
   ABSTAIN is a valid autonomy outcome but not a performance success.
10. Only after a positive single-task result, run a fresh-start repeat and a
    runtime-experience-search ablation.  Then consider a matched-failure
    QuantCodeEval task or QFBench canary.  Defer large multi-task search,
    protection panels, and the asynchronous scheduler until this gate passes.

## Domain-specialized state without exhaustive enumeration

The experience interface provides an extensible quant runtime-state record:

- `observed_symptom`;
- `pipeline_stage`;
- `quant_state_variable`;
- `suspected_component`;
- `supporting_runtime_evidence`;
- `competing_explanation`;
- `confidence`;
- `experiment_needed`.

The Evolver supplies values and may introduce new state variables or stages.
The repository does not encode a long T26 answer-derived failure taxonomy into
the action layer.

## Readout and claim boundary

AP-2 reports four levels independently:

1. `autonomy_feasible`: the Evolver completes search, a real experiment,
   feedback consumption, and submission or grounded ABSTAIN.
2. `feedback_driven`: a later decision is explicitly caused by an earlier
   observed runtime result rather than repeating the same proposal.
3. `component_helpful`: a self-selected intervention repairs a failure,
   improves properties, or achieves the same outcome more efficiently.
4. `benchmark_helpful`: the independently evaluated final candidate improves
   the frozen optimize reference; binary success requires 17/17.

One positive AP-2A trajectory establishes feasibility on T26 only.  Stable
autonomous capability requires an independent fresh-start repeat, and transfer
requires a separately justified task with a matched failure mechanism.
