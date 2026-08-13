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

When a previously completed candidate panel is imported into a later search,
derive the same process and timeline profile from its persisted attempt files
and attach it to that history experience. No Worker rerun is needed. Thus the
later Evolver receives runtime experience from H0/comparison runs and from
scored candidate panels, not only the candidate score vector.

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

The live activation CLI accepts repeated `--task` arguments so a mechanism
search can expose only its declared target and protection panel. The next run
uses `--task T12 --task T19`; T01 and T18 remain preserved historical outcomes
but are not current optimization targets.

## First live use and observed information gap

The first focused live activation over T12 with T19 protection ended in a
calibrated ABSTAIN. The Evolver read the accumulated experience view and exact
prior records, but concluded that the same harness had produced both a full
T12 pass and a partial T12 result while four candidate mechanisms tied on the
binary panel. The run used 23 successful model requests, about 1.25 million
tokens, and $0.0294. It changed no candidate and ran no new Worker panel.

Inspection after the run found that the persisted Worker traces already
contained a useful sequence: public-definition retrieval, data inspection,
candidate writes, local checks, public-probe failures, revisions, and later
probe success. The answer-free projection had reduced this to role and generic
tool-status order, so the Evolver could not use the sequence to distinguish a
missing capability from a repair-loop or implementation-state problem.

The projection now additionally retains coarse action and quant-stage labels,
implementation revision counts, and public-probe outcome order. It still
omits commands, arguments, messages, stdout, submitted source text, and
verifier details. This is an evidence-sufficiency repair motivated by the
observed ABSTAIN, not a new fixed failure taxonomy or a measured reward gain.
