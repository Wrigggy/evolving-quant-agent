# Cross-Benchmark Breadth Adapter Preflight — 2026-08-15

## Conclusion

The next breadth experiment is ready at the zero-model boundary. A thin
experience adapter now gives the Evolver one answer-free view over QFBench and
QuantCodeEval while leaving each benchmark's Worker contract and official
verifier separate. The QFBench evidence corpus builds from four real tasks, and
the newly staged QuantCodeEval T26 and T27 environments execute their official
golden programs and pass all checkers.

This preflight made no model calls, cost nothing, and is not a benchmark result.
Its purpose is to establish that the next paid experiment can test component
selection across more than the previously studied T18/T24 branches without
mixing benchmark-specific answer surfaces.

## Mechanism implemented

`qea/component_experience.py` builds a small, portable navigation corpus. Each
task card contains public task state, answer-free outcome, runtime summary,
Worker trace/artifact pointers, and a short list of relevant prior components.
The component cards retain both positive and negative experience so the
Evolver can reuse, refine, compose, reject, or abstain instead of repeatedly
inventing the same intervention.

The common layer is intentionally thin:

- shared: task-state cards, runtime experience, component evidence, retrieval,
  and search operators;
- benchmark-specific: candidate format, Worker execution, and official score;
- protected: reference answers and raw verifier details remain unavailable to
  the Evolver.

The retrieval rule is advisory public-term overlap, not an exhaustive finance
failure taxonomy. A no-match task remains free to synthesize a new component or
abstain. Components marked QuantCodeEval-only are not proposed for QFBench.

The preregistered engineering panel is in
`data/breadth/BREADTH_CANARY.json`. It contains two targets and one protection
from each benchmark:

| Benchmark | Target tasks | Protection tasks |
| --- | --- | --- |
| QuantCodeEval | T26, T27 | T19 |
| QFBench | swap-curve-bootstrap-ois, earnings-surprise-calculator | credit-spread-decomposition, historical-var-data-prep |

The paid phase is bounded to at most two Evolver calls per target, normally one
Worker call per target, at most eight Worker calls in total, 300 completed model
requests, and $0.60 provider cost. A successful target gets one repeat and one
protection check; a scored non-improvement, regression, or calibrated abstention
stops that branch.

## Measured preflight evidence

The real QFBench A6 authorized-evidence snapshot produced four task cards, five
component cards, and 47 files. Its frozen baselines are:

- swap-curve-bootstrap-ois: 17/19 in all five recorded repeats;
- earnings-surprise-calculator: 4/8 in all five recorded repeats;
- credit-spread-decomposition protection: 39/39 in all five repeats;
- historical-var-data-prep protection: 12/12 in all five repeats.

For QuantCodeEval, 161 public-release files for T26/T27 and their runtime support
were placed under
`/data/qea-julius-storage/benchmarks/quantcodeeval-breadth-source-20260815` on
the personal bc machine. The source occupies 11,009,685 bytes. No WRDS account
or data was used.

The official golden/checker smoke ran with networking disabled in the existing
Python 3.11.15 engineering-canary container:

- T26: golden completed; 17/17 checker properties passed;
- T27: golden completed; 18/18 checker properties passed.

The QFBench corpus build and focused adapter/fetch/component tests passed. The
test command was:

```text
.venv/bin/python -m pytest -q \
  tests/test_component_experience.py \
  tests/test_fetch_quantcodeeval_breadth_source.py \
  tests/test_quantcodeeval_components.py \
  tests/test_quantcodeeval_v2_evidence.py
```

Result: 14 passed. Python compilation and `git diff --check` also passed.

## Interpretation and next experiment

The preflight establishes breadth infrastructure, not component efficacy. The
next paid phase should first obtain answer-free H0 Worker experience for T26 and
T27, then build their task cards. The Evolver should receive the combined
cross-benchmark corpus and choose the component locus itself. We will compare
whether it reuses/refines a supported component, composes multiple components,
or synthesizes a new domain-specific state mechanism.

The smallest informative first batch is one QuantCodeEval target and one
QFBench target. Run a repeat and protection task only after an improvement.
This distinguishes three questions without expanding to the full benchmarks:

1. Can runtime history localize a useful component on an unseen task?
2. Can the same navigation mechanism work across two benchmark contracts?
3. Does composing more than one component help without damaging a known-good
   protection task?

Detailed machine-readable evidence is in
`results/cross-benchmark-breadth-preflight-20260815/RESULT.json`.
