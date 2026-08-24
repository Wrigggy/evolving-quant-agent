# Quant-H0-S6-Core-v2 protocol repair and breadth plan

Date: 2026-08-24  
Status: Frozen, not yet run

## Decision

The first Legacy/Core/Full construct-calibration repetition is retained as a
valid development result, but its thin Core is not accepted as the QRS starting
substrate. Core was directionally stronger and cheaper in that repetition, yet
only one of its three valid cells produced a complete S1--S6 marker trace. Full
also completed the protocol in only one of three cells. The frozen terminal
condition `S6_PROTOCOL_NOT_REALIZED` therefore controls, and the as-is reverse
repetition will not run.

The next Worker revision is `Quant-H0-S6-Core-v2`. It changes only the observed
marker-execution boundary:

- an entered state must be completed before the next state begins;
- revisits must use the exact S5-to-S2/S3/S4 grammar;
- S6 must emit ENTER before COMPLETE;
- the Worker performs a terminal protocol audit and reports, rather than
  retroactively fabricating, an earlier omitted event.

Core-v2 adds no quantitative method, formula, estimator, data-cleaning rule,
artifact checklist, task identifier, expected value, hidden property, or
benchmark-specific convention. It keeps the same Worker model, shell tool and
descriptor, runtime, context, iteration budget, temperature, and verifier.

## Execution sequence

The frozen executable plan is
`data/breadth/QF_QUANT_H0_S6_CORE_V2_BREADTH_PLAN.json`.

1. Run a three-cell Core-v2-only protocol gate on the disclosed construct
   tasks used in the antecedent repetition. All three cells must be valid and
   must have complete, ordered, well-formed S1--S6 traces. Official scores are
   retained but cannot authorize the breadth phase.
2. If and only if the protocol gate passes, run newly scheduled matched
   executions for repetition 1 of a 12-task Legacy-versus-Core-v2 breadth map.
   The task identities and contracts are historically public/exposed
   development material, not unseen or sealed. They span all six repository
   manifest domains, with one low and one high repository-classified
   difficulty task per domain.
3. Audit all 24 matched cells before launching the separately frozen reverse
   ordering. Scores may not change the task set, grouping, Worker, provider,
   route, or budget.

S6-Full does not enter the breadth wave. Its role is exhausted by the
three-task construct calibration: it did not outperform Core and did not repair
marker reliability.

## Task-selection integrity

Breadth tasks are selected mechanically from
`MANIFEST_85_BASELINE.baseline.primary` using only public `task_id`, `domain`,
`difficulty`, `reward_kind`, and `resource_source` fields. Eligibility requires
binary reward so native reward and win--tie--loss are comparable, uses upstream
resources so a QEA-authored fallback contract is not an additional treatment,
and excludes the three disclosed construct-calibration tasks. This leaves 57
eligible development tasks, fully enumerated in the plan. The domain and
difficulty fields are repository-maintained public-contract taxonomy, not an
official randomized QFBench sampling frame. Within each domain and low/high
difficulty stratum, a fixed pre-run pseudorandom draw over sorted task IDs
selects one task. The test suite reconstructs the exact 12-task vector from the
pinned manifest.

No prior reward, property count, failed-property identity, verifier result,
Worker trace, artifact contents, or researcher preference after observing an
outcome may affect the selection. This is a deliberately stratified
development breadth map and must be disclosed as such. Selection is
outcome-blind, but the task identities are not historically unseen,
contamination-free, or sealed. The estimand is an equal-domain descriptive map
over the 57-task eligible development universe, not an unbiased estimate of
the full 77-task primary population.

## Metrics and interpretation

The primary unit is task by fresh repetition. Report:

- every Legacy and Core-v2 official reward and passed/total vector;
- paired win--tie--loss;
- equal-task means within domain and an equal-domain macro;
- marker completeness and protocol issues separately from correctness;
- turns, tool calls/errors, artifacts, requests, tokens, cost, and wall time.

The win--tie--loss unit is each of 24 matched task-repetition pairs. Average
the two repetition rewards within task, then the two tasks within domain, then
the six domain values with equal weight. For a non-full Legacy cell,
`headroom_closure=(Core_passed-Legacy_passed)/(total-Legacy_passed)` without
clipping; a full Legacy cell is N/A. Two repetitions provide descriptive
discordance and order reversal, not a stability, significance, or broad
superiority claim. Engineering retention also requires every Core cell to be
valid and aggregate Core cost, tokens, and Worker wall time each to remain at
or below 1.50 times Legacy.

Do not aggregate raw properties as the headline, because tasks expose
different property counts. Do not interpret marker completeness as correct
quantitative reasoning.

If Core-v2 is close to ceiling across the breadth panel, disclose the strength
of the human-authored substrate and screen a harder public development panel by
a new outcome-blind rule. Do not weaken Core-v2 to manufacture QRS headroom.
Tasks used for construct calibration or adaptive QRS target selection are not
sealed. A separate never-feedback panel remains necessary for final
generalization claims.

## Boundary relative to the main method

This plan calibrates a Worker substrate only. It contains no Evolver, Candidate
Information-Set Reviewer, candidate, promotion, AHE, or sealed evaluation. A
successful Core-v2 breadth result would not clear the QRS main gate. Main still
requires a QRS-only public/answer-free entrypoint, a universal review of the
exact effective cumulative candidate, fail-closed Worker dispatch, and a fresh
Review-PASS candidate that yields retained official gain without exposing
hidden answer semantics.
