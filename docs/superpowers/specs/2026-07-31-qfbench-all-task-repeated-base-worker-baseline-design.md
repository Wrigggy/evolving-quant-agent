# QFBench All-Task Repeated Base-Worker Baseline Design

> Date: 2026-07-31<br>
> Status: approved for implementation and paid execution<br>
> Backend: trusted shared-host rootless Docker on `bc`<br>
> Benchmark: QFBench `024921eb507fcc0c4ffe3e0a96802724be1ae84a`

## Objective and Claim Boundary

Measure the frozen GDPval-style base worker's QFBench performance and model-run
variance before attributing changes to harness evolution. This is a pure
baseline: it creates no evolver sandbox, proposes no candidate, performs no
keep/rollback decision, and never uses a previous repetition's artifacts as
input to a later repetition.

The result may support claims about the fixed worker on the pinned public
QFBench task universe. It does not establish trading alpha, live execution
quality, rootless/E2B score parity, or an evolution gain.

## Frozen Task Universe

The pinned source contains 86 tasks. The registered run roster is:

- **Primary:** 77 runnable non-copy-oracle tasks, aggregated across the six
  domains already defined by the 2026-07-21 QFBench audit.
- **Diagnostic:** eight runnable copy-oracle tasks. The worker and official
  verifier may run, but these scores never enter the primary mean or confidence
  interval.
- **Structural exclusion:** `sec-8k-event-alpha`. Its pinned official verifier
  raises before producing a reward, so no paid worker call is made and no zero
  is imputed.

Primary domain counts are derivatives 23, risk/credit 16, systematic strategy
17, rates/FX/macro 11, execution/microstructure 5, and data engineering 5. The
eight diagnostic tasks are the registered copy-oracle set in
`docs/PROJECT_MEMORY.md`.

Eleven primary tasks have no complete upstream CPU, memory, build-timeout,
agent-timeout, and verifier-timeout contract. Their manifest must explicitly
record the QEA preregistered fallback: 2 CPU, 4 GiB, 600-second build timeout,
2,400-second worker timeout, and 300-second verifier timeout. These are
`barone-adesi-whaley`, `bs-greeks-pde`, `compound-option-geske`,
`copula-sampling-rank-correlation`, `digital-barrier-options`,
`dupire-local-vol`, `first-passage-time`, `geometric-mean-reverting-jd`,
`lookback-options`, `ohlc-realized-vol-estimators`, and `smith-tail-index`.
The report must also show a 66-task resource-declared sensitivity result.

## Immutable Run Contract

- Base worker: `qea/worker_gdpval_weak`, snapshotted once; its directory digest
  is part of the run identity.
- Model route: `deepseek/deepseek-v4-pro` through the existing fixed OpenRouter
  proxy route. Public instruction/environment data may leave the host only in
  model requests governed by that route.
- Repetitions: five independent repetitions of all 85 runnable tasks.
- Schedule: primary then diagnostic within every repetition; worker concurrency
  4 and verifier concurrency 3, subject to the existing weighted host-capacity
  gate.
- Maximum scoring work: 425 worker attempts plus 425 independent verifier
  attempts. No evolver lifecycle exists.
- Official tests and reference data enter only task-specific, no-network
  verifier containers. Official solutions are neither uploaded nor run.

Every attempt identity binds run ID, benchmark commit, task ID, panel role,
repetition checkpoint, and worker digest. A later repetition therefore cannot
reuse an earlier repetition's completed score. Resume may reuse only the exact
same attempt identity after validating its persisted worker execution and
official score.

## Runner and Artifact Design

Add a dedicated baseline path rather than overloading `--iters 1`. The runner
accepts the immutable 85-task manifest and total repetition count, assembles the
existing rootless full-harness evaluator without an evolver, and persists:

- immutable config and identity digests;
- phase/repetition checkpoint state;
- per-attempt worker execution, proxy audit, official score, and lifecycle;
- per-repetition primary and diagnostic summaries;
- aggregate statistics, cost audit, failure inventory, and exact run roster.

`--stop-after-repetition 1` is an operational calibration boundary, not part of
the immutable experiment identity. Resuming the same five-repetition run must
continue at repetition two without duplicating completed model requests.

## Statistical Estimand

For each repetition, preserve official per-task rewards and calculate the
existing six-domain macro-average:

```text
R_rep = mean_domain(mean_task(reward))
```

The primary headline is the mean of the five `R_rep` values. Report sample
standard deviation, standard error, and a two-sided 95% Student-t interval
across repetitions. Also report each domain and each task across repetitions,
including mean, sample standard deviation, minimum, maximum, and success count
for binary rewards. Do not pool 385 primary attempts as if they were IID. Show
diagnostic and 66-task resource-declared sensitivity statistics separately.

## Calibration, Cost, and Stop Gates

Run repetition one first, then audit before continuing. The measured five-task
reference implies a rough 425-attempt model cost near USD 26, but task
heterogeneity makes this an estimate rather than a budget fact. Continue to
repetitions two through five only if repetition one has:

1. 85/85 official scores and no infrastructure score misclassified as zero;
2. complete successful-request usage and cost records;
3. zero worker/evolver exposure to credentials, tests, references, solutions,
   or verifier-only outputs;
4. zero run-owned residual containers or networks after exact-ID cleanup; and
5. projected total provider cost no greater than USD 60.

Stop rather than retry ambiguously accepted model requests, silently substitute
resource contracts, repair official rewards, or broaden cleanup beyond exact
run-owned IDs. A reproducible task-specific image build failure is recorded and
fixed before any scoring call for that task.

## Rootless Materialization and Images

Materialize role-separated public and trusted snapshots directly from the
pinned public source. The public root contains only Docker context,
instruction, and environment data. The trusted root contains official tests
and reference data. Solution paths remain denied.

Reuse the accepted task-neutral base, proxy, and NexAU donor images. Build and
bind immutable worker/verifier images for every registered task; existing
five-task identities may be reused only after byte and resource-contract
parity. Build manifests, dependency locks, image IDs, daemon identity, and the
assembled 85-task image-set digest are preserved before scoring.

## Acceptance Criteria

The experiment is complete only when five repetitions produce 425 content-
addressed official scores, all proxy audits reconcile, the statistical output
can be regenerated from raw scores, the firewall audit passes, exact-ID reaper
finds no pending resource, and the final report keeps primary, diagnostic,
resource-fallback, infrastructure, and cost claims distinct.
