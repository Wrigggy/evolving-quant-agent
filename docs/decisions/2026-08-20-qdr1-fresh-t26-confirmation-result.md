# QDR-1 fresh T26 harness confirmation

Date: 2026-08-20

## Question

P-v2 showed that phase-aware component use could repair a retained T26 artifact
from 12/17 to 14/17. This follow-up asks a different question: does the retained
harness also change a normal Worker trajectory when no prior strategy is
available?

## Setup

One answer-blind Worker received the public T26 instruction, public data and
paper text, shell access, and the retained QDR-1 r2
`check_quant_relations` component. No `strategy.py` was pre-staged. The Worker
had to construct `/app/output/strategy.py` from scratch.

The candidate prompt described an early declared-relations checkpoint. A
generic middleware fallback was configured for assistant turn 24, matching the
turn at which the earlier Quant-H0 trajectory first had a draft. The fallback
could require an applicability decision and protect work after a component
observation, but it could not write relation declarations, call the component,
edit the strategy, or inspect checker answers.

The retained comparison is the fresh Quant-H0 T26 attempt from AP-3 r3, which
scored 12/17 with reward zero.

## Measured trajectory

The Worker wrote its first parsable draft on assistant turn 10 and independently
called `check_quant_relations` on turn 12. This was twelve turns earlier than
the configured fallback, so the first activation came from the candidate
harness and Worker policy rather than middleware enforcement.

The first audit declared six public quantitative relations. It realized two
and returned four errors and four warnings. The Worker used these findings as a
repair agenda, rewrote the strategy, and re-audited on turn 15. The second call
realized all six relations with zero errors, zero warnings, and zero measured
truncation residual. It then ran public-data smokes and delivered the artifact.

The official verifier passed 15/17 properties, a net gain of three over the
12/17 Quant-H0 comparison; binary reward remained zero. A3, B3, B5, and B9
changed from failure to pass, while B7 changed from pass to failure. The result
therefore contains four repairs and one regression rather than monotone
property improvement.

The run completed 40 model requests in 767.525 seconds and cost $0.182935552,
with no rate-limit retry. The Worker first declared the work complete on turn
27, but completion middleware continued to request additional post-observation
transitions through turn 40. Those calls produced more smokes and re-audits but
were unnecessary for establishing the first clean re-audit and initial
completion. This is a measured efficiency defect to repair before scaling.

## Conclusion

This is positive fresh-trajectory evidence. The retained harness did more than
patch a seed artifact: it caused a no-seed Worker to activate the quantitative
component, act on its findings, and obtain a net official property gain. The
fact that activation preceded the fallback checkpoint makes this stronger than
a forced-tool-call result.

It is still one adaptive optimize-task observation. The unchanged binary
reward, B7 regression, lack of repeat, and absence of transfer prevent a
stability or benchmark-level performance claim. The next experiment starts
again from Quant-H0 at the harness level: the Evolver may index retained
optimize evidence, while every Worker remains answer-blind. Before multi-task
coordination, that run should test whether the outer loop can select, refine,
and submit a useful candidate without experimenter promotion.

Evidence is mirrored at
`results/bc-mirror/qce-t26-qdr1-fresh-confirmation-20260820-r1/`; the compact
record is `data/quantcodeeval/QDR1_FRESH_T26_CONFIRMATION_RESULT.json`.
