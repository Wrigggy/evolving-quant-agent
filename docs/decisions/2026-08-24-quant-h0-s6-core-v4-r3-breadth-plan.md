# Quant-H0-S6-Core-v4 R3 structured-state gate and breadth plan

Date: 2026-08-24
Status: Frozen, not yet run

## Decision

Core-v3 is retained as a protocol failure and is not expanded. Its R2 gate
showed three incompatible text-marker behaviors: terminal retrospective
backfill on Swap, premature normal termination after a standalone S1 marker on
Holdings, and partially interleaved markers emitted only after substantive
evidence work on FX. The trusted text parser was syntactically green on two
cells, but a role-and-turn chronology audit found zero of three complete
transition-timed traces.

Core-v4 replaces text markers with one passive structured
`record_quant_state` tool. The tool accepts only `stage`, `action`, and a short
public summary, returns a constant nonterminal acknowledgement, and performs no
file I/O, shell execution, quantitative computation, correctness check,
artifact inspection, evaluator access, or next-step recommendation. The
existing shell tool and descriptor remain byte-identical. Model, provider,
runtime, budgets, stage meanings, public task inputs, and verifier remain
fixed.

The trusted runner now preserves genuine NexAU structured tool-call and result
blocks alongside the existing flattened trace text. Core-v4 protocol parsing
uses only those structured blocks. Prose, shell commands, stdout, direct text,
or final-response backfill cannot create a state event. Recorder calls must be
isolated successful turns; only skill loading may precede S1 ENTER; calls after
S6 COMPLETE are rejected.

## Protocol gate

Run exactly one new Core-v4-only gate under
`qf-quant-h0-s6-core-v4-protocol-gate-20260824-r3` on the unchanged construct
tasks:

1. `swap-curve-bootstrap-ois`
2. `13f-amendment-aware-crowding`
3. `fx-forward-cross-rate`

All three Worker/verifier observations must be valid and all three structured
traces must realize ordered S1--S6 transitions with no malformed, failed,
mixed-tool, pre-S1 substantive, revisit, or post-S6 issue. Official scores are
recorded but cannot authorize breadth. Any failure stops with zero breadth
dispatch.

## Conditional 12-task breadth

If and only if the gate passes, run the already frozen Legacy Quant-H0 versus
Core breadth map. The selector, eligible pool, exact tasks, six-domain
stratification, two task strata per domain, arm-order reversal, metrics,
thresholds, and budgets are unchanged from the Core-v3 freeze. Repetition 1 is
24 Worker/verifier cells over 12 tasks. Repetition 2 is frozen but remains
conditional on a complete, valid, reconciled first repetition.

The headline unit is the native task/repetition binary reward, not pooled raw
properties. Report every per-task passed/total vector, paired win--tie--loss,
per-task means, within-domain means, and the equal-domain macro. Headroom is
considered operationally retained only when at least six of twelve tasks are
non-full in at least one repetition and at least four of six domains contain
such a task. If Core is full in both repetitions on at least ten tasks and
fewer than six passed properties remain across all Core cells, retain the
strong scaffold and select a harder public panel by a separately frozen
outcome-blind rule; do not weaken Core to manufacture QRS headroom.

## Claim boundary

Core-v4 is a disclosed human-authored thin six-state scaffold plus passive
structured observability. Recorder calls, model turns, tokens, cost, and wall
time are part of the Core treatment. This experiment does not isolate the
causal effect of state labels alone and does not test QRS, Evolver, Candidate
Review, AHE, stable promotion, sealed generalization, or QFBench-wide
superiority. The 12 tasks are historically exposed public development tasks,
and deliberate selection plus all exact task IDs must be disclosed.

Executable plan:
`data/breadth/QF_QUANT_H0_S6_CORE_V4_BREADTH_PLAN.json`.
