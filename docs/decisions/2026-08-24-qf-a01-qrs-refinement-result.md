# QFBench A0.1 QRS refinement result

Date: 2026-08-24  
Status: retained negative after a valid target-stage rollback

## Decision

Retain A0.1 as a complete negative refinement lineage. R1 and R2 exposed two
different orchestration failures before a valid candidate could be measured.
R3 removed those ambiguities: the Evolver changed the executable component,
the fresh Worker called it, and the fixed controller compared the candidate
against the retained 67/68 parent. The candidate remained 67/68, reward zero,
so the controller correctly rolled it back after target and did not spend on
repeat or protection.

This does not support benchmark gain or stable harness improvement. It does
support a narrower mechanism diagnosis: the refined checker was active, but
the Worker failed to translate one public contract clause into the predicates
passed to that checker.

## Retained lineage

### R1: State Card gate abstention

The Evolver recovered a concrete refinement hypothesis from the A0 target and
repeat: prevent caller-loosened SVI positivity checks and extend completeness
checking to required numeric table cells. The mandatory State Card interface
then rejected every proposed ACT relation with `ACT selected relation has no
support`. The middleware ledger records eight materialization attempts; the
Evolver summary described seven. With no accepted card, the Evolver returned
`ABSTAIN`, no candidate was admitted, and no Worker stage was launched.

R1 used 27 completed requests, 3,107,331 tokens, and $0.078508572. It is an
interface-gated calibrated abstention, not evidence against the refinement
hypothesis and not a benchmark result.

### R2: invalid empty-diff ACT

After the State Card schema was made usable, the Evolver declared `ACT` and
named `tools`, `systemprompt`, and `tool_descriptions`. The materialized
candidate nevertheless had an empty diff, zero changed files, no actual
component roles, `measurement_only=true`, and
`declared_roles_match_actual=false`. The old admission path checked that the
copied worker directory was structurally runnable but did not require it to
differ from the parent, so it admitted the unchanged snapshot and advanced the
controller to `TARGET`.

No R2 target Worker was launched. R2 used 19 completed requests, 1,980,265
tokens, and $0.095760508. Treat it as an invalid ACT and an observed admission
bug, not as a candidate or benchmark result.

### R3: valid activation without official gain

R3 produced the valid `qf-a01-localvol-qrs-c2-r3` candidate. It changed
`systemprompt.md`, the `check_parameter_admissibility` descriptor, and
`tools/admissibility.py`; declared and actual component roles matched. The
refinement made strict-positive predicates non-loosenable by an inclusive zero
floor, treated missing values in declared strict-positive columns as
violations, and extended checking beyond fitted-parameter tables.

The fresh `dupire-local-vol` Worker called
`check_parameter_admissibility` ten times, including twice on
`svi_params.csv`. The component was therefore available and activated. Both
SVI calls, however, declared only `T`, `b`, `sigma`, and `rmse` as strictly
positive. They omitted `a`, even though the Evolver's predeclared Research-
State relation targeted strict positivity of that intercept. The checker
truthfully accepted the predicates it was given; the official verifier then
retained the same sole failure, `TestSVIParams::test_svi_a_positive`.

The comparison was 67/68, reward zero, for both parent and candidate. The
controller recorded `ACTIVATED_WITHOUT_OFFICIAL_GAIN`, returned `ROLLBACK` for
`target_gain_not_observed`, and stopped after target. Repeat and protection
were not run. Thus the observed gap is contract-to-predicate binding of `a`,
not checker non-activation.

R3 proposal used 28 completed requests, 2,683,796 tokens, and $0.070165888.
The target used 37 completed requests, 2,076,865 tokens, and $0.066999076. The
valid R3 proposal-plus-target path therefore used 65 completed requests,
4,760,661 tokens, and $0.137164964.

## Accounting

Across R1 proposal, R2 proposal, R3 proposal, and R3 target, the retained path
used 111 completed requests, 9,848,257 tokens, and $0.311434044. R1 and R2 are
kept because they explain why the lineage required three run identities; they
are engineering observations, not failed benchmark candidates.

## Interpretation and next boundary

A0.1 narrows the remaining search defect. A deterministic audit can only
enforce the predicates the Worker binds from the task contract. Tool reach,
repeated calls, and a green tool verdict do not establish that every relevant
contract variable was included. The next refinement should improve how the
Worker constructs or reviews contract-to-predicate bindings, while keeping the
checker general and answer-blind; hard-coding the task's expected value or
private property is neither needed nor permitted.

No official gain, repeat, protection, promotion, sealed result, or QRS-
superiority claim follows from this lineage. The valid measured contribution
is a target-stage rollback with a specific runtime mechanism observation.

## Evidence

- Compact result: `data/breadth/QF_A01_QRS_REFINEMENT_RESULT.json`
- R1 mirror:
  `results/bc-mirror/qf-a01-localvol-qrs-refine-20260823-r1-artifacts`
- R2 mirror:
  `results/bc-mirror/qf-a01-localvol-qrs-refine-20260824-r2-artifacts`
- R3 mirror:
  `results/bc-mirror/qf-a01-localvol-qrs-refine-20260824-r3-artifacts`
- Frozen plans: `data/breadth/QF_A01_QRS_REFINEMENT_PLAN.json`,
  `data/breadth/QF_A01_QRS_REFINEMENT_R2_PLAN.json`, and
  `data/breadth/QF_A01_QRS_REFINEMENT_R3_PLAN.json`
