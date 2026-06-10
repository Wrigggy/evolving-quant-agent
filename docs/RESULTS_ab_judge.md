# Result — judge-identity A/B: deepseek-v4-pro (self-judging) vs qwen3.7-max

Same frozen submissions, same deterministic A/B anonymization orderings → all
disagreement attributable to judge identity. S0 = the aa_qwen_test run's frozen
seed anchor (30 tasks); S1 = fresh seed sample; C1 = fresh sample from the
incumbent that kept the `financial_calculator` edit. k=2 votes/match.
Data quality: 0 empty deliverables, 0 excluded tasks, 0 judge hard-failures
(v1 of this A/B was discarded — a proxy outage emptied ~all of C1; the run was
also blocked ~3h by a DeepSeek-provider 402 "Insufficient Balance" upstream
incident, auto-recovered by a probe watchdog).

## Headline numbers

| | deepseek-v4-pro | qwen3.7-max |
|---|---|---|
| null S1-vs-S0 win share (expect ~0.5) | 0.381 (margin 0.119) | 0.455 (margin 0.05) |
| effect C1-vs-S0 win share | 0.400 | 0.458 |
| Elo vs seed (anchor 1000) | 933 | 972 |
| keep decision | **False** | **False** |

Cross-judge agreement on identical matches: **null 93.8%** (15/16 mutually
decided; 1 direction flip), **effect 87.5%** (14/16; 2 flips). Most
disagreements are decided-vs-tie, not direction reversals.

## Conclusions

1. **Self-judging is not the dominant error source.** deepseek (same family as
   the worker) agrees with qwen on ~90% of mutually decided matches and reaches
   identical keep decisions. Using the ~3x-cheaper deepseek judge for the
   pairwise gate is defensible; qwen showed a smaller null deviation (0.05 vs
   0.119), so qwen stays the default judge.
2. **The aa_qwen_test iter-2 keep did NOT replicate.** On fresh candidate
   samples, the kept `financial_calculator` incumbent loses to seed under BOTH
   judges (0.40 / 0.46 vs the original anchor's 0.524). A single-sample
   pairwise win at n=30, k=2 (0.609 = 14/23 decided; binomial 95% CI roughly
   0.41–0.78) is not stable evidence. This matches the rubric diagnostic, which
   had *dropped* on that edit.
3. **Fix adopted:** the gate now has a replication step (loop.py) — when a
   candidate passes the win-share gate, its deliverables are regenerated and
   re-matched against the incumbent; only a replicated win is kept.

Artifacts: `results/ab_judge_v2/ab_judge.json` (verdicts, per-task
disagreements), `results/ab_judge_v2/submissions.json` (all graded texts).
