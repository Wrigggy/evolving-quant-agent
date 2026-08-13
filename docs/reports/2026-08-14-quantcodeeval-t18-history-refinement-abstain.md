# QuantCodeEval T18 History-Guided Refinement

Date: 2026-08-14  
Status: measured calibrated abstention; no candidate benchmark run

## Question

After an autonomously discovered T18 warmup-boundary component activated but
left the official score unchanged, can the Evolver use that failed intervention
as searchable runtime experience, eliminate it, and either identify a better
bounded component or abstain instead of repeating or guessing?

## Setup

- Target/protection evidence panel: T18/T19.
- Evolver route: `deepseek/deepseek-v4-flash-0731`, required provider
  `deepseek`, no fallback.
- H0 was reused, not resampled: T18 Type A `2/4`, Type B `14/14`; T19 `18/18`.
- Prior activation:
  `/data/qea-julius-storage/runs/qce-component-route-t18-20260814-r1`.
- Prior scored candidate:
  `/data/qea-julius-storage/runs/qce-component-route-t18-candidate-20260814-r1`.
- Current run:
  `/data/qea-julius-storage/runs/qce-component-refine-t18-20260814-r2`.

The current evidence contained the prior decision, exact candidate diff,
component tests, answer-free official outcome, and final scored Worker artifact.
The updated component ledger marked `warmup_boundary_arbitration` as fully
activated but unsupported. No checker details, hidden property definitions, or
reference answers were exposed.

## Result

The Evolver returned legal `ABSTAIN` and left the harness unchanged. It cited
the prior history entry, prior diff, relevant-experience view, component ledger,
T18 instruction and paper, T18 H0 summaries, and T19 protection summary.

Its elimination was evidence-based:

- the prior Worker loaded the evolved skill, ran an exactly-120 fixture, and
  changed the classifier flip index;
- T18 nevertheless remained exactly Type A `2/4` plus Type B `14/14`;
- therefore the warmup flip index was empirically score-invariant and should
  not be repeated;
- the weight-cap formula already matched the public contract and did not
  warrant an intervention.

Two mechanisms survived but were not publicly identifiable:

1. inclusive percentile thresholds versus strict thresholds or rank-count
   quintile membership;
2. first-month `NaN` versus zero behavior under sample versus population
   standard deviation.

The instruction and paper do not uniquely select among those conventions in
the authorized evidence tier. The failing two Type A property definitions are
also unavailable. The Evolver therefore refused to hard-code one reading and
correctly produced no candidate.

## Cost and stop

The finalized proxy audit recorded 24 completed requests, 1,807,639 tokens, and
$0.0492410744. No candidate benchmark evaluation was launched, so there was no
Worker or verifier cost and no T18/T19 resampling. All containers were cleaned.

The persisted search-state round recorded one request and zero cost because the
ABSTAIN path finalized before reconciling the proxy audit. The top-level proxy
audit is the authoritative accounting record for this run. A focused fix now
reconciles finalized proxy usage into future ABSTAIN search states; this run was
not repeated or historically rewritten.

## Interpretation

This is positive evidence for cumulative Evolver experience even though it is
not a benchmark improvement. The Evolver did more than see the previous edit:
it used the measured tie to eliminate that intervention, preserved the still
viable competitors, and stopped when public evidence could not identify a
bounded component with a discriminating prediction.

The current T18 search branch should stop here. Another T18 mutation under the
same answer-free evidence would be guesswork. The next informative experiment
should either obtain a new public discriminating observation or move this
history-guided component-search protocol to another task where public/runtime
evidence can distinguish the remaining mechanisms.

