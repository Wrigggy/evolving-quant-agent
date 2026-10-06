# T29 directed Evolver registration: temporal_causality + executable fix required

## Status

Local registration only — not yet dispatched. This record describes the
diagnosis, evidence basis, and required intervention type for the next
registered T29 Evolver round. No model call, upload, or score change.

## Diagnosis summary

T29 (`cross-sectional-momentum`) scores 12/19 on the latest family own-pair
comparison (both arms). The task estimates cross-sectional momentum using
a predictive regression: the December 1994 predictor is paired with the
January 1995 response in the original Worker's `_is_pairs` construction
(strategy.py lines 265–274). This is a `temporal_causality` failure:

- `shift(-1)` on the return column moves the response forward by one row
- The IS/OOS mask filters on predictor date only, not response date  
- The last IS-dated predictor row can pair with the first OOS return row
- This makes the final regression coefficient dependent on a January 1995
  response that was not yet available at the December 1994 decision point

The [Oct 6 audit](../../../output/research-audits/20261006-t29-is-target-support/actual-public-notes.md)
runs seven check groups (PASS, exit0) on the original Worker CSVs. Key
findings:

- 678 monthly rows / 55 anomaly series / 55 BM panels
- All six fits contain 252 finite pairs; the final pair is Dec1994 predictor
  with Jan1995 response
- Predeclared +10bp market-response perturbation changes December market
  weight by 0.001893 — measurable counterfactual dependence

This is the same as-of violation structure as the `temporal_causality`
failure class in the Evolver contract.

## Why this round is different from earlier T29 work

Prior T29 observations were read-only diagnostics by the investigator. No
Evolver has been registered on T29 with this as-of framing. This is the
first registration that:

1. Names `temporal_causality` as the failure class
2. Requires an **executable** fix (see constraint below)
3. Provides the audit evidence as seed

## Prompt-skepticism constraint — REQUIRED

Per the Oct 6 2026 `evolver_systemprompt.md` update: `temporal_causality`
failure class **requires** at least one executable component alongside any
prompt change:

- Acceptable: `tools/` function that enforces as-of date filtering before
  regression; `validator/` that checks final pair timestamps; `skills/`
  with a reusable is_pairs builder
- **Not acceptable**: a prompt-only ACT reminding the Worker to "ensure
  data is point-in-time" — this does not deterministically enforce the fix

The Evolver must pass the persistence test: a Worker following a prompt
reminder can still produce the same failure on a different task instance
with different year boundaries. An executable fix that truncates the IS
pairs before regression cannot.

## Evidence available to the Evolver

- Public task instruction: T29 `instruction.md` (1974–1994 estimation,
  1995–2017 OOS fixed parameters)
- Original Worker artifact: `strategy.py` lines 265–293 (`_is_pairs`
  construction and regression loop)
- Original Worker trace: JSONL trace from
  `qr-family-own-pair-refinement-parent-qce-20261005-r1`
- Score: 12/19 binary 0 in both fresh parent and candidate arms
- No evaluator code, expected values, or reference answers

## Predicted mechanism

**Target Research State transition:** Research Operation → correct
point-in-time pair construction

**Predicted observable:** An executable function that filters `_is_pairs`
to exclude any row where the response timestamp falls outside the IS window
boundary will prevent the Dec1994/Jan1995 crossover. The fix is
task-agnostic: any task using `shift(-1)` pairing with a date mask needs
the same bounded response filter.

**Protection task:** T27 (already 17/18 with correct matched finite pairs
in the latest parent — do not regress this).

## Next step

Register a fresh E round on T29 using:
- Panel: `qr-family-own-pair-refinement-parent-qce-20261005-r1` (train split)
- Active task: T29
- Evidence tasks: T29 (plus optionally T24/T26 for context)
- Failure class: `temporal_causality`
- Component requirement: at least one of `tools/`, `validator/`, `skills/`
- Protection: T27 non-regression

This is the highest-priority QCE round because:
1. Clear executable fix path (truncate IS pairs at boundary date)
2. Diagnosis confirmed with 7-check audit
3. Cross-benchmark second evidence point if successful
4. Fits the research-method experimentation story: "learned to enforce
   as-of discipline as a reusable tool, not a one-time prompt"
