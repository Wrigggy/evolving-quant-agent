# QFBench Self-Hosted Rootless Docker Direct-Cutover Design

> Date: 2026-07-30<br>
> Status: approved direction; ready for implementation planning<br>
> Target branch: `qfbench-selfhosted-vm-backend`<br>
> Target host: `julius@bc-server`<br>
> Supersedes: the requirement to keep E2B as the default formal-scoring backend or run a new matched E2B panel before cutover

## Objective

Move the complete QFBench full harness to the existing self-hosted rootless Docker runtime. A trusted coordinator runs as `julius` on `bc-server`; one isolated evolver proposes one candidate per iteration; multiple isolated task workers evaluate that candidate concurrently; independent offline verifiers score worker artifacts as they become available. New experiments use rootless Docker directly rather than treating it as a provider-parity pilot.

E2B historical runs remain immutable comparison evidence. The E2B adapter stays available as an explicit rollback/debug option, but new rootless runs do not require `E2B_API_KEY`, E2B templates, E2B lifecycle leases, or a new paid E2B comparison.

## Preserved Boundaries

Direct cutover changes orchestration, not benchmark semantics. It preserves:

- QFBench commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a`, the preregistered 20 optimize / 10 held-out split, official rewards, domain aggregation, and keep/rollback gates;
- the Rich answer-free feedback contract: optimize public goals/rubrics, worker-observable trajectories, candidate history, and sanitized criterion evidence may reach the evolver;
- strict isolation of official tests, reference values, trusted verifier logs, solutions, credentials, and held-out outcomes from evolver and worker surfaces;
- independent no-network verification, content-addressed attempts, immutable run identities, exact-ID cleanup, and idempotent resume;
- the prohibition on downloading, uploading, checking out, or running official solutions.

The shared-host administrator remains outside the container boundary and may theoretically inspect `julius`-owned files. That accepted residual risk must remain explicit in reports; rootless Docker is not described as microVM-equivalent isolation.

## Direct-Cutover Decision

Rootless Docker becomes the target execution backend for evolver, worker, verifier, and credential-proxy roles. The coordinator, scheduler, checkpoint writer, admission controller, artifact store, and exact-ID reaper remain trusted host processes. Containerizing the coordinator is deferred because it would require exposing the rootless Docker control socket and would not improve task isolation.

No new E2B run is required to authorize rootless development or scoring. Existing E2B artifacts may be replayed to detect verifier regressions, but replay is an engineering check rather than a provider-acceptance gate. A rootless-only staged rollout prevents a faulty 30-task five-iteration launch without preserving E2B as the operational default.

## Iteration Orchestration

Each outer iteration is deliberately asymmetric:

```text
checkpoint + optimize evidence
             |
             v
      one evolver container
             |
             v
       candidate admission
             |
             v
  N task workers in parallel (initial N=8)
             |
             +--> artifact A --> offline verifier A --+
             +--> artifact B --> offline verifier B --+--> aggregate
             +--> ...                                  |
             +--> artifact N --> offline verifier N --+
                                                        |
                                                        v
                                                keep / rollback
                                                        |
                                                        v
                                                   checkpoint
```

Only one evolver may be active for an arm at a time. It terminates before candidate workers start, so an iteration has one unambiguous proposal identity. Workers fan out over tasks after deterministic admission. A verifier starts as soon as its corresponding worker artifact is finalized; verification need not wait for every worker, so worker execution and verification form a bounded pipeline.

The seed worker is evaluated once on optimize tasks. Each admitted candidate is evaluated on the same optimize panel. Held-out tasks run only for the seed and final incumbent, preserving the existing schedule. Failed admission produces no worker or verifier fan-out and records an infrastructure/admission outcome rather than a benchmark score.

## Rootless Role Model

Extend the provider-neutral sandbox contract with an `evolver` role. Every untrusted role uses an immutable image identity and structured argv execution with `shell=False`.

### Evolver

- Receives a read-only evidence bundle and a writable candidate-output tmpfs.
- Uses its own internal network and credential-proxy container.
- Receives only a non-secret placeholder model key.
- Cannot access official tests, reference data, held-out evidence, the trusted artifact store, host paths, or the Docker socket.
- Emits one candidate archive plus a proposal trace. The coordinator validates both before any scoring work starts.

### Worker

- Receives the public task bundle and admitted candidate worker only.
- Uses an attempt-specific internal network and proxy; concurrent workers do not share a bridge network.
- Has no official tests, reference data, unrestricted provider credential, host mount, or Docker socket.
- Produces a content-addressed artifact archive and sanitized worker-observable evidence.

### Verifier

- Runs in an independent container with `--network none`.
- Receives official tests/reference data from coordinator-trusted mode-`700` storage only after container creation.
- Receives only the finalized, hash-verified worker artifact for the same attempt.
- Returns official scalar reward, bounded pass/fail counts, dependency/test identities, and sanitized criterion evidence. Raw assertions and reference values remain trusted-only.

### Credential Proxy

- Is created per evolver or worker attempt, not shared across untrusted attempts.
- Joins one internal attempt network plus a rootless outbound network.
- Reads the real provider token from an owner-only file unavailable to the caller container.
- Allows only the preregistered provider origin, API path, and model identity; strips caller authorization and injects the real header.
- Records request identity, token usage, provider-reported cost, latency, and failure class without logging prompts, responses, or credentials.

## Scheduler and Capacity

Replace the E2B account lease with a host-local weighted resource lease. Each runnable role reserves its declared CPU, memory, PID, tmpfs, and timeout contract before container creation. The scheduler also reserves coordinator and Docker headroom and stops launching when host load, available memory, disk, or inode thresholds fail.

Initial scored concurrency is eight workers. Verifiers enter the same weighted lease pool rather than receiving a separate unlimited concurrency value. The scheduler may overlap a verifier with remaining workers only when the combined declared resources fit. It must never infer capacity solely from the host's nominal 64 cores and 100+ GB RAM.

Every attempt gets a distinct container ID, network ID, proxy ID, spec digest, artifact digest, and lifecycle record. Image builds are completed before a scored run and never occur concurrently with formal scoring.

## Full-Harness Integration

Add a backend-neutral full-harness proposer parallel to the existing backend-neutral worker/verifier executor:

- `SandboxFullHarnessProposer` packages evolver code, admitted mutation surfaces, evidence, and public model configuration;
- `RootlessDockerBackend` handles evolver, worker, verifier, proxy, and canary roles;
- a rootless runtime factory wires the backend, image manifests, resource lease, model proxy, worker executor, verifier, and proposer into `QFBenchEvolutionRunner`;
- the CLI accepts `--executor rootless-docker` and uses it as the default for new self-hosted experiment configs;
- `--executor e2b` remains explicit and retains native E2B IDs, but no rootless path imports or requires the E2B SDK at runtime.

Candidate mutation remains runtime data. A new candidate is uploaded into the existing immutable worker image; worker images are not rebuilt each iteration. Admission continues to protect model/provider settings, benchmark paths, verifier configuration, network policy, resource limits, tracer settings, and external credentials.

## Identity, Checkpoint, and Resume

The run identity includes source commit, benchmark/task manifests, feedback-contract digest, worker/evolver image digests, per-task verifier image and lock digests, model/provider/egress identity, resource policy, scheduler policy, seed-worker digest, and admission-policy digest.

At minimum, checkpoint after:

1. evolver proposal and trace finalization;
2. candidate admission;
3. every worker artifact finalization;
4. every official verifier score;
5. iteration aggregation and keep/rollback;
6. held-out seed/final aggregation.

Resume rejects identity drift. Completed content-addressed model proposals, worker artifacts, and verifier scores are reused. A pending or unknown provider request is never silently repeated: its request identity and proxy/provider record must first establish whether it completed. If completion cannot be proven, quarantine the attempt and require an explicitly new attempt identity rather than risking a duplicate hidden model call. Lifecycle manifests are persisted immediately after create and before start or upload.

The reaper remains exact-ID only. It scans the requested run root, verifies labels and spec digest, dry-runs by default, and removes only explicitly recorded unfinished containers and networks. Broad label deletion, wildcard cleanup, and `docker system prune` remain forbidden.

## Failure Taxonomy

Only a worker that reached the official task runtime and exhausted the declared behavioral timeout becomes official reward zero. The following remain infrastructure failures and are safely retryable under the same content identity:

- image, container, network, proxy, transfer, or dependency-lock failure;
- provider region/authentication rejection, or a transport failure proven to precede request acceptance;
- verifier dependency or no-network policy failure;
- corrupt, oversized, traversing, symlinked, or hash-mismatched bundles;
- lifecycle persistence, cleanup, disk, OOM, or host-capacity failure.

Candidate logic that completes but fails official tests is an ordinary benchmark result. Admission rejection, infrastructure failure, and benchmark failure must remain distinct in summaries.

An ambiguous provider disconnect after request acceptance is not automatically retryable under the same attempt identity. It is quarantined until provider request records prove whether a response was generated.

## Rootless-Only Rollout

Migration proceeds entirely on rootless Docker:

1. Preserve the two existing unstaged report edits and deploy a clean reviewed source commit, including trusted-snapshot mode hardening.
2. Run the complete local dependency environment and all rootless/full-harness unit tests.
3. Build immutable evolver, proxy, base, and 30 task-role worker/verifier images.
4. Run no-model role, network, secret, filesystem, cgroup, cross-attempt, and exact-ID cleanup canaries.
5. Validate the actual experiment model and provider route from `bc-server` through the credential proxy.
6. Complete one fresh `historical-var-data-prep` worker-to-verifier attempt.
7. Run one rootless Rich evolver proposal, admission, and worker import/tool smoke.
8. Replay available historical artifacts across all 30 offline rootless verifiers as a regression check.
9. Run a five-task one-iteration full-harness pilot, then the existing five-task three-iteration schedule if the first pilot is clean.
10. Run a 30-task one-iteration pilot with 60 official attempts and a deliberate coordinator termination/resume.
11. Audit scores, identities, leakage scans, costs, resource telemetry, and zero pending containers/networks.
12. Run the rootless 30-task five-iteration experiment with 140 official attempts.

Stages stop at the first failure, but failure does not redirect formal work back to E2B automatically. The rootless implementation is repaired and resumed under a new or compatible content-addressed identity as appropriate.

## Acceptance Criteria

Direct migration is complete when:

1. Evolver, worker, verifier, and proxy all run through the rootless provider-neutral backend; the new run requires no E2B credential or template.
2. One evolver produces at most one admitted candidate per iteration, and candidate identity is fixed before parallel scoring begins.
3. Parallel workers and pipelined verifiers obey weighted resource limits and attempt-specific network/filesystem isolation.
4. Worker/evolver direct egress fails, proxy-only model access succeeds, and the real credential is absent from every caller-visible surface.
5. Official tests/reference data never enter worker/evolver images, bundles, mounts, traces, logs, prompts, or artifacts; official solutions have no lifecycle.
6. Independent offline verifiers execute the pinned official tests and preserve the deterministic reward contract without an LLM judge.
7. A real interrupted multi-task run resumes without duplicating completed proposal, worker, verifier, or score operations.
8. Every managed container and network is represented by one immutable lifecycle identity; final exact-ID audit reports zero pending resources.
9. Run artifacts record provider requests/tokens/cost where exposed, role-attributed container durations, host resource observations, failures, and explicit `null` values for unavailable billing fields.
10. The five-task and 30-task one-iteration rootless pilots complete before the 140-attempt five-iteration launch.

Passing these criteria establishes the self-hosted rootless Docker execution backend for this repository. It does not by itself establish stable evolution gains, held-out transfer, statistical significance, or microVM-equivalent security.

## Repository and Integration Policy

Implementation remains isolated on `qfbench-selfhosted-vm-backend`. Existing uncommitted report changes are preserved and excluded from migration commits unless separately reviewed. Each commit is scoped to one runtime, test, deployment, or evidence change. No branch is merged without explicit user direction.
