# QFBench coordinated local-vol result

Date: 2026-08-21

## Outcome

The bounded multi-task experiment now has one local official binary gain, but
not a promotable pair-level candidate. Starting from two corrected QFBench
trajectories, the Evolver autonomously selected a shared surface/calibration
validation mechanism and later refined it from runtime feedback. A normal-
budget fresh Worker under that frozen candidate solved `dupire-local-vol` at
68/68 and reward 1, compared with the retained same-model Quant-H0 result of
67/68 and reward 0. The same unchanged candidate then scored 36/39 and reward
0.92 on `localvol-barrier`, below its corrected retained comparator of 38/39
and reward 0.96. The protection gate therefore failed and the candidate is not
promoted.

## Why the task panel changed

The original fixed pairs were selected from historical QFBench scores. Two
evaluator integration bugs were found before interpreting those scores:

1. public task inputs were not staged at the paths expected by Workers; and
2. some official checkers looked for the output directory through
   `OUTPUT_DIR`, while the runtime only populated `/app/output`.

After both fixes, zero-model replay of retained artifacts made 14 of 16 old A6
tasks full reward. The original rates and corporate-action low-score screens
were therefore invalid as search evidence. A corrected options screen retained
two nearby residuals: `dupire-local-vol` at 67/68 and `localvol-barrier` at
38/39. The selected shared object became calibration and strict invariants of
an option surface before downstream local-vol pricing.

Two other branches remain useful negative results. A full-budget comparison on
`localvol-barrier` before the corrected pair scored 0/7 for both Quant-H0 and
the candidate. A holdings pair gave the Evolver one 46/51 trajectory and one
42/42 trajectory; it cited both and returned calibrated ABSTAIN because the
remaining issues were task-specific rather than one reusable mechanism.

## Autonomous search and feedback

In `mtpair-localvol-calibration-20260821-r1`, the Evolver issued ACT and built a
multi-file `validate_surface_artifacts` component. Its ten-request fresh probe
wrote a pipeline outside the output directory but ended before producing an
artifact or calling the component.

The follow-up view preserved the prediction, candidate diff, answer-free
Worker trace, score, and execution observation. In
`mtpair-localvol-calibration-feedback-20260821-r3`, the Evolver cited that
history, selected `REFINE`, and changed three surfaces:

- the system prompt now asks for incremental artifact writes and early
  validation;
- the tool description treats a partial output directory as an actionable
  construction checklist; and
- the executable validator reports missing standard deliverables instead of a
  passive success.

The Evolver also increased the bounded probe from ten to twelve requests. That
probe still ended with no artifacts or component calls after sequential code
errors. This is a negative short-probe result, not evidence that the frozen
candidate could not work with a normal budget. The feedback campaign used 35
completed requests; known usage was 1,924,715 tokens and $0.096348284, with one
completed response missing provider usage.

## Fresh target confirmation

The experimenter then dispatched the frozen r3 candidate on a seedless fresh
`dupire-local-vol` Worker with the candidate's normal 60-iteration limit. This
was a confirmation run, not another autonomous Evolver-selected probe.

The Worker wrote artifacts incrementally, called
`validate_surface_artifacts` five times, revised its surface construction and
delivery contracts, and completed eight outputs. The official verifier passed
all 68 checks, producing reward 1. The logical run survived two
`post_accept_transport` replacements. Across all three attempt segments it had
60 completed model requests, 3,578,594 tokens, and $0.096793984 in known
provider cost; the cost is a lower bound because the two quarantined requests
have unknown billing status. The final Worker used 50 turns and 50 tool calls
over 1,947.288 seconds.

This is the first measured QFBench chain in this route where an autonomously
refined executable component was activated by a fresh Worker and coincided
with an official binary target improvement.

## Protection result

The unchanged frozen candidate was then run at normal budget on
`localvol-barrier`. It called the validator three times and completed all
required artifacts, but the official verifier passed 36/39 checks and returned
reward 0.92. The failures covered two interior local-vol values and the
local-vol Monte Carlo vanilla-price consistency check. This run used 52
completed requests, 5,686,821 tokens, and $0.151399300.

The candidate therefore regressed relative to the corrected 38/39, reward-0.96
comparator. The fixed pair's promotion condition is not met. Do not describe
the result as stable transfer, pair-level improvement, or benchmark-wide gain.

## Mechanism conclusions

Measured conclusions:

- multi-trajectory evidence can lead the Evolver to an executable, quant-
  specific artifact-validation component rather than prompt-only mutation;
- persisted runtime feedback changed the Evolver's next candidate and probe
  design;
- a fresh Worker actually used that component, and one official binary target
  gain was observed; and
- the same component is not automatically safe or helpful on a nearby task.

The short probe budgets were too small to estimate final candidate capability:
both bounded probes stopped before delivery, whereas the successful fresh run
needed 50 turns. The normal-budget Workers also spent many late turns on
repeated audit and numerical refinement. Search should next learn a bounded
completion/stopping policy and use protection evidence to refine component
scope. A broad scheduler remains deferred until this local regression is
addressed or a different candidate passes the same target-plus-protection
chain.

Compact machine-readable evidence:
`data/breadth/MT_LOCALVOL_R3_RESULT.json`.
