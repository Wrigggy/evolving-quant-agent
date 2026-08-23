# QFBench QRS coordinated-gate selectivity result

Date: 2026-08-24
Status: retained proposal-only canary; recall positive, predeclared selectivity negative

Superseding interpretation: two independent read-only audits classify G- as
`INVALID_SEMANTIC_NEGATIVE_CONTROL`. The frozen procedural criterion still
failed, but the G- ACT is not evidence of semantic over-admission. Its candidate
must not be run or retained unchanged because it embeds an answer-rich
serialization convention that is stricter than the public contract.

A separate answer-boundary audit rejects the concrete G+ candidate as well.
The public instruction does not specify SVI `a>0`; the optimize-only diagnostic
revealed the hidden `a==0`/`a>0` predicate, and the candidate copied strict
`a>0` plus exact-bound rejection into Worker-visible tool code, description,
and prompt. G+ remains evidence that the revised gate recovered proposal
eligibility, not that it constructed an evaluation-eligible candidate.

## Decision

Retain the two-case gate canary as a mixed proposal-level result. G+ recovered
the predeclared known-positive local-volatility opportunity with a legal,
admitted, nonempty `ACT`. G- unexpectedly also returned a legal, admitted,
nonempty `ACT`, whereas the frozen selectivity criterion required calibrated
`ABSTAIN`. The frozen plan therefore stopped immediately after G- and launched
no Worker.

The canary supports recovered proposal recall on one known-positive case, but
it fails the predeclared two-case procedural selectivity test. Two subsequent
read-only audits agree that G- is not a valid semantic negative control. The
Evolver grounded a plausible final-weight-state reconciliation stress case in
both the holdings target and successful Brinson contrast, so its ACT does not
show that the revised gate indiscriminately over-admitted a mechanism.

## Frozen setup

- Both proposal runs started from Quant-H0 and reused the Final-H0 QRS evidence
  views. No new parent Worker was run.
- G+ was the R4-backed local-volatility case, labeled known-positive only in the
  experiment design. R4 artifacts and outcomes were not exposed to the Evolver.
- G- was the holdings case predeclared as a selectivity negative control.
- The stop rule required G+ `ACT` and G- `ABSTAIN`. Any G- mutation stopped the
  plan before target, repeat, or protection evaluation.
- Optimize diagnostics remained Evolver-only. No Worker saw answers, expected
  values, or trusted verifier diagnostics.

## G+: local-volatility recall case

The Evolver returned an admitted, nonempty `ACT` and created
`audit_surface_artifacts`. Its selected relation was
`written_surface_parameter_admissibility`, localized to
`evaluation_reconciliation`. The proposal added executable checks over written
surface artifacts, including strict SVI parameter admissibility, and changed
the tool registration, descriptor, system prompt, and executable tool.

All three grouped component smokes passed. The proposal used 40 completed
requests, 2,870,880 tokens, and $0.084221288. This satisfies the G+ proposal
recall criterion. It does not show Worker activation or benchmark improvement
because the plan never reached the Worker stage.

The later answer-boundary audit found that this candidate must not reach that
stage. The public task asks for the surface artifacts and observable diagnostics
but does not state the strict SVI condition `a>0`. The answer-rich optimization
diagnostic exposed that the hidden failure was `a==0` and the expected predicate
was `a>0`. The candidate then hard-coded `a>0` and exact-bound rejection into
`audit_surface_artifacts`, its Worker-visible description, and the system
prompt. Although the Evolver was permitted to use the diagnostic for diagnosis,
the hidden answer could not be persisted in a reusable candidate or passed to a
blind Worker. Therefore G+ retains only the measured proposal-eligibility
recovery; its concrete candidate is rejected and must not be run or retained.

## G-: holdings selectivity control

Instead of the expected `ABSTAIN`, the Evolver returned an admitted, nonempty
`ACT` and created `reconcile_portfolio_state`. It selected
`final_state_downstream_reconciliation`, arguing that downstream turnover and
summary artifacts should be reproducible from the final effective-holdings
weight state and use native pair typing. The proposal changed the tool
registration, descriptor, system prompt, and executable tool.

Both grouped component smokes passed. The proposal used 27 completed requests,
3,117,263 tokens, and $0.092374372. Under the frozen experimental definition,
this is a failed G- selectivity outcome, so no Worker was dispatched.

The proposal cited a well-formed final weight-state artifact, counts-derived
turnover, self-referential summary validation, and the successful Brinson
trajectory as a contrast satisfying the same reconciliation family. Both
read-only audits therefore classify the case as
`INVALID_SEMANTIC_NEGATIVE_CONTROL`: it is a plausible reconciliation stress
case, not a clean situation in which calibrated abstention is semantically
required.

The audits also found a separate research-integrity defect in the candidate.
The public instruction says that any unambiguous manager-pair encoding is
acceptable, while the candidate requires a two-element array. That stricter
serialization convention came from answer-rich optimization evidence rather
than the public contract. The candidate must not be run or retained unchanged.
Only the general final-state reconciliation mechanism remains a legitimate
hypothesis; it must be separated from the answer-derived pair-encoding rule
before any future Worker evaluation.

## Accounting and operations

Together the proposals used 67 completed requests, 5,988,143 tokens, and
$0.176595660. There were zero retries, Worker dispatches, verifier executions,
service restarts, or related runtime residue.

## Interpretation and boundary

The gate repair recovered one known-positive intervention opportunity and
allowed both Evolvers to produce locally executable candidates. However, the
predeclared outcome was selective `ACT`/`ABSTAIN`, not simply two valid diffs.
Because G- also acted, the selectivity gate failed by its frozen criterion.

That procedural failure is not a semantic precision result. The negative
control was invalid, so the experiment cannot determine whether the revised
gate over-admits unsupported candidates. Conversely, a plausible relation and
passing smokes do not make the concrete G- candidate runnable: its answer-rich
pair-serialization requirement violates the reusable-candidate boundary.

The same structural-admission-versus-research-integrity distinction applies to
G+. Admission and local smokes show that the gate can produce an executable
mutation, but they do not certify that its semantics came from public evidence.
Here the decisive strict-SVI predicate came from the answer-rich diagnostic and
crossed into Worker-visible surfaces. Neither concrete candidate is therefore
eligible for target evaluation, even though the frozen plan stopped first on
the G- procedural event.

This is proposal-level search behavior only. It supports neither benchmark
gain, Worker activation, candidate quality, stable promotion, QRS superiority,
a population precision/selectivity estimate, sealed performance, nor component
causality. The measured unexpected `ACT` and frozen stop remain unchanged; the
superseding audit changes only their scientific interpretation and rejects the
unchanged G- candidate from further evaluation. The G+ answer-boundary audit
likewise rejects its concrete candidate without changing the measured proposal
decision, admission, smokes, or accounting.

## Artifacts

- Compact result: `data/breadth/QF_QRS_COORDINATED_GATE_SELECTIVITY_RESULT.json`
- Frozen plan: `data/breadth/QF_QRS_COORDINATED_GATE_SELECTIVITY_PLAN.json`
- G+ proposal mirror:
  `results/bc-mirror/qf-qrs-coordinated-gate-selectivity-20260824-r1-localvol-positive-proposal/`
- G- proposal mirror:
  `results/bc-mirror/qf-qrs-coordinated-gate-selectivity-20260824-r1-holdings-negative-proposal/`
