# QFBench Self-Hosted Rootless Docker Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a provider-neutral sandbox contract and a rootless-Docker QFBench worker/verifier backend, then prove resource, network, evaluator-firewall, lifecycle, resume, and verifier parity on `bc-server` without starting a formal 30-task scoring run.

**Architecture:** Keep the trusted coordinator outside containers. Run workers on a per-run internal Docker network with model access only through a credential-injecting proxy; run independent verifiers with `--network none`; move only content-addressed artifacts between roles. Preserve the existing E2B path unchanged while introducing backend-neutral lifecycle records, exact-ID cleanup, role-separated QFBench materialization, immutable image identities, and staged live canaries.

**Tech Stack:** Python 3.10+, pytest, rootless Docker Engine 29.x, Docker CLI, user systemd, Git/SSH, QFBench commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a`, NexAU pinned by the repository lock files.

## Global Constraints

- Work only on branch `qfbench-selfhosted-vm-backend`, based on `qfbench-full-harness-feedback-ab@0b04a35f5afe21ab9ca79c0c88c36a87f6597bac`; do not merge it.
- Keep `--executor e2b` as the default. Existing E2B template IDs, sandbox IDs, results, and completed Control/Rich A/B artifacts remain unchanged.
- Do not start a new 30-task, five-iteration, or paired A/B scoring run under this plan.
- Do not upload or execute official solutions. Worker-visible material must exclude `tests/`, references, raw rubric verdicts, credentials, and `.env`.
- Official tests may exist only in coordinator-trusted storage and a separate verifier container created with `--network none`.
- Never add `julius` to the system `docker` group and never connect this backend to `/var/run/docker.sock`.
- All host process execution uses argument vectors with `shell=False`. No task-controlled value may become shell syntax, a host path, a Docker option, or a container label key.
- Every live container must have QEA ownership labels, an immutable image reference, a persisted lifecycle manifest, a bounded resource contract, and exact-ID cleanup evidence.
- Secrets stay under `~/qea/runtime/secrets` with directory mode `700` and file mode `600`; they are not committed, copied from the local `.env`, mounted into workers, or printed.
- Stop at the first failed live gate. Treat image, transfer, proxy, dependency, isolation, verifier, or cleanup failures as infrastructure failures, never official score zeroes.
- Use test-driven development: add a failing focused test, run it and confirm the expected failure, implement the minimum behavior, rerun the focused test, then run the relevant regression slice.

---

## Task 1: Define and validate the provider-neutral sandbox contract

**Files:**

- Create: `qea/sandbox_backend.py`
- Create: `tests/test_sandbox_backend.py`

- [ ] **Step 1: Add failing tests for valid identity and invalid specifications**

  Cover deterministic identity, immutable mappings, path rules, label-safe identifiers, positive resources, allowed roles, allowed network policies, and immutable image references.

  ```python
  from types import MappingProxyType

  import pytest

  from qea.sandbox_backend import SandboxSpec, SandboxSpecError


  def make_spec(**changes):
      values = {
          "role": "worker",
          "run_id": "canary-20260728",
          "attempt_id": "attempt-001",
          "task_id": "historical-var-data-prep",
          "image_ref": "sha256:" + "a" * 64,
          "cpu_count": 2,
          "memory_mb": 4096,
          "pids_limit": 256,
          "timeout_seconds": 900,
          "network_policy": "worker-proxy-only",
          "environment": {"QEA_ROLE": "worker"},
          "writable_tmpfs_mb": {"/tmp": 256, "/qea": 512},
      }
      values.update(changes)
      return SandboxSpec(**values)


  def test_spec_digest_is_order_independent_and_mappings_are_immutable():
      left = make_spec(environment={"B": "2", "A": "1"})
      right = make_spec(environment={"A": "1", "B": "2"})
      assert left.spec_sha256 == right.spec_sha256
      assert isinstance(left.environment, MappingProxyType)
      with pytest.raises(TypeError):
          left.environment["A"] = "changed"


  @pytest.mark.parametrize(
      "change",
      [
          {"role": "oracle"},
          {"image_ref": "python:3.12"},
          {"cpu_count": 0},
          {"memory_mb": 0},
          {"pids_limit": 0},
          {"timeout_seconds": 0},
          {"network_policy": "host"},
          {"writable_tmpfs_mb": {"relative": 32}},
          {"writable_tmpfs_mb": {"/tmp/../host": 32}},
          {"environment": {"MODEL_API_KEY": "secret"}},
      ],
  )
  def test_spec_rejects_unsafe_values(change):
      with pytest.raises(SandboxSpecError):
          make_spec(**change)
  ```

- [ ] **Step 2: Run the focused tests and confirm collection fails**

  Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_sandbox_backend.py`

  Expected: failure with `ModuleNotFoundError: No module named 'qea.sandbox_backend'`.

- [ ] **Step 3: Implement immutable contract objects and the protocol**

  Define these public types in `qea/sandbox_backend.py`:

  ```python
  class SandboxSpecError(ValueError):
      """A sandbox request violates the backend-neutral safety contract."""


  @dataclass(frozen=True)
  class SandboxSpec:
      role: Literal["worker", "verifier", "proxy", "canary"]
      run_id: str
      attempt_id: str
      task_id: str
      image_ref: str
      cpu_count: int
      memory_mb: int
      pids_limit: int
      timeout_seconds: int
      network_policy: Literal["none", "worker-proxy-only", "proxy-outbound"]
      environment: Mapping[str, str] = field(default_factory=dict)
      writable_tmpfs_mb: Mapping[str, int] = field(default_factory=dict)

      @property
      def spec_sha256(self) -> str:
          return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


  @dataclass(frozen=True)
  class SandboxHandle:
      backend: str
      native_id: str
      immutable_image_ref: str
      spec_sha256: str


  @dataclass(frozen=True)
  class SandboxCommandResult:
      exit_code: int
      stdout: str
      stderr: str
      timed_out: bool


  @dataclass(frozen=True)
  class SandboxState:
      backend: str
      native_id: str
      status: str
      labels: Mapping[str, str]
      immutable_image_ref: str


  @dataclass(frozen=True)
  class KillResult:
      native_id: str
      outcome: Literal["killed", "already_absent"]


  class SandboxBackend(Protocol):
      def create(self, spec: SandboxSpec) -> SandboxHandle: pass
      def start(self, handle: SandboxHandle) -> None: pass
      def put_bytes(self, handle: SandboxHandle, path: str, payload: bytes) -> None: pass
      def read_bytes(self, handle: SandboxHandle, path: str) -> bytes: pass
      def run(
          self,
          handle: SandboxHandle,
          argv: Sequence[str],
          *,
          environment: Mapping[str, str],
          timeout_seconds: int,
      ) -> SandboxCommandResult: pass
      def inspect(self, native_id: str) -> SandboxState | None: pass
      def list(self, labels: Mapping[str, str]) -> Sequence[SandboxState]: pass
      def kill(self, native_id: str) -> KillResult: pass
  ```

  In `SandboxSpec.__post_init__`, copy mappings into sorted `MappingProxyType` values; reject secret-like environment values, except the exact public sentinel `qea-proxy-placeholder` for `OPENAI_API_KEY`; reject control characters, slashes, or values outside `[A-Za-z0-9_.-]` in identity fields; accept only `sha256:<64 lowercase hex>`, `<registry path>@sha256:<64 lowercase hex>`, or `e2b-template:<validated template ID>` image references; canonicalize with sorted compact JSON.

- [ ] **Step 4: Run focused and dependency-light regression tests**

  Run:

  ```bash
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_sandbox_backend.py
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_smoke.py
  ```

  Expected: both commands pass.

- [ ] **Step 5: Commit the contract**

  ```bash
  git add qea/sandbox_backend.py tests/test_sandbox_backend.py
  git commit -m "feat(sandbox): define backend-neutral contract"
  ```

## Task 2: Add lifecycle schema v2 and exact-ID backend-neutral reaping

**Files:**

- Create: `qea/sandbox_lifecycle.py`
- Create: `qea/sandbox_reaper.py`
- Create: `tests/test_sandbox_lifecycle.py`
- Create: `tests/test_sandbox_reaper.py`
- Preserve: `qea/e2b_reaper.py`
- Preserve: `tests/test_e2b_reaper.py`

- [ ] **Step 1: Write failing lifecycle and reaper tests**

  Tests must prove: atomic initial persistence before start, schema version 2 fields, terminal cleanup states, dry-run default, duplicate-ID rejection, label/spec mismatch refusal, and exact-ID-only kill.

  ```python
  def test_reaper_refuses_identity_mismatch(tmp_path):
      lifecycle = write_open_lifecycle(
          tmp_path,
          native_id="container-abc",
          spec_sha256="1" * 64,
      )
      backend = FakeBackend(
          states={
              "container-abc": make_state(
                  native_id="container-abc",
                  labels={"qea.managed": "true", "qea.spec-sha256": "2" * 64},
              )
          }
      )
      report = reap_sandboxes(tmp_path, backend=backend, apply=True)
      assert report.identity_mismatch_ids == ("container-abc",)
      assert backend.killed_ids == []
      assert read_json(lifecycle)["cleaned_up"] is False


  def test_reaper_dry_run_does_not_kill(tmp_path):
      write_open_lifecycle(tmp_path, native_id="container-abc")
      backend = FakeBackend(states={"container-abc": make_state(native_id="container-abc")})
      report = reap_sandboxes(tmp_path, backend=backend)
      assert report.pending_ids == ("container-abc",)
      assert backend.killed_ids == []
  ```

- [ ] **Step 2: Run focused tests and confirm missing-module failures**

  Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_sandbox_lifecycle.py tests/test_sandbox_reaper.py`

  Expected: collection fails because the lifecycle and reaper modules do not exist.

- [ ] **Step 3: Implement lifecycle schema v2**

  `SandboxLifecycle` must contain:

  - `schema_version=2`, `backend`, `role`, `run_id`, `attempt_id`, `task_id`;
  - `native_id`, `immutable_image_ref`, `spec_sha256`, and a JSON-safe copy of the resource contract;
  - `created_at`, optional `started_at`, optional `finished_at`, `cleaned_at`;
  - `cleaned_up`, `cleanup_method`, `cleanup_result`, and optional sanitized `failure`;
  - `attempt_identity_sha256` so resume compares run/config/image/input identities before reuse.

  Expose `create_lifecycle`, `mark_started`, `mark_finished`, and `mark_cleaned`. Each mutation must use same-directory temporary write, `flush`, `os.fsync`, and `os.replace`. Never persist environment values.

- [ ] **Step 4: Implement safe exact-ID reaping**

  `reap_sandboxes(root, *, backend, apply=False)` must:

  1. resolve `root` and require an existing directory;
  2. scan only `*-sandbox-lifecycle-v2.json` below it;
  3. reject malformed schema, backend mismatch, duplicate native IDs, empty IDs, and paths that resolve outside `root`;
  4. call `backend.inspect(native_id)` for each unfinished record;
  5. require labels `qea.managed=true`, `qea.backend=<backend>`, and `qea.spec-sha256=<record digest>`;
  6. report dry-run candidates without mutation;
  7. on `apply=True`, call `backend.kill(native_id)` and atomically persist `killed` or `already_absent`;
  8. retain `identity_mismatch` and `failed` as uncleaned records.

- [ ] **Step 5: Run new and legacy reaper tests**

  ```bash
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_sandbox_lifecycle.py tests/test_sandbox_reaper.py
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_e2b_reaper.py
  ```

  Expected: all pass; the v1 E2B reaper API is unchanged.

- [ ] **Step 6: Commit lifecycle work**

  ```bash
  git add qea/sandbox_lifecycle.py qea/sandbox_reaper.py tests/test_sandbox_lifecycle.py tests/test_sandbox_reaper.py
  git commit -m "feat(sandbox): add exact-ID lifecycle recovery"
  ```

## Task 3: Implement the rootless Docker backend with a fake command runner

**Files:**

- Create: `qea/backends/__init__.py`
- Create: `qea/backends/rootless_docker.py`
- Modify: `pyproject.toml`
- Create: `tests/test_rootless_docker_backend.py`

- [ ] **Step 1: Add failing command-construction and safety tests**

  Assert exact argv for `docker create`, `start`, `cp`, `exec`, `inspect`, `ps`, and `rm --force`. Include hostile task text and prove it remains one argv item. Prove the backend rejects the system socket, TCP endpoints, mutable tags, host paths, unknown labels, and unowned kill targets.

  ```python
  def test_create_emits_bounded_rootless_container_argv():
      runner = RecordingRunner(
          replies=[CompletedCommand(0, b"container-abc\n", b"")]
      )
      backend = RootlessDockerBackend(
          docker_host="unix:///run/user/1013/docker.sock",
          runner=runner,
      )
      handle = backend.create(make_spec())
      argv = runner.calls[0].argv
      assert argv[:3] == ("docker", "--host", "unix:///run/user/1013/docker.sock")
      assert "--read-only" in argv
      assert ("--cap-drop", "ALL") == adjacent_pair(argv, "--cap-drop")
      assert ("--security-opt", "no-new-privileges") == adjacent_pair(argv, "--security-opt")
      assert ("--memory", "4096m") == adjacent_pair(argv, "--memory")
      assert ("--memory-swap", "4096m") == adjacent_pair(argv, "--memory-swap")
      assert ("--pids-limit", "256") == adjacent_pair(argv, "--pids-limit")
      assert handle.native_id == "container-abc"


  def test_backend_rejects_system_docker_socket():
      with pytest.raises(RootlessDockerError, match="system Docker socket"):
          RootlessDockerBackend(
              docker_host="unix:///var/run/docker.sock",
              runner=RecordingRunner(),
          )
  ```

- [ ] **Step 2: Run the focused test and confirm the missing backend**

  Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_rootless_docker_backend.py`

  Expected: collection fails because `qea.backends.rootless_docker` does not exist.

- [ ] **Step 3: Implement a structured subprocess boundary**

  Add:

  ```python
  @dataclass(frozen=True)
  class CompletedCommand:
      returncode: int
      stdout: bytes
      stderr: bytes


  class CommandRunner(Protocol):
      def run(
          self,
          argv: Sequence[str],
          *,
          input_bytes: bytes | None = None,
          timeout_seconds: int | None = None,
      ) -> CompletedCommand: pass
  ```

  The production runner calls `subprocess.run(tuple(argv), shell=False, input=input_bytes, capture_output=True, timeout=timeout_seconds, check=False)`. Redact secrets from raised errors and truncate captured output to a declared maximum.

- [ ] **Step 4: Implement Docker operations and ownership checks**

  Build container creation from fixed options plus validated `SandboxSpec` fields. Required labels are:

  ```text
  qea.managed=true
  qea.backend=rootless-docker
  qea.role=<role>
  qea.run-id=<run_id>
  qea.attempt-id=<attempt_id>
  qea.task-id=<task_id>
  qea.spec-sha256=<spec_sha256>
  ```

  Use `--network none` for verifier/canary `none`. Add rootless-specific `create_internal_network(run_id)` and `remove_internal_network(run_id)` methods: create a deterministic QEA-labeled network with `docker network create --internal`; attach a worker only to that network; create a proxy on the rootless default outbound bridge and connect it to the internal network before starting it. Exact network removal must inspect and match the QEA run label first. Use `docker cp - <id>:<absolute path>` with a deterministic tar stream for uploads and `docker cp <id>:<path> -` for reads. Before `run`, `read`, `start`, or `kill`, inspect the native ID and verify all ownership labels and the handle digest. Return `already_absent` only for Docker's exact not-found result.

- [ ] **Step 5: Add timeout and decoding tests**

  Verify host timeout produces `SandboxCommandResult(timed_out=True, exit_code=124)` with bounded UTF-8 replacement decoding; a container exit does not become `timed_out`; nonzero Docker control-plane exits raise `RootlessDockerError` and are not benchmark results.

- [ ] **Step 6: Run focused and contract tests**

  ```bash
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_rootless_docker_backend.py
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_sandbox_backend.py tests/test_sandbox_lifecycle.py tests/test_sandbox_reaper.py
  ```

- [ ] **Step 7: Register the backend package and verify the built wheel**

  Add `qea.backends` to `[tool.setuptools].packages` in `pyproject.toml`. Build a wheel in a temporary directory, list its members, and require both `qea/backends/__init__.py` and `qea/backends/rootless_docker.py` to be present.

- [ ] **Step 8: Commit the backend**

  ```bash
  git add qea/backends pyproject.toml tests/test_rootless_docker_backend.py
  git commit -m "feat(sandbox): add rootless Docker adapter"
  ```

## Task 4: Add an E2B adapter without changing the existing E2B execution path

**Files:**

- Create: `qea/backends/e2b.py`
- Create: `tests/test_e2b_sandbox_backend.py`
- Reuse: `qea/executors/e2b_protocol.py`
- Preserve: `qea/executors/e2b_nexau.py`

- [ ] **Step 1: Write failing adapter contract tests with the existing fake SDK shape**

  Test create, file transfer, command result conversion, inspect/list capability reporting, native-ID kill, and preservation of E2B template IDs. The adapter must reject Docker image identities and accept an E2B identity of the form `e2b-template:<template-id>`.

- [ ] **Step 2: Run the focused tests and confirm collection failure**

  Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_e2b_sandbox_backend.py`

- [ ] **Step 3: Implement `E2BSandboxBackend` as a compatibility adapter**

  Keep a private mapping from native ID to live SDK object for create/start/upload/run/read/kill in the current process. Expose `supports_list=False` and raise a typed capability error for list/inspect operations the installed E2B SDK cannot prove safely. Do not emulate E2B inspect by guessing or call a broad account-wide kill API. Preserve SDK-native `sandbox_id` verbatim in `SandboxHandle.native_id`.

- [ ] **Step 4: Run the adapter plus the complete existing E2B executor slice**

  ```bash
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_e2b_sandbox_backend.py
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests -k "e2b or qfbench"
  ```

  Expected: the compatibility adapter passes and existing executor tests remain unchanged. Do not wire the adapter into `E2BNexAUExecutor` in this migration.

- [ ] **Step 5: Commit the compatibility adapter**

  ```bash
  git add qea/backends/e2b.py tests/test_e2b_sandbox_backend.py
  git commit -m "feat(sandbox): expose E2B compatibility adapter"
  ```

## Task 5: Materialize role-separated QFBench inputs without solutions

**Files:**

- Modify: `qea/benchmarks/qfbench.py`
- Create: `scripts/materialize_qfbench_rootless_snapshot.py`
- Modify: `tests/test_qfbench_adapter.py`
- Create: `tests/test_qfbench_rootless_materializer.py`

- [ ] **Step 1: Add failing path-classification and manifest tests**

  Test one fixture tree containing public environment/instruction files, official tests, a test reference file, and an official solution. Expected output:

  - `public/` contains only allowed Docker/base and task instruction/environment paths;
  - `trusted-verifier/` contains tests and verifier reference data;
  - neither tree nor either manifest contains a solution path;
  - a selected blob with a mismatched Git OID or SHA-256 aborts atomically;
  - an unexpected task-root path is denied instead of copied.

- [ ] **Step 2: Run focused tests and observe the missing API**

  Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_qfbench_rootless_materializer.py tests/test_qfbench_adapter.py`

- [ ] **Step 3: Implement an explicit role classifier**

  Add `classify_qfbench_path(path, *, task_ids) -> Literal["public", "trusted-verifier", "deny"]`. Use component-aware `PurePosixPath` checks, not substring checks. Allow only the pinned repository Docker/base paths already required by `materialize_qfbench_raw_snapshot`, plus these task subtrees:

  ```text
  tasks/<task_id>/instruction.md
  tasks/<task_id>/task.toml
  tasks/<task_id>/instruction/
  tasks/<task_id>/environment/
  tasks/<task_id>/tests/
  ```

  If the pinned repository represents instruction or environment as a file rather than a directory, allow that exact file after the fixture confirms the tree shape. Deny every `solution` component, archive, symlink/submodule entry, credential-like filename, and unknown task-root path.

- [ ] **Step 4: Implement a two-root materializer**

  Add `materialize_qfbench_role_snapshot` that first resolves every selected path and Git blob OID, downloads into a temporary directory, verifies the Git blob identity and SHA-256, writes deterministic public/trusted manifests, scans both temporary roots for forbidden components, and only then atomically renames them into place. The public manifest must not enumerate trusted paths. The trusted manifest may enumerate tests but never solutions.

- [ ] **Step 5: Add a dry-run-first CLI**

  `scripts/materialize_qfbench_rootless_snapshot.py` arguments:

  ```text
  --source-tree <local Git tree containing the pinned commit>
  --commit 024921eb507fcc0c4ffe3e0a96802724be1ae84a
  --task-id <repeatable>
  --task-panel-manifest <path>
  --public-root <path>
  --trusted-root <path>
  --plan-only (default)
  --apply
  ```

  Exactly one of repeatable `--task-id` or `--task-panel-manifest` is required. `--plan-only` prints counts, paths, blob IDs, and destination roles without downloading. `--apply` requires empty or absent destination version directories and refuses overwrite.

- [ ] **Step 6: Run tests and a local five-task plan-only command**

  Use the five task IDs pinned in `data/qfbench/MANIFEST.json`; read them programmatically from `pilot.optimize` and `pilot.held_out` instead of retyping them.

  ```bash
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_qfbench_rootless_materializer.py tests/test_qfbench_adapter.py
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python scripts/materialize_qfbench_rootless_snapshot.py \
    --source-tree /private/tmp/qea-qfbench-024921eb \
    --commit 024921eb507fcc0c4ffe3e0a96802724be1ae84a \
    --task-panel-manifest data/qfbench/MANIFEST.json \
    --public-root /tmp/qea-qfbench-public \
    --trusted-root /tmp/qea-qfbench-trusted \
    --plan-only
  ```

  Expected: the plan reports zero solution paths and performs no writes outside temporary planning state.

- [ ] **Step 7: Commit materialization changes**

  ```bash
  git add qea/benchmarks/qfbench.py scripts/materialize_qfbench_rootless_snapshot.py tests/test_qfbench_adapter.py tests/test_qfbench_rootless_materializer.py
  git commit -m "feat(qfbench): split public and verifier inputs"
  ```

## Task 6: Generate and record immutable rootless image builds

**Files:**

- Create: `qea/rootless_images.py`
- Create: `scripts/build_qfbench_rootless_images.py`
- Create: `tests/test_rootless_images.py`

- [ ] **Step 1: Write failing build-context firewall and manifest tests**

  Prove that worker/verifier contexts reject `solution`, `.env`, private keys, symlinks, sockets, device nodes, unknown files, and test paths in the worker context. Prove build plans pin base digests, hash generated Dockerfiles and lock files, and refuse mutable final identities.

- [ ] **Step 2: Run focused tests and confirm missing-module failure**

  Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_rootless_images.py`

- [ ] **Step 3: Implement deterministic build-plan objects**

  Add `RootlessImageBuildPlan` and `RootlessImageManifest`. Support a `base` role before task-specific `worker` and `verifier` roles. The base plan rewrites the QFBench base Dockerfile `FROM` to an immutable upstream digest and contains only the official `docker/` inputs plus the inert supervisor; task plans rewrite either official QFBench base family to the measured immutable local base image ID. Every plan contains role, task ID where applicable, QFBench commit, base image digest, sorted context members with SHA-256, generated Dockerfile bytes, dependency-lock hashes, CPU/memory/timeouts, and an identity digest. The manifest adds Docker Engine/rootless versions, final image ID, repository digest when available, and build timestamp.

- [ ] **Step 4: Implement dry-run-first build execution**

  Generate contexts beneath a new temporary directory, scan before calling Docker, and install the inert supervisor at `/usr/local/bin/qea-sandbox-supervisor` on the read-only image layer so the role tmpfs mounts cannot hide it. Invoke `docker build --pull=false --network=none` when dependencies are fully vendored, and use a dedicated explicitly allowed build network only for the dependency-warming phase. Runtime tests and references must never be baked into an image. Inspect the built image and require an immutable `sha256:` ID before writing the manifest atomically.

- [ ] **Step 5: Add CLI modes and test them with a fake runner**

  ```text
  --role base|worker|verifier
  --task-id <task-id> (required for worker and verifier)
  --public-root <versioned path>
  --trusted-root <versioned path> (required for verifier dependency warming only; never copied into context)
  --manifest-root <versioned path>
  --base-image-ref <immutable upstream digest for base, or measured QFBench base image ID for task roles>
  --docker-host unix:///run/user/<uid>/docker.sock
  --plan-only (default)
  --build
  ```

  `--build` refuses `/var/run/docker.sock`, a dirty or unverified materialization manifest, an existing manifest directory, and any solution path.

- [ ] **Step 6: Run focused tests**

  Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_rootless_images.py tests/test_qfbench_rootless_materializer.py`

- [ ] **Step 7: Commit image planning**

  ```bash
  git add qea/rootless_images.py scripts/build_qfbench_rootless_images.py tests/test_rootless_images.py
  git commit -m "feat(qfbench): add immutable rootless image builds"
  ```

## Task 7: Run QFBench workers and offline verifiers through the neutral backend

**Files:**

- Create: `qea/executors/sandbox_nexau.py`
- Create: `tests/test_sandbox_nexau.py`
- Reuse: `qea/executors/bundles.py`
- Reuse: `qea/executors/e2b_nexau.py`
- Preserve: `qea/loop_benchmark.py`

- [ ] **Step 1: Write failing fake-backend tests for role separation and failure taxonomy**

  Tests must prove:

  - worker creation receives only `build_worker_bundle` output and proxy-placeholder environment;
  - verifier creation is independent, `network_policy="none"`, and receives only tests plus the hashed artifact archive;
  - no official solution lifecycle or method exists;
  - the inert container starts only after lifecycle persistence, then upload writes into the running tmpfs before task execution;
  - behavioral timeout becomes official zero only when the task command reached its declared timeout;
  - create/start/upload/proxy/verifier/cleanup errors remain typed infrastructure failures;
  - artifacts are hashed before upload and after verifier extraction;
  - proposer-facing feedback contains only the existing answer-free contract.

- [ ] **Step 2: Run focused tests and confirm collection failure**

  Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_sandbox_nexau.py`

- [ ] **Step 3: Extract backend-independent parsing without changing E2B behavior**

  Reuse the existing remote runner payload, NexAU summary parser, artifact collector, verifier score parser, dependency-lock hash logic, and sanitized feedback constructors. If a helper is currently nested in `e2b_nexau.py`, move it to `sandbox_nexau.py` only after adding a characterization test that compares old and new output byte-for-byte for the same fixture. Import the helper back into `e2b_nexau.py` so the E2B path remains behaviorally identical.

- [ ] **Step 4: Implement `SandboxNexAUExecutor`**

  Constructor dependencies must be explicit: backend, lifecycle root, immutable worker image ref, public task root, resource contract, worker network name, proxy base URL, placeholder API key, and clock. Do not accept a real model key. Create lifecycle immediately after `backend.create`, start only the fixed inert supervisor, upload the deterministic bundle into running tmpfs, execute the runner with structured argv, collect bounded outputs and artifacts, mark finish, and clean by exact native ID in `finally`.

- [ ] **Step 5: Implement `SandboxQFBenchVerifier`**

  Constructor receives a separate backend handle factory, trusted test root, immutable verifier image ref, and verifier resource contract. Force `network_policy="none"` regardless of caller input. Copy tests and artifact archive only after creation; run the exact official verifier command already characterized by E2B tests; return only scalar reward, bounded pass/fail counts, content hashes, dependency identity, and sanitized criterion evidence.

- [ ] **Step 6: Run focused, E2B characterization, and firewall tests**

  ```bash
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_sandbox_nexau.py
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests -k "e2b_nexau or bundle or firewall or verifier"
  ```

- [ ] **Step 7: Commit executor work**

  ```bash
  git add qea/executors/sandbox_nexau.py qea/executors/e2b_nexau.py tests/test_sandbox_nexau.py
  git commit -m "feat(qfbench): run isolated roles via sandbox backend"
  ```

## Task 8: Add the fixed-upstream credential proxy and secret non-exposure tests

**Files:**

- Create: `qea/model_proxy.py`
- Create: `scripts/run_qea_model_proxy.py`
- Create: `tests/test_model_proxy.py`

- [ ] **Step 1: Write failing proxy policy tests against local fixture servers**

  Use an HTTP fixture upstream and a fixture proxy listener. Verify: fixed host/path routing, inbound `Authorization` removal, configured bearer injection, alternate absolute-form host rejection, hop-by-hop header removal, bounded request bodies, response streaming, disabled access logging, sanitized errors, and graceful shutdown. Scan captured stdout/stderr and the worker request echo for the real key; both must be absent.

- [ ] **Step 2: Run focused tests and confirm missing-module failure**

  Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_model_proxy.py`

- [ ] **Step 3: Implement the narrow reverse proxy**

  Use Python standard-library `ThreadingHTTPServer` plus `http.client.HTTPConnection` or `HTTPSConnection`. Configuration contains one parsed upstream origin, one allowed path prefix, bearer token loaded from a file descriptor or mode-`600` file, request/response size limits, connect/read timeouts, and no access logger. Reject `CONNECT`, upgrade requests, alternate hosts, userinfo, fragments, path traversal, and all methods except the model API methods required by the current provider fixture.

- [ ] **Step 4: Keep the secret out of process arguments and Docker inspect**

  `scripts/run_qea_model_proxy.py` accepts `--token-file`, not a token value. Create the proxy with a tmpfs at `/run/qea-secrets`, start its fixed entrypoint waiting for `/run/qea-secrets/model-token`, then upload the token bytes to that running tmpfs with mode `600`; do not use an environment variable, process argument, Docker secret label, image layer, or host bind mount. The worker receives `OPENAI_BASE_URL=http://qea-model-proxy:<port>/v1` and `OPENAI_API_KEY=qea-proxy-placeholder`. Add a recursive secret scan over worker inspect JSON, environment, filesystem, logs, trace, summary, artifacts, and lifecycle output, plus proxy inspect JSON, arguments, environment, and logs. Delete the proxy container by exact ID after each run so the tmpfs disappears.

- [ ] **Step 5: Run focused tests and repository secret/firewall slices**

  ```bash
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_model_proxy.py
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests -k "secret or firewall or network"
  ```

- [ ] **Step 6: Commit proxy work**

  ```bash
  git add qea/model_proxy.py scripts/run_qea_model_proxy.py tests/test_model_proxy.py
  git commit -m "feat(sandbox): add fixed-upstream model proxy"
  ```

## Task 9: Build a dry-run-first rootless canary CLI

**Files:**

- Create: `qea/rootless_canary.py`
- Create: `scripts/run_qfbench_rootless_canary.py`
- Create: `tests/test_rootless_canary.py`
- Create: `configs/qfbench_rootless_canary.json`

- [ ] **Step 1: Write failing stage-order and stop-on-failure tests**

  Model these ordered stages exactly:

  ```text
  daemon
  immutable-images
  resources-2cpu-4gib
  resources-4cpu-8gib
  filesystem-and-capabilities
  verifier-no-egress
  worker-proxy-synthetic
  nexau-no-model
  force-kill-reap-resume
  verifier-replay
  historical-var-seed-worker
  ```

  Assert the CLI defaults to planning, requires `--apply` for live mutation, persists one JSON result per stage, records `not_run` after the first failure, and never exposes a command for formal 30-task scoring.

- [ ] **Step 2: Run focused tests and confirm missing-module failure**

  Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_rootless_canary.py`

- [ ] **Step 3: Implement static preflight and identity checks**

  Validate source commit, clean worktree, QFBench commit, public/trusted manifest digests, image digests, Docker host, rootless security options, user namespace range, cgroup v2 controllers, secret file modes, and absence of solution paths. Emit a redacted plan with exact intended container/network names and zero secret values.

- [ ] **Step 4: Implement resource and isolation evidence collection**

  Inside each canary container, collect and hash:

  ```text
  /sys/fs/cgroup/cpu.max
  /sys/fs/cgroup/memory.max
  /sys/fs/cgroup/memory.swap.max
  /sys/fs/cgroup/pids.max
  /proc/self/status
  /proc/self/mountinfo
  /proc/net/route
  /proc/net/ipv6_route
  ```

  Also record effective UID/GID, `CapEff`, writable paths, network interfaces, Docker-socket absence, and cross-attempt marker absence. Compare observed values to the declared spec and fail closed.

- [ ] **Step 5: Implement network canaries**

  For verifier `--network none`, require DNS, public IPv4 raw TCP, public IPv6 raw TCP, HTTP, HTTPS, GitHub, PyPI, model host, `169.254.169.254`, and Docker socket access to fail. For workers, require the same direct requests to fail while a synthetic request through the internal proxy succeeds. Run the secret scanner after the proxy call.

- [ ] **Step 6: Implement force-kill/reaper/resume and replay gates**

  Use a child coordinator process with a deterministic marker. After it persists a live lifecycle record, terminate only that coordinator PID, run the reaper dry-run, assert the exact native ID, apply the kill, and resume using the same attempt identity. Assert completed content hashes are reused and no completed model/verifier operation is duplicated. Replay a previously recorded, content-addressed historical artifact through the self-hosted verifier and compare reward, bounded counts, test hash, and dependency-lock hash against its recorded E2B result.

- [ ] **Step 7: Implement the fresh seed-worker gate**

  Run only `historical-var-data-prep`, one worker attempt, and one independent offline verifier. Assert no oracle lifecycle, no solution member, no worker test member, and no verifier network. Record model identity, token/cost fields when the provider exposes them, and `null` for unavailable billing fields.

- [ ] **Step 8: Run CLI unit tests and a local plan-only command**

  ```bash
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_rootless_canary.py
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python scripts/run_qfbench_rootless_canary.py \
    --config configs/qfbench_rootless_canary.json \
    --plan-only
  ```

  The config file must contain only public identities and paths relative to the remote runtime root; secrets are referenced by an external file path.

- [ ] **Step 9: Commit the canary harness**

  ```bash
  git add qea/rootless_canary.py scripts/run_qfbench_rootless_canary.py tests/test_rootless_canary.py configs/qfbench_rootless_canary.json
  git commit -m "feat(qfbench): add rootless backend canary gates"
  ```

## Task 10: Add the remote-host preflight and deployment runbook

**Files:**

- Create: `scripts/check_qfbench_rootless_host.py`
- Create: `tests/test_rootless_host_check.py`
- Create: `tests/fixtures/rootless_host_bc.json`
- Create: `docs/runbooks/qfbench-rootless-docker-vm.md`

- [ ] **Step 1: Write failing parser tests for the known host requirements**

  Cover rootless socket path, UID, `newuidmap`, `newgidmap`, `/etc/subuid`, `/etc/subgid`, user namespaces, cgroup v2 controllers, user systemd, linger, rootless security options, filesystem space, memory, CPU, Docker version, Git commit, and secret/runtime directory modes. Tests use recorded command outputs and perform no SSH.

- [ ] **Step 2: Run focused tests and confirm missing-module failure**

  Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_rootless_host_check.py`

- [ ] **Step 3: Implement a read-only host checker**

  The script emits JSON and a human summary; it never installs packages, changes groups, starts services, writes secrets, or creates Docker resources. Exit `0` only when every required item is proven. Mark optional `fuse-overlayfs` as unnecessary on the observed kernel/ext4 host rather than failing.

- [ ] **Step 4: Document exact remote bootstrap commands**

  The runbook must contain these phases and safeguards:

  1. verify `ssh bc`, forwarded GitHub auth on port 443, VPN `/32` route, host identity, capacity, and shared-host load;
  2. create `~/qea/git`, `~/qea/worktrees`, `~/qea/runtime/{images,qfbench-public,trusted-verifier,secrets}`, and `~/qea/runs` with explicit modes;
  3. initialize `~/qea/git/evolving-quant-agent.git` as a bare repository;
  4. push only the committed feature branch to `bc:~/qea/git/evolving-quant-agent.git` and create the named remote worktree;
  5. install rootless Docker for `julius` with `dockerd-rootless-setuptool.sh install`, confirm `systemctl --user status docker`, and export only `DOCKER_HOST=unix:///run/user/1013/docker.sock` in the experiment shell;
  6. run the read-only host checker and plan-only materializer/image/canary commands;
  7. apply materialization, image builds, and canaries one gate at a time;
  8. run long coordinators in `tmux`, record exact PIDs/IDs, and use exact-ID reaping;
  9. stop user Docker and remove only explicitly named QEA canary resources if rollback is required.

  Explicitly prohibit recursive repo copy, local `.env` transfer, solution materialization, system Docker access, broad `docker system prune`, and wildcard cleanup.

- [ ] **Step 5: Run tests and validate shell snippets manually with non-mutating commands**

  ```bash
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests/test_rootless_host_check.py
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python scripts/check_qfbench_rootless_host.py --fixture tests/fixtures/rootless_host_bc.json
  ```

- [ ] **Step 6: Commit deployment documentation**

  ```bash
  git add scripts/check_qfbench_rootless_host.py tests/test_rootless_host_check.py tests/fixtures/rootless_host_bc.json docs/runbooks/qfbench-rootless-docker-vm.md
  git commit -m "docs(qfbench): add rootless VM deployment runbook"
  ```

## Task 11: Run the complete local verification gate

**Files:**

- Modify only if failures reveal a scoped defect in files from Tasks 1–10.

- [ ] **Step 1: Confirm the worktree and dependency identities**

  ```bash
  git status --short --branch
  git rev-parse HEAD
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python --version
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pip freeze
  ```

  Save dependency output under an untracked temporary audit path, not in the commit.

- [ ] **Step 2: Run formatting-independent static checks**

  ```bash
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m compileall -q qea scripts
  git diff --check
  rg -n "(/var/run/docker.sock|solution/|MODEL_API_KEY|OPENAI_API_KEY)" qea scripts configs docs/runbooks tests
  ```

  Inspect every match. The system-socket and secret-key names may appear only in rejection tests or explanatory error text; solution paths may appear only in firewall tests and prohibitions.

- [ ] **Step 3: Run focused backend and firewall suites**

  ```bash
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider \
    tests/test_sandbox_backend.py \
    tests/test_sandbox_lifecycle.py \
    tests/test_sandbox_reaper.py \
    tests/test_rootless_docker_backend.py \
    tests/test_e2b_sandbox_backend.py \
    tests/test_qfbench_rootless_materializer.py \
    tests/test_rootless_images.py \
    tests/test_sandbox_nexau.py \
    tests/test_model_proxy.py \
    tests/test_rootless_canary.py \
    tests/test_rootless_host_check.py
  ```

- [ ] **Step 4: Run the complete repository test suite**

  Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests`

  Expected: exit code `0`; record the test count and duration. Skips are acceptable only when they are existing documented network/paid gates or the new live rootless gate.

- [ ] **Step 5: Run existing deterministic harness smoke**

  Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python run.py --mock`

  Expected: the deterministic evolve/falsify/rollback fixture completes without credentials.

- [ ] **Step 6: Review the diff and commit any verified corrections**

  ```bash
  git status --short
  git diff --stat 0b04a35f5afe21ab9ca79c0c88c36a87f6597bac..HEAD
  git diff --check 0b04a35f5afe21ab9ca79c0c88c36a87f6597bac..HEAD
  ```

  If corrections were needed, commit them with a scoped message. Do not squash evidence-bearing commits during implementation.

## Task 12: Bootstrap `bc-server` without sudo and transfer only committed source

**Files:**

- Remote mutation only under `julius` home and user systemd.
- No repository source changes unless the live preflight reveals a code defect.

- [ ] **Step 1: Re-verify the live connection and machine class**

  From the local machine, run read-only checks for `ssh bc`, hostname, UID, 64 CPU, memory, filesystem, cgroup v2, user namespace ranges, user systemd, linger, Docker/rootless prerequisites, forwarded GitHub authentication, and the `/32` VPN route. Abort if the host identity, UID, route, or prerequisite state differs from the recorded design.

- [ ] **Step 2: Initialize the remote bare repository and runtime directories**

  Create only the explicit paths in the design. Set trusted/secrets directories to `700`; set public/image/run directories to `750` or stricter. Initialize the bare Git repository only if absent. If it exists, verify it is a bare repository owned by `julius` before use.

- [ ] **Step 3: Push the feature branch to the SSH Git remote**

  Add a temporary local remote named `bc-qea` targeting `bc:~/qea/git/evolving-quant-agent.git`, verify its URL, and push only `qfbench-selfhosted-vm-backend`. Do not push `.env`, untracked files, generated results, `.claude`, or virtual environments. On the VM, create the named worktree from that branch and verify its HEAD equals the local commit.

- [ ] **Step 4: Install and start rootless Docker for `julius`**

  Run `dockerd-rootless-setuptool.sh install` as `julius`, not through sudo. Start and enable `docker.service` with `systemctl --user`; verify `loginctl show-user julius -p Linger` remains `yes`. Set `DOCKER_HOST=unix:///run/user/1013/docker.sock` in the tmux experiment shell only. Confirm `docker info` reports rootless security options and does not address the system socket.

- [ ] **Step 5: Run the committed read-only host preflight remotely**

  Save the JSON result under `~/qea/runs/preflight-20260728/`. If any required item fails, stop; do not build images or create containers.

- [ ] **Step 6: Record the remote deployment identity**

  Record source commit, branch, Docker client/server versions, rootless socket, kernel, cgroup mode, CPU/memory/filesystem snapshot, user namespace range, and public IP reachability from the coordinator. Exclude environment values, SSH agent contents, secret paths beyond their declared location, and credentials.

## Task 13: Execute live isolation and lifecycle canaries

**Files:**

- Live artifacts: `~/qea/runs/qfbench-rootless-canary-20260728/`
- Local source changes only for a reproduced and tested defect.

- [ ] **Step 1: Run materialization in plan-only mode, inspect it, then apply**

  Use the pinned QFBench commit and five-task public panel. Confirm the plan includes zero solution paths. Apply into new versioned public and trusted roots; verify file modes, blob IDs, SHA-256 values, and the public/trusted separation scan.

- [ ] **Step 2: Build worker and verifier images one role at a time**

  Run plan-only, inspect the context member list, then build. Record final immutable image IDs/digests. Scan image histories and exported filesystem listings for tests, references, solutions, credentials, host paths, and Docker sockets. Stop if any forbidden member is present.

- [ ] **Step 3: Run daemon, image, and two resource gates**

  Require exact observed cgroup values for 2 CPU/4 GiB and 4 CPU/8 GiB, including swap equal to memory and the declared PID limit. Record host load before and after. Do not proceed if rootless cgroup delegation does not enforce the contract.

- [ ] **Step 4: Run filesystem, capability, socket, metadata, and cross-attempt gates**

  Require read-only root, bounded tmpfs, `CapEff` without added capabilities, `no-new-privileges`, no host mounts, no Docker socket, failed metadata access, and absent markers from another attempt.

- [ ] **Step 5: Run verifier no-egress and worker synthetic-proxy gates**

  Require every verifier network probe to fail. Require worker direct probes to fail while the synthetic proxy succeeds. Search all worker-visible surfaces for the synthetic real token and require zero matches before using a paid provider token.

- [ ] **Step 6: Run the exact-image NexAU no-model gate**

  Import NexAU, load its pinned dependency lock, invoke non-network tools used by the worker runner, and write/read a synthetic artifact. This gate must make no model call and no verifier call.

- [ ] **Step 7: Run force-kill, dry reaper, exact kill, and resume**

  Verify the dry report contains one exact native ID, apply contains the same ID, lifecycle cleanup is atomic, resume reuses completed hashes, no duplicate operation occurs, and the final managed-container list is empty.

- [ ] **Step 8: Record a gate summary before any historical artifact or paid model call**

  The summary contains pass/fail, evidence hashes, durations, unavailable billing fields as `null`, and the exact first failure if present. If any stage failed, stop here and keep formal scoring blocked.

## Task 14: Execute verifier replay and one fresh historical-var seed-worker canary

**Files:**

- Live artifacts: `~/qea/runs/qfbench-rootless-canary-20260728/`
- Create after results: `docs/reports/2026-07-28-qfbench-rootless-backend-canary-report.md`
- Modify after decision: `docs/PROJECT_MEMORY.md`
- Create after decision: `docs/decisions/2026-07-28-qfbench-rootless-backend-gate.md`

- [ ] **Step 1: Select one historical artifact by recorded content hash**

  Choose an existing `historical-var-data-prep` worker artifact that already has an official E2B verifier result. Record its source run, attempt ID, artifact hash, E2B verifier image/template identity, test hash, dependency-lock hash, reward, and bounded counts. Do not copy a solution or oracle output.

- [ ] **Step 2: Replay the artifact through the self-hosted offline verifier**

  Require identical artifact hash after transfer, identical official reward, identical bounded counts, identical executed-test hash, identical dependency-lock hash, verifier `--network none`, and zero worker/model lifecycle. A mismatch blocks the fresh worker and formal scoring.

- [ ] **Step 3: Run one fresh seed worker and independent verifier**

  Use only the public `historical-var-data-prep` instruction/environment, the immutable worker image, proxy-only model access, and the isolated verifier. This is one paid model attempt plus its worker/verifier lifecycles, not an evolution iteration. Record tokens/cost when exposed and do not infer missing billing values.

- [ ] **Step 4: Audit evaluator exposure and cleanup**

  Recursively scan worker/evolver prompts, trace, summary, artifacts, environment, inspect output, and logs for tests, references, solutions, raw rubric verdicts, and credentials. Require zero live QEA container IDs and no leftover per-run networks except explicitly retained evidence metadata.

- [ ] **Step 5: Run the quant-research readiness gate**

  Mark performance publication `NOT_READY` because this plan establishes backend parity/isolation only and produces no repeated performance estimate. Confirm no data split, reward aggregation, transaction-cost assumption, benchmark attribution, or completed A/B result changed.

- [ ] **Step 6: Write the dated canary report and decision**

  Report every gate, exact identities, evidence paths/hashes, failures, costs, and limitations. State one of:

  - `accepted for five-task backend panel; formal 30-task scoring remains blocked`, or
  - `not accepted; E2B remains the only formal-scoring backend`.

  Update `docs/PROJECT_MEMORY.md` and add a new decision record; do not rewrite the 2026-07-21 through 2026-07-27 historical reports.

- [ ] **Step 7: Verify and commit the evidence documents**

  ```bash
  git diff --check
  /Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests
  git add docs/reports/2026-07-28-qfbench-rootless-backend-canary-report.md docs/decisions/2026-07-28-qfbench-rootless-backend-gate.md docs/PROJECT_MEMORY.md
  git commit -m "results(qfbench): record rootless backend canary"
  ```

  Do not commit raw secrets, trusted test sources, generated containers, `.env`, or host-specific private state. Do not merge the branch.

## Completion Gate

Implementation is complete only when:

- Tasks 1–11 pass locally with a clean worktree and the unchanged E2B path;
- Tasks 12–13 prove rootless daemon identity, immutable images, resource controls, firewall, proxy secret non-exposure, exact-ID cleanup, and idempotent resume on `bc-server`;
- Task 14 proves offline verifier parity and one fresh oracle-free seed-worker lifecycle;
- the dated report explicitly distinguishes backend evidence from model-performance evidence;
- the final managed-container inventory is empty;
- no full 30-task or five-iteration experiment has been started;
- no branch has been merged.
