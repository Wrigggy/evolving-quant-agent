# QFBench Rootless Full-Harness Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make self-hosted rootless Docker the default, E2B-independent execution path for the complete QFBench full harness: one isolated evolver per iteration, attempt-isolated workers, offline verifiers, bounded pipelining, and resumable scoring.

**Architecture:** Keep `QFBenchEvolutionRunner` and its content-addressed checkpoints as the trusted coordinator. Extend the provider-neutral sandbox contract for evolvers and attempt-scoped networks; place evolvers, workers, verifiers, and per-attempt credential proxies behind `RootlessDockerBackend`; split evaluation into bounded worker and verifier stage pools, while a host-local weighted lease limits aggregate CPU, memory, and live sandboxes. Load immutable per-role image identities from build manifests. Keep E2B available only through explicit `--executor e2b` selection and compatibility aliases.

**Tech Stack:** Python 3.10+, dataclasses, `threading.Condition`, context managers, rootless Docker CLI, NexAU, pytest, existing QFBench artifact/checkpoint formats.

## Global Constraints

- Work only on branch `qfbench-selfhosted-vm-backend` in `/Users/kevinwu/Coding/evolving-quant-agent/.claude/worktrees/qfbench-selfhosted-vm-backend`.
- Do not stage or modify the existing user edits in `docs/reports/2026-07-27-qfbench-full-harness-feedback-ab-report.{md,pdf}`.
- Do not merge any branch. Make one scoped commit per task after its tests pass.
- Preserve QFBench commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a`, the preregistered 20 optimize / 10 held-out schedule, official rewards, and keep/rollback semantics.
- Never expose official tests, reference values, raw trusted verifier logs, held-out outcomes, `.env`, real provider tokens, or official solutions to evolver or worker code.
- Official verifiers always run with `network_policy="none"`; worker/evolver model access is only through an attempt-specific proxy network.
- No rootless execution path may import or require the E2B SDK, E2B templates, or `E2B_API_KEY`.
- All container execution uses structured argv. Do not add shell-concatenated commands, broad label deletion, wildcards for cleanup, or `docker system prune`.
- Preserve backward-compatible reads of existing E2B artifacts and checkpoints; identity drift must still fail closed.
- This plan covers local core implementation and documentation. Remote deployment, 30-task image construction, paid model calls, canaries, pilots, and the 140-attempt run are a separate rollout plan and do not begin here.

---

## Task 1: Add Evolver and Attempt-Scoped Networks to the Sandbox Contract

**Files:**

- Modify: `qea/sandbox_backend.py`
- Modify: `qea/backends/rootless_docker.py`
- Modify: `tests/test_sandbox_backend.py`
- Modify: `tests/test_rootless_docker_backend.py`

- [ ] **Step 1: Write failing contract tests**

Add tests proving that:

1. a `SandboxSpec` whose role is `evolver` is valid and its canonical payload includes the role;
2. `network_scope` participates in `spec_digest`, so otherwise-identical attempts on different scopes cannot share identity.
3. two worker specs with `network_scope="attempt-a"` and `network_scope="attempt-b"` produce distinct internal network IDs and names;
4. a proxy joins only the network handle created for its own scope;
5. unsafe or blank scopes fail before a Docker command is issued;
6. network cleanup uses the recorded native network ID, validates its labels/identity, and treats an already absent ID idempotently;
7. evolver/worker accept only proxy-only policy, verifier accepts only `none`, and proxy accepts only `proxy-outbound`;
8. legacy specs with `network_scope=None` retain their existing run-scoped name for historical canary compatibility.

Run:

```bash
.venv/bin/python -m pytest -q tests/test_sandbox_backend.py tests/test_rootless_docker_backend.py
```

Expected: new evolver/scope tests fail because the role and field do not exist.

- [ ] **Step 2: Extend the public types**

Implement this shape in `qea/sandbox_backend.py`:

```python
SandboxRole = Literal["worker", "verifier", "evolver", "proxy", "canary"]

@dataclass(frozen=True)
class SandboxSpec:
    role: SandboxRole
    run_id: str
    attempt_id: str
    task_id: str
    image_ref: str
    cpu_count: int
    memory_mb: int
    pids_limit: int
    timeout_seconds: int
    network_policy: NetworkPolicy
    environment: Mapping[str, str] = field(default_factory=dict)
    writable_tmpfs_mb: Mapping[str, int] = field(default_factory=dict)
    executable_tmpfs_paths: frozenset[str] = field(default_factory=frozenset)
    network_scope: str | None = None
```

Include `network_scope` in the canonical JSON payload. Add role/policy cross-validation in `SandboxSpec.__post_init__`; retain `worker-proxy-only` as the compatibility name shared by worker and evolver. Add this immutable handle:

```python
@dataclass(frozen=True)
class SandboxNetworkHandle:
    backend: str
    native_id: str
    name: str
    run_id: str
    network_scope: str
    identity_sha256: str
```

Add a runtime-checkable `ScopedNetworkBackend` protocol without changing the base sandbox API. Its exact methods are `create_internal_network(self, *, run_id: str, network_scope: str) -> SandboxNetworkHandle` and `remove_internal_network(self, handle: SandboxNetworkHandle) -> KillOutcome`.

- [ ] **Step 3: Implement deterministic scoped names**

Change `RootlessDockerBackend._internal_network_name` to accept `(run_id, network_scope=None)`. Preserve `qea-<safe-run>-internal` for `None`; for an explicit scope use a readable bounded prefix plus a SHA-256 suffix derived from the unsanitized run/scope pair, for example `qea-<run>-<scope>-<12 hex>-internal`. Enforce Docker's name length and allowed-character constraints.

Use the same function in `create`, `start`, and `create_internal_network`. On create, inspect and persist Docker's native network ID plus labels for backend, run, scope, and network identity. `remove_internal_network` must inspect the exact native ID, verify all labels match the handle, and remove by native ID. Add a `qea.network-scope` label when a scope is present. Never fall back from a requested explicit scope to the run-level network.

- [ ] **Step 4: Run the focused tests**

```bash
.venv/bin/python -m pytest -q tests/test_sandbox_backend.py tests/test_rootless_docker_backend.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add qea/sandbox_backend.py qea/backends/rootless_docker.py tests/test_sandbox_backend.py tests/test_rootless_docker_backend.py
git commit -m "feat(sandbox): isolate rootless attempt networks"
```

## Task 2: Replace Account Leases with a Weighted Host Resource Pool

**Files:**

- Create: `qea/resource_lease.py`
- Create: `tests/test_resource_lease.py`

- [ ] **Step 1: Write deterministic concurrency tests**

Use `threading.Event`, barriers, and short acquire timeouts rather than timing-based sleeps. Cover:

- capacity and request validation;
- immediate acquisition when CPU, memory, PID, tmpfs, and sandbox counts fit;
- FIFO blocking when any dimension is exhausted;
- overlap when the combined declared resources fit;
- duplicate live lease keys rejected;
- oversized requests rejected rather than waiting forever;
- load, available-memory, disk, and inode headroom failures stop admission before container creation;
- timeout reports requested and currently available capacity;
- context-manager and exception paths release exactly once.

Run:

```bash
.venv/bin/python -m pytest -q tests/test_resource_lease.py
```

Expected: import failure because the module does not exist.

- [ ] **Step 2: Implement the resource API**

Create immutable validated types and a thread-safe pool:

```python
@dataclass(frozen=True)
class ResourceRequest:
    cpu_count: int
    memory_mb: int
    pids_limit: int
    tmpfs_mb: int
    sandboxes: int = 1

@dataclass(frozen=True)
class ResourceCapacity:
    cpu_count: int
    memory_mb: int
    pids_limit: int
    tmpfs_mb: int
    sandboxes: int

@dataclass(frozen=True)
class HostHealthSnapshot:
    load_1m: float
    available_memory_mb: int
    free_disk_mb: int
    free_inodes: int

@dataclass(frozen=True)
class HostHeadroomPolicy:
    max_load_1m: float
    min_available_memory_mb: int
    min_free_disk_mb: int
    min_free_inodes: int
```

`HostResourceLeasePool.__init__` takes one usable `ResourceCapacity` (already reduced for coordinator/Docker headroom), a `HostHeadroomPolicy`, and a host-health probe callable. Its `acquire(key: str, request: ResourceRequest, *, timeout_seconds: float = 120.0) -> ResourceLease` returns a lease with idempotent `release`, `__enter__`, and `__exit__`. Use one `threading.Condition`, monotonic deadlines, FIFO tickets, and exact accounting across all five dimensions. Fail admission while load, available memory, free disk, or free inodes violate the headroom policy. The pool is process-local by design and the rootless runtime takes an exclusive coordinator lock for its run root; crash recovery remains the lifecycle/reaper's responsibility.

- [ ] **Step 3: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/test_resource_lease.py
git add qea/resource_lease.py tests/test_resource_lease.py
git commit -m "feat(runtime): add weighted host resource leases"
```

## Task 3: Make Worker Execution Records Provider-Neutral

**Files:**

- Create: `qea/executors/execution_record.py`
- Modify: `qea/executors/e2b_nexau.py`
- Modify: `qea/executors/sandbox_nexau.py`
- Modify: `qea/loop_benchmark.py`
- Create: `tests/test_execution_record.py`
- Modify: `tests/test_e2b_nexau_executor.py`
- Modify: `tests/test_sandbox_nexau.py`
- Modify: `tests/test_qfbench_evolution.py`

- [ ] **Step 1: Characterize the persisted schema**

Write tests that load an existing E2B-style `worker_execution.json` through the new neutral API and assert byte-compatible persistence for all current fields. Add a test showing the benchmark loop treats only a neutral behavioral timeout as official zero; sandbox creation, transfer, proxy, or verifier failures must propagate as infrastructure failures.

Run:

```bash
.venv/bin/python -m pytest -q tests/test_execution_record.py tests/test_e2b_nexau_executor.py tests/test_sandbox_nexau.py tests/test_qfbench_evolution.py
```

Expected: new neutral imports fail.

- [ ] **Step 2: Extract neutral records and errors**

Move the provider-independent fields and JSON functions into:

```python
class WorkerExecutionError(RuntimeError):
    pass

class WorkerBehaviorTimeout(WorkerExecutionError):
    def __init__(self, message: str, *, log_uri: str | None = None) -> None:
        super().__init__(message)
        self.log_uri = log_uri

@dataclass(frozen=True)
class WorkerExecution:
    attempt_id: str
    artifact_dir: Path
    artifacts: tuple[ArtifactRecord, ...]
    trace_uri: str
    log_uri: str
    final_text_uri: str
    summary: dict
    sandbox_id: str
    cleaned_up: bool
```

Implement `persist_worker_execution(execution: WorkerExecution, attempt_dir: Path) -> None` and `load_worker_execution(attempt: TaskAttempt, run_dir: str | Path) -> WorkerExecution | None` with the current JSON keys and artifact rehash checks.

Re-export compatibility names from `e2b_nexau.py` so existing callers and artifacts continue to work. `SandboxWorkerTimeout` and `E2BWorkerTimeout` must be catchable as `WorkerBehaviorTimeout` without making unrelated infrastructure exceptions official zeroes.

- [ ] **Step 3: Neutralize the evaluator name**

Rename the implementation class to `QFBenchSandboxEvaluator`, import neutral timeout/load helpers, and leave:

```python
QFBenchE2BEvaluator = QFBenchSandboxEvaluator
```

as a compatibility alias. Refactor its current single task-chain pool into explicit resumable stages:

```python
@dataclass(frozen=True)
class PendingVerification:
    index: int
    task: QFBenchTask
    attempt: TaskAttempt
    execution: WorkerExecution
```

`_run_worker_stage` must persist/validate the attempt and return either a completed score, an official timeout-zero, or `PendingVerification`. `_run_verifier_stage` consumes only `PendingVerification`, writes `completed-score.json`, and returns the indexed score. `evaluate` uses separate `ThreadPoolExecutor` instances for `worker_concurrency` and `verifier_concurrency`; as each worker future completes, submit its artifact immediately to the verifier pool. Restore results by original task index regardless of completion order. A verifier failure leaves the worker manifest reusable and retries only verification on resume.

Add `worker_concurrency`, `verifier_concurrency`, and a scheduler/resource-policy digest to the run configuration identity. Preserve `concurrency` as a deprecated worker-concurrency alias for existing E2B configs, and reject conflicting values.

Allow `BenchmarkEvolutionConfig.n_iters` in `{1, 3, 5}` so rootless rollout pilots can execute one iteration without faking a larger schedule.

- [ ] **Step 4: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/test_execution_record.py tests/test_e2b_nexau_executor.py tests/test_sandbox_nexau.py tests/test_qfbench_evolution.py
git add qea/executors/execution_record.py qea/executors/e2b_nexau.py qea/executors/sandbox_nexau.py qea/loop_benchmark.py tests/test_execution_record.py tests/test_e2b_nexau_executor.py tests/test_sandbox_nexau.py tests/test_qfbench_evolution.py
git commit -m "refactor(qfbench): neutralize worker execution records"
```

## Task 4: Create Attempt-Scoped Credential Proxy Sessions

**Files:**

- Modify: `qea/model_proxy.py`
- Create: `qea/executors/sandbox_proxy.py`
- Modify: `tests/test_model_proxy.py`
- Create: `tests/test_sandbox_proxy.py`

- [ ] **Step 1: Write proxy lifecycle and secret tests**

Using a fake backend that records all specs, uploads, exec calls, and cleanup, prove:

- each session creates one explicit scoped network and one proxy container;
- two attempts in the same run never share a network or proxy ID;
- the real token is transferred only to the proxy's private secret path and never appears in `SandboxSpec.environment`, public argv, lifecycle metadata, or returned session;
- the returned base URL resolves the proxy container alias and allowed path prefix;
- normal exit, start failure, transfer failure, and caller exceptions all exact-kill the recorded proxy ID and remove only the recorded scoped network;
- lifecycle persistence occurs immediately after create and before secret transfer/start;
- a missing or wrong request `model` is rejected before upstream forwarding;
- audit records contain request identity, exact model, timestamps/latency, upstream/provider request ID, usage, reported cost, and failure class, while excluding prompts, responses, authorization, and token bytes;
- a disconnect proven to precede upstream acceptance is retryable, a completed response is reusable, and an ambiguous post-accept disconnect is persisted as quarantined/non-retryable;
- a backend lacking `ScopedNetworkBackend` fails closed.

Run:

```bash
.venv/bin/python -m pytest -q tests/test_model_proxy.py tests/test_sandbox_proxy.py
```

Expected: session module import fails.

- [ ] **Step 2: Make proxy plans scope-aware**

Add `network_scope`, `allowed_model`, and a private audit path to `build_model_proxy_sandbox_plan`; pass the scope into the proxy `SandboxSpec` and both policy values into the private proxy configuration. Keep old canary call sites source-compatible with explicit migration in Task 9, but production rootless callers must always provide all three.

Extend the proxy server's `ModelProxyConfig` to require `allowed_model` and `audit_file`. Parse the bounded JSON request body before forwarding and require its `model` to equal the preregistered value. Append one JSONL audit record per request using an atomic owner-only writer. Preserve explicit `null` for provider usage/cost fields that are unavailable.

- [ ] **Step 3: Implement the context manager**

Create:

```python
@dataclass(frozen=True)
class SandboxProxyConfig:
    image_ref: str
    resource_contract: SandboxResourceContract
    token_file: Path
    upstream_base_url: str
    allowed_path_prefix: str
    allowed_model: str
    listen_port: int = 8080
    timeout_seconds: int = 120

@dataclass(frozen=True)
class SandboxProxySession:
    base_url: str
    network_scope: str
    network_name: str
    network_id: str
    native_id: str
    lifecycle_uri: Path
    audit_uri: Path
    allowed_model: str
```

`SandboxProxyManager.open` is a context manager with keyword-only `run_id`, `attempt_id`, `task_id`, `caller_role: Literal["worker", "evolver"]`, and `run_dir`; it yields `SandboxProxySession`.

Validate `token_file` is a regular, non-symlink file owned by the current UID with no group/other bits. Read it only in trusted coordinator memory, transfer it to the proxy's private path, then discard references. Persist create/start/cleanup transitions through the existing lifecycle helpers. Download the scrubbed audit before cleanup and classify the final request state as `not_accepted`, `completed`, or `quarantined`. Use the recorded proxy and network native IDs in cleanup. Resume must not reopen a quarantined content identity.

- [ ] **Step 4: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/test_model_proxy.py tests/test_sandbox_proxy.py
git add qea/model_proxy.py qea/executors/sandbox_proxy.py tests/test_model_proxy.py tests/test_sandbox_proxy.py
git commit -m "feat(proxy): isolate rootless model sessions per attempt"
```

## Task 5: Build Immutable Proxy/Evolver Images and an Explicit Image Set

**Files:**

- Modify: `qea/rootless_images.py`
- Create: `qea/rootless_image_set.py`
- Modify: `scripts/build_qfbench_rootless_images.py`
- Create: `scripts/assemble_qfbench_rootless_image_set.py`
- Modify: `tests/test_rootless_images.py`
- Create: `tests/test_rootless_image_set.py`

- [ ] **Step 1: Add failing evolver-plan tests**

Assert that an evolver call to `prepare_rootless_image_plan` with `task_id=None`:

- derives from an immutable base image reference;
- installs the same pinned NexAU dependency and Git runtime needed by `remote_evolver.py`;
- contains no public task environment, official test, reference, or solution file;
- rejects any task ID or trusted root for the evolver role;
- has an identity that changes with the base image or dependency lock;
- is accepted by `--role evolver` in plan-only CLI mode.

Assert that the proxy role contains only the pinned proxy runtime/lock and no NexAU, task, trusted, reference, or solution content. Assert base/proxy/evolver reject task/trusted-root arguments; worker/verifier require a task ID; verifier alone requires the trusted root.

Write image-set tests for one explicit immutable index containing base, proxy, evolver, and the requested worker/verifier pairs. Reject missing/duplicate roles, wrong benchmark commit, mutable image references, dependency-lock/resource drift, a task outside the requested panel, and a tampered top-level identity.

Run:

```bash
.venv/bin/python -m pytest -q tests/test_rootless_images.py tests/test_rootless_image_set.py
```

Expected: role validation fails.

- [ ] **Step 2: Add task-neutral proxy and evolver roles**

Extend `RootlessImageRole` to `Literal["base", "proxy", "evolver", "worker", "verifier"]`. Add an evolver Dockerfile layer that installs pinned NexAU/Git but accepts no task material. Add a thin proxy role rooted in the immutable base, containing only the fixed proxy runtime and an explicit dependency lock/role identity. Extract the NexAU lock for worker/evolver, verifier lock for verifier, and proxy/base Python lock for proxy/base. Every result manifest retains its role, source/base identity, image ID, dependency-lock hash, resources, and Docker/rootless identity.

- [ ] **Step 3: Add the image-set index**

Implement `RootlessImageSet` loading/writing in `qea/rootless_image_set.py`. `scripts/assemble_qfbench_rootless_image_set.py` accepts explicit manifest paths rather than scanning an accumulating build directory. It writes schema version, benchmark commit, base/proxy/evolver manifest and image IDs, sorted per-task worker/verifier entries, resources/lock hashes, and one recomputed `identity_sha256`. Old immutable builds remain preserved without causing duplicate discovery.

- [ ] **Step 4: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/test_rootless_images.py tests/test_rootless_image_set.py
git add qea/rootless_images.py qea/rootless_image_set.py scripts/build_qfbench_rootless_images.py scripts/assemble_qfbench_rootless_image_set.py tests/test_rootless_images.py tests/test_rootless_image_set.py
git commit -m "feat(images): define rootless full-harness image set"
```

## Task 6: Implement a Backend-Neutral Sandbox Evolver

**Files:**

- Create: `qea/executors/sandbox_runtime.py`
- Create: `qea/executors/sandbox_evolver.py`
- Modify: `qea/executors/sandbox_nexau.py`
- Modify: `qea/executors/remote_evolver.py`
- Modify: `qea/loop_benchmark.py`
- Create: `tests/test_sandbox_evolver.py`
- Modify: `tests/test_sandbox_nexau.py`

- [ ] **Step 1: Port the E2B evolver behavior contract into failing fake-backend tests**

Cover deterministic input bundle identity, diagnosis/evidence upload, `remote_evolver.py` invocation, bounded/safe candidate extraction, expected trace/final/prediction/access/summary downloads, dependency-lock verification, and cleanup. Add rootless-specific assertions:

- role is `evolver` and network policy is proxy-only;
- network scope is `evolver-iteration-<n>` within the run;
- only placeholder provider credentials enter the evolver;
- the resource lease is acquired before create and released after exact cleanup;
- proxy session closes even when admission output is invalid or execution raises;
- shell-free structured argv is used throughout;
- lifecycle v2 records the backend-native container ID and spec digest;
- completed resume binds run ID, iteration, input digest, scrubbed diagnosis digest, model, image/spec digest, and backend, and rejects drift in any field;
- an unfinished/ambiguous model request is quarantined and cannot reopen a proxy/container under the same content identity;
- result manifest is written only after validated output and exact cleanup.

Run:

```bash
.venv/bin/python -m pytest -q tests/test_sandbox_evolver.py tests/test_e2b_evolver.py
```

Expected: sandbox evolver import fails.

- [ ] **Step 2: Extract shared neutral sandbox mechanics**

Create `sandbox_runtime.py` with public `SandboxInfrastructureError`, `SandboxResourceContract`, UTC/atomic-JSON helpers, required-tmpfs validation, normalized backend calls, structured required command execution, public model environment validation, and exact lifecycle finish/cleanup. Import and re-export these names from `sandbox_nexau.py` so existing callers do not break. Do not make the new proposer import private worker/verifier helpers.

- [ ] **Step 3: Implement the neutral proposer**

Create public types whose result fields match the current E2B proposer so the runner wrapper remains stable:

```python
@dataclass(frozen=True)
class SandboxEvolverConfig:
    image_ref: str
    resource_contract: SandboxResourceContract
    command_timeout_seconds: int = 1800
    max_input_files: int = 2000
    max_input_bytes: int = 512 * 1024 * 1024
    max_candidate_files: int = 2000
    max_candidate_bytes: int = 64 * 1024 * 1024
    lease_timeout_seconds: float = 120.0

@dataclass(frozen=True)
class SandboxEvolverResult:
    iteration: int
    candidate_dir: Path
    candidate_digest: str
    input_bundle_sha256: str
    trace_uri: Path
    final_uri: Path
    prediction_uri: Path
    access_summary_uri: Path
    summary_uri: Path
    command_log_uri: Path
    lifecycle_uri: Path
    dependency_lock_uri: Path
    sandbox_id: str
    proxy_sandbox_id: str
    network_id: str
    cleaned_up: bool
    backend: str
    spec_sha256: str
```

`SandboxFullHarnessProposer.__init__` takes keyword-only `config`, `backend`, `lifecycle_root`, `proxy_manager`, `resource_pool`, `model_name`, and optional `clock`. Its `propose` keeps the current keyword-only E2B proposer call shape: `candidate_dir`, `evidence_dir`, `evolver_dir`, `diagnosis`, `iteration`, `run_id`, `run_dir`, and optional public-only `model_env`, returning `SandboxEvolverResult`.

Build a content-addressed evolver attempt ID from run, iteration, input/diagnosis digest, image/spec, and model. Atomically reserve the combined evolver-plus-proxy request before creating either container so partial acquisition cannot deadlock. Require `/tmp` and `/qea` bounded tmpfs. The configured sandbox lifetime must be at least the command timeout. Upload the deterministic bundle, provider-neutral `remote_evolver.py`, and scrubbed diagnosis; run setup and the evolver as separate structured argv calls; download and safely extract only candidate output plus the five proposal evidence files. Add backend/spec metadata to `_proposal_metadata()` while preserving every legacy field.

Keep `E2BFullHarnessProposer` unchanged as the explicit rollback/debug path; do not force it through the neutral proxy implementation. Use the existing neutral bundle/archive helpers in `qea/executors/bundles.py`, and implement any missing pure safety helper in the new module rather than changing E2B behavior. Change only `remote_evolver.py`'s provider-specific docstring; its execution semantics stay unchanged.

- [ ] **Step 4: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/test_sandbox_evolver.py tests/test_e2b_evolver.py
git add qea/executors/sandbox_runtime.py qea/executors/sandbox_evolver.py qea/executors/sandbox_nexau.py qea/executors/remote_evolver.py qea/loop_benchmark.py tests/test_sandbox_evolver.py tests/test_sandbox_nexau.py
git commit -m "feat(evolver): run full-harness proposals in sandboxes"
```

## Task 7: Add the Rootless Runtime Catalog and Task Routers

**Files:**

- Create: `qea/rootless_runtime.py`
- Modify: `qea/executors/sandbox_nexau.py`
- Create: `tests/test_rootless_runtime.py`
- Modify: `tests/test_sandbox_nexau.py`

- [ ] **Step 1: Write manifest and router tests**

Build small explicit image-set fixtures and prove the catalog rejects:

- mutable tags or malformed Docker image IDs;
- duplicate/missing base, proxy, evolver, worker, or verifier roles;
- wrong benchmark commit/task ID;
- mismatched manifest identity, dependency lock, or declared resource contract;
- unexpected task roles or a task outside the requested panel.

Router tests must prove:

- each task selects its exact worker/verifier image and resources;
- worker lease covers proxy plus worker declared resource totals and releases before verifier acquisition;
- worker router creates an attempt-scoped proxy/network and passes only its URL plus placeholder key;
- verifier router never opens a proxy and always uses `network_policy="none"`;
- with separate worker/verifier pools, a fast worker's verifier may overlap a still-running worker only when the weighted capacity permits;
- completed worker execution and verifier score are reused on resume without new containers.

Run:

```bash
.venv/bin/python -m pytest -q tests/test_rootless_runtime.py tests/test_sandbox_nexau.py tests/test_qfbench_evolution.py
```

Expected: catalog/router imports fail.

- [ ] **Step 2: Implement immutable catalog loading**

Create:

```python
@dataclass(frozen=True)
class RootlessTaskRuntime:
    task_id: str
    worker_image_ref: str
    verifier_image_ref: str
    worker_resources: SandboxResourceContract
    verifier_resources: SandboxResourceContract
    identity_sha256: str

@dataclass(frozen=True)
class RootlessRuntimeCatalog:
    benchmark_commit: str
    base_image_ref: str
    evolver_image_ref: str
    proxy_image_ref: str
    tasks: Mapping[str, RootlessTaskRuntime]
    identity_sha256: str

```

Implement `load_rootless_runtime_catalog(image_set_manifest: Path, task_ids: Sequence[str], *, benchmark_commit: str) -> RootlessRuntimeCatalog`.

Load only the explicitly selected image-set index from Task 5. Recompute its top-level identity and each referenced role manifest/lock/resource identity; require the selected task panel to match exactly. Return a sorted read-only task mapping and the image-set digest for run identity. Never discover a formal run's image set by recursively scanning all historical manifests.

- [ ] **Step 3: Implement worker and verifier routers**

Create `RootlessWorkerRouter.execute` returning `WorkerExecution` and `RootlessVerifierRouter.verify` returning `OfficialTaskScore`, using the existing executor/verifier keyword signatures.

For a worker, reserve the combined worker and proxy resource request, open `SandboxProxyManager` with `network_scope=attempt.attempt_id`, instantiate `SandboxNexAUExecutor` with the task runtime and session URL, execute, close proxy/network, then release. Modify `SandboxNexAUExecutor` to put the explicit scope into `SandboxSpec`; retain the old run-scoped name only for legacy canary callers.

For a verifier, reserve its declared request, instantiate `SandboxQFBenchVerifier`, verify with no network, clean up, then release. Do not transfer trusted task material until after verifier creation.

- [ ] **Step 4: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/test_rootless_runtime.py tests/test_sandbox_nexau.py tests/test_qfbench_evolution.py
git add qea/rootless_runtime.py qea/executors/sandbox_nexau.py tests/test_rootless_runtime.py tests/test_sandbox_nexau.py tests/test_qfbench_evolution.py
git commit -m "feat(qfbench): route tasks through rootless runtime"
```

## Task 8: Build the Rootless Full-Harness Factory and Wire the CLI

**Files:**

- Modify: `pyproject.toml`
- Create: `qea/rootless_full_harness.py`
- Modify: `run.py`
- Create: `tests/test_rootless_full_harness.py`
- Modify: `tests/test_run_cli.py`

- [ ] **Step 1: Write CLI validation tests before production changes**

Test that:

- `--executor` accepts `rootless-docker` and `e2b`, defaulting to `rootless-docker` for QFBench full-harness runs;
- rootless accepts `--iters 1`, while preserving 3/5 schedules;
- rootless requires one preregistered config and one explicit image-set manifest;
- the config validates Docker socket/UID, public/trusted roots, owner-only token file, exact provider origin/path/model, resource capacities, headroom thresholds, and stage concurrency;
- separate worker/verifier concurrency is recorded in run identity, while legacy `--concurrency` remains an alias for worker concurrency;
- rootless rejects `--allow-verifier-network` and does not read `E2B_API_KEY` or require template manifests;
- rootless dispatch does not call `_load_dotenv` and never accepts the real model key through CLI/environment;
- selecting E2B preserves current validation and behavior;
- importing or constructing the rootless path succeeds when the E2B package is unavailable;
- a 30-task one-iteration dry-run estimate reports 60 official scoring attempts;
- CLI approval text describes model-provider egress and self-hosted compute, not E2B charges.

Run:

```bash
.venv/bin/python -m pytest -q tests/test_run_cli.py
```

Expected: new executor and options fail.

- [ ] **Step 2: Declare the actual rootless coordinator dependency**

Add a focused optional extra instead of making E2B a rootless dependency:

```toml
qfbench-rootless = [
  "PyYAML>=6.0",
]
```

The coordinator needs PyYAML for candidate admission; NexAU remains inside immutable runtime images. Leave the existing legacy `qfbench` extra unchanged.

- [ ] **Step 3: Implement the only production rootless assembly point**

Create:

```python
@dataclass(frozen=True)
class RoleExecutionLimits:
    pids_limit: int
    timeout_seconds: int
    writable_tmpfs_mb: Mapping[str, int]

@dataclass(frozen=True)
class RootlessFullHarnessConfig:
    docker_host: str
    expected_uid: int
    public_root: Path
    trusted_root: Path
    token_file: Path
    upstream_base_url: str
    allowed_path_prefix: str
    allowed_model: str
    evolver_resources: SandboxResourceContract
    proxy_resources: SandboxResourceContract
    worker_limits: RoleExecutionLimits
    verifier_limits: RoleExecutionLimits
    capacity: ResourceCapacity
    headroom: HostHeadroomPolicy
    worker_concurrency: int
    verifier_concurrency: int

@dataclass(frozen=True)
class RootlessFullHarnessRuntime:
    backend: SandboxBackend
    evaluator: QFBenchSandboxEvaluator
    proposer: SandboxFullHarnessProposer
    image_identity_digest: str
    scheduler_identity_digest: str
    runtime_identity_digest: str
```

`build_rootless_full_harness_runtime` takes `config`, `image_set_manifest`, benchmark snapshot/task panel, `run_id`, and `results_root`. It validates exact commit/tasks/resources/locks, takes an exclusive coordinator lock under the run root, constructs one backend and weighted pool, the proxy manager, per-task routers, neutral proposer, and two-stage evaluator, and returns the immutable runtime identities consumed by checkpoint identity. It imports no E2B module. Unit tests construct the factory with E2B absent and prove that any image/model/egress/resource/headroom/stage-concurrency change changes or rejects runtime identity.

- [ ] **Step 4: Split provider-specific CLI construction**

Refactor `_run_qfbench` into validation/common configuration plus `_run_qfbench_rootless` and `_run_qfbench_e2b`. Import E2B modules only inside the explicit E2B branch.

Add options:

```text
--rootless-config
--rootless-image-set-manifest
```

The JSON rootless config contains paths and policies but never the token value. The rootless branch passes the selected image set and config to the factory; the proxy manager alone reads the token file. Load `.env` only after selecting the explicit legacy E2B branch. Print the actual backend and immutable runtime identity rather than an unconditional E2B label.

- [ ] **Step 5: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/test_rootless_full_harness.py tests/test_run_cli.py tests/test_qfbench_evolution.py tests/test_rootless_runtime.py
git add pyproject.toml qea/rootless_full_harness.py run.py tests/test_rootless_full_harness.py tests/test_run_cli.py
git commit -m "feat(cli): default QFBench full harness to rootless"
```

## Task 9: Prove Full-Harness Isolation, Pipeline, and Resume Invariants

**Files:**

- Modify: `qea/rootless_canary.py`
- Modify: `scripts/smoke_qfbench_full_harness.py`
- Create: `tests/test_qfbench_rootless_full_harness.py`
- Modify: `tests/test_qfbench_isolation.py`
- Modify: `tests/test_qfbench_pilot_contract.py`
- Modify: `tests/test_rootless_canary.py`
- Modify: `tests/test_qfbench_full_harness_scripts.py`

- [ ] **Step 1: Build a fake-backend end-to-end harness test**

Run a one-iteration, two-task fake experiment through the real rootless factory and runner. The fake backend should block/release roles using events so the test proves this exact sequence:

1. exactly one evolver runs and exits;
2. admission fixes one candidate digest;
3. two workers may run concurrently;
4. task A verifier starts after A artifact finalization while task B worker is still live if capacity fits;
5. no verifier receives a proxy or network;
6. aggregation and keep/rollback occur only after both official scores;
7. checkpoints exist after proposal, admission, each artifact, each score, and aggregation.

Kill the coordinator fixture after the first score, reconstruct it with the same identity, and assert completed proposal/worker/score operations are not repeated. Change one catalog/model/resource/scheduler identity field and assert resume rejects drift.

- [ ] **Step 2: Add artifact/firewall assertions**

Recursively scan every evolver/worker visible bundle, spec, lifecycle record, trace, log, and artifact for sentinels representing official tests, reference values, held-out outcomes, real token, and `.env`; all must be absent. Assert verifier inputs contain only the matching finalized artifact and trusted task material. Assert no path or fixture contains an official solution lifecycle.

- [ ] **Step 3: Migrate canary/smoke assembly to production rootless code**

Update `rootless_canary.py` to load the explicit image set, recognize proxy/evolver roles, use attempt-scoped network handles, and call the production proxy/runtime factory rather than duplicating run-wide network assembly. Add a no-model evolver import/tool stage; do not make a model call in unit tests.

Add `--executor rootless-docker|e2b` to `scripts/smoke_qfbench_full_harness.py`, default rootless, with rootless config/image-set inputs. Rootless import mode and Rich mode must assemble through `build_rootless_full_harness_runtime`; the legacy E2B SDK/key/templates remain isolated to the explicit E2B branch. Exact reaping dispatches through the selected backend and records evolver/worker/verifier/proxy/network IDs, image/lock identities, request usage/cost, and cleanup state.

Extend the existing canary/script tests to prove rootless help/import paths make zero model requests, touch no E2B module/key/template, use offline verification, and leave an empty managed inventory.

- [ ] **Step 4: Run the integration tests**

```bash
.venv/bin/python -m pytest -q tests/test_qfbench_rootless_full_harness.py tests/test_qfbench_isolation.py tests/test_qfbench_pilot_contract.py tests/test_rootless_canary.py tests/test_qfbench_full_harness_scripts.py
```

Expected: all pass deterministically without Docker, network, E2B, or model credentials.

- [ ] **Step 5: Commit**

```bash
git add qea/rootless_canary.py scripts/smoke_qfbench_full_harness.py tests/test_qfbench_rootless_full_harness.py tests/test_qfbench_isolation.py tests/test_qfbench_pilot_contract.py tests/test_rootless_canary.py tests/test_qfbench_full_harness_scripts.py
git commit -m "test(qfbench): cover rootless full-harness resume"
```

## Task 10: Record the Direct-Cutover Decision and Verify the Phase

**Files:**

- Create: `docs/decisions/2026-07-30-qfbench-rootless-direct-cutover.md`
- Modify: `docs/PROJECT_MEMORY.md`
- Modify: `docs/runbooks/qfbench-rootless-docker-vm.md`

- [ ] **Step 1: Write the superseding decision**

Record the user's approved change: rootless Docker is now the default full-harness backend and a new matched E2B panel is not a prerequisite. Preserve the earlier E2B results and rootless r6 canary as dated evidence. Explicitly state residual shared-host admin risk, exact evaluator firewall rules, E2B explicit-fallback status, and the fact that remote paid rollout has not yet run.

- [ ] **Step 2: Update canonical memory and the runbook**

Update `docs/PROJECT_MEMORY.md` with a dated rootless direct-cutover entry pointing to the new decision and the approved design. In the runbook, document rootless-default CLI configuration, token-file permissions, immutable manifest input, caps, dry-run/preflight, exact-ID audit, and stop conditions. Do not add the secret value, `.env` contents, official tests, or remote host-private paths to Git.

- [ ] **Step 3: Create a clean full-dependency test environment**

The repository's lightweight `.venv` may not contain PyYAML. Create an isolated environment outside the worktree and install the edited rootless extra:

```bash
python3 -m venv /private/tmp/qea-rootless-full-harness-venv
/private/tmp/qea-rootless-full-harness-venv/bin/pip install -e '.[qfbench-rootless]' pytest
```

If package download is blocked by the local sandbox, request the normal network escalation; do not weaken dependency or test coverage.

- [ ] **Step 4: Run the focused and full regression suites**

```bash
/private/tmp/qea-rootless-full-harness-venv/bin/python -m pytest -q \
  tests/test_sandbox_backend.py \
  tests/test_rootless_docker_backend.py \
  tests/test_resource_lease.py \
  tests/test_execution_record.py \
  tests/test_model_proxy.py \
  tests/test_sandbox_proxy.py \
  tests/test_rootless_images.py \
  tests/test_rootless_image_set.py \
  tests/test_sandbox_evolver.py \
  tests/test_sandbox_nexau.py \
  tests/test_rootless_runtime.py \
  tests/test_rootless_full_harness.py \
  tests/test_qfbench_evolution.py \
  tests/test_qfbench_rootless_full_harness.py \
  tests/test_qfbench_isolation.py \
  tests/test_qfbench_pilot_contract.py \
  tests/test_rootless_canary.py \
  tests/test_qfbench_full_harness_scripts.py \
  tests/test_run_cli.py

/private/tmp/qea-rootless-full-harness-venv/bin/python -m pytest -q tests
```

Expected: all tests pass. Any API/E2B/live tests remain skipped behind their existing explicit environment flags; do not turn those flags on during this local core phase.

- [ ] **Step 5: Audit imports, placeholders, secrets, and worktree scope**

```bash
rg -n "TODO|FIXME|pass$|NotImplementedError" qea run.py tests/test_qfbench_rootless_full_harness.py
rg -n "E2B_API_KEY|from e2b|import e2b" qea/rootless_runtime.py qea/executors/sandbox_evolver.py qea/executors/sandbox_proxy.py
rg -n "official_solution|solutions/|\.env|OPENROUTER_API_KEY" qea run.py docs/runbooks/qfbench-rootless-docker-vm.md
git status --short
git diff --check
```

Expected: no implementation placeholders; no E2B dependency in rootless modules; no leaked secret/solution material; only the two pre-existing report modifications remain outside committed work; no whitespace errors.

- [ ] **Step 6: Commit documentation**

```bash
git add docs/PROJECT_MEMORY.md docs/decisions/2026-07-30-qfbench-rootless-direct-cutover.md docs/runbooks/qfbench-rootless-docker-vm.md
git commit -m "docs(qfbench): record rootless direct cutover"
```

- [ ] **Step 7: Produce the separate rollout plan**

After this core phase passes, write `docs/superpowers/plans/2026-07-30-qfbench-rootless-remote-rollout.md` covering reviewed source deployment, evolver/base/proxy/30 worker/30 verifier image publication, role/network/secret/cgroup canaries, actual model-route validation, fresh worker-verifier attempt, Rich evolver smoke, 30-verifier replay, five-task one-iteration pilot, five-task three-iteration pilot, 30-task kill/resume pilot, audit, and finally the 140-attempt 30×5 run. Do not execute that rollout from this core plan.

## Completion Gate

This phase is complete only when:

1. rootless full-harness construction needs neither the E2B package nor E2B credentials;
2. evolver, worker, verifier, and proxy all use the provider-neutral backend;
3. one evolver terminates before candidate fan-out;
4. workers are attempt-network-isolated and verifiers are offline;
5. weighted capacity bounds all concurrently live role resources;
6. one-iteration fake full-harness interruption/resume creates no duplicate completed work;
7. evaluator-firewall scans pass;
8. the full local test suite passes in the declared dependency environment;
9. `git status` contains no new uncommitted implementation files and still preserves the user's two report edits;
10. no remote build, model call, or paid scoring run was started by this phase.
