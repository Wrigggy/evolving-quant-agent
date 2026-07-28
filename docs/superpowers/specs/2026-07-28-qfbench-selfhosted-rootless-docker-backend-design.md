# QFBench Self-Hosted Rootless Docker Backend Design

> Date: 2026-07-28
> Status: proposed for implementation and parity canaries; not approved for formal scoring
> Base branch: `qfbench-full-harness-feedback-ab` at `0b04a35f5afe21ab9ca79c0c88c36a87f6597bac`
> Target host: `julius@bc-server`, reached through the `bc` SSH alias and an exact `/32` OpenVPN route

## Objective

Add a provider-neutral sandbox boundary and a self-hosted rootless Docker backend so QEA can run QFBench workers and independent offline verifiers on the shared 64-core CPU host without granting `julius` sudo or access to the system Docker socket. The first accepted result is an isolation and parity canary, not a benchmark-performance claim and not a replacement for the measured E2B backend.

The implementation must preserve the completed full-harness Control/Rich A/B, its E2B identities, the evaluator firewall, content-addressed resume, and exact-ID cleanup. No official solution is uploaded or executed. Formal 30-task scoring remains on E2B until the new backend passes every gate in this design and a new dated decision accepts the evidence.

## Scope

This design includes:

- a provider-neutral sandbox protocol above create, transfer, execution, inspection, exact kill, and lifecycle metadata;
- an E2B adapter that preserves existing behavior and native E2B identifiers;
- a local rootless Docker adapter used by a coordinator running on `bc-server`;
- digest-recorded Docker image builds for the pinned QFBench base and selected task roles;
- worker-only model access through an internal credential proxy;
- independent verifier containers with `--network none`;
- exact CPU, memory, PID, writable-space, timeout, and read-only-root controls;
- lifecycle manifests, exact-ID reaping, forced termination, and idempotent resume;
- public/no-secret canaries followed by an oracle-free `historical-var-data-prep` verifier parity run.

This design does not include:

- rerunning either completed 140-attempt A/B arm;
- promoting the Rich iteration-3 candidate;
- uploading or running QFBench official solutions;
- copying the local `.env`, `.ssh`, `.claude`, virtual environments, historical `results/`, or full QFBench repository to the VM;
- adding `julius` to the root-equivalent system `docker` group;
- claiming microVM-equivalent isolation, E2B parity, performance gain, or cost savings before measured evidence exists.

## Chosen Approach

Use the VM as a persistent coordinator and rootless Docker execution node. Source remains reviewable in local Git and is transferred through a bare Git repository plus a named remote worktree. The QFBench snapshot is materialized from the pinned public commit with an explicit role manifest; solutions are excluded. Secrets live outside the repository in a mode-`600` coordinator directory.

Two alternatives are rejected for formal scoring:

1. **System Docker group access.** Membership permits mounting the host filesystem and is effectively root on a shared server.
2. **Bare Python subprocesses or user-space `proot` wrappers.** They cannot provide reliable cgroup limits, network denial, mount separation, or exact container lifecycle evidence.

The fallback when rootless Docker is unavailable is a VM-resident coordinator with E2B workers/verifiers. That is operationally useful but is not a self-hosted backend.

## Runtime Architecture

```text
local Mac source-of-truth
  -> SSH Git push
  -> ~/qea/git/evolving-quant-agent.git (bare)
  -> ~/qea/worktrees/qfbench-selfhosted-vm-backend
       |
       +-- trusted coordinator process (julius)
       |     - checkpoints and lifecycle manifests
       |     - public worker bundles
       |     - trusted verifier bundles
       |     - rootless Docker control socket
       |
       +-- per-run internal worker network
       |     +-- worker container
       |     |     - no Docker socket
       |     |     - no tests, reference values, solutions, or real key
       |     |     - internal proxy is its only network peer
       |     +-- credential-proxy container
       |           - internal worker network plus outbound network
       |           - fixed HTTPS upstream only
       |           - injects the model Authorization header
       |
       +-- verifier container
             - --network none
             - independent writable filesystems
             - official tests copied only after creation
             - worker artifacts copied through a content-addressed archive
```

The coordinator is trusted and owns the rootless Docker socket. No worker, verifier, evolver, task bundle, or generated artifact receives or mounts that socket.

## Provider-Neutral Interfaces

Create `qea/sandbox_backend.py` with immutable value objects and a narrow protocol:

```python
@dataclass(frozen=True)
class SandboxSpec:
    role: str
    run_id: str
    attempt_id: str
    task_id: str
    image_ref: str
    cpu_count: int
    memory_mb: int
    pids_limit: int
    timeout_seconds: int
    network_policy: str
    environment: Mapping[str, str]
    writable_tmpfs: Mapping[str, int]

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

class SandboxBackend(Protocol):
    def create(self, spec: SandboxSpec) -> SandboxHandle: pass
    def put_bytes(self, handle: SandboxHandle, path: str, payload: bytes) -> None: pass
    def read_bytes(self, handle: SandboxHandle, path: str) -> bytes: pass
    def run(self, handle: SandboxHandle, argv: Sequence[str], *, environment: Mapping[str, str], timeout_seconds: int) -> SandboxCommandResult: pass
    def inspect(self, native_id: str) -> SandboxState | None: pass
    def list(self, labels: Mapping[str, str]) -> tuple[SandboxState, ...]: pass
    def kill(self, native_id: str) -> KillResult: pass
```

All calls use argv sequences or structured fields. The Docker adapter must never concatenate task-controlled text into a host shell command. Manifests retain `backend`, the provider-native ID, immutable image reference, spec digest, resource contract, timestamps, and cleanup result.

The existing E2B executor behavior is preserved behind `E2BSandboxBackend`; E2B template/build IDs remain authoritative and are not rewritten as Docker image IDs. `--executor e2b` remains the default and must pass the unchanged test suite.

## Rootless Docker Adapter

`qea/backends/rootless_docker.py` uses the Docker CLI through an injected command runner. Production commands are argv lists executed with `shell=False`; tests use a deterministic fake runner. The adapter talks only to `DOCKER_HOST=unix:///run/user/1013/docker.sock` and refuses `/var/run/docker.sock`.

Every container is created detached with:

- labels `qea.managed=true`, `qea.backend=rootless-docker`, role, run ID, attempt ID, task ID, and spec digest;
- immutable `image@sha256:digest`, never a mutable tag for a scored canary;
- `--cpus`, `--memory`, `--memory-swap` equal to memory, and `--pids-limit`;
- `--read-only`, `--cap-drop ALL`, and `--security-opt no-new-privileges`;
- no host PID, IPC, network, device, privileged, or host-path mounts;
- bounded tmpfs mounts for `/tmp`, `/qea`, `/app`, `/tests`, and `/logs` according to role;
- no Docker socket and no access to another attempt's writable storage.

The adapter creates the container before starting it, persists the lifecycle manifest immediately after receiving the native ID, and only then starts or copies data. A coordinator crash between create and start is therefore recoverable by exact ID.

Inside-container evidence records `/sys/fs/cgroup/cpu.max`, `memory.max`, `memory.swap.max`, and `pids.max`, plus the effective UID, capabilities, mounts, network interfaces, and absence of the Docker socket. A canary fails if declared and observed limits differ.

## Images and Dependency Identity

The VM materializes only `docker/`, the five public task instruction/environment trees needed for the canary panel, and their official `tests/` trees in coordinator-trusted storage. `solution/` paths are excluded at the manifest and downloader layers. Every file is checked against the pinned Git blob ID from QFBench commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a`.

`scripts/build_qfbench_rootless_images.py` generates role-specific build contexts:

- the worker context contains the public QFBench base, task environment, pinned NexAU Python 3.12 environment, runner, and dependency locks;
- the verifier context contains the task runtime and warmed official verifier dependencies, but not test source or expected/reference data;
- tests are copied into a verifier container only at attempt runtime;
- solutions are rejected from every build context.

The build manifest records the benchmark commit, source blob/hash set, generated Dockerfile hash, base image digest, final image ID/digest, CPU/memory/timeouts, NexAU lock hash, verifier lock hash, build timestamp, and Docker/rootless versions. Rebuilding a changed identity requires a new manifest directory.

## Network and Credential Boundary

Verifier containers use Docker `--network none`. The verifier canary must prove failure of:

- DNS resolution;
- raw TCP to public IPs;
- HTTP and HTTPS;
- GitHub, PyPI, package registries, and the model host;
- `169.254.169.254` and common cloud metadata names;
- the rootless Docker API socket.

Worker containers attach only to an internal per-run network. They cannot directly resolve or reach public destinations. A dedicated credential-proxy container attaches to that internal network and a rootless outbound network. Its configuration fixes one HTTPS upstream derived from `LLM_BASE_URL`, disables access logging, rejects alternate hosts, strips inbound authorization, and injects the real bearer token from a mode-`600` env file outside the repo.

The worker receives an internal HTTP base URL and a non-secret placeholder key. The real key must be absent from worker environment, filesystem, command arguments, process listings, stdout/stderr, trace, artifacts, Docker inspect output, and proposer evidence. The proxy never receives official tests or worker artifacts.

## Evaluator Firewall and Data Flow

Existing deterministic bundle builders remain the source of role separation:

```text
worker bundle   = public task files + candidate worker
verifier bundle = official tests + immutable worker artifacts
oracle bundle   = forbidden for this migration
```

Coordinator-trusted test storage is mode `700`. Worker container creation, image context, bundle members, mounts, and network peers are scanned for test/reference/solution canaries. The artifact archive is hashed before verifier upload and re-hashed after extraction. The verifier returns only official scalar reward, bounded pass/fail counts, content hashes, and sanitized public criterion evidence. Raw assertions, expected values, test names, trusted logs, and reference data remain outside proposer-facing files.

## Lifecycle, Failure, and Resume

Generalize lifecycle schema version 2 to include backend and provider-native identity. The exact-ID reaper:

1. scans only lifecycle manifests below the requested run root;
2. rejects duplicate or malformed native IDs;
3. inspects each ID and requires matching QEA labels and spec digest;
4. performs a dry run by default;
5. kills only explicitly listed unfinished IDs with `--apply`;
6. records `killed`, `already_absent`, `identity_mismatch`, or `failed` atomically.

The forced-failure canary starts a labeled container, records its lifecycle, kills the coordinator, runs a dry reaper, applies the exact kill, and resumes with the same run/config/image/manifest identities. Completed attempt hashes must be reused and no model call or verifier execution may be duplicated.

Worker behavioral timeout remains an official zero only after the runtime proves that the container reached the official task timeout. Container creation, image, transfer, proxy, dependency-lock, verifier-network, and cleanup failures remain infrastructure errors and are never converted to benchmark zeros.

## Deployment Layout

The remote host uses:

```text
~/qea/git/evolving-quant-agent.git/                 bare Git repository
~/qea/worktrees/qfbench-selfhosted-vm-backend/     execution worktree
~/qea/runtime/images/                               immutable build manifests
~/qea/runtime/qfbench-public/                       pinned public worker inputs
~/qea/runtime/trusted-verifier/                     mode-700 tests/reference inputs
~/qea/runtime/secrets/                              mode-700 directory, mode-600 files
~/qea/runs/                                         checkpoints, attempts, logs, lifecycles
```

Git transfers committed source and history only. Public task data uses a pinned materializer and manifest. Generated artifacts use targeted resumable transfer only when required. `.env`, `.ssh`, `.claude`, virtual environments, old results, output caches, inspection data, and solutions are not recursively copied.

The rootless daemon is installed and managed by `julius` through user systemd. `loginctl` linger keeps it alive after SSH logout. Long coordinators run in `tmux` and write checkpoints under `~/qea/runs`; loss of the VPN or local SSH session must not terminate them.

## Test and Canary Sequence

Run gates in this order and stop at the first failure:

1. Existing dependency-light and full local tests on the unchanged E2B path.
2. Protocol and Docker argv unit tests with a fake command runner.
3. Bundle firewall, path traversal, secret, symlink, label, identity, and exact-ID reaper tests.
4. Rootless daemon canary and immutable image digest inspection.
5. Resource canaries for exactly 2 CPU/4 GiB and 4 CPU/8 GiB, including cgroup evidence.
6. Read-only-root, capability, PID, tmpfs, Docker-socket, metadata, and cross-attempt isolation canaries.
7. Verifier `--network none` DNS/raw-TCP/HTTP/HTTPS/registry/model-host canary.
8. Worker internal-network and credential non-exposure canary with a synthetic echo endpoint before any paid model call.
9. No-model NexAU import/tool canary in the exact worker image.
10. Forced-kill, exact-ID reaper, and idempotent resume canary.
11. Replay one content-addressed historical worker artifact through both offline verifier backends and require identical official reward, pass/fail counts, and executed-test/dependency-lock hashes.
12. Run one fresh seed-worker `historical-var-data-prep` attempt with an independent offline verifier; no solution lifecycle is permitted.

Only after all twelve gates pass may a new decision authorize the same public five-task panel. A five-task pass is required before any 30-task repetition or provider-cost conclusion.

## Acceptance Criteria

The self-hosted canary is accepted only when:

1. The original E2B test suite and CLI behavior remain passing and E2B-native IDs remain unchanged.
2. Every Docker image and container has an immutable recorded identity and exact resource contract.
3. Worker direct egress fails, proxy-only model access succeeds, and the real credential is absent from all worker-visible surfaces.
4. Verifier DNS, raw TCP, HTTP, HTTPS, registries, metadata, model host, and Docker socket access all fail.
5. Tests/reference values never enter worker/evolver images, bundles, mounts, logs, traces, artifacts, or prompts.
6. Worker/verifier containers, writable filesystems, and networks are independent; handoff is artifact-only and hash-verified.
7. CPU, memory, swap, PID, writable-space, read-only-root, capability, and timeout evidence matches the task contract.
8. Forced kill, dry-run reaping, exact kill, and resume leave zero pending QEA container IDs and duplicate no completed operation.
9. The replay verifier result matches E2B for the same artifact payload, and the fresh seed-worker canary completes without an oracle or solution.
10. Run artifacts record source commit, public-data manifest, image digests, config digest, model identity, tokens/cost when exposed, lifecycle durations, failures, and unavailable billing fields as `null`.

Passing these criteria establishes self-hosted rootless Docker canary evidence. It does not establish microVM-equivalent security, stable model performance, held-out transfer, a formal evolution gain, or production readiness on an untrusted multi-user host.

## Research-Integrity Gate

Quant research publication remains `NOT_READY` during backend construction because this work changes infrastructure rather than signal logic and has no new repeated performance estimate. Data/split/leakage semantics, official reward aggregation, transaction-cost conventions inside tasks, benchmark attribution, and historical results remain unchanged. Any later performance report must separately pass the repository quant-research checklist and distinguish backend parity from model or harness improvement.
