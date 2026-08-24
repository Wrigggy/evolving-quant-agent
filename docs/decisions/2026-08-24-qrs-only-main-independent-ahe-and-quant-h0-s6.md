# QRS-only main, independent AHE baseline, and observable Quant-H0-S6

Date: 2026-08-24
Status: accepted prospective architecture; code migration and main experiment remain `NO-GO`
Supersedes: `2026-08-24-main-metrics-task-selection-and-candidate-review-story-alignment.md`

## Decision

The paper and final research code will no longer treat Generic and QRS as two
runtime arms of one main experiment. The prospective program has three
independent tracks:

1. **QRS-only main.** A cumulative QRS lineage starts from a newly frozen
   Quant-H0-S6, proposes only from public or answer-free evidence, passes a
   mandatory Candidate Information-Set Review, and then follows target,
   independent repeat, answer-free protection, freeze, and sealed evaluation.
   This is the headline method and the only evolution implementation retained
   in the final release code.
2. **QRS-no-State mechanism ablation.** A separately frozen executable removes
   State-Card construction and state-conditioned retrieval/routing while
   retaining the same H0-S6, public evidence, task order, model, budget,
   Candidate Review, and downstream controller. It tests the quantitative
   contribution of the Research-State representation. It is not called
   Generic, is not AHE, does not share candidates or post-treatment history
   with QRS, and is retained as an archival branch or experiment artifact
   rather than as a mode in the final release.
3. **Independent AHE reproduction.** AHE is reproduced from its own pinned
   implementation and lifecycle. Source-faithfulness is established before a
   minimal quantitative-task adapter is added. The reproduction remains in a
   separate repository or frozen branch and is reported as an external
   baseline, not as a `generic` switch inside QRS. A common Candidate
   Information-Set Review may be applied after AHE proposes a candidate and
   before the blind Worker, but that integrity gate is explicitly not part of
   AHE's search mechanism.

Historical Generic/QRS canaries remain immutable development records. Their
data, dated decisions, and claim-ledger rows are retained for research
integrity, but their executable Generic modes and paired-campaign launchers are
not part of the final QRS release path.

## Why the earlier matched-main design was wrong

The superseded design conflated two questions:

- whether a Quant Research State representation changes quantitative search;
- whether QRS compares favorably with a published generic harness-evolution
  method.

A no-State QRS ablation can answer the first question because it changes one
method element under the same controller. It cannot stand in for AHE. A
faithful AHE baseline must preserve AHE's own proposal and retention logic, so
it should not be implemented as a label inside the QRS runner. Conversely,
forcing AHE and QRS to share every internal promotion definition would weaken
baseline fidelity. Cross-method comparison therefore uses common frozen
inputs, official sealed outcomes, and resource accounting, while each method's
internal development trajectory is reported on its own terms.

## Answer boundary: current status is not solved

There are two distinct blindness questions.

1. **Raw-artifact isolation.** The rootless QFBench Worker does not receive
   verifier solutions, official property identities, optimize-only
   diagnostics, or Candidate Reviewer feedback. The latest public-only
   holdings R2, R3, and R4 lineages also stopped every non-`PASS` candidate
   before a Worker or verifier was dispatched.
2. **Semantic projection.** An Evolver can read allowed optimization feedback
   and translate a hidden predicate into a Worker-visible prompt, tool,
   descriptor, memory entry, routing rule, or runtime directive. The raw file
   can remain hidden while its answer semantics still reach the Worker.

The second problem is only conditionally controlled. Candidate
Information-Set Review currently works when explicitly enabled, but it is not
a repository-wide dispatch invariant:

- the lineage constructors and trusted controller retain an opt-in legacy path
  that can enter `TARGET` without Review;
- preconstructed candidates can start at `TARGET` even when a Review flag is
  present;
- the discovery runner can append an Evolver-authored Worker directive after
  admission and dispatch a selected probe outside Review;
- older QFBench and QuantCodeEval paths do not share one candidate-dispatch
  choke point;
- cumulative Quant-H0-to-candidate review is optional rather than mandatory;
- supplied public excerpts are not universally re-read and authenticated from
  a trusted public source; and
- structured claim inventory is contract-dependent rather than required for
  every QRS `ACT`.

No real public-only candidate has yet completed

```text
Review PASS -> exact reviewed harness -> blind Worker -> retained official gain.
```

The accurate status is therefore: the latest public-only path has a useful
fail-closed Reviewer and has live-validated the non-`PASS` stop, but the answer
boundary is not yet universally solved.

## Mandatory pre-Worker invariant

Before any main run, the code must enforce one rule at the actual Worker
dispatch boundary:

> Quant-H0-S6 is the only unevolved Worker that may run without Candidate
> Review. Every changed candidate must have a recorded `PASS` over the exact
> effective Worker material before it can reach any Worker.

Closing this rule requires all of the following:

1. missing Review is a plan error, not a supported legacy mode;
2. preconstructed candidates either enter Review or are forbidden in the main
   controller;
3. proposal generation is proposal-only; selected-probe direct dispatch is
   forbidden in the main path;
4. any extra Worker instruction or runtime overlay is materialized before
   Review and included in the reviewed surface;
5. the controller always reviews cumulative Quant-H0-S6-to-effective-candidate
   material;
6. public support is read by the trusted controller from frozen public task or
   reference files, rather than accepted as an unauthenticated free-text claim;
7. every QRS `ACT` supplies a structured inventory covering every changed
   Worker-visible surface; and
8. the six contaminated historical candidates are mechanically excluded from
   main history. Main history begins empty, or with separately reviewed
   public-only episodes only.

Reviewer `PASS` is permission to evaluate the candidate. It is not Worker
correctness, behavioral uptake, official gain, promotion, or generalization.
The Reviewer reviews the **candidate information set**; it does not review the
Worker's answer and has no mutation, evaluation, or promotion authority.

## Quant-H0-S6: six observable stages, unchanged shell

The present Quant-H0 prompt names six Research States but explicitly allows
them to be revisited or omitted. It does not require trace markers. A read-only
audit of five retained Worker traces found no explicit six-state markers:

| Trace | Assistant turns | Tool results | Explicit S1--S6 markers |
|---|---:|---:|---:|
| public-only holdings H0 | 47 | 51 | 0 |
| public-only credit-migration H0 | 16 | 19 | 0 |
| public-only EVT-POT-VaR H0 | 27 | 31 | 0 |
| Final-H0 holdings parent | 17 | 25 | 0 |
| Final-H0 local-vol parent | 30 | 33 | 0 |

The traces contain natural planning, implementation, checking, and delivery,
but the stages are inferred post hoc. They are not a reliable stage-indexed
history interface.

We will therefore create a new baseline identity, **Quant-H0-S6**, rather than
editing Quant-H0 in place. It retains the same frozen model, shell tool,
execution limits, credentials boundary, and artifact contract. The prompt adds
a short observable protocol:

1. `S1 MANDATE`: deliverables, public constraints, and completion conditions;
2. `S2 EVIDENCE`: files, schemas, missingness, dependencies, and information-
   time caveats;
3. `S3 REPRESENTATION`: objects, units, assumptions, identities, and public
   quantitative relations;
4. `S4 OPERATION`: the executed implementation, estimation, calibration,
   pricing, risk, backtest, or other research operation;
5. `S5 EVALUATION`: public checks, numeric/schema/reconciliation findings, and
   any explicit revisit of S2--S4; and
6. `S6 ARTIFACT`: delivered paths, completion checks, and unresolved caveats.

Each stage is entered at least once. A stage that is genuinely irrelevant is
recorded as `NOT_APPLICABLE` with a public reason rather than silently skipped.
S5 may explicitly revisit S2, S3, or S4, and S6 occurs only after artifact and
reconciliation checks. The Worker emits concise markers such as
`[QSTATE S2 ENTER]` and `[QSTATE S6 COMPLETE]`; it is not asked to reveal chain
of thought. A trusted post-run parser writes a separate
`research-state-trace.json` next to the attempt record, not inside the
submission artifacts. The marker ledger is indexing evidence, not proof that a
stage was performed correctly.

Because this protocol changes Worker behavior, token use, tool sequencing, and
possibly official outcomes, Quant-H0-S6 is a new experimental baseline. Every
main QRS parent and every comparative AHE or no-State run must start fresh from
the same frozen H0-S6. Historical Quant-H0 scores cannot be mixed with H0-S6
candidate results.

The six-stage protocol is a disclosed human-designed quantitative substrate.
The QRS contribution is not the existence of six labels; it is using their
observed state transitions to condition evidence retrieval, relation
selection, component routing, refinement, and retained experience.

## Task families and human selection

Human selection is permitted for a mechanism-development panel, but concealing
it would make the study easier to challenge, not harder. The paper will state
that the development tasks are deliberately selected and will publish:

- the complete eligible task pool;
- public inclusion and exclusion rules fixed before proposal;
- the family strata and deterministic selection rule within each stratum;
- target, repeat, and protection roles;
- exclusions and reasons; and
- the freeze time.

Selection may require a valid prescribed runtime, an auditable public contract,
fresh H0-S6 headroom, and an answer-free protection task. These criteria define
a mechanism-development panel and do not estimate performance over all of
QFBench.

The sealed panel is separate. It is frozen before optimization from tasks that
did not influence candidate selection, diagnosis, or refinement. It is
family-stratified by a predeclared rule and evaluated once per frozen H0-S6,
QRS, and external AHE endpoint. Complete per-task and per-property vectors are
reported; sealed outcomes never return to search, history, task selection, or
promotion.

## Metrics

The main QRS result uses endpoints that map directly to the lifecycle and do
not depend on a paired Generic arm.

### QRS development endpoint

The stable-promotion rate is

```text
number of predeclared opportunities that achieve
Review PASS -> strict target gain -> repeat-consistent footprint
-> property-safe protection
divided by all predeclared QRS opportunities.
```

`ABSTAIN`, rejected admission, non-`PASS` Review, no target gain, repeat drift,
unsafe protection, and an invalid execution that remains invalid after its one
frozen setup recovery all count as zero in the conservative primary endpoint.
A separately labelled execution-valid sensitivity analysis may omit the last
category only. Tasks, routes, budgets, and failed opportunities are never
adaptively replaced.

### QRS final endpoint

The headline generalization endpoint is the complete sealed official task and
property vector for frozen H0-S6 and the frozen final QRS incumbent, with a
task mean inside each family and an equal-family macro. The macro supplements,
but never replaces, the per-task vector.

### Quant-specific ablation endpoint

QRS and QRS-no-State use the same lifecycle, so their proposal, Review,
state-transition, stable-promotion, sealed-vector, and cost funnels can be
compared across separate independent runs. This is the mechanism comparison;
it is not the headline main denominator and it is not called AHE.

### External AHE endpoint

AHE may have a different internal retention lifecycle. The clean cross-method
comparison is therefore the common frozen sealed official vector and resource
use under the same Worker model, task information, task panel, and outer budget.
QRS stable-promotion rate remains an internal method metric unless the AHE
reproduction independently supports an exactly comparable lifecycle.

## Final code boundary

The final release executable contains:

- Quant-H0-S6;
- QRS State-Card construction and state-conditioned retrieval/routing;
- the universal Candidate Information-Set Review and fail-closed controller;
- public-evidence construction, target/repeat/protection lifecycle, sealed
  evaluation, and accounting.

It does not expose Generic, QRS-no-State, or AHE as runtime treatment switches.
QRS-no-State is a frozen ablation artifact; AHE remains in its independent
reproduction repository. Historical Generic code may remain reachable only in
an archival tag or commit needed to reconstruct dated development results.

## Readiness and next actions

Main readiness remains `NO-GO`. The minimum order is:

1. make Candidate Review a universal, cumulative, exact-effective-candidate
   dispatch invariant;
2. implement Quant-H0-S6 and its trusted stage parser without changing the
   shell tool;
3. run no-model protocol/parser tests and one fresh public-only H0-S6
   engineering canary proving observable 6/6 stage coverage;
4. obtain one fresh public-only QRS candidate with overall Review `PASS`, run
   the exact reviewed candidate on a blind Worker, and retain a strict official
   gain;
5. require independent repeat and answer-free protection before calling it a
   stable promotion;
6. freeze the QRS main task manifest and sealed panel; and
7. run the QRS-only main, the separate no-State ablation, and the independent
   AHE reproduction as three separately identified experiment tracks.

The prior Generic--QRS main plan is superseded and must not be launched.

## Claim boundary

This is a prospective architecture decision and a read-only control-flow and
trace audit. It does not establish a solved answer boundary, a six-stage H0
benefit, a Review-PASS Worker result, an official gain, stable promotion, QRS
superiority, AHE reproduction, or sealed performance.
