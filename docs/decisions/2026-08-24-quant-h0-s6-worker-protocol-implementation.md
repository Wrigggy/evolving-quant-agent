# Quant-H0-S6 reusable-capability rule and six-stage Worker skill

Date: 2026-08-24
Status: implemented and locally tested; no Worker or benchmark run
Implements: `2026-08-24-qrs-only-main-independent-ahe-and-quant-h0-s6.md`

## Decision

Quant-H0-S6 is a new Worker identity at `qea/worker_quant_h0_s6`; the historical
`qea/worker_quant_h0` remains unchanged. The new identity preserves the exact
shell descriptor and the same model, context, iteration, completion-token,
temperature, streaming, timeout, retry, tracing, and artifact runtime. Its only
harness changes are a system-prompt research objective and one registered
six-stage workflow skill. The trusted Worker runner also injects the same
reusable-capability boundary into its immutable runtime contract, so an evolved
candidate cannot remove it by editing its own prompt.

## Reusable-capability rule

The system prompt now makes the optimization object explicit to the Worker:
the immediate obligation is to complete the current public task, while the
capability being sampled is a reusable quantitative-research harness rather
than a patch for this task.

This does not ban task-specific behavior. Exact filenames, schemas, formulas,
conventions, thresholds, and rounding rules are legitimate when the current
public instruction, supplied public data, or a predeclared public reference
states them. The prompt instead forbids using hidden checker behavior,
reference answers, expected outputs, official property identities, prior task
scores, or unstated benchmark-specific constants as research rules. When the
public sources do not distinguish plausible conventions, the Worker records
the ambiguity and uses a defensible public or conventional interpretation
rather than claiming evaluator alignment.

The identity prompt makes the objective legible, while the trusted runtime
contract makes the minimum boundary non-removable by a candidate. This Worker
instruction still complements, but cannot replace, the trusted Candidate
Information-Set Reviewer. A model instruction is not an enforcement boundary;
every evolved candidate still needs cumulative exact-material Review before a
fresh Worker.

## Six-stage workflow skill

`agent.yaml` registers
`skills/quant-research-six-stage-workflow/SKILL.md`, and the system prompt
requires the Worker to load it before substantive shell work. The skill defines:

1. S1 Research Mandate and Contract;
2. S2 Research Evidence and Data;
3. S3 Quantitative Representation;
4. S4 Research Operation;
5. S5 Evaluation and Reconciliation; and
6. S6 Research Artifact and Completion.

Every stage emits concise `[QSTATE ...]` markers. Silent omission is not
allowed: a genuinely irrelevant stage uses `NOT_APPLICABLE` with a public
reason. S5 may emit `REVISIT S2`, `REVISIT S3`, or `REVISIT S4`; the repaired
stage is then entered and completed again. S6 begins only after an S5 terminal
marker. Summaries are short public research-state records, not private
chain-of-thought.

The skill gives the Worker a comparable research workflow without embedding an
asset class, task ID, verifier property, expected numeric constant, formula, or
strategy. The task-specific artifact can vary; the reusable capability is the
public-grounded process used to construct and validate it.

## Trusted trace record

`qea.research_state_trace` parses markers from assistant messages only. For a
Worker that registers the S6 skill, both sandbox executors materialize
`research-state-trace.json` in the trusted attempt directory after downloading
the raw trace. The record contains marker events, counts, order, revisits,
missing stages, malformed markers, and protocol issues. It explicitly records
that marker presence is not evidence that the quantitative work was correct.
It is not copied into the task submission artifact directory.

The public-only QFBench trajectory builder recognizes the registered S6 skill,
labels the parent `Quant-H0-S6`, and copies this trusted marker index into the
answer-free Evolver evidence beside the raw Worker trace. The task card records
its exact evidence path. This makes state-indexed history retrievable without
adding a score, verifier result, optimize diagnostic, or candidate episode.

## Local validation

Focused tests cover:

- byte-identical shell capability and identical runtime/model fields relative
  to historical Quant-H0;
- successful full-harness admission of the prompt-plus-skill successor;
- the hardcoded reusable-harness and public-grounding rule;
- all six stage definitions, markers, revisits, and explicit N/A behavior;
- absence of the observed local-vol, holdings, credit-migration, score, and
  numeric answer patches;
- complete, missing, malformed, reordered, and revisit trace parsing;
- materialization only when the S6 skill is registered; and
- compatibility with the E2B, sandbox, remote Worker, admission, and mutation
  paths;
- answer-free public-trajectory inclusion of the state index only for an S6
  parent.

No model, Worker, verifier, provider, remote service, or benchmark was run.
The next measured step is one separately frozen public-only Quant-H0-S6
engineering canary. It must confirm actual skill loading, S1--S6 marker
coverage, sensible stage summaries, unchanged shell capability, official
execution validity, and bounded cost. A green marker ledger alone is not a
benchmark or capability gain.

## Claim boundary

This implementation makes the intended generalization target and six-stage
workflow explicit and testable. It does not show that the Worker follows the
skill in a live run, that the stages improve task performance or diagnosis,
that answers cannot reach the Worker through another control path, that a QRS
candidate passes Review, or that QRS improves over Quant-H0-S6 or AHE.
