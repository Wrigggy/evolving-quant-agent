# QFBench QRS coordinated-gate selectivity result

Date: 2026-08-24
Status: retained proposal-only canary; recall positive, predeclared selectivity negative

## Decision

Retain the two-case gate canary as a mixed proposal-level result. G+ recovered
the predeclared known-positive local-volatility opportunity with a legal,
admitted, nonempty `ACT`. G- unexpectedly also returned a legal, admitted,
nonempty `ACT`, whereas the frozen selectivity criterion required calibrated
`ABSTAIN`. The frozen plan therefore stopped immediately after G- and launched
no Worker.

The canary supports recovered proposal recall on one known-positive case, but
it fails the predeclared two-case selectivity test. It does not yet establish
that G- was a semantic false positive: the Evolver grounded a reusable
final-weight-state reconciliation relation in both the holdings target and the
successful Brinson contrast. The experimenter-assigned negative-control label
therefore needs re-audit before attributing the result entirely to gate
over-admission.

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

The scientific interpretation is less binary than the protocol verdict. The
proposal cited a well-formed final weight-state artifact, counts-derived
turnover, self-referential summary validation, and the successful Brinson
trajectory as a contrast satisfying the same reconciliation family. That does
not prove the candidate would improve the official task, but it makes the
negative-control label contestable. A label audit should distinguish a genuine
reusable-but-unproven opportunity from indiscriminate gate admission.

## Accounting and operations

Together the proposals used 67 completed requests, 5,988,143 tokens, and
$0.176595660. There were zero retries, Worker dispatches, verifier executions,
service restarts, or related runtime residue.

## Interpretation and boundary

The gate repair recovered one known-positive intervention opportunity and
allowed both Evolvers to produce locally executable candidates. However, the
predeclared outcome was selective `ACT`/`ABSTAIN`, not simply two valid diffs.
Because G- also acted, the selectivity gate failed by its frozen criterion.

This is proposal-level search behavior only. It supports neither benchmark
gain, Worker activation, candidate quality, stable promotion, QRS superiority,
a population precision/selectivity estimate, sealed performance, nor component
causality. The G- result should be retained rather than relabeled after the
fact; any re-audit changes the interpretation of the control, not the measured
unexpected `ACT`.

## Artifacts

- Compact result: `data/breadth/QF_QRS_COORDINATED_GATE_SELECTIVITY_RESULT.json`
- Frozen plan: `data/breadth/QF_QRS_COORDINATED_GATE_SELECTIVITY_PLAN.json`
- G+ proposal mirror:
  `results/bc-mirror/qf-qrs-coordinated-gate-selectivity-20260824-r1-localvol-positive-proposal/`
- G- proposal mirror:
  `results/bc-mirror/qf-qrs-coordinated-gate-selectivity-20260824-r1-holdings-negative-proposal/`
