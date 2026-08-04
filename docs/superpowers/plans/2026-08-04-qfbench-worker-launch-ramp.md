# QFBench Worker Launch Ramp Implementation Plan

**Goal:** Preserve epoch-2 concurrency twelve while removing the provider-facing twelve-request startup burst.

**Architecture:** Rate-limit only new worker execution starts inside the common two-stage evaluator. Carry the interval through a backward-compatible rootless config schema and bind it into the scheduler digest. Require the preregistered paid batch canary to exercise the exact formal value.

**Tech Stack:** Python 3.10+, standard-library threads/time, pytest, rootless Docker, JSON configs.

### Task 1: Add the evaluator launch gate

- Modify `qea/loop_benchmark.py`.
- Modify `tests/test_qfbench_evolution.py`.
- First add failing tests for invalid intervals, minimum spacing between actual
  executor calls, zero-delay behavior, and no delay for resumable evidence.
- Implement a lock-protected monotonic launch gate used only before
  `executor.execute()`.

### Task 2: Bind the ramp to rootless scheduler identity

- Modify `qea/rootless_full_harness.py`.
- Modify `tests/test_rootless_full_harness.py`.
- Add schema 4 with required `worker_launch_interval_seconds`; retain schemas
  1-3 with implicit zero.
- Pass the interval to the evaluator and include it in the scheduler payload.
- Prove that changing only the interval changes scheduler/runtime identity but
  not image identity.

### Task 3: Harden the paid canary contract

- Modify `scripts/smoke_qfbench_full_harness.py`.
- Modify `tests/test_qfbench_full_harness_scripts.py`.
- Require interval two in the epoch-2 paid panel, record it in the result, and
  retain the twelve-way lifecycle-overlap assertion.

### Task 4: Verify, deploy, and rerun canaries

- Run focused tests, the rootless safety panel, and the complete local suite.
- Commit and deploy the exact SHA without merging.
- Publish schema-4 configs with interval two and unique run IDs.
- Run no-model, provider-route, paid twelve-worker, and recovery canaries.
- Proceed to the fresh five-repetition formal run only if all gates pass.
