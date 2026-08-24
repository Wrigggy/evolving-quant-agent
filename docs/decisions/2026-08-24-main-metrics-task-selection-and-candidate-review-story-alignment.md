# Main metrics, task selection, and candidate-review story alignment

Date: 2026-08-24
Status: accepted prospective design; main experiment remains `NO-GO`

## Decision

The paper will describe one end-to-end object: evolution of a frozen-model
quantitative research harness from public evidence, with a mandatory
information-boundary review before any changed harness reaches a fresh Worker.
The Reviewer in this boundary is the **Candidate Information-Set Reviewer**.
It reviews the candidate, not the Worker answer and not the benchmark score.

The main comparison will use three roles:

1. Quant-H0, the frozen unevolved reference harness;
2. a matched Generic full-harness Evolver using the same public trajectory and
   artifact evidence but no Quant Research State representation; and
3. the QRS-guided full-harness Evolver, whose treatment is the State Card and
   state-, relation-, and component-conditioned retrieval and routing.

Generic and QRS receive the same model, provider route, Quant-H0 start,
mutation surface, public evidence, family order, budget, admission checks,
Candidate Information-Set Review, Worker, verifier, repeat policy, and
protection policy. Each arm maintains its own cumulative incumbent. Candidates
and outcomes are never shared across arms after treatment begins.

Unless a faithful AHE reproduction is separately implemented and audited, the
paper will call the Generic arm a **matched generic trajectory-guided
full-harness baseline**, not “AHE-on-quant.” The optional Quant Research
Reviewer remains a search aid and is not the Candidate Information-Set
Reviewer or a required main-treatment component.

## Why raw-file blindness was insufficient

The retrospective provenance audit found that all six previously evaluated
development candidates contained at least one answer-rich semantic projection.
The raw optimize-only diagnostic was not placed in the Worker context. The
failure occurred one step earlier: the Evolver translated a diagnostic-only
predicate into a Worker-visible prompt, tool implementation, descriptor, or
automatic profile. For example, a diagnostic exposed that a hidden evaluator
rejected a raw SVI intercept at zero; a later candidate encoded `a > 0` as a
standard admissibility rule even though the public task contract did not state
that rule. The Worker therefore received the hidden answer semantics through
the harness rather than through the original file.

This is not data leakage at the file-transfer layer. It is information leakage
at the claim layer. “The Worker did not receive the diagnostic file” is true
but insufficient. The required condition is that every decision-changing
Worker-visible claim is supported by information the blind Worker is allowed
to possess.

## Mandatory Candidate Information-Set Review

Every admitted changed candidate in every search arm must enter a pre-Worker
Candidate Information-Set Review. The trusted controller, not the Evolver,
constructs the review package from:

- the complete cumulative Quant-H0-to-candidate Worker-visible material;
- a complete inventory of decision-changing claims and their changed surfaces;
- the public task contract and any independent reference frozen before the
  candidate was proposed; and
- optimize-only material, when present, solely to identify a forbidden origin,
  never as positive support.

The Reviewer is arm-blind and uses the same criteria for Generic and QRS. It
must assess both claim support and coverage of all changed Worker-visible
surfaces. A claim passes only when a cited public contract or predeclared
independent reference entails the rule that will reach the Worker. A
diagnostic-only claim is rejected. Unsupported but non-contradicted claims are
inconclusive. An undeclared decision-changing exposure makes coverage
incomplete. Only overall `PASS` plus complete coverage permits a fresh Worker;
`REJECT` or `INCONCLUSIVE` holds the candidate for refinement or stops the
lineage.

The Candidate Information-Set Reviewer cannot edit the harness, call the
Worker, observe a sealed outcome, or promote a candidate. A `PASS` means only
that the candidate is eligible for blind evaluation. Official gain, repetition,
protection, and sealed performance remain separate downstream observations.
Reviewer calls, tokens, time, and cost are included in the arm accounting.

## Task-family selection

Purposeful human selection is permitted for mechanism development, but it must
be disclosed. The paper will not describe a deliberately selected task panel
as if it were an unselected benchmark sample. Before the first main proposal,
the experiment record must publish:

- the complete candidate-task pool considered;
- task-level inclusion and exclusion criteria;
- the task-family stratification and the person-independent selection rule
  within each stratum;
- the selected target, repeat, protection, and sealed roles;
- the freeze time; and
- every excluded task with its exclusion reason.

The development panel may deliberately emphasize tasks with valid runtimes,
publicly auditable contracts, nontrivial fresh Quant-H0 headroom, and a matched
answer-free protection task. This makes it a mechanism-development panel, not
an estimate of performance on the entire benchmark distribution.

The sealed panel must be frozen before the first main optimization run from the
remaining eligible tasks, stratified by family, and evaluated once per frozen
final incumbent. Sealed outcomes never enter proposal, retrieval, refinement,
promotion, or task selection. No task used to choose, debug, or refine a
candidate is called sealed or out of sample.

## Primary and secondary metrics

The paper will use two primary endpoints because development selection and
final generalization answer different questions.

### Development primary: stable-promotion rate

A candidate opportunity is a predeclared family-round within an independent
cumulative lineage. Its success indicator is one only if all of the following
hold:

1. a nonempty candidate is admitted and receives Candidate Information-Set
   Review `PASS` with complete coverage;
2. the blind target Worker yields a strict official improvement with no
   introduced failed property and a nonempty resolved-property footprint;
3. an independent repeat reproduces the same resolved-property footprint with
   no new failed property; and
4. the matched answer-free protection task is aggregate-safe and property-set
   safe.

Stable-promotion rate is the number of successful opportunities divided by the
fixed number of predeclared opportunities with valid matched execution.
`ABSTAIN`, rejected admission, Reviewer `REJECT` or `INCONCLUSIVE`, no-gain
targets, inconsistent repeats, and unsafe protection all remain visible in this
denominator. An observation that remains infrastructure-invalid after the one
frozen setup recovery is reported as operational attrition; the affected
Generic--QRS pair is omitted from the scientific rate under a predeclared
paired-missingness rule, and a companion intent-to-run sensitivity rate counts
it as zero. It may not be replaced by a new task, route, budget, or unreported
best-of-N attempt.

### Final primary: sealed official performance

After each arm's cumulative lineage is complete, its final incumbent is frozen
and evaluated on the sealed panel. The paper reports the complete task reward
and property vectors. To prevent a large family from dominating, it also
reports an equal-weight task mean within each family followed by an equal-weight
macro across families. The Quant-H0, Generic, and QRS vectors are shown
together; the macro never replaces the per-task values.

### Secondary diagnostics and efficiency

The proposal, admission, Reviewer, Worker-exposure or component-activation,
Research-State correction, target-gain, repeat-consistency, and
protection-safety stages form one diagnostic funnel. Their rates explain where
an arm succeeds or stops; they are not independent benchmark victories.
Efficiency metrics are total model requests, tokens, provider cost, verifier
calls, and wall time per lineage and to the first stable promotion. A lineage
without a stable promotion is reported as censored at its full frozen budget,
not omitted.

The statistical unit is the independent cumulative lineage, not each task
within a lineage. Within-lineage family outcomes share an incumbent and are
dependent. At least four independent lineages per arm are preferred for a
paper-level comparison, with counterbalanced family order. Two per arm is a
descriptive mechanism study only and will not support a broad superiority or
significance claim.

## Relationship to retained development results

All historical official scores, controller decisions, costs, and runtime facts
remain measured records. The provenance audit changes their interpretation,
not their values. Search-v2, A0, R4, and Final-H0 no longer establish a clean
reusable harness gain because their evaluated candidates were contaminated by
answer-rich semantic projection. They remain useful development evidence about
controller behavior, repeat instability, protection, and the observed need for
the pre-Worker review.

The public-only holdings line then demonstrated the intended boundary in live
use: complete claim coverage can coexist with insufficient public support, and
the Reviewer can hold a candidate before any Worker or verifier runs. The
credit-migration proposal calibrated `ABSTAIN` when a public artifact mismatch
had ambiguous semantics. The EVT-POT-VaR prescreen stopped as runtime-invalid
for mechanism selection after the prescribed dependency was unavailable.
None supplies the still-missing paper readiness result.

## Main readiness and next experiment

Main readiness remains `NO-GO`. Before launching the comparative main wave,
the repository must retain at least one fresh candidate that:

1. is proposed only from public-contract and answer-free trajectory evidence;
2. passes the mandatory arm-blind Candidate Information-Set Review with complete
   cumulative-surface coverage;
3. is evaluated by a blind fresh Worker; and
4. produces a retained strict official improvement.

Repeat and protection are additionally required before calling that candidate
stable or promoted. This bounded public-only readiness experiment should be
completed before spending on the multi-lineage matched Generic-versus-QRS main
wave. The main protocol, task pool, selection rule, family order, lineages,
budgets, and sealed panel must then be frozen in a separate executable plan.

## Claim boundary

This decision defines the prospective method, metrics, and disclosure policy.
It is not an experiment result. The existing Reviewer canaries establish
bounded discrimination and live pre-Worker holding behavior, not infallibility.
No clean public-only Worker gain, stable promotion, Generic-versus-QRS
superiority, or sealed improvement has yet been measured.
