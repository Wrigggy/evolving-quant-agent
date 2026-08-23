# Public-only holdings lineage R1 proposal-stage result

Date: 2026-08-24  
Status: legal admitted proposal; stopped at frozen activation-binding gate

## Decision

Retain `qf-public-only-holdings-proposal-20260824-r1` as one legal public-only
proposal observation. The Evolver returned a nonempty `ACT`, admission accepted
the candidate, all nine admission checks passed, and the only mutation was an
11-line, 1,463-byte addition to `systemprompt.md`.

Do not advance this candidate to Candidate Information-Set Review or a Worker.
The controller recorded activation binding `status=none`, with no new or
modified registered tools. The frozen proposal-stage gate required a singleton
callable-component activation binding before a separate review resume. The
observed binding is therefore `NON-SINGLETON`, and the frozen decision is
`STOP`.

## Frozen scope

The deployment used source version `320ab1b`. The frozen
`QF_PUBLIC_ONLY_HOLDINGS_LINEAGE_R1_PLAN` authorized one proposal stage and
required it to stop. The proposal received public contracts plus an answer-free
fresh-H0 trajectory package. Official scores, CTRF/verifier files, optimize
diagnostics, failed properties, checker outputs, expected values, and prior
candidate episodes were excluded.

This stage allowed zero Reviewer requests, zero Worker sessions, and zero
verifier executions. A selected probe could be described but was not enabled
for dispatch.

## Measured proposal

The preflight completed with zero model requests. The live proposal returned
`ACT`, `admitted=true`, and a nonempty diff. The declared and actual component
roles both contained only `systemprompt`. `agent.yaml` and the existing shell
tool description were unchanged.

The mutation added a reusable data-convention discipline section to the system
prompt. It covered canonical keys before joins and filters, declared-universe
coverage, missing-value and numeric-type handling, and source reconciliation.
The diff added 11 lines and 1,463 bytes.

All nine admission checks passed: file manifest, protected config, Python
compile, declared imports, subprocess timeouts, local bindings, local skills,
local middlewares, and component reachability. There was one Quant Research
State Card and one state-retrieval operation. The candidate declared three
Worker-visible claims: cross-table key canonicalization, numeric-column
coercion, and filing-total reconciliation. Their proposal-supplied provenance
and coverage had not yet been validated by the arm-blind Reviewer.

## Bounded candidate-content audit

A read-only scan of the complete 11-line Worker-visible addition found no
embedded turnover formula, verifier-derived canonical output label, mandatory
pair/list shape, official result or property, checker predicate, expected
value, or answer.

This is only a bounded forbidden-content surface audit. It does not replace or
predict the arm-blind Candidate Information-Set Reviewer. In particular, it
does not prove that every decision-changing semantic claim has sufficient
public provenance or that the candidate would receive Reviewer `PASS`.

## Frozen gate and stopped pipeline

The candidate made no registered callable-component change:

- activation-binding status: `none`;
- new registered tools: empty;
- modified registered tools: empty.

The controller artifact records phase `INFORMATION_SET_REVIEW`, but it also
records `stopped_after_stage=proposal`. The phase is the next staged location,
not evidence that a review happened. Under the frozen proceed/stop criterion,
the non-singleton binding stops the lineage. Reviewer, Worker, verifier, and
selected probe counts are all zero.

The legacy discovery summary reported contract score 0.7272727272727273,
`discriminating_probe_recorded=false`, `final_component_consistent=false`, and
`final_mechanism_consistent=false`. These are retained as diagnostics only;
they are not the primary hard gate and do not supersede the explicit
activation-binding stop.

## Accounting and cleanup

The proposal used 22 completed requests and 2,093,270 total tokens at a
provider cost of $0.061361376. There were zero retries and zero failed
requests. The service reported success with `NRestarts=0`; cleanup completed
and related residue was zero.

## Interpretation boundary

The positive result is proposal construction, not candidate performance: the
Evolver used public-only evidence to create and admit a nonempty candidate with
an explicit claim inventory. The negative result is gate compatibility: a
prompt-only mutation cannot satisfy the frozen requirement for one activated
callable component.

No Reviewer verdict exists, no Worker saw the candidate, no official verifier
ran, and no benchmark score changed. This result therefore establishes neither
candidate quality nor harness gain. The candidate is not eligible for further
dispatch under R1.

## Artifacts

- Compact result:
  `data/breadth/QF_PUBLIC_ONLY_HOLDINGS_LINEAGE_R1_PROPOSAL_RESULT.json`
- Frozen plan:
  `data/breadth/QF_PUBLIC_ONLY_HOLDINGS_LINEAGE_R1_PLAN.json`
- Proposal mirror:
  `results/bc-mirror/qf-public-only-holdings-proposal-20260824-r1`
- Controller mirror:
  `results/bc-mirror/qf-public-only-holdings-lineage-20260824-r1-controller-state`
