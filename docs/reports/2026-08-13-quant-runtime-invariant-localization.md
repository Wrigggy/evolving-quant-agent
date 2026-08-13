# Quant runtime experience and public-invariant localization

Date: 2026-08-13

Status: measured engineering canary; autonomous discovery followed by an
investigator-seeded localization control; not a formal benchmark estimate

## Outcome

The runtime-experience mechanism is operational, but accumulated history alone
did not produce an autonomous candidate on the focused T12/T19 panel. Two real
Evolver activations both ended in calibrated ABSTAIN after reading prior
candidate diffs, outcomes, submitted-code facts, and answer-free Worker runtime
experience.

The first activation saw generic event/tool order. The evidence projection was
then extended to preserve coarse public-definition retrieval, data inspection,
candidate revision, synthetic check, and public-probe outcome order. Replay of
four prior T12 traces showed that every branch eventually passed the existing
public probe even though official results ranged from 8/16 to 16/16. The second
activation used this richer contrast and still ABSTAINed: another optional
free-form probe was not a supported causal intervention.

An investigator-seeded localization control then replaced Worker-authored
expected-value code with a declarative quant-invariant tool. The initial tool
correctly computed the operation selected by the Worker, but still allowed the
Worker to cite “average return” while declaring an additive sum. That first
canary scored only 8/16. The observed mismatch motivated one bounded repair:
the tool now binds public quantity vocabulary to the operation it computes:

- `average_return` uses the arithmetic mean;
- `cumulative_return` uses geometric compounding; and
- `additive_sum` is allowed only when the public definition explicitly states
  a sum.

The repaired harness solved T12 twice in independent Worker samples and
preserved the T19 protection task.

| Run | Role | Result | Requests | Tokens | Cost |
| --- | --- | ---: | ---: | ---: | ---: |
| `qce-runtime-experience-autonomous-activation-20260813-r1` | autonomous Evolver | calibrated ABSTAIN | 23 | 1,250,694 | $0.0294336896 |
| `qce-quant-runtime-actions-autonomous-activation-20260813-r2` | autonomous Evolver with action history | calibrated ABSTAIN | 22 | 1,659,130 | $0.0461811952 |
| `qce-quant-invariant-seeded-t12-20260813-r1` | initial seeded invariant | T12 8/16, reward 0 | 32 | 761,905 | $0.0207160072 |
| `qce-quant-invariant-seeded-t12-20260813-r2` | public-quantity-bound invariant | T12 16/16, reward 1 | 23 | 622,616 | $0.0237421464 |
| `qce-quant-invariant-seeded-t12-repeat1-20260813-r2` | independent repeat | T12 16/16, reward 1 | 17 | 360,994 | $0.0151102112 |
| `qce-quant-invariant-seeded-t19-protect-20260813-r2` | protection check | T19 18/18, reward 1 | 20 | 447,123 | $0.0196123480 |
| **Total** | | | **137** | **5,102,462** | **$0.1547955976** |

All provider requests completed successfully, fallback was disabled, and all
recorded containers and networks were cleaned. H0 was reused rather than
resampled.

## What the runtime evidence changed

The first action-history implementation was not itself a reward mechanism. It
made a previously hidden contrast inspectable:

- prior T12 Workers read the paper and data;
- they revised the strategy and exercised a public probe;
- every final branch obtained a passing free-form probe;
- passing that probe did not predict the official all-property outcome.

This eliminated the coarse explanation that failed Workers simply did not
test. It localized the problem to what the test represented. The old probe
allowed the Worker to choose both the public interpretation and the assertion,
so a coherent but wrong interpretation could self-confirm.

The declarative tool initially retained the same weakness one level higher:
it independently computed a declared sum but did not check whether the public
basis actually said average. The 8/16 canary exposed this directly. After the
operation was bound to public quantity vocabulary, the two independent T12
samples selected `average_return`, passed the final structured invariant, and
passed all official properties.

## Claim boundary

Measured:

- the richer runtime experience reached the Evolver and supported a more
  specific calibrated ABSTAIN;
- the old free-form probe was non-discriminating across the observed T12
  branches;
- the repaired public-quantity-bound invariant produced two consecutive T12
  full passes and one T19 full pass;
- the initial seeded invariant produced a negative 8/16 result before the
  observed mismatch was repaired.

Not measured:

- autonomous discovery of the final invariant component;
- improvement over a fairly repeated H0 distribution;
- transfer beyond T12/T19;
- a QuantCodeEval benchmark-level gain; or
- formal statistical reliability from two target repetitions.

The strongest current conclusion is mechanism viability: runtime experience
localized a non-discriminating self-authored test, and a public-definition-
bound executable component removed the observed definition drift in a small
focused panel. The final mechanism remains investigator-seeded and must be
made discoverable or reusable by the Evolver before it counts as autonomous
harness evolution.

## Next experiment

Do not immediately expand to the four-task or full public panel. First append
the negative 8/16 attempt, the two T12 solves, and the T19 protection outcome
to searchable experience. Give the Evolver the exact component and the causal
lesson: independently computing a Worker-declared operation was insufficient;
the public term had to bind the operation.

The next autonomous search should be allowed to `REUSE` or refine this
component for a new target, select a different public quantity vocabulary, or
ABSTAIN. A useful success criterion is an autonomous ACT that reuses the tool
without task-specific constants, activates it in the Worker, and improves one
new task while preserving T19. Only after that should the experiment expand or
estimate repeatability with more seeds.
