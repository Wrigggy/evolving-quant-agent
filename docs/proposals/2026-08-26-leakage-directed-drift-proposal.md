# Proposal: Leakage-Directed Drift in Agent Harness Evolution

**Status:** Draft for review
**Date:** 2026-08-26
**Supersedes:** the six-state-ontology framing as the headline claim
**Branch:** `qfbench-discovery-evolver`

---

## 1. The claim

> When an agent improves its own harness against a reward that is *silent about
> one dimension of correctness*, the search drifts toward violating that
> dimension. Quantitative research is the domain where this is structurally
> sharp and measurable, because lookahead makes an artifact **simultaneously
> more wrong and better scored**.

This is a pathology of self-improvement that existing agent benchmarks cannot
exhibit. On TerminalBench, SWE-bench, AppWorld, or GDPval, a harness that
"cheats" is caught by the tests, because the tests define correctness. In quant
research, a backtest that peeks at future information produces *cleaner* results
and passes *more* numerical-tolerance checks. The reward gradient points the
wrong way.

We propose to (a) verify this drift occurs, (b) measure its magnitude, and (c)
test whether an evolved point-in-time discipline suppresses it.

---

## 2. Why this angle, and not the previous ones

### 2.1 The six-state ontology is not defensible as a headline

The QRS contribution as currently written is a *representation* claim: six
Research States (mandate → evidence → representation → operation →
reconciliation → artifact) improve the Evolver's credit assignment. Three
problems:

1. **The states are not load-bearingly quant.** Relabel them for software
   engineering and the method is unchanged. The domain supplies vocabulary, not
   structure.
2. **A direct competitor already does the learned version.** The gated
   quality-diversity archive of [arxiv:2607.13683](https://arxiv.org/abs/2607.13683)
   keys patches on the *(where × why)* pathology an edit addresses, discovered
   rather than hand-authored, and reports positive sealed gains (+9 to +15.5 pp).
3. **No quant reader.** QFBench binary reward is coding correctness. The story
   makes no financial claim.

### 2.2 Selection-noise correction is largely scooped

An earlier draft of this proposal led with porting the finance multiple-testing
instruments (White's Reality Check, Harvey–Liu–Zhu, Bailey–López de Prado
Deflated Sharpe / PBO) to harness promotion. Adversarial literature check found:

- [arxiv:2607.13683](https://arxiv.org/abs/2607.13683) already runs K=3
  repetitions throughout, activation beacons, and a **paired 2σ credit gate**
  (z ≥ 1.96 on per-task paired differences). Its ablation already quantifies the
  thing we intended to measure: a single-run Δ>0 rule credits a genuinely
  neutral mechanism as a win ~60% of the time, and as a ≥3pp win ~25% of the time.
- Their argument that **no multiple-testing correction is needed for the credited
  number** is correct: the credited comparison is a single sealed evaluation, so
  candidate churn during development cannot inflate it. Researcher degrees of
  freedom are spent on train.

So "deflate the credited gain" solves a non-problem. What *does* survive is
narrower and is retained here as Contribution 2: a noisy promotion gate does not
bias the sealed number, it **wastes the search** — the lineage becomes a partial
random walk, the terminal harness is no better than H0, and the sealed panel
correctly reports zero. You spend the full cell budget to learn nothing.

### 2.3 The field has posed an open question that QFBench is built to answer

[arxiv:2607.12227](https://arxiv.org/abs/2607.12227) reports that harness
evolution **does not consistently beat test-time scaling** at matched compute on
TerminalBench: parallel sampling leads pass@1 (72.3 vs 67.4), and harness gains
appear only when multiple attempts can be filtered. The authors concede two
alternative explanations — TerminalBench scores are already high, and a shell
plus a basic prompt may cover most solvable tasks — and close with an explicit
recommendation: **test harness evolution on benchmarks that are both hard and
harness-sensitive.**

QFBench is measurably both. From the 85×5 repetition bank (77 primary tasks × 5
independent repetitions of the frozen base Worker):

| Property | Value |
|---|---|
| Binary pass rate | 0.4286 |
| Graded reward, task mean | 0.4385 |
| Tasks that always fail (0/5) | 33 |
| Tasks that always pass (5/5) | 19 |
| Flippable tasks | 25 |

43% pass rate leaves real headroom, and the domain requires data lineage,
convention discipline, and independent validation — exactly the harness surface.
**QEA is positioned to answer the open question the field's own critique paper
poses, on the benchmark it asks for.**

---

## 3. The structural precondition, verified

For leakage-directed drift to be testable, QFBench verifiers must *not* already
penalize lookahead. We audited the verifier criteria files:

```
data/qfbench/VERIFIER_CRITERIA_30.json
data/qfbench/VERIFIER_CRITERIA_TRAIN_30.json
```

Scanning all criterion names for `lookahead|point-in-time|as-of|future|restate|
amend|survivor|leak|shift|lag`: **zero criterion names match.** The tokens
`amend` and `lag` appear only incidentally elsewhere in the payload.

**QFBench does not check point-in-time correctness.** The reward is silent about
it. That is precisely the condition the hypothesis requires — and it is itself a
reportable finding about how agentic quant benchmarks are currently built.

### Leakage-exposed task inventory

From the family listing, tasks whose correctness depends on information timing:

- **data_engineering (4/5):** `13f-amendment-aware-crowding`,
  `corporate-action-adjustment`, `earnings-surprise-calculator`,
  `form4-cross-sectional-sale-pressure`
- **systematic_strategy (8/17):** `sma-crossover-spy`, `momentum-backtest`,
  `bollinger-backtest-aapl`, `cross-sectional-momentum`, `event-study-earnings`,
  `double-sort`, `residual-momentum`, `etf-cross-asset-lead-lag`
- **execution_microstructure (2/5):** `intraday-volume-fitting-and-execution-scheduling`,
  `binance-btc-participation-tca`
- **rates_fx_macro (1/11):** `fomc-tone-event-study`

Roughly **15 of 77 tasks** are structurally leakage-exposed.

### The built-in natural experiment

`13f-amendment-aware-crowding` is *explicitly* about amendment awareness — the
task statement itself demands as-of discipline, so leakage is at least partly
observable through its own tests. The plain backtests (`sma-crossover-spy`,
`momentum-backtest`, `bollinger-backtest-aapl`) have no such guard.

This gives a within-benchmark contrast requiring **no new task construction**:
evolve on leakage-unchecked tasks, then measure whether the promoted harness
degrades on leakage-*checked* tasks. It reuses the existing protection-task
machinery exactly as designed.

---

## 4. Contributions

### C1 — Leakage-directed drift (headline)

**Hypothesis H1.** Under a leakage-permissive reward, harness evolution promotes
components that increase measured reward *by* relaxing information-timing
discipline.

**Instrument.** An **as-of audit**: a deterministic, evaluator-side checker that
inspects a Worker artifact for information-timing violations — a feature computed
from a timestamp at or after the label it predicts, a join whose right side is
not filtered to as-of, a restated field consumed without vintage selection, a
universe defined from end-of-sample survivors, a fill/execution priced before the
signal that triggers it. The audit is **answer-free**: it reads the artifact's
data flow, not the gold values, so it can run on any attempt without touching
sealed material.

The audit is *not* part of the reward. It is a measurement channel, held outside
the Worker and outside the Evolver, exactly as the official verifier is today.
This preserves the firewall: the evolution loop optimizes the unchanged official
reward and never sees the leakage score.

**Design.**
1. **Baseline drift rate.** Run the as-of audit retrospectively over the 85×5
   bank (425 existing scored attempts, already on disk, zero model cost). Report
   the leakage rate of the *frozen* base Worker per task and per family. This
   establishes H0 drift with no new spend.
2. **Evolved drift rate.** Run the audit on every Phase-1 candidate attempt in
   the Main campaign. Report leakage rate as a function of promotion depth.
3. **The drift test.** Regress leakage rate on lineage depth. H1 predicts a
   positive slope: as the harness is optimized against a leakage-silent reward,
   leakage increases.
4. **The protection test.** Score the terminal harness on the leakage-*checked*
   subset. H1 predicts degradation there even if the official aggregate improves.

**Falsification.** A flat or negative slope, with promoted candidates showing no
leakage increase, falsifies H1. That is also informative: it would say the
harness mutation surface does not reach data handling, which localizes where
self-improvement can and cannot go.

**Why null is still publishable.** The instrument, the baseline drift measurement
on 425 existing attempts, and the finding that a quant agent benchmark contains
no point-in-time criteria all stand independently of the drift slope's sign.

### C2 — Evaluation design for hard, harness-sensitive domains

Answering [arxiv:2607.12227](https://arxiv.org/abs/2607.12227)'s open call
requires getting the statistics right first. Three measured results, all computed
from the 85×5 bank with zero model calls
(`scripts/analyze_evaluation_power.py`):

**(a) Effective sample size is a third of the nominal one.**
52 of 77 tasks (68%) are deterministic under repetition — 33 always fail, 19
always pass. Only 25 tasks can register any harness effect. A 12-task sealed
panel drawn 2-per-family contains **3.5 flippable tasks on average**, and 24% of
panels contain ≤2. Mean-reward deltas on small panels are far noisier than the
task count suggests. We are not aware of this being reported for agentic
benchmarks, and it applies to any pass@1 harness comparison.

**(b) The planned sealed endpoint is underpowered.**

| Sealed design: 12 tasks × 2 reps/arm | |
|---|---|
| sd(Δ) under the null | 0.068 |
| MDE, 80% power, α=0.05 | 0.190 |
| Equivalent reliable task flips | 2.28 of 12 |
| One reliable task flip | 1.23σ — not detectable |

Graded reward gives no relief: because the graded reward is itself near
all-or-nothing (51/77 tasks have zero within-task sd, flippable tasks have sd
≈ 0.45–0.55), sd(Δ) is 0.0678 graded versus 0.0675 binary. Prior mechanism
evidence (Search-v2: 1–2 task flips per family, with offsetting protection
regressions) sits *below* the detection threshold.

**(c) The deployed promotion gate is a coin-flip machine.**
The Main R2 gate requires no binary regression on focus ∪ anchors, a strictly
higher focus mean, and ≥1 focus win. It compares **one fresh candidate draw
against a single frozen cached parent draw**. Under the null of no true effect:

| Gate (identical cell cost) | P(promote \| no effect) | P(promote \| lift=0.30) | E[false promotions] / 12 visits | P(≥1 false) |
|---|---|---|---|---|
| deployed | 0.129 | 0.578 | **1.58** | **0.83** |
| net ≥2 focus tasks | 0.051 | 0.401 | 0.56 | 0.45 |
| net ≥3 focus tasks | 0.010 | 0.238 | 0.14 | 0.13 |

Two findings worth reporting:

- **The gate that looks strict is not.** "No regression anywhere" sounds
  conservative, but because the parent is a *frozen single noisy draw*, a lucky
  parent draw blocks a good candidate and an unlucky one waves through a neutral
  candidate. Expected spurious promotions per campaign: 1.58.
- **Adding repetitions to a zero-threshold gate makes it worse.** Going from 1 to
  3 paired repetitions with no threshold raised false promotion from 0.123 to
  0.175, because sharper estimates make "any positive mean difference" easier to
  satisfy. What buys false-positive control is a **threshold**, not precision.
  A net-≥2 rule cuts campaign false promotions 3× **at identical cost**.

This confirms and extends [arxiv:2607.13683](https://arxiv.org/abs/2607.13683)'s
ablation (single-run gates credit neutral mechanisms ~60% of the time) to a
different domain and a specific deployed gate, and it supplies the cost-matched
fix. We claim confirmation and extension, not discovery.

### C3 — QRS demoted to an ablated diagnosis substrate

The six Research States stay, as the layer that tells the Evolver *where to
look*. They stop being the contribution. The QRS-no-State ablation stays, but it
now answers a scoped question: does state-conditioned diagnosis change *which
leakage-relevant component* gets proposed? That is a question about search
behavior, not an ontology claim.

---

## 5. Experimental plan

### Phase A — zero-cost, immediate (no model calls)

| Step | Output |
|---|---|
| A1 | Implement the as-of audit as an evaluator-side checker with unit tests |
| A2 | Run it over the 425 attempts in the 85×5 bank → baseline leakage rate by task and family |
| A3 | Run it over all logged prior campaigns (30×5, Search-v2, MT-1, main0b) → retrospective drift |
| A4 | Freeze the power analysis and the gate comparison (`scripts/analyze_evaluation_power.py`) |
| A5 | Reviewer contamination-injection suite → catch rate and false-reject curve |

**A2 and A3 are the critical path.** If the frozen base Worker already leaks on a
measurable fraction of leakage-exposed tasks, C1 has an effect to grow from and
the headline is established before any paid run. Cost: zero.

### Phase B — design revision before launch

| Step | Change |
|---|---|
| B1 | Replace the promotion gate with the net-≥2 threshold rule (same cost, 3× fewer false promotions) |
| B2 | Re-select the sealed panel to over-weight flippable and leakage-exposed tasks, and raise reps from 2 to 3 on the flippable subset only |
| B3 | Add the **test-time-scaling baseline** the field says is missing: best-of-K sampling from frozen H0 at cell cost matched to the whole evolution campaign |
| B4 | Add the leakage-checked protection subset as a fixed sentinel panel |

B3 is non-negotiable for credibility. Per
[arxiv:2607.12227](https://arxiv.org/abs/2607.12227), harness evolution loses to
parallel sampling at matched compute on at least one benchmark. A reviewer will
ask. Without this arm, the campaign cannot answer.

### Phase C — the main campaign

Unchanged in shape from Main R2 (Phase 0 bank → two six-family sweeps → sealed
endpoint), with the revised gate, the added baseline arm, and the as-of audit
running as a passive measurement channel on every attempt.

Cell budget: the existing ≤320 scientific cells plus the B3 baseline arm. The
audit adds zero cells because it is post-hoc analysis of artifacts already
produced.

---

## 6. What each outcome supports

| Outcome | Claim |
|---|---|
| Positive drift slope, degradation on leakage-checked tasks | **Self-improvement discovers reward hacking in a domain where the verifier is silent.** Headline. |
| Flat slope, no leakage increase | The harness surface does not reach data handling; localizes the reach of self-improvement. Plus the instrument and baseline stand. |
| Base Worker already leaks heavily | Agentic quant benchmarks systematically fail to test information timing. Reportable independent of evolution. |
| Sealed Δ ≈ 0 with net-≥2 gate | With false promotions cut 3×, a null is now interpretable as a real absence of transferable gain rather than a polluted lineage. |
| Best-of-K matches or beats evolution | Replicates 2607.12227 on a hard, harness-sensitive benchmark — a substantive negative result the field explicitly asked for. |

Every branch yields a statement. That is the property the current story lacks.

---

## 7. Honest risks

1. **The as-of audit may be hard to make precise.** Detecting lookahead from an
   artifact's data flow is a static-analysis problem with false positives.
   Mitigation: report per-rule precision on hand-labelled attempts from the 85×5
   bank before using the audit for any claim; prefer high-precision, low-recall
   rules and report recall honestly.
2. **Base leakage may be near zero.** If the frozen Worker rarely leaks, drift
   has little room. Mitigation: A2 tells us this for free, before commitment.
3. **15 leakage-exposed tasks is a small panel.** Drift slope estimates will be
   noisy. Mitigation: score leakage at the *rule-violation* level rather than
   task level for finer resolution, and treat the slope as descriptive.
4. **"Reward hacking" framing may overreach.** The Worker is not adversarial; it
   optimizes a reward that happens to be silent. Mitigation: use
   *specification-silent drift* in the paper and reserve the stronger term for
   the discussion.
5. **The three 2026 papers may contain more overlap than the fetched summaries
   reveal.** Mitigation: read all three in full before writing the related-work
   section. This proposal's positioning rests on fetched summaries, not full
   texts.

---

## 8. Decision requested

1. Approve the pivot: leakage-directed drift as headline, evaluation design as
   second contribution, QRS demoted to diagnosis substrate.
2. Authorize Phase A (zero model cost, entirely local, no paid run).
3. Confirm that B1–B4 revise the Main R2 method before launch, which requires a
   fresh method freeze and supersedes the 2026-08-25 two-sweep decision record.

Main R2 remains `frozen_method_not_launch_authorized`. Nothing in this proposal
authorizes a paid or remote run.

---

## 9. References

- White, H. (2000). A Reality Check for Data Snooping. *Econometrica* 68(5), 1097–1126.
- Harvey, C. R., Liu, Y., & Zhu, H. (2016). ...and the Cross-Section of Expected Returns. *RFS* 29(1), 5–68.
- Bailey, D. H., & López de Prado, M. (2014). The Deflated Sharpe Ratio. *Journal of Portfolio Management* 40(5), 94–107.
- Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2017). The Probability of Backtest Overfitting. *Journal of Computational Finance* 20(4), 39–69.
- Brown, S. J., Goetzmann, W. N., & Ross, S. A. (1995). Survival. *Journal of Finance* 50(3), 853–873.
- Lin, J., Liu, S., Pan, C., et al. (2026). *Agentic Harness Engineering*. arXiv:2604.25850.
- Lee, Y., Nair, R. S., Zhang, Q., et al. (2026). *Meta-Harness: End-to-End Optimization of Model Harnesses*. arXiv:2603.28052.
- *Rethinking the Evaluation of Harness Evolution for Agents* (2026). arXiv:2607.12227.
- *Self-Evolving Agent Harnesses via Gated Semantic Quality-Diversity* (2026). arXiv:2607.13683.
- *SEAGym: An Evaluation Environment for Self-Evolving LLM Agents* (2026). arXiv:2606.17546.
