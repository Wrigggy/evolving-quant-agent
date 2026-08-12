# QuantCodeEval canary and property-guided harness search

> Date: 2026-08-12
>
> Status: adapter implemented and locally tested; official source audited;
> ephemeral T16/T24 role materialization measured; durable source snapshot,
> runtime image, model calls, scores, and harness benefit not yet measured

> Superseded later on 2026-08-12 by the
> [measured five-round canary result](2026-08-12-quantcodeeval-five-round-canary-result.md).

## Decision

Use QuantCodeEval first as a two-task engineering canary for discovering a
productive harness-evolution mechanism.  Do not initially treat it as a full
baseline, a frozen external benchmark, or evidence that QEA improves quant
performance.

The canary pins the official fully-public release at commit
`9bdacc4898aeec08813764290b12d356e0a011d1` and starts with:

- `T16`, Volatility-Managed Portfolios, representing volatility and portfolio
  construction;
- `T24`, Earnings Extrapolation, representing an event-driven strategy.

The official reward remains binary: a task scores `1` only when every property
checker passes.  Type-A and Type-B pass/total counts may be exposed to the
Evolver as answer-free diagnostic evidence, but individual property IDs,
checker code, checker messages, reference implementations, and verdict details
remain trusted-verifier-only.

The immediate search method is a quant-specific engineering mechanism,
provisionally named **Property-Guided Bidirectional Harness Search (PGBHS)**.
It combines:

1. backward decomposition from task success into public Type-A domain
   invariants and Type-B paper-specific obligations;
2. evidence localization from a public clause to an expected artifact or
   function and then to an observed trace or artifact fact;
3. forward mutations over harness components rather than task solution code;
4. explicit deletion/rollback and small complementary candidate archives;
5. error-class routing so the mutation surface is chosen by the quant failure
   mechanism rather than by an unrestricted generic brainstorm.

This decision does not replace the existing QFBench suite.  It adds a small
mechanism-localization surface whose structured properties may solve the
semantic-identifiability bottleneck observed in A6.

## What was implemented

The repository now contains:

- `data/quantcodeeval/MANIFEST_CANARY.json`: pinned upstream identity,
  environment hashes, public-track identity, and the T16/T24 canary;
- `qea/benchmarks/quantcodeeval.py`: fail-closed role materialization and public
  snapshot loading;
- `qea/verifiers/quantcodeeval_runtime.py`: dependency-light, trusted in-sandbox
  validation and official binary reward emission;
- `qea/verifiers/quantcodeeval.py`: coordinator-side result validation, binary
  score parsing, and answer-free Type-A/Type-B progress summaries;
- `scripts/materialize_quantcodeeval_canary.py`: CLI for materializing disjoint
  public-worker and trusted-verifier roots;
- a backward-compatible score-parser injection point in
  `SandboxQFBenchVerifier`, allowing the existing sandbox execution path to
  retain its isolation machinery while using the QuantCodeEval score contract;
- deterministic adapter and firewall tests in
  `tests/test_quantcodeeval_adapter.py`.

The materializer copies only manifest-bound public data, the paper, and the
public instruction into the worker role.  It copies checkers and the checker
runtime into an owner-only trusted role.  Every consumed upstream path must be
tracked and byte-identical to the pinned Git `HEAD`; `pyproject.toml` and
`uv.lock` must additionally match the recorded hashes.  It rejects symlinks,
revision or dirty-worktree drift, data digest drift, overlapping role roots,
existing destinations, and any copy of golden references, strategy digests,
property definitions, traces, or prior results.

The worker output contract is deliberately narrow:

```text
/app/output/strategy.py
```

The trusted verifier validates complete checker-manifest coverage and treats a
missing submission as a structured all-error result rather than as a fabricated
infrastructure score.

## Source audit of QuantCodeEval

The official [dataset card](https://huggingface.co/datasets/quantcodeeval/task_data/blob/main/DATASET_CARD.md)
describes 30 paper-reproduction tasks, 572 implemented property checkers, and
1,350 released traces.  The benchmark distinguishes reusable Type-A domain
properties from paper-specific Type-B properties; the release's historical
`A11` identifier is counted as Type-B, which the QEA parser preserves.  The
release is unusually useful for mechanism discovery because it provides a real
intermediate-goal structure instead of only a terminal pass/fail result.

That openness also creates an isolation obligation.  Papers, instructions,
checkers, reference implementations, traces, and result tables coexist in the
upstream repository.  A direct checkout inside a worker would invalidate the
evaluation firewall.  The QEA adapter therefore materializes role-specific
views from a pinned coordinator-side checkout; the upstream layout is never
mounted wholesale into a worker.

The official fully-public track contains ten tasks:

```text
T01 T12 T16 T18 T19 T24 T26 T27 T28 T29
```

Only two are used in the first canary.  No held-out task is declared yet,
because this stage tests whether the evolution mechanism can produce a legal,
non-empty, admitted harness intervention at all.  A held-out split must be
preregistered before any transfer or benchmark-gain claim.

### Other quant and finance benchmark candidates

The current landscape supports a layered design rather than replacing every
benchmark with QuantCodeEval:

- [QFBench](https://github.com/QF-Bench/QuantitativeFinance-Bench) remains the
  broader stateful, air-gapped quant mini-project surface and is already deeply
  integrated with QEA;
- [QuantCode-Bench](https://arxiv.org/abs/2604.15151) provides 400 textual
  strategy-to-Backtrader tasks with compile, execution, trade, and semantic
  gates; the existing QEA audit keeps it as a conditional frozen near-domain
  external-transfer check, not an adaptive mutation source;
- [BacktestBench](https://arxiv.org/abs/2605.17937) reports 18,246 annotated
  items over metrics, ticker selection, strategy selection, and parameter
  confirmation, plus a multi-agent backtesting baseline.  It is promising for
  later backtest-workflow transfer, but its release and evaluator have not been
  audited or adapted here;
- the [Finance Agent Benchmark](https://huggingface.co/datasets/vals-ai/finance_agent_benchmark)
  emphasizes SEC-filings research and financial modeling rather than
  quantitative paper-to-code reproduction, so it is a promotion-domain
  candidate rather than the first search-mechanism surface;
- [Herculean](https://huggingface.co/datasets/TheFinAI/Herculean) advertises
  offline trading, hedging, report, and XBRL tasks.  It is new and unaudited in
  this repository; evaluate provenance, runner completeness, and evaluator
  isolation before assigning it a suite role.

QuantCodeEval is chosen first because its public property hierarchy maps
directly to the missing evidence-to-intervention mechanism.  That is a research
fit decision, not a claim that it is the most authoritative finance benchmark.

## Related harness-evolution methods

### Agentic Harness Engineering

[Agentic Harness Engineering](https://arxiv.org/abs/2604.25850) exposes every
editable component as a file, compresses trajectories into a layered evidence
corpus, and binds an edit to a predicted next-round outcome.  Its most useful
lessons for QEA are component observability, drill-down evidence, reversible
edits, and falsifiable change manifests.  We retain those engineering
principles.

QEA should not copy its search loop as the claimed method.  AHE's search is
largely domain-agnostic and its terminal benchmark evidence is comparatively
sparse.  QuantCodeEval lets QEA route edits through finance-specific failure
families and public property structure.

### Meta-Harness

[Meta-Harness](https://arxiv.org/abs/2603.28052) gives the proposer filesystem
access to source, scores, and histories from prior candidates, and treats rich
historical access as more useful than aggressively compressed textual
feedback.  For QEA, the important import is a persistent, inspectable candidate
archive—not unrestricted exposure to verifier details.  Every retained
iteration should include candidate source, declared mutation, answer-free
evidence, score vector, cost, and rollback/admission state.

### Bidirectional Evolutionary Search

[Bidirectional Evolutionary Search](https://arxiv.org/abs/2605.28814) combines
forward candidate evolution with backward goal decomposition.  Forward
operators can expand, recombine, delete, or replace candidate parts; backward
search turns a sparse terminal objective into checkable subgoals.

For executable harnesses, QEA should translate this from token-trajectory
operators to component-level operators.  The backward tree should be grounded
in QuantCodeEval's public evaluation taxonomy and task contract, not inferred
from hidden checker diagnostics:

```text
official task success
  -> Type-A domain invariants / Type-B paper obligations
  -> public instruction clause
  -> expected artifact or function
  -> observed artifact and trace fact
  -> harness-addressable failure class
```

### HarnessCompass and Evo-Bench

[HarnessCompass](https://arxiv.org/abs/2608.01918) proposes task-agnostic edit
constraints, proactive first-person agent feedback, component-wise optimization,
and later consolidation.  The first three are useful for this canary: collect a
worker self-report about what harness support was missing, mutate one component
family at a time, and reject task-answer patches.

[Evo-Bench](https://arxiv.org/abs/2608.09096) identifies tasks whose scores are
sensitive to harness quality before constructing evolution splits.  QEA should
eventually run a similar sensitivity screen across the ten public-track tasks.
For the immediate two-task canary, sensitivity is not yet established; T16 and
T24 are selected for mechanism diversity and manageable data size, not because
they are proven to be harness-sensitive.

Finally, [Rethinking the Evaluation of Harness Evolution for Agents](https://arxiv.org/abs/2607.12227)
finds that harness evolution does not consistently beat simple test-time
discovery under matched feedback and budget and may generalize poorly.  This is
not a blocker for a two-task engineering canary, but it makes matched best-of-N,
independent repetitions, and frozen held-out evaluation mandatory before any
broad performance claim.

## QEA's special opportunity

The current A6 chain demonstrated route, preflight, checkpoint, rollover, and
truthful `ABSTAIN` behavior, but never completed:

```text
legal ACT -> non-empty full-harness diff -> validation -> admission
          -> small candidate panel
```

Its bottleneck is not whether files are writable.  It is whether available
evidence distinguishes a harness-addressable mechanism strongly enough to
justify a specific edit.

QuantCodeEval supplies a better localization surface.  The Evolver can organize
public evidence into the following finance-specific taxonomy without receiving
answers:

| Failure family | Typical public evidence | Preferred mutation surface |
|---|---|---|
| Artifact/interface | missing `strategy.py`, import/API/signature mismatch, malformed output | tool wrapper or pre-submit middleware validator |
| Data/temporal integrity | lag convention, look-ahead risk, date alignment, missing-value handling | temporal-integrity audit skill or middleware |
| Quant definition/estimation | formula, annualization, normalization, windowing, regression specification | paper-to-code contract extraction and numerical self-check |
| Portfolio/execution | weight construction, rebalance timing, position direction, constraints | portfolio construction checklist or executable validator |
| Resource/termination | timeout, excessive data load, incomplete artifact | runtime/tool policy |
| Isolated task-specific Type-B failure | one paper-specific obligation with no cross-task mechanism | local probe or `ABSTAIN`; no global harness mutation |

This routing policy is intentionally narrower than a general-purpose search
algorithm.  A finance-specific method is sufficient for the present research
goal if it repeatedly converts quant evidence into useful, general harness
interventions.

## Proposed first evolution experiment

### H0: minimal seed

Use `qea/worker_gdpval_weak` as a deliberately minimal seed.  It is confirmed
to contain one one-line system prompt, one built-in `run_shell_command` tool and
its description, and the NexAU `agent.yaml`; it has no skills, middleware,
memory, finance tools, or task-specific code.  Its current digest is
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`,
which matches the documented QFBench five-repeat seed.  Therefore the answer to
whether the current base harness is effectively shell-only is **yes**.  The
launch identity must still bind a copied immutable H0 snapshot rather than rely
on this mutable source path.

### Evidence retained for every call

Keep all five iteration records.  Each immutable iteration directory should
contain:

- exact harness tree and digest;
- task, model, provider, reasoning, runtime, and image identity;
- worker trace and final artifact manifest;
- official binary reward and per-task score vector;
- answer-free Type-A/Type-B pass/total counts;
- declared failure taxonomy, causal hypothesis, component target, predicted
  property-family change, and protected behavior;
- validation, admission, rollback, request, token, latency, and cost records.

These records are legitimate work evidence and can seed later analysis.  They
must not be reused as an independent fresh baseline or as a statistically
independent first evolution round.  Reuse is valid only when the exact H0,
model/runtime identity, task split, number of samples, and feedback protocol are
unchanged and the run was preregistered as shared evidence.

### Search mechanics

Maintain a very small archive, initially H0 plus at most two live candidates.
For each iteration:

1. run T16 and T24 with the current harness and preserve complete trusted and
   public evidence in their proper roles;
2. construct an answer-free evidence packet from public clauses, artifact
   facts, trace facts, and Type-A/Type-B aggregate counts;
3. classify the failure family and decide `ACT` or `ABSTAIN`;
4. if acting, change one component family with a declared predicted effect;
5. validate the harness diff and score the candidate on both tasks;
6. retain, roll back, or archive the candidate based on the official vector,
   protected behavior, runtime/cost, and prediction consistency.

Deletion is a first-class mutation.  Cross-parent transplantation is allowed
only after two admitted candidates exhibit complementary property-family
coverage; it should not appear in the first blind proposal.

The first productive mechanism gate is deliberately engineering-scale:

```text
one evidence-grounded ACT
+ one non-empty full-harness diff
+ validation and admission
+ completion of the two-task candidate panel
+ observed change in the predicted property family
```

This does not establish aggregate improvement.  Formal controls come only
after the productive path exists:

- matched best-of-N/test-time-discovery control;
- multiple independent repetitions;
- a frozen held-out public-track split;
- task-sensitivity screening;
- matched model requests, tokens, wall time, and compute budget;
- uncertainty and per-task vectors, not only a task mean.

## Measured adapter audit on 2026-08-12

The pinned T16/T24 source subset was downloaded into an ephemeral exact-revision
Git checkout and successfully materialized with the checked-in CLI.  The output
contained:

| Role | Files | Size | Forbidden-answer scan |
|---|---:|---:|---|
| public worker | 11 | 1.6 MiB | zero matches |
| trusted verifier | 190 | 2.1 MiB | zero matches |

The official checker manifests contained 18 properties for T16 (6 Type-A, 12
Type-B) and 17 for T24 (7 Type-A, 10 Type-B).  The copied trusted runtime's
missing-target path produced a complete 18-property error result, binary reward
zero, and an answer-free family summary.  This validates source identity, data
hashes, role construction, forbidden-file filtering, complete-manifest
handling, and coarse evidence serialization.

The focused adapter, sandbox-verifier, QFBench isolation, and smoke suite passed
`93` tests.  This includes rejection of a modified instruction in an otherwise
correct-revision checkout and preservation of the official `A11` Type-B
classification exception.  The complete NexAU-enabled repository suite then
passed `1195 passed, 1 skipped`; the first sandboxed full-suite attempt had 41
loopback-binding failures, and the required unsandboxed rerun cleared all 41.
This audit did not install the official numerical environment, run
the full checker suite against a strategy, compare a golden reference, build a
container image, or invoke a model.

## Gates before a live canary

The implementation tests prove adapter behavior only.  Before model execution:

1. promote the ephemeral pinned role materialization into a durable,
   content-addressed source and role snapshot;
2. build and digest-pin a Python 3.11 verifier image from the upstream lock;
3. run official golden-reference parity inside the trusted role only, followed
   by a deliberately failing strategy canary;
4. prove worker and Evolver mounts contain no checker, reference, property,
   trace, or prior-result files;
5. prove the verifier has no network and cannot receive model credentials;
6. record exact source, image, runtime, model, provider, concurrency, timeout,
   and cost identities;
7. run a zero-request preflight before any paid task.

Until these gates pass, the accurate statement is: **QuantCodeEval canary
adapter implemented, locally contract-tested, and successfully materialized
from the official T16/T24 source subset; no official checker score from a
strategy and no evolution result exists.**
