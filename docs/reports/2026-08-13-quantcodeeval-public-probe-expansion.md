# QuantCodeEval public behavior-probe expansion

Date: 2026-08-13

Status: measured engineering canary; investigator-authored mechanism; not a
formal benchmark estimate

## Outcome

The four-task public-data expansion is operational and produced a useful
mechanism-localization result. An investigator-authored worker added two
components to the ordinary shell worker:

- a `quant-contract-arbitration` skill for distinguishing competing finance
  definitions; and
- a `probe_public_behavior` tool that imports the draft strategy in a fresh
  temporary directory and executes independently calculated assertions using
  only public task inputs.

The final fresh four-task run scored `T01=0, T12=0, T18=0, T19=1`, for a task
mean of `0.25`. This matches the binary vector obtained by transferring the
autonomous r8 static-audit candidate, but it does not imply the two mechanisms
are equivalent. The behavior probe was activated on T01, T12, and T19; T18
exhausted one long generation path before writing a candidate. A separate T18
retry wrote a candidate, activated the probe, and still reproduced H0's
`16/18` property result.

The strongest result is therefore not a universal score gain. It is a
localization result:

1. Public executable probes can change generated quantitative definitions and
   can produce a fully correct candidate on T12 in one sample.
2. The same T12 mechanism is not stable: a fresh panel sample passed `12/16`,
   not `16/16`.
3. T01 and T18 did not improve even when the mechanism was available or fully
   activated.
4. T19 passed under both the autonomous r8 static audit and the manual public
   behavior probe, making it the current positive transfer task but not yet
   identifying which component is necessary.

## Experimental sequence

All worker calls used `deepseek/deepseek-v4-flash-0731` through DeepSeek with
no fallback. The rootless worker, verifier, and model-proxy setup was unchanged
within these comparisons. H0 was sampled before the candidate mechanisms; its
saved artifacts were replayed through the corrected verifier without model
calls.

| Stage | T01 | T12 | T18 | T19 | Requests | Tokens | Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| H0 replay | 2/17 | 14/16 | 16/18 | 16/18 | 121 sampling requests | 2,890,386 | $0.1000396712 |
| autonomous r8 transfer | 2/17 | 8/16 | 16/18 | 18/18 | 62 | 1,233,285 | $0.0569713984 |
| manual probe v1, T12 only | - | 7/16 | - | - | 13 | 203,616 | $0.0105279832 |
| manual probe v2, T12 only | - | 16/16 | - | - | 22 | 460,404 | $0.0174447056 |
| manual probe v2, fresh panel | 2/17 | 12/16 | no artifact | 18/18 | 68 | 1,776,058 | $0.0833991200 |
| manual probe v2, T18 retry | - | - | 16/18 | - | 24 | 921,144 | $0.0352327584 |

The fractions are property passes, not partial official rewards. QuantCodeEval
uses an all-properties gate, so only the two `18/18` T19 rows and the
single-task `16/16` T12 row have official reward 1. The H0 sampling count
includes the original expansion run plus the T19 retry; verifier replay used
zero additional model requests.

The four manual-mechanism runs together used 127 requests, 3,361,222 tokens,
and `$0.1466045672`. They are distinct diagnostic samples and must not be
pooled as repeated formal benchmark trials.

## What activated

The final fresh panel retained complete traces:

| Task | Probe trace mentions | Skill trace mentions | Worker outcome |
| --- | ---: | ---: | --- |
| T01 | 9 | 5 | candidate written; 2/17 |
| T12 | 2 | 5 | candidate written; 12/16 |
| T18 | 0 | 0 | no candidate after long responses |
| T19 | 9 | 5 | candidate written; 18/18 |

The T18 retry recorded 10 probe mentions and 5 skill mentions, wrote a valid
candidate, and passed 16/18. This separates two effects: missing-artifact
completion is sampling-sensitive, while the unchanged T18 property result is
not explained by lack of component activation in the retry.

T12 also separates availability from reliability. The successful v2 sample
implemented an arithmetic prior-year average; the fresh panel sample selected
a geometric prior-period return and passed only 12/16. The skill exposed the
competing definitions and the tool ran, but the worker did not consistently
bind its asserted public basis to the implementation it finally submitted.
The next mechanism needs component state that preserves this decision and
checks candidate/probe consistency, not another longer prose reminder.

## Comparison with the autonomous r8 component

r8 was genuinely autonomous: the Evolver used accumulated answer-free history,
selected a static unit/structure audit, changed agent configuration, prompt,
tool description, and executable tool code, then passed component smoke and
candidate admission. Its expansion transfer improved T19 to 18/18 but regressed
T12 from 14/16 to 8/16.

The public-probe worker was investigator-authored to test a different causal
hypothesis after r9 falsified continued static-audit growth. It also passed
T19, had no effect on T01, reproduced H0 on the T18 retry, and showed a
high-variance T12 benefit. This makes the project-specific search problem more
concrete: components have conditional value, and successful search must learn
activation scope and retained decision state rather than globally accumulating
rules.

## Next autonomous experiment

Use the manual worker only as a diagnostic search parent, not as an official
incumbent. Give the Evolver the complete answer-free four-task contrast:

- T19: activated positive example;
- T01: activated but unchanged negative example;
- T12: one full pass followed by a 12/16 fresh sample, showing definition-state
  instability;
- T18: missing artifact in the panel, then activated 16/18 retry, separating
  completion from quant correctness.

Keep the full harness mutation surface open. The Evolver must compare at least
two mechanisms and choose the component itself. Plausible component locations
include conditional `routing`, persistent decision `memory`, executable
candidate/probe consistency validation, and early-draft completion state, but
these are investigator hypotheses rather than instructions to implement a
specific finalizer. Evaluate a candidate first with its own local component
smoke, then on this four-task panel. Preserve every rejected or scored attempt
in the existing history so subsequent rounds can read exact prior changes and
outcomes. Search remains variable-length and should stop on no new information,
calibrated abstention, a working mechanism, or budget—not an arbitrary five
rounds.

## Evidence and validation

The complete generated evidence is mirrored additively under:

- `results/bc-mirror/qce-expansion-h0-replay-fixed-20260813-r4/`
- `results/bc-mirror/qce-expansion-r8-candidate-20260813-r1/`
- `results/bc-mirror/qce-manual-public-probe-t12-20260813-r1/`
- `results/bc-mirror/qce-manual-public-probe-t12-20260813-r2/`
- `results/bc-mirror/qce-manual-public-probe-expansion-20260813-r1/`
- `results/bc-mirror/qce-manual-public-probe-t18-retry1-20260813/`

The final two services exited successfully. After each run, the remote host
reported zero experiment containers and zero experiment networks. The focused
adapter, candidate, replay, and retained-output suite passed `16 passed, 21
deselected` after the run.
