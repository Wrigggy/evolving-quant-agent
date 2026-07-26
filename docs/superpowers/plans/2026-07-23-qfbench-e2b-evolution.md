# QFBench E2B Evolution Implementation Plan

> **For agentic workers:** Execute this plan in order, keep each task test-first, and run the listed verification before moving on.

**Goal:** Add a pinned QFBench adapter and an E2B-backed NexAU execution path that can run reproducible 3- or 5-iteration evolution, while keeping a small lineage-separated held-out set outside mutation selection.

**Architecture:** Introduce benchmark-neutral task, execution, verification, and aggregation contracts rather than adding QFBench branches to the GDPval loop. A worker sandbox receives only the public task bundle and worker snapshot; a distinct verifier sandbox receives the produced artifacts plus hidden tests and returns the official QFBench reward and answer-free diagnostic tags. The local coordinator owns evolution, checkpointing, global concurrency, and held-out policy.

**Tech stack:** Python 3.10+, pytest, NexAU 0.3.9, E2B Python SDK 2.30.0, Docker-compatible QFBench task images, JSON manifests.

## Global constraints

- Pin QFBench to commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a`; never silently follow the upstream default branch.
- Preserve each task's official verifier reward. Aggregate with equal-weight domain macro-averaging; do not invent a substitute reward gradient.
- Never place hidden tests, oracle output, solutions, reference values, raw verifier diagnostics, E2B keys, or model-provider keys in a worker-visible bundle or shell environment.
- Use task-family/workflow lineage for split isolation. For the pilot, optimize on `historical-var-data-prep`, `momentum-backtest`, and `evt-pot-var`; evaluate `fx-forward-cross-rate` and `option-put-call-parity-forward-audit` only at seed and final checkpoints as a small promotion holdout.
- Exclude all eight copy-oracle tasks from optimization and held-out reporting.
- Store raw traces and task artifacts remotely or under the run directory; only compact summaries and stable URIs enter the coordinator state and proposer feedback.
- Do not rewrite the 2026-07-21 decision or report. Add a superseding dated record only if implementation evidence changes a decision.

Implementation addendum (source-audited 2026-07-23): the initially selected `sec-8k-event-alpha` official verifier raises before writing reward at the pinned commit, so the manifest marks it inoperable and substitutes the previously identified high-order held-out candidate `option-put-call-parity-forward-audit`. E2B task construction supports both registry digests and a shared immutable E2B base template/build ID; the latter remains cloud-validation-pending until explicit paid-run authorization.

## Task 1: Pin and load the QFBench snapshot

**Files:**

- Create: `data/qfbench/MANIFEST.json`
- Create: `scripts/fetch_qfbench.py`
- Create: `qea/benchmarks/__init__.py`
- Create: `qea/benchmarks/qfbench.py`
- Test: `tests/test_qfbench_adapter.py`

1. Write failing tests that construct a minimal QFBench-style fixture and assert commit validation, task metadata loading, explicit optimize/held-out membership, unknown-task rejection, lineage overlap rejection, and copy-oracle exclusion.
2. Run `python3 -m pytest tests/test_qfbench_adapter.py -q`; expect collection/import failure.
3. Add a manifest containing repository URL, pinned commit, known task count/reward distribution, excluded copy-oracle IDs, and pilot split IDs.
4. Implement `QFBenchTask`, `QFBenchSnapshot`, and `load_qfbench_snapshot()`. Keep public worker files and verifier-only files as separate resolved path lists.
5. Implement a fetch script that clones/fetches into an explicit destination, checks out the pinned commit, verifies `HEAD`, and refuses a dirty or mismatched snapshot unless `--force` is explicitly supplied.
6. Re-run the focused test and then `python3 -m pytest tests/test_smoke.py tests/test_qfbench_adapter.py -q`.

## Task 2: Add benchmark-neutral evaluation contracts

**Files:**

- Modify: `qea/benchmark.py`
- Create: `qea/evaluation.py`
- Test: `tests/test_evaluation_contract.py`
- Modify: `tests/test_benchmark_grader.py`

1. Write failing tests for stable attempt IDs, canonical artifact hashes, official task scores in `[0, 1]`, answer-free feedback, equal-weight domain macro scores, and missing-domain rejection.
2. Run `python3 -m pytest tests/test_evaluation_contract.py -q`; expect failure.
3. Add immutable `TaskAttempt`, `ArtifactRecord`, `OfficialTaskScore`, `EvaluationSummary`, and `BenchmarkSplit` models plus `TaskExecutor` and `TaskVerifier` protocols.
4. Implement `aggregate_domain_macro()` so task count cannot overweight a domain. Include per-domain scores and task rewards in persisted summaries.
5. Extend `Benchmark` without breaking the existing GDPval fixture and real benchmark constructors.
6. Run `python3 -m pytest tests/test_evaluation_contract.py tests/test_benchmark_grader.py tests/test_smoke.py -q`.

## Task 3: Separate worker execution from official verification

**Files:**

- Create: `qea/executors/__init__.py`
- Create: `qea/executors/bundles.py`
- Create: `qea/verifiers/__init__.py`
- Create: `qea/verifiers/qfbench.py`
- Test: `tests/test_qfbench_isolation.py`

1. Write failing fixture-based tests proving that worker archives contain the instruction, allowed inputs, and worker snapshot but no verifier files; verifier archives contain task tests and produced artifacts but no credentials.
2. Add deterministic tar/zip bundle builders with sorted members, normalized metadata, SHA-256 digests, path traversal rejection, and explicit byte/file limits.
3. Implement QFBench result parsing for the official reward file and CTRF/pytest output. Map detailed failures to a small allowlist of answer-free tags such as `missing_artifact`, `invalid_schema`, `runtime_error`, or `tests_failed`; do not expose assertions or expected values.
4. Hash all returned artifacts and record the verifier command, exit status, official reward, image digest, and log URI.
5. Run `python3 -m pytest tests/test_qfbench_isolation.py -q`.

## Task 4: Run NexAU and the verifier in separate E2B sandboxes

**Files:**

- Create: `qea/executors/e2b_nexau.py`
- Create: `qea/executors/e2b_protocol.py`
- Create: `qea/e2b_lease.py`
- Test: `tests/test_e2b_nexau_executor.py`
- Test: `tests/test_e2b_lease.py`

1. Inspect the installed E2B 2.30.0 API and encode the narrow filesystem/command interface used by the executor as a protocol that can be faked in tests.
2. Write failing tests for sandbox creation, task/worker upload, an in-sandbox NexAU command, generic output collection (`json`, `csv`, `html`, images, source, and office files), separate verifier creation, secret allowlisting, cleanup in `finally`, timeout handling, and reconnect-without-LLM-resampling.
3. Implement `E2BNexAUExecutor`. Pass only task-scoped model credentials to the NexAU process, never E2B control credentials; scrub all environment/log summaries before persistence.
4. Implement `E2BQFBenchVerifier` using a separate template and verifier bundle. Disable verifier network for publication runs; allow an explicit canary-only override while dependencies are being baked.
5. Add a file-locked global lease with a configurable cap (default 12), heartbeat, stale-lease reaping, and idempotent attempt IDs.
6. Ensure every sandbox is killed in `finally`, and persist enough state to reap an orphan after coordinator failure.
7. Run `python3 -m pytest tests/test_e2b_nexau_executor.py tests/test_e2b_lease.py tests/test_qfbench_isolation.py -q`.

## Task 5: Generate pinned E2B task overlays

**Files:**

- Create: `qea/qfbench_images.py`
- Create: `scripts/build_qfbench_e2b_templates.py`
- Test: `tests/test_qfbench_images.py`

1. Write failing tests that verify a generated overlay rewrites only the upstream `FROM` line, uses a registry-visible digest, installs pinned NexAU/verifier dependencies, and leaves the upstream snapshot untouched.
2. Implement pure overlay generation separately from E2B template creation so it is unit-testable without network access.
3. Record the upstream Dockerfile digest, base image digest, generated overlay digest, E2B template ID, and build timestamp in a run-specific image manifest. Refuse mutable tags for non-canary runs.
4. Add `--dry-run`, `--task`, and `--publish` modes. Require explicit invocation for paid/networked template builds.
5. Run `python3 -m pytest tests/test_qfbench_images.py -q`.

## Task 6: Generalize Level-B evolution and add resume

**Files:**

- Create: `qea/loop_benchmark.py`
- Modify: `qea/loop_levelb.py`
- Modify: `qea/falsify.py`
- Modify: `qea/manifest.py`
- Test: `tests/test_qfbench_evolution.py`
- Test: `tests/test_levelb_resume.py`

1. Write failing tests for exactly 3 and 5 iterations, optimize-only selection, seed/final-only held-out evaluation, absence of held-out task IDs/rewards in proposer payloads, keep/rollback behavior, domain non-regression gates, and resume after a forced interruption.
2. Implement `BenchmarkEvolutionConfig` with explicit optimize and held-out split objects, iteration count restricted to 3 or 5 for the pilot, global concurrency, seed, and budget fields.
3. Refactor the existing Level-B mechanics behind a benchmark-neutral evaluator while preserving `run_gdpval_levelb()` compatibility.
4. Select mutations using optimize rewards only. Evaluate promotion holdout before iteration 1 and after the accepted final worker; never feed held-out diagnostics or scores to the proposer.
5. Write checkpoints atomically after each task attempt and accepted/rolled-back iteration. On resume, reuse completed attempt IDs and artifacts rather than resampling an LLM call.
6. Extend manifests with benchmark repository/commit, split IDs and lineage labels, task image digests, worker hash, attempt IDs, official rewards, domain macros, trace/artifact URIs, timings, token/cost data, and cleanup status.
7. Run `python3 -m pytest tests/test_qfbench_evolution.py tests/test_levelb_resume.py tests/test_levelb_evolve.py -q`.

## Task 7: Expose a safe CLI and dependency profile

**Files:**

- Modify: `run.py`
- Modify: `pyproject.toml`
- Test: `tests/test_run_cli.py`

1. Write failing parser tests for `--benchmark qfbench`, `--executor local|e2b`, `--qfbench-root`, `--iters 3|5`, explicit split overrides, `--resume`, `--concurrency`, and canary verifier-network controls.
2. Preserve existing `--mock`, `--real`, and `--levelb` behavior. Require `--benchmark qfbench` for the new path so no legacy command silently changes meaning.
3. Add a pinned optional dependency group for NexAU/E2B and produce actionable errors when it or the QFBench snapshot is missing.
4. Make the CLI print the resolved benchmark commit, split, image/template IDs, estimated task-attempt count, and whether external LLM data egress/paid E2B execution is enabled before starting.
5. Run `python3 -m pytest tests/test_run_cli.py tests/test_smoke.py -q`.

## Task 8: Verify parity and run the staged pilot

**Files:**

- Create: `docs/runbooks/2026-07-23-qfbench-e2b-pilot.md`
- Create after evidence exists: `docs/reports/2026-07-23-qfbench-e2b-pilot-report.md`
- Modify after evidence exists: `docs/PROJECT_MEMORY.md`
- Test: `tests/test_qfbench_pilot_contract.py`

1. Add a contract test covering copy-oracle exclusion, split lineage separation, worker/verifier bundle isolation, no-secret environment construction, artifact integrity, official reward parsing, and held-out feedback isolation.
2. Run the full dependency-light suite: `python3 -m pytest tests -q`. Record exact pass/fail counts and duration.
3. Fetch the pinned snapshot and run the local oracle parity canary for `historical-var-data-prep`. Require reward `1.0` and 12/12 official tests, matching `results/qfbench_smoke/20260721T144046+0800_024921eb/run_status.json`.
4. Build or select digest-pinned E2B templates, then repeat oracle parity in E2B. Require exact reward/test parity, complete artifact/log URIs, secret/firewall checks, and no orphan sandbox.
5. After explicit authorization for paid E2B and external model data egress, run the seed baseline on the three optimize tasks and two promotion-holdout tasks.
6. Run the 3-iteration evolution. If it completes cleanly, the budget allows it, and the user requests the larger run, repeat with 5 iterations from a fresh run ID.
7. Report optimize per-task rewards, equal-weight domain macro, seed-to-final held-out delta, keep/rollback history, wall time, tokens/cost, sandbox failures, and artifact locations. Do not claim a formal benchmark improvement from five pilot tasks.
8. Add the dated pilot report and update `PROJECT_MEMORY.md` with evidence and any superseding decisions. Preserve all older dated records verbatim.

## Final verification checklist

- `python3 -m pytest tests -q` passes from a clean environment with networked tests gated.
- `python3 run.py --mock` remains deterministic and passes its keep/rollback fixture.
- A forced-kill/resume test performs no duplicate model call for a completed attempt.
- Worker bundles and worker-visible environment contain no verifier, oracle, reference answer, E2B control key, or unrelated provider key.
- Local and E2B oracle canaries have identical official reward and test counts.
- The 3-iteration run completes with three optimize tasks and two seed/final-only promotion-holdout tasks; a 5-iteration run is supported by the same code path.
- All task, worker, image, artifact, trace, and verifier identities are content-addressed or digest-pinned.
- Every created sandbox is terminated or listed in a reaper manifest with cleanup status.
