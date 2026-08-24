# QRS Reviewer-policy-v2 qualification R1 retained engineering failure

> Date: 2026-08-25 · Experiment: `qf-qrs-reviewer-policy-v2-qualification-20260825-r1` · Decision: `FAIL_ENGINEERING_PRE_REVIEW`; Main `NO-GO`; R1 cannot resume or be reused

## Measured setup and answer boundary

R1 was the separately frozen engineering qualification authorized only through
panel one. It deployed source revision
`701ceac236e454b94f08eb7ed5fc8e9ba322fa31` under the fixed plan
[`QF_QRS_REVIEWER_POLICY_V2_QUALIFICATION_PLAN.json`](../../data/breadth/QF_QRS_REVIEWER_POLICY_V2_QUALIFICATION_PLAN.json).
It was not Main and authorized no later panel, sealed task, automatic recovery,
or reuse of any qualification material.

All four fresh Primitive-H0 Worker/verifier cells and runtime histories were
valid. The descriptive records were 62/63 on
`crypto-funding-rate-basis-carry`, 35/35 on `cir-bond-pricing`, 28/28 on
`copula-equity-fitting`, and 12/12 on `historical-var-data-prep`. These are
single canary observations, not a stable baseline or an evolved comparison.

The answer-free bank boundary passed a post-H0 audit. Panel one exposed exactly
the crypto focus plus the CIR and historical-VaR cross-family anchors;
the copula task remained controller-only. The proposal's 41 non-log authorized
evidence files matched the controller-materialized panel tree. No official
score/reward, verifier output, failed property, expected value, hidden test,
optimization diagnostic, prior-mini material, or sealed outcome entered the
Evolver surface. Worker-created files named `artifacts/results.json` were
blind Worker deliverables rather than official evaluator results.

## Proposal and exact failure

One Evolver call returned an admitted `ACT` with one
`task_agnostic_harness_policy` claim, `s3_s4_convention_binding`. Its declared
basis contained the frozen QRS workflow framework and exact answer-free crypto
and CIR trajectory references from two distinct families. The candidate
changed only
`skills/quant-research-six-stage-workflow/SKILL.md`: S3 was asked to pin
public-text-grounded operational conventions before S4, and S4 was asked to
re-confirm that its first execution realized that lock. The system prompt,
agent configuration, tools, and tool descriptions were unchanged.

The controller copied that exact candidate into a run-scoped frozen tree
before package construction. The copied tree matched the Evolver candidate,
used `0555` directories and `0444` files, and contained no symlink. Because no
Reviewer call occurred, it is retained only as a **forensic pre-Review
snapshot**. It is not a reviewed, accepted, or PASS candidate despite the
historical directory name `reviewed-candidates`.

R1 then failed while constructing the Candidate Information-Set Review
package. The CIR observation cited raw trajectory lines 20, 24, 28, 30, and
32. Those complete JSONL turns were 1,128, 13,117, 5,262, 12,729, and 3,606
bytes. `scripts/run_qfbench_lineage_controller.py` serialized the complete
turns into a 35,891-byte excerpt, exceeding its 24,000-byte bound, and raised:

```text
LineageError: workflow trajectory excerpt exceeds the Review bound
```

The cited material was fresh answer-free Worker content and structured tool
calls, including code; it was not official, verifier, expected-value, reward,
score, or hidden diagnostic material. The byte bound therefore detected an
oversized representation, not an answer-boundary violation.

The package-builder call was outside the controller's `LineageError` handler,
and the outer global scheduler caught only `GlobalSchedulerError`. The
exception consequently exited the systemd service with status 1 instead of
recording a controlled information-set `HOLD`. The global scheduler state
remained stale at `RUNNING/PANELS`, with H0-only accounting. No Review package
or verdict was created.

## Downstream execution, accounting, and cleanup

Actual downstream counts were zero Reviewer calls, zero candidate Worker
cells, and zero of twelve planned matched cells. There was no binary matched
reward, panel decision, answer-free handoff, later panel, sealed task, or
same-stop resume.

The four H0 cells used 96 completed requests, 2,025,035 tokens, and
$0.087611724. The completed Evolver used 22 requests, 2,123,105 tokens, and
$0.063318604. The exact forensic aggregate from the completed child artifacts
is therefore **118 requests, 4,148,140 tokens, and $0.150930328**. The stale
global scheduler state retained only 96 requests, 2,025,035 tokens, and
$0.087611724; it omitted the completed proposal because the uncaught exception
prevented import and terminal reconciliation.

All 19 child Worker, Verifier, Evolver, proxy, and network lifecycle records
were cleaned by exact ID. The crash left the health timer active, so cleanup
was not initially terminal. After its manual stop, the final live audit at
2026-08-25 04:08:39 +08:00 found zero related process, container, network,
volume, transient service/timer, or follow-on dispatch. The retained run tree
and read-only pre-Review snapshot are forensic artifacts, not live residue.

## Decision and claim boundary

R1 is retained as `FAIL_ENGINEERING_PRE_REVIEW`. It demonstrates that four
fresh cells, the answer-free bank, an admitted one-skill ACT, and exact
pre-Review freezing were reachable. It does **not** evaluate Reviewer policy
v2: there was no Reviewer call or verdict. It also does not validate the
snapshot-to-Worker path, matched scheduler, binary reward, handoff, resume, or
automatic cleanup/accounting terminal.

Main remains `NO-GO`. R1 is terminal and must not be resumed or reused. Its
candidate, claim, snapshot, evidence/access state, score, controller state, and
decision cannot seed a later qualification or Main. Any repair requires a
separately frozen source, plan, run identity, launch decision, and fresh
evidence. This result supports no candidate quality, benchmark gain,
promotion, reusable harness, sealed result, main readiness, or QRS
effectiveness claim.

The compact canonical record is
[`QF_QRS_REVIEWER_POLICY_V2_QUALIFICATION_R1_RESULT.json`](../../data/breadth/QF_QRS_REVIEWER_POLICY_V2_QUALIFICATION_R1_RESULT.json).
