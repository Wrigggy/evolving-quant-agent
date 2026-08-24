# Quant-H0-S6 Core/Full construct calibration

Date: 2026-08-24
Status: implemented and locally tested; paid canary frozen but not launched
Supersedes the baseline choice, but not the implementation record, in
`2026-08-24-quant-h0-s6-worker-protocol-implementation.md`.

## Decision

The prospective QRS substrate is **Quant-H0-S6-Core**, not the previously
implemented detailed S6 workflow by default. Core fixes a small, observable
Research State interface:

1. S1 Research Mandate and Contract;
2. S2 Research Evidence and Data;
3. S3 Quantitative Representation;
4. S4 Research Operation;
5. S5 Evaluation and Reconciliation; and
6. S6 Research Artifact and Completion.

It fixes concise entry/completion markers, public-grounded `NOT_APPLICABLE`,
and S5 revisit semantics. It does not prescribe data-audit checklists,
particular quantitative methods, early artifact drafting, independent
perturbations, schema/finite-value checklists, or reconciliation algorithms.
Those are candidate harness capabilities that QRS may synthesize as tools,
skills, validators, memory, routing, middleware, or prompt policies.

The existing `qea/worker_quant_h0_s6` is retained and renamed conceptually as
**S6-Full** for calibration. It is a strong, human-authored quant-workflow
baseline, not the default starting state of the claimed method. Its detailed
stage advice may improve Workers, but such a gain belongs to manual workflow
engineering rather than QRS evolution.

## Relation to QuantaAlpha-like trajectory evolution

The useful analogy is the decomposition, not the solution content. A stable
state interface makes an end-to-end trajectory indexable, lets the Evolver
locate the earliest consequential mismatch, and lets later history retrieval
address a specific state transition. QRS differs in evolutionary object: it
changes the persistent Worker harness rather than factor hypotheses or factor
expressions. The S1--S6 ontology is therefore instrumentation shared by the
baseline and evolved agent, not the claimed learned capability.

## Why Full is not automatically the main baseline

Choosing Full whenever it scores better would move the target of evolution
into the starting harness. Conversely, deleting a genuinely useful rule only
to manufacture headroom would be equally misleading. The calibration therefore
separates two questions:

- **Core versus legacy:** what does a thin state interface change in validity,
  official outcome, trace observability, and cost?
- **Full versus Core:** what additional capability and overhead come from
  detailed human-authored stage advice?

Core remains the construct-aligned QRS substrate if it realizes the protocol,
preserves execution validity, avoids repeated task-level regression, and has
tolerable overhead. This decision does not require it to preserve historical
headroom. If Core improves the Worker, the gain is disclosed and harder public
development tasks are re-screened. Full remains a reported strong baseline or
ablation; its detailed rules are not moved into Core merely because they score
well.

## Frozen three-arm canary

`data/breadth/QF_QUANT_H0_S6_MATCHED_CANARY_PLAN.json` freezes Legacy, Core,
and Full on three deliberately selected development roles:

- `swap-curve-bootstrap-ois`: stable rates headroom;
- `13f-amendment-aware-crowding`: long, variable data/reconciliation work; and
- `fx-forward-cross-rate`: a recent full-score ceiling and protocol-overhead
  control.

Each task has two fresh repetitions with reversed arm order, for eighteen
Worker/verifier cells. The canary reports every task-by-repetition official
vector, execution validity, stage realization, turns/tool calls/errors,
requests/tokens/cost/wall time, and an equal-task macro only as a secondary
summary. It has no Evolver, candidate, Candidate Reviewer, promotion, history,
or sealed claim.

Task selection is purposive and disclosed. Historical scores motivate the
roles only; no score, failed-property identity, diagnostic, verifier output,
candidate history, or prior artifact enters a Worker.

## Main-path boundary

This baseline canary does not close the candidate answer boundary. The main QRS
path remains `NO-GO` until Candidate Information-Set Review is fail-closed at
the actual Worker-dispatch boundary, covers cumulative Core-to-effective-
candidate material and trusted public sources, runs an immutable reviewed
snapshot, and cannot be bypassed by a selected probe or preconstructed
candidate. One fresh public-only Review-`PASS` candidate must then reach a
blind Worker as that exact reviewed snapshot and produce a retained strict
official gain. Repeat and answer-free protection remain necessary for stable
promotion.
