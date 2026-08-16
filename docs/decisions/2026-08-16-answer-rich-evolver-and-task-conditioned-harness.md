# Answer-Rich Optimization Evolver and Task-Conditioned Harness

**Date:** 2026-08-16

**Status:** Accepted definition and next-experiment protocol

**Scope:** QuantCodeEval and QFBench harness-evolution experiments

**Supersedes:** The universal answer-free proposer policy for explicitly declared optimization tasks only. Historical answer-free experiments and their claim boundaries remain unchanged.

## Decision

QEA may expose post-run, answer-bearing rubric feedback from a declared
optimization task to the **Evolver**. The Worker remains blind. The Evolver's
output must be a reusable, task-conditioned harness capability rather than a
task-specific answer patch.

Three terms are now distinct:

1. **Task-specific evidence is allowed.** An optimization episode may tell the
   Evolver which rubric item failed, the expected and observed behavior, a
   counterexample, the implicated public interface, and the item-level change
   across attempts.
2. **Task-conditioned behavior is desired.** A reusable component may inspect
   the current public task instruction, paper, data schema, runtime state, and
   Worker artifact to construct checks or route behavior for that task.
3. **Task-specific harness patches are overfit.** A persistent component may
   not encode an optimization task ID, its expected constants or outputs, its
   reference implementation, or fixed assertions that apply only to that task.
   Such a proposal is retained as an optimization-only or rejected search
   branch, not promoted to the reusable component catalog.

The basic learning loop is:

```text
blind Worker attempt
    -> trusted optimization evaluation
    -> answer-bearing diagnostic packet to Evolver
    -> task-specific failure abstraction
    -> task-conditioned reusable harness edit
    -> fresh blind Worker
    -> optimization score plus answer-free transfer/protection checks
```

Answers do not enter the Worker prompt, Worker filesystem, Worker tools, or the
reusable candidate. This is a scientific-role boundary, not a security-paper
exercise; a declared split, a simple feedback mode, and ordinary experiment
evidence are sufficient for the engineering canary.

## Why the Worker remains blind

Giving the answer directly to the Worker turns the experiment into iterative
task-solution repair. That can be a useful comparison method, but it no longer
tests whether the Evolver converted runtime evidence into a better harness.

The QEA treatment therefore separates:

- **Evolver supervision:** use optimization answers to diagnose a missing
  capability and modify the shared harness;
- **Worker measurement:** run a fresh Worker without answer material to test
  whether the new harness changes behavior and outcome;
- **solution-search baseline:** optionally give equivalent feedback to a
  task-level solution optimizer in a separately labelled matched-budget arm.

## Split and feedback setup

| Split | Evolver feedback | Worker feedback | Used for search? | Interpretation |
|---|---|---|---|---|
| `optimize` / held-in | post-run rubric item, expected vs observed, counterexample, trace, artifact and score | public task plus evolved harness only | yes | supervised harness discovery and optimization gain |
| `protection` / selection | answer-free outcome and process evidence | public task plus evolved harness only | yes, as a regression gate | development evidence, not final held-out generalization |
| `transfer` | answer-free outcome; no task answer | public task plus frozen candidate only | only if explicitly converted to development after the run | provisional transfer while still blind |
| `sealed_heldout` | none before final reporting | public task plus frozen harness only | no | final generalization evidence |

A task whose score repeatedly affects candidate selection is development data,
even if its answer is never exposed. Self-Harness calls its regression split
“held-out,” but QEA reserves `sealed_heldout` for tasks that do not affect the
search lineage.

For the current canary:

- T26 becomes an answer-rich optimization task;
- T19 remains answer-free protection/development because it has already been
  used repeatedly for candidate decisions;
- T27 may be used once as an answer-free transfer canary, but becomes
  development data if its result is used for another edit;
- untouched tasks must be selected later for sealed final evaluation.

## Optimization diagnostic packet

The first implementation should stay simple. After a blind optimization
Worker is scored, the trusted coordinator may prepare an Evolver-only record
containing:

```text
task and attempt
rubric criterion
expected behavior or answer
observed behavior
minimal failing example or counterexample, when available
affected public interface
previous and current item-level verdict
relevant Worker action and artifact facts
```

The complete optimization rubric may be made available for drill-down when the
compact record is insufficient. The candidate Worker receives neither form.
Raw checker implementation is not required by default because expected
behavior and counterexamples carry the useful supervision with less irrelevant
implementation detail.

Two experience views are retained:

- an Evolver-only optimization episode may contain answer-bearing details;
- a reusable component card contains only the abstract failure mechanism,
  component change, predicted Worker effect, activation, target result,
  repeat, protection, transfer, and rejection lessons.

This preserves the cumulative search history without copying a task answer
into the Worker harness.

## Macro setup borrowed from related work

### Learning to Discover at Test Time

[Learning to Discover at Test Time](https://arxiv.org/abs/2601.16175) is a
single-problem discovery method. It updates the policy while solving one test
problem, keeps a buffer of candidate states and rewards, reuses promising
states, and returns the best discovered solution. The paper explicitly does
not require the adapted policy to generalize to other problems; the solution,
not the policy, is the final artifact.

QEA borrows:

- persistent storage of every candidate, reward, action, and outcome;
- explicit incumbent/best-state retention rather than treating the latest
  candidate as the best;
- progressively focusing search on promising branches while retaining some
  exploration;
- matched-budget best-of-N or task-solution-search controls.

QEA does not borrow its claim boundary. TTT-Discover permits problem-specific
adaptation because it seeks one best solution. A task-specific QEA harness does
not become reusable merely because it improves its optimization task.

### Self-Harness

[Self-Harness](https://arxiv.org/abs/2606.09498) is the closer macro setup. It
holds the model and evaluator fixed, mines verifier-grounded failure patterns
from held-in traces, asks the same model in a proposer role for diverse minimal
harness edits, and promotes edits only after regression evaluation. Its
failure mining separates verifier cause, causal trace status, and reusable
agent mechanism. The paper explicitly excludes task-specific difficulty,
unstable outcomes, and model capability limits when they do not imply a useful
harness change.

QEA adopts:

- blind task execution followed by proposer-facing failure evidence;
- failure patterns grounded in repeated cases rather than one anecdote;
- a distinction between terminal verifier cause and reusable agent mechanism;
- minimal component hypotheses with predicted behavioral effects;
- answer-free regression/transfer checks before reusable promotion;
- fixed model, evaluator, task protocol, and budget within a comparison.

QEA modifies two aspects:

- optimization evidence may be richer than Self-Harness and include rubric
  answers because the Worker remains blind and transfer is tested separately;
- the split used repeatedly for regression is called protection/selection, not
  final held-out. Final generalization uses a sealed split that never guides
  search.

### MLEvolve

[MLEvolve](https://arxiv.org/abs/2606.06473) also accumulates task-specific
runtime experience, but each search node is a complete solution for one
Kaggle-style task. Its task-specific plans, metrics, execution logs, and code
edits are appropriate for solution search. QEA borrows its cross-branch memory,
planner-coder separation, and targeted diff editing, but does not treat its
per-task solution specialization as evidence for reusable harness evolution.

## Promotion semantics

A candidate can have four distinct outcomes:

- `optimization_only`: improves the answer-rich optimization task but has no
  answer-free transfer evidence;
- `overfit_task_patch`: encodes a task answer, constant, identifier, or fixed
  task-only assertion; retained as a rejected search lesson;
- `protected_candidate`: repeated optimization improvement with no measured
  protection regression, but transfer remains unresolved;
- `reusable_candidate`: repeated optimization improvement plus unchanged-code
  answer-free improvement or preservation on a relevant transfer panel.

Only the last two may remain in the active component lineage, and only a
`reusable_candidate` enters the reusable component catalog. A later sealed
evaluation is still required for a broad generalization claim.

The engineering canary does not need exhaustive statistical controls. It does
need at least one independent target repeat, observed component activation,
and an answer-free protection or transfer check before promotion.

## Reclassification of the 2026-08-16 T26 candidate

The `clause_semantic_revision_loop` candidate mixed:

- a potentially general contract-read, independent-validation, revise, and
  re-audit workflow; and
- T26-specific static assertions that reported irrelevant failures on T19.

It is therefore not yet a reusable component. Its measured activation remains
valid, but the bundle is classified as an unresolved mixed candidate with
task-specific residue. The T19 18/18 result motivates testing the general
workflow; it does not validate the T26 assertions.

## Next experiment

1. Reuse the existing T26 H0 and candidate attempts; do not rerun them merely
   to construct feedback.
2. Build a post-run Evolver-only T26 diagnostic packet with item-level rubric,
   expected-versus-observed behavior, counterexamples, prior mutations, and the
   13/17 -> 14/17 -> 12/17 contrast.
3. Ask the Evolver to distinguish task-specific evidence from a reusable
   missing capability and choose `REFINE`, `SPLIT`, `SYNTHESIZE`, or `ABSTAIN`.
4. Require a prediction for both T26 and an answer-free protection/transfer
   task. Do not prescribe a finalizer, checker, or other implementation.
5. Run the admitted candidate on a fresh blind T26 Worker. Repeat only after a
   measured improvement, then run T19 protection and one unchanged-code T27
   transfer canary.
6. Keep a matched task-solution refinement or best-of-N control for later fair
   comparison; it is not a blocker for this small mechanism experiment.

No paid run is authorized or launched by this documentation decision.
