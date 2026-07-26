# QFBench Verifier Template Repair Design

## Status and Authorization

The account owner authorized the current E2B account to publish three paid verifier templates and run one no-model, no-network verifier canary for each. This repair is limited to `delta-hedging-pnl-simulation`, `swap-curve-bootstrap-ois`, and `form4-cross-sectional-sale-pressure`. It does not rerun workers, repair the 14 historical scores, call a model provider, upload or execute official solutions, or modify the evolve agent.

## Problem

The three published verifier manifests under `output/qfbench-e2b-images/20260725_30x5_024921eb/` recorded `verifier_uvx_warm_command: null`. Their official `tests/test.sh` scripts invoke pytest through a shell-prefixed `if uvx ...` command, which the old parser did not recognize. The resulting templates contained only the base Python dependency lock. In no-network verification, `uvx` could not resolve the official test environment, contaminating 14 scores with infrastructure zeros.

Local code now recognizes the exact `if uvx` form and fails closed when a script contains an unrecognized `uvx` invocation. New cloud templates and live offline evidence are still required.

## Considered Approaches

1. **Publish three new verifier templates and run three empty-artifact offline canaries — selected.** This is the smallest auditable repair. It proves dependency availability and official pytest startup without model calls or solutions.
2. **Overwrite or rebind the old manifests.** Rejected because it destroys lineage between the contaminated run and corrected templates.
3. **Immediately rerun all 14 scores or the complete 30-task experiment.** Rejected because score repair is outside the current authorization and should begin only after the templates pass their canaries.

## Template Publication

Use QFBench commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a` and reuse the published shared base:

- template ID: `h4d9iarzjjts2z472o8d`
- build ID: `b82873ce-db6e-4269-a689-ecb9354bf207`
- source manifest: `output/qfbench-e2b-images/20260725_30x5_024921eb/qfbench-base.image.json`

Generate verifier-only manifests in a new immutable directory:

```text
output/qfbench-e2b-images/20260726_verifier_repair_024921eb/
```

The dry-run preflight must establish all of the following before `--publish`:

- exactly three `*.verifier.image.json` files and no worker manifests;
- each manifest has a non-null `verifier_uvx_warm_command` matching the official declaration;
- each dependency-lock command resolves through the same `uvx` package set;
- each new identity differs from the contaminated manifest identity;
- all task operations, CPU, memory, timeout, upstream hash, commit, base template, and base build remain pinned;
- neither the build context nor manifest includes `solution/`.

Publication is resumable and publish-once. A partial failure leaves completed template/build IDs in their new manifests; rerunning the same command reuses them and only builds missing identities. Old manifests and templates remain untouched.

## No-Network Canary

Add a verifier-template smoke command that accepts the pinned snapshot, manifest directory, repeatable task IDs, results directory, run ID, and an explicit `--approve-paid-e2b` gate. The command must not construct a worker executor or load model credentials.

For each task, it creates an empty local artifact directory and calls the normal trusted `E2BQFBenchVerifier`. The verifier therefore receives only:

```text
official tests + trusted template data + empty worker artifacts
```

Each verifier sandbox is created with `envs={}` and `allow_internet_access=False`. The normal offline transformation removes only the pinned uv bootstrap and sets `UV_OFFLINE=1`. Official solutions are neither bundled nor executed.

The expected reward is normally zero because required worker outputs are intentionally absent. The canary passes only when:

- the official script reaches pytest;
- `tests_passed + tests_failed > 0`;
- stdout/stderr do not contain the known offline dependency-resolution failure markers;
- `/opt/qea/verifier-requirements.lock` is non-empty and copied into the run artifacts;
- the verifier harness records official and executed script hashes plus the lock hash;
- the verifier sandbox lifecycle is recorded and ends with `cleaned_up=true`;
- the final exact-ID reaper dry-run reports no pending sandbox IDs for the canary run.

Any dependency failure, missing reward, zero executed-test count, cleanup failure, or unexpected network requirement fails the canary and blocks historical score repair.

## Test Strategy

Implementation follows red-green TDD.

1. Add a failing unit test for the canary CLI authorization gate and verifier-only task selection.
2. Add a failing unit test proving the canary uses an empty artifact directory, never instantiates a worker/model path, and rejects a zero-test result.
3. Add a failing unit test for successful per-task result persistence and lifecycle/lock evidence checks.
4. Implement the smallest smoke command that satisfies those tests by reusing `E2BQFBenchVerifier`, `TaskAttempt`, and the existing template manifest loader.
5. Run the existing QFBench image/isolation/executor tests, then the complete `tests/` suite.
6. Generate the three manifests locally and run machine-readable preflight assertions before publication.
7. Publish the three templates and run the three live no-network canaries.

Live evidence is separate from unit-test evidence. A local parser test cannot substitute for E2B Linux cache parity.

## Artifacts and Decision Record

Persist:

- the three corrected published manifests under the new output directory;
- a canary directory under `results/qfbench_verifier_canary/` containing per-task official score, trusted command log, executed script, dependency lock, harness hashes, and lifecycle/cleanup records;
- a machine-readable canary summary with pass/fail status for each task and final pending-ID count;
- `docs/decisions/2026-07-26-qfbench-verifier-template-repair.md` recording old and new template/build IDs, build times, canary results, costs as measured or `not measured`, and the remaining 14-score repair boundary;
- an update to `docs/PROJECT_MEMORY.md` that points to the new decision without rewriting the 2026-07-25 historical result.

The repair is complete only when all three live canaries pass and cleanup is verified. Even then, the 2026-07-25 aggregate scores remain provisional until a separately authorized superseding rescore repairs the 14 contaminated attempts.
