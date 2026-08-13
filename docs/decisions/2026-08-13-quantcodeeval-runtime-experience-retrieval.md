# QuantCodeEval runtime-experience retrieval and extensible domain guidance

Date: 2026-08-13

Status: implemented and locally smoke-tested; no paid model or benchmark run in
this change.

## Decision

Keep the complete QuantCodeEval mutation archive as the source of truth, and
derive three small Evolver-facing navigation files for later rounds:

- `CATALOG.json` summarizes every attempted mechanism, changed file role,
  activation, answer-free task outcome, selection, and result-validated lesson;
- `ANCESTRY.json` shows which attempted candidates extend another archived
  candidate and identifies the current search parent when available;
- `RELEVANT.json` ranks all retained experiences using target-task overlap,
  measured outcome, new information, domain tags, and recency. The current
  engineering run does not truncate this view; a future large archive may set
  a documented display limit without deleting the underlying catalog.

The navigation layer links back to the exact archived entry. It does not
replace the full source and diff, so the Evolver can move from a short lesson
to the actual implementation when deciding whether to continue, reuse, revert,
fuse, or run a new probe.

Retain a longer answer-free Worker runtime timeline. Each event records only
its position and role; tool results may additionally record success/error,
duration, exit-code counts, truncation, and consecutive error runs. Message
content, commands, arguments, stdout, stderr, and evaluator details remain
excluded. This gives later rounds enough temporal evidence to distinguish an
early execution failure from a late completion/finalization failure without
exposing answers.

Treat the finance failure map as optional diagnostic vocabulary. The Evolver
may use a known breakdown stage and failure class, add free-form `domain_tags`,
propose a new concise class, or leave the fixed classification unspecified.
The binding requirements remain competing hypotheses, inspected evidence, a
falsifiable prediction, explicit component roles, and a coherent intervention.

## Why

The earlier mechanism already preserved exact rejected candidates and made
them accessible, but expected the Evolver to browse a growing archive manually.
It also reduced a long Worker attempt to aggregate counts. The missing feature
was therefore experience retrieval and temporal runtime structure, not another
memory store.

A closed mandatory failure taxonomy was too rigid for exploratory harness
evolution. Domain vocabulary is useful for locating finance/data/execution
state, but it should help the Evolver choose and test components rather than
force every failure into an enumerated box.

## Local evidence

Focused unit tests cover:

- a rejected prompt intervention becoming an explicit unsupported lesson;
- a second round reading that lesson and its exact diff before switching to an
  executable tool component;
- extensible domain tags and an explicit branch/search operator;
- a runtime timeline that preserves tool-error position/duration while omitting
  message and tool-output content.

This confirms the local mechanism and evidence flow only. It does not show that
the retrieval view or domain guidance improves QuantCodeEval reward.
