# Post-AP-2M Quant Research Reviewer Canary

Status: accepted experiment-path revision, 2026-08-19. This decision inserts a
bounded Quant Research Reviewer mechanism test after AP-2M and before AP-3. It
does not claim that the Reviewer is implemented or effective.

## Naming and ordering

The repository's existing name is **AP-2M**; there is no prior `MP-2` record.
This decision interprets the discussion's `MP-2` as AP-2M and revises the
ordered path to:

```text
AP-2M warm-history autonomous-probe canary
    -> QR-1 Quant Research Reviewer canary
    -> AP-3 H0 autonomous bootstrap
```

AP-2M remains unchanged. It asks whether the Evolver can choose one Worker
experiment and make a feedback-grounded second decision. QR-1 then isolates a
different question: whether a task-conditioned quantitative review process can
identify and discriminate the Worker failure mechanism more accurately than a
generic trajectory summary or the existing failure-map labels. AP-3 uses the
Reviewer only if QR-1 passes its mechanism gates; otherwise AP-3 retains its
previous evidence path.

## Why this is a separate node

The existing broad failure classes and later stage-by-semantic-class map are
useful retrieval and reasoning aids, but neither reconstructs the task's
quantitative process or actively tests competing causes. The existing public
probes test a supplied semantic hypothesis; they do not generate the hypothesis
from the task, artifact, and trajectory.

Combining Reviewer construction with AP-2M would confound autonomous experiment
choice with research-state identification. QR-1 therefore starts only after the
AP-2M control loop has been judged on its original contract.

## Proposed Reviewer mechanism

For one Worker attempt, the Quant Research Reviewer receives the public task
contract, permitted task inputs and schemas, Worker trajectory, final artifact,
component-use observations, and the diagnostics allowed by the optimize-data
policy. It does not edit the Worker harness.

The Reviewer must:

1. reconstruct a small task-conditioned expected research-state graph;
2. reconstruct the realized process from the artifact and trajectory;
3. identify a concrete mismatch rather than only assign a failure label;
4. maintain at least two plausible explanations when the evidence permits;
5. choose one low-cost executable or artifact-based audit that discriminates
   those explanations, or return `insufficient_contrast`;
6. report the surviving capability diagnosis, expected corrected state, and
   possible harness loci without prescribing task-answer code.

The initial review lenses are non-exclusive and optional: information and
temporal integrity, data and universe integrity, quantity and estimation
semantics, portfolio and execution accounting, empirical validation, and
artifact or workflow state. They are search priors, not a closed failure
taxonomy.

## QR-1A: identification canary

Use a small controlled panel built from observed repository failures and simple
paired variants. Keep the first panel narrow:

- one temporal or fit-scope leakage case;
- one quantity or estimator-semantics case;
- one portfolio-timing or accounting case;
- one artifact-revision or delivery case;
- at least one ambiguous case for which abstention is correct.

Each case has a known injected or previously established mismatch, a nearby
alternative explanation, and one inexpensive discriminating audit. The cases
must not contain hidden final-test answers.

Compare, on the same evidence:

1. the current generic/two-axis failure-map diagnosis; and
2. the Quant Research Reviewer with task-conditioned state reconstruction and
   executable review.

Report:

- whether the true mechanism survives in the reviewer's final hypotheses;
- whether the adjacent explanation is correctly eliminated;
- whether the suggested capability and harness loci are compatible with the
  known mechanism;
- inappropriate leakage or finance-failure claims on non-applicable cases;
- calibrated `insufficient_contrast` on the ambiguous case;
- model calls, tool calls, and review cost.

QR-1A passes only if the Reviewer adds discrimination beyond relabeling the
failure map. A verbose finance critique without a correct state mismatch or a
probe-caused hypothesis update is a negative result.

## QR-1B: one live intervention canary

Only after QR-1A passes, choose one unresolved optimize task whose public
contract and retained trajectory expose at least two plausible mechanisms. Do
not default to T26 merely because it has extensive history; select the task
whose evidence can actually test Reviewer discrimination.

Run a minimal matched comparison:

- **generic arm:** current trajectory evidence and failure-map guidance;
- **reviewer arm:** the same evidence plus the QR-1 review and audit result.

Use the same initial harness, Evolver and Worker routes, mutation surface,
candidate budget, and official verifier. The Evolver remains responsible for
choosing and implementing the component; the Reviewer supplies diagnosis, not
the solution.

For each admitted candidate, record separately:

1. component reach and activation;
2. whether the predicted research-state transition occurred;
3. official property or task change;
4. independent repeat or protection evidence if the first result is positive;
5. calls, tokens, runtime, and cost.

The mechanism gate does not require an immediate benchmark-wide gain. It does
require the Reviewer arm to produce a better-grounded component intervention or
avoid a mislocalized intervention, and for the predicted state transition to
be observable in a fresh Worker. Official score improvement remains a separate
performance result.

## Relationship to AP-3

If QR-1A and QR-1B are positive, AP-3 starts from H0 under its existing evidence
and autonomy boundaries but inserts the Reviewer between the run-local H0
Worker and Evolver round one. The Reviewer may request only the bounded audit
allowed by the AP-3 coordinator. Evolver round two still receives the actual
Worker experiment result and owns retain, refine, rollback, compose, submit, or
ABSTAIN.

If Reviewer identification is no better than the failure map, its probes are
self-confirming, or its diagnosis does not influence an activated component,
do not make it part of AP-3. Preserve the negative result and continue AP-3
with the previously accepted generic evidence path.

## Claim boundary

Before QR-1, the project may say only that a Quant Research Reviewer is a
proposed post-AP-2M mechanism. A positive QR-1A supports task-conditioned quant
failure identification on the controlled panel. A positive QR-1B additionally
supports Reviewer-guided component localization on one live task. Neither alone
supports benchmark-wide performance, general quantitative-research ability, or
superiority to AHE.

The later faithful AHE-on-quant comparison remains necessary for the paper's
broader method claim.
