# Adversarial Novelty and Verification Positioning

Status: provisional research-story revision, 2026-08-19. This record refines
the same-day Quant Research Agent writing direction after an adversarial review
from the perspective of an Agentic Harness Engineering author. It proposes a
method and experiment boundary; it does not report a new experiment.

## Adversarial verdict

The current sentence, "quant systems evolve research outputs while QEA evolves
the Quant Research Worker Agent," is a useful motivation but is not by itself a
defensible novelty claim. Agentic Harness Engineering (AHE) already evolves a
frozen model's full prompt, tools, middleware, skills, sub-agent configuration,
and long-term memory from accumulated trajectories. It already records a root
cause, predicted fixes and regressions, next-round task deltas, file-level
rollback, component ablations, and frozen-harness transfer.

Therefore, changing the domain, benchmark, role name, or failure vocabulary
would still look like AHE applied to quantitative tasks. The repository's early
AHE-derived evolve--falsify--rollback and NexAU substrate must remain explicitly
attributed infrastructure or baseline material, outside the novelty claim.

AQuA creates a second boundary. It already retains validated quantitative
experiments to improve later factor hypotheses and model configurations under a
fixed research scaffold. QEA can still study a higher-level evolving object---
the Worker Agent harness---but this distinction becomes meaningful only if the
quantitative research process changes the evolution algorithm and verification
protocol rather than merely the terminology.

## Revised method candidate

The proposed differentiator is a **quant research-state intervention loop**.
The Evolver does not move directly from a generic failure summary to a harness
edit. It must construct and test the following chain:

```text
observed Worker trajectory
    -> competing explanations of the relevant quant research state
    -> predicted capability deficit
    -> reachable harness component
    -> predicted research-state transition
    -> component intervention
    -> fresh Worker trajectory
    -> intervention verdict
```

The Quant Research State is open rather than a closed benchmark-error list. It
may describe data and temporal scope, quantity semantics, estimation, portfolio
or execution state, empirical validation, and artifact delivery when those
states are relevant to the observed trajectory. Its research value must be
tested by whether it improves localization and evolution, not by whether its
field names sound financial.

The editable surface remains the complete Worker harness. A component
intervention may add or modify a prompt, executable tool, memory representation,
middleware, validator, routing rule, or workflow. The method should preserve
rejected, inactive, unstable, and effective interventions as later Evolver
experience.

## Verification is an intervention verdict, not a second benchmark

The official benchmark verifier remains fixed and identical for all methods.
QEA adds an **intervention verifier** that interprets the official result
together with the Worker trajectory. This avoids the false claim that AHE uses
only a simple scalar: AHE already verifies predicted edits against task-level
outcome deltas. The proposed difference is that QEA tests whether a predicted
quant research capability was actually mediated by the edited component.

The mutable Worker-side validator and the immutable official evaluator must be
kept conceptually and operationally distinct. The Evolver may improve how the
Worker checks its own work, but it may not edit the official evaluator or give
its hidden expected values to the Worker. Optimize diagnostics may be exposed
under the declared evidence policy; any task that changes candidate selection
is development evidence, and a sealed final result is collected only after the
harness is frozen.

For an intervention, record four observable questions:

1. **Reach and activation:** Did the fresh Worker encounter the relevant state
   and actually use the changed component?
2. **State correction:** Did the predicted quantitative-research behavior
   change, such as binding the intended quantity, respecting temporal scope,
   validating an estimator, or completing the required artifact?
3. **Artifact outcome:** Did the fixed official verifier improve at the
   property or task level?
4. **Stability and scope:** Does the effect survive an independent fresh Worker
   run, and does it avoid a declared protection regression or appear on a
   matched failure mechanism when such a task is available?

These questions produce informative non-binary verdicts before final
promotion:

- **inactive:** the component was not reached or used;
- **mislocalized:** the component activated but the predicted state did not
  change;
- **behaviorally effective but insufficient:** the state changed as predicted,
  but the official artifact outcome did not improve enough;
- **task-effective:** activation, state correction, and target outcome agree;
- **stable or reusable:** the effect repeats or transfers under a declared
  matched mechanism without protection regression.

Only official benchmark outcomes support benchmark-performance claims. The
intermediate verdicts support mechanism diagnosis and determine what experience
the next Evolver round receives. This makes verification part of search rather
than a post-hoc case-study label.

The existing T26 record illustrates why this distinction matters: a component
can pass a local smoke and be invoked by a Worker yet remain unstable at the
property level; another harness can improve a supplied artifact; a fresh blind
Worker result then tests whether the harness altered the full research process.
These are different claims and should not be collapsed into one score.

## Decisive AHE baseline

The final evaluation should include a faithful AHE-on-quant reproduction rather
than compare only against shell-only H0 or prompt mutation. Both methods should
share:

- the same minimal Worker seed and editable harness surface;
- the same Worker and Evolver model routes and reasoning settings;
- the same optimize task split, official verifier, rollout repetitions, and
  answer-access policy;
- the same maximum model-token or verifier-call budget;
- the same frozen final task split and no-feedback rule.

The controlled difference should be the evolution evidence and promotion rule:

- **AHE baseline:** generic layered trajectory reports, generic root-cause
  attribution, change manifest, and task-delta verdicts;
- **QEA:** competing quant research-state hypotheses, predicted component-
  mediated state transitions, and the activation/state/outcome intervention
  verdict above.

Useful measurements are frozen final binary reward, property completion where
officially available, gain per Worker or verifier call, frequency of inactive
or mislocalized edits, stability across fresh repeats, and matched transfer or
protection outcomes. A stronger final result would show that QEA reaches more
official task solves or reaches them with fewer expensive evaluations while
producing fewer inactive or falsely attributed components.

Two additional controls address the strongest alternative explanations:

- a compute-matched repeated-Worker or sequential-refinement baseline tests
  whether the gain comes only from spending the same budget on more attempts;
- an AQuA-style state-only baseline retains validated research memory and
  hypothesis history while freezing tools, middleware, validators, routing,
  and workflow, testing whether full-harness adaptation is necessary.

These controls may be smaller than the main AHE comparison during the mechanism
phase, but a broad benchmark claim cannot attribute gains to harness evolution
without accounting for additional sampling and fixed-harness experience.

## Minimum ablations

The smallest convincing set is:

1. H0, with no evolution;
2. prompt-only evolution;
3. faithful AHE-on-quant under the matched budget;
4. QEA without quant research-state diagnosis, using generic failure summaries;
5. full QEA;
6. full QEA with mechanism-mediated promotion replaced by task-score-only
   promotion, if budget permits.

The central comparison is 3 versus 5. Comparisons 4 and 6 test whether the
claimed method contributes beyond a domain label and post-hoc analysis.

The cleanest diagnosis experiment is a two-by-two comparison:

| Proposal evidence | Candidate verdict |
|---|---|
| generic layered trajectory diagnosis | next-round task delta |
| quant-state diagnosis with competing causes | next-round task delta |
| generic layered trajectory diagnosis | activation/state/outcome verdict |
| quant-state diagnosis with competing causes | activation/state/outcome verdict |

If running four complete evolution campaigns is too expensive, reuse a shared
pool of already proposed candidates: let both verdict methods judge the same
candidates, then run those candidates on an independent target/protection
panel. This isolates whether the intervention verifier predicts real activation,
improvement, and regression better than a task-delta verdict without requiring
four unconstrained searches.

## Claim that may survive the review

The paper should not claim to invent harness evolution or recursive
quantitative research. A defensible working claim is:

> We study harness evolution as quantitative research-state intervention. The
> Evolver converts Worker trajectories into competing hypotheses about the
> research process, predicts which harness component should mediate a specific
> state transition, and verifies the intervention through component activation,
> behavioral state correction, and fixed quantitative outcomes. This yields a
> more diagnostic and potentially more evaluation-efficient evolution loop than
> generic task-delta-driven harness engineering.

The compact story remains:

> AQuA improves the research generated under a fixed research scaffold. AHE
> evolves a general coding-agent harness from observable task deltas. QEA asks
> whether a quantitative research agent can evolve through verified
> interventions on its own research process.

This is provisional until the AHE-on-quant comparison and the diagnosis and
verification ablations are measured.

## Sources

- [Agentic Harness Engineering](https://arxiv.org/abs/2604.25850)
- [AQuA](https://arxiv.org/abs/2608.12841)
- [same-day Quant Research Agent writing direction](2026-08-19-iclr-quant-research-agent-evolution-writing-direction.md)
