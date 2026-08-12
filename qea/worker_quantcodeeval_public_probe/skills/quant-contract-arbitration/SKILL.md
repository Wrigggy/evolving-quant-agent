---
name: quant-contract-arbitration
description: >-
  Use for quantitative coding tasks with competing return, window, lag,
  normalization, annualization, or grouping definitions. Converts public
  prose into discriminating executable examples before submission.
---

# Quant contract arbitration

Treat a plausible implementation as a hypothesis, not as its own test oracle.

1. Extract the quantity, observation frequency, window endpoints, aggregation
   operator, units, grouping keys, missing-data rule, and application date from
   the public instruction and paper.
2. List at least two plausible definitions and build the smallest fixture on
   which they differ. Record the public sentence or equation that selects one.
3. Compute the expected value directly in the probe. Do not call a candidate
   helper to produce both actual and expected values.
4. Perturb one current, one prior, one missing, and one boundary observation
   when those cases matter to the definition.
5. Keep the submitted module portable: data passed as an argument wins. For an
   unavoidable implicit public-data lookup, support `Path(__file__).parent /
   "data"`, `/app/data`, and `Path.cwd() / "data"`; do not depend only on the
   draft's original directory.

## Definition rules

- A cumulative or holding-period return is geometric:
  `prod(1 + r) - 1`, unless the public contract explicitly defines another
  operator.
- An average return is an arithmetic mean. A sum is a sum only when explicitly
  stated or when the mathematical definition is additive rather than a return.
- A sign rule maps positive, negative, and exact zero separately. Preserve NaN
  only for genuinely unavailable inputs; do not turn an exact zero into NaN.
- A value at time `t` described as known before trading at `t` must be unchanged
  when only the current realized return is perturbed.
- Equal weighting requires an explicit active set and denominator. Check zero
  signals and missing observations separately.
- Annualization depends on frequency: monthly mean uses 12 and monthly Sharpe
  uses square root of 12; daily analogues use the declared trading-day count.

If the instruction and paper genuinely do not distinguish two definitions,
state that uncertainty and prefer the conventional finance meaning above. Do
not hide the ambiguity behind a passing smoke test.
