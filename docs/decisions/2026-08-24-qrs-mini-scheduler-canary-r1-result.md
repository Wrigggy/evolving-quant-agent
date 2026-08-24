# QRS mini scheduler R1 retained setup-invalid result

> Date: 2026-08-24 · Experiment: `qf-qrs-mini-scheduler-canary-20260824-r1` · Decision: setup-invalid; Main `NO-GO`

## Measured setup and outcome

R1 was the first live four-task control-plane canary for the externally frozen
Primitive-H0. It ran fresh development Workers on
`13f-amendment-aware-crowding`, `dupire-local-vol`, `localvol-barrier`, and
`swap-curve-bootstrap-ois`, materialized four valid runtime histories, and
built the answer-free panel bank. The descriptive official records were
48/51, 67/68, 39/39, and 19/19. They are retained to reconstruct the run, not
to select a baseline or estimate a QRS effect.

The single Evolver session returned `ACT` and wrote a nonempty candidate across
the skill and system-prompt surfaces. The controller rejected admission before
Candidate Information-Set Review. The generated global-bank evidence contract
had omitted the structured `quant_property_v2` decision protocol, so the ACT
did not contain the required valid pre-write multi-role declaration. This is a
decision-plumbing setup failure. It is not a semantic Reviewer rejection and
does not measure whether the candidate would have helped a Worker.

Genuine Reviewer calls were zero. Candidate matched Worker cells were zero.
There was no reviewed snapshot dispatch, panel result, curriculum handoff,
promotion, sealed evaluation, or main reuse. The outer scheduler ended at
`STOP_PANEL` with the generic message `candidate Review returned no valid
terminal verdict`; the causal earlier failure was proposal admission.

## Exact accounting and artifacts

The four H0 cells used 157 completed requests, 8,034,288 tokens, and
$0.226392320. The Evolver proposal used 20 completed requests, 2,206,066
tokens, and $0.068323584. The exact total was 177 completed requests,
10,240,354 tokens, and $0.294715904. Reviewer and candidate-Worker accounting
were both zero.

The compact retained record is
[`QF_QRS_MINI_SCHEDULER_CANARY_R1_RESULT.json`](../../data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_R1_RESULT.json).
The local additive mirror is
[`results/bc-mirror/qf-qrs-mini-scheduler-canary-20260824-r1/`](../../results/bc-mirror/qf-qrs-mini-scheduler-canary-20260824-r1/),
including `trajectory-bank/TRAJECTORY-BANK-RESULT.json`,
`scheduler-state/SCHEDULER-RESULT.json`, and
`scheduler-state/panel-1-controller/CONTROLLER-RESULT.json`.

## Decision and boundary

R1 is retained as `FAIL_SETUP_INVALID`. It supports only that fresh H0 banking
worked and the controller blocked an ACT without the required structured
declaration. It supports no Candidate Review, candidate quality, benchmark
gain, stable promotion, sealed performance, or QRS-effectiveness claim.

A separately frozen R2 was permitted to repair only the observed structured
decision and pause/resume plumbing, rebuild every H0 trajectory and evidence
surface fresh, and preserve the same scientific setup. R1 material was not
eligible for R2 or Main.
