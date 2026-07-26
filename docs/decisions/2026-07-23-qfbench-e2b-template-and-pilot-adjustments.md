# Decision Record: QFBench E2B Template and Pilot Adjustments

> Date: 2026-07-23
> Status: accepted for implementation; paid cloud validation pending explicit authorization
> Supersedes: only the registry-only template transport and `sec-8k-event-alpha` pilot candidacy in the [2026-07-21 runtime decision](2026-07-21-qfbench-and-runtime-architecture.md)

Subsequent template identity, dependency-lock, resource, and orphan-cleanup hardening is recorded in the [2026-07-24 decision](2026-07-24-qfbench-template-reproducibility-and-cleanup.md). The evidence snapshot below remains the 2026-07-23 state.

## Decision

Keep the 2026-07-21 execution architecture: the coordinator remains local, the complete NexAU worker runs inside a task E2B sandbox, and official verification runs in a separate no-network sandbox. Add an E2B-native template transport alongside the preferred registry-digest transport:

1. Stage only `docker/sandbox.Dockerfile` and `docker/requirements-sandbox.txt`, then build the pinned QFBench base once as an E2B template; tests and solutions never enter the upload context.
2. Record its template/build IDs, source Dockerfile and requirements hashes, and an in-image `pip freeze` lock.
3. Extend that immutable base with each task's validated single-stage `WORKDIR`, `COPY`, and `RUN` operations.
4. Publish separate worker (`nexau==0.3.9`) and verifier (`uv==0.9.5`) templates.
5. Warm the verifier's exact official `uvx` dependency declaration at build time. At no-network runtime, remove only recognized uv installer bootstrap lines and record official/executed script hashes; preserve the official test and reward body.

The published E2B build ID freezes runtime bytes but does not make a future rebuild identical because upstream uses mutable `python:3.11-slim` and ranged Python requirements. Reuse the recorded build; use a registry-visible digest when available.

## Pilot Split Adjustment

The pinned `sec-8k-event-alpha` verifier calls `write_outputs` with one extra positional argument. Pytest therefore raises before `reward.txt` is written, and `test.sh` has no fallback reward. Treating that infrastructure defect as an agent score of zero would violate the official-reward policy; locally patching it would create a non-official reward.

Mark the task inoperable at commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a` and replace it with the 2026-07-21 high-order candidate `option-put-call-parity-forward-audit`. The resulting split is:

- Optimize: `historical-var-data-prep`, `momentum-backtest`, `evt-pot-var`.
- Held-out seed/final only: `fx-forward-cross-rate`, `option-put-call-parity-forward-audit`.

## Evidence Boundary

Local verification currently shows `123 passed, 1 skipped`, successful pinned five-task sparse checkout, successful generation of all ten task-role manifests, and a dry-run 3-iteration schedule of 16 task attempts. No E2B template was published and no cloud parity, seed score, or evolution score was measured: the paid publication action was rejected pending explicit account-owner authorization.
