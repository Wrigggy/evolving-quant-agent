# QFBench Epoch-2 Canary Panel Correction

Date: 2026-08-04

Status: approved under the standing in-scope modification and direct-run authorization

## Problem

The preregistered twelve-task concurrency canary contradicted its own resource
gate. `historical-var-data-prep` and `fx-forward-cross-rate` require 4 CPU and
8 GiB workers, while the canary requires every worker to use 2 CPU and 4 GiB.
At twelve-way overlap, the original panel plus twelve model proxies would need
52 CPU and 104 GiB, exceeding the declared 48 CPU and 96 GiB capacity. The
gate correctly stopped before containers or model calls were created.

## Decision

Keep the ten valid tasks and replace only the two heavy tasks with primary,
same-domain, manifest-explicit standard tasks:

- `historical-var-data-prep` -> `ohlc-realized-vol-estimators` in
  `risk_credit`;
- `fx-forward-cross-rate` -> `geometric-mean-reverting-jd` in
  `rates_fx_macro`.

Both replacements use the pinned QEA fallback contract of 2 CPU and 4 GiB.
The canary remains baseline-only, uses the immutable seed worker, requires
worker/verifier concurrency 12/3, and preserves the 48 CPU, 96 GiB, 8,192 PID,
40 GiB tmpfs, and 24-sandbox capacity contract. It does not expose feedback,
rubrics, tests, references, solutions, or credentials to workers.

## Verification

Tests must load the real pinned baseline snapshot and prove that the exact
twelve-task panel is primary, unique, and uniformly 2 CPU/4 GiB. A mutated
4-CPU task must still fail closed. The paid canary must use a new publish-once
run ID and require measured worker overlap 12, official DeepSeek V4 Flash
routing without fallback or replay, complete cost accounting, offline
verifiers, exact-ID cleanup, and zero residual containers or networks.

Preserve the first failed canary directory as zero-spend evidence of the
preregistration correction; do not reuse or rewrite it.
