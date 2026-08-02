# QFBench Autonomous Repair Supervisor Design

> Date: 2026-08-02<br>
> Status: approved for implementation<br>
> Scope: formal QFBench runs on the self-hosted rootless Docker backend<br>
> Controller: the local Mac; execution node: shared trusted `bc-server`

## Context

Long QFBench repetitions can stop on recoverable harness defects after valid,
paid worker outputs have already been persisted. Manual polling makes recovery
slow and risks inconsistent intervention. The chosen design automates bounded
infrastructure repair while preserving the existing official-provider,
evaluator-firewall, checkpoint, cost, and exact-cleanup contracts.

The first acceptance incident is the stopped repetition-one run
`qfbench-rootless-base-85x5-official-deepseek-20260801`. Its verifier bundle
omits a worker-produced `__pycache__/*.pyc` artifact even though that artifact
is present in the worker manifest. Four durable worker executions lack scores;
they must be resumed verifier-only, without another worker or model call.

## Goals and Non-Goals

The supervisor should detect a stopped or failed formal run, preserve immutable
evidence, classify the failure, invoke a tightly scoped Codex repair when safe,
test and deploy an exact source commit, run a bounded canary, and resume the
original run idempotently. It may make at most three code-changing repair
attempts before requiring human review.

It does not optimize worker behavior, alter rewards, inspect official answers,
relax verifier isolation, change the preregistered model/provider/image/config,
merge branches, or clean resources outside the exact run identity.

## Architecture

### Deterministic bc Sentinel

A small process on `bc-server` observes only run-owned processes, checkpoint
files, exact-ID Docker resources, and supervisor state under
`/home/julius/qea/runtime/supervisor`. Directories use mode `0700` and files
containing incident details use mode `0600`. The sentinel never edits source,
calls an LLM, reads credentials, or decides a code fix. It atomically emits a
sanitized incident document, freezes hashes of relevant evidence, and may run
only the existing exact-ID safety reaper after proving coordinator termination.

Use a `systemd --user` service when the host supports lingering user services.
Otherwise run the same process through a documented `tmux`/`nohup` fallback and
record that reboot persistence is degraded. This deployment choice must not
change incident semantics.

### Mac launchd Controller

A local `launchd` job polls at approximately 60-second intervals, acquires a
single advisory lock, and connects with `ssh -o BatchMode=yes bc`. Transient VPN
or SSH failures use bounded exponential backoff and do not mutate remote state.
During an active repair/resume window, a run-scoped `caffeinate` process may
keep the Mac awake. If the Mac sleeps or the VPN is unavailable, the bc
sentinel retains the incident for later processing.

The controller downloads only sanitized incident metadata and approved logs.
It never copies `.env`, model tokens, official tests, reference data, or raw
verifier output to the repair prompt.

### Local Repair Adapter

For a classified repairable infrastructure defect, the controller invokes
`codex exec` in the existing feature worktree with a fixed prompt containing
the incident id, failure signature, source commit, allowed paths, acceptance
tests, and preserved security boundaries. Codex must diagnose first, add a
failing regression test, implement the smallest repair, run focused and full
tests, and create a scoped feature-branch commit. No merge is permitted.

The exact tested commit is pushed to the feature branch and to bc's deploy-only
ref. bc checks out that commit in a clean detached worktree. Direct editing of
the remote source tree is forbidden. Runtime identities are rebuilt only when
their inputs changed and are recorded before execution.

### Canary and Resume

Every repair runs a bounded, networkless verifier canary against copied
checkpoint artifacts before touching the formal run. The canary validates
artifact hashes, verifier `--network none`, trusted-data confinement, expected
score behavior, exact cleanup, and absence of worker/model requests. Only a
passing canary permits `--resume` on the original run. Resume reuses completed
scores, reusable worker manifests, and persisted timeouts according to the
approved recovery policy.

## Incident State and Idempotency

The durable state machine is:

```text
observed -> frozen -> classified -> repairing -> tested -> deployed
         -> canary_passed -> resumed -> resolved
```

`hard_stop` and `repair_budget_exhausted` are terminal states. An incident id is
content-addressed from the run id, source commit, failing exit-evidence hash,
and normalized failure signature. Atomic state transitions, one local lock,
and one active incident prevent duplicate Codex invocations, deployments,
model samples, and resumes. Restarting either controller reloads the same state
rather than creating a new attempt.

## Classification and Repair Budget

Known replay-safe interruptions may proceed directly to canary/resume. A new
non-security harness defect may enter repair. Only one repair can run at a time,
and the active formal run receives at most three code-changing cycles until a
human explicitly resets the budget. Each cycle requires a new commit, regression
test evidence, full-suite evidence, deployment manifest, and canary manifest.

The controller must enter `hard_stop` without calling Codex or resuming when it
detects any of the following:

- verifier network/firewall drift or trusted-data exposure;
- credential, `.env`, official-test/reference, solution, or raw-verdict leakage;
- benchmark, model, required provider, fallback policy, image, scheduler,
  runtime, configuration, task-set, or checkpoint identity drift;
- historical evidence hash mismatch or conflicting terminal state;
- ambiguous upstream request acceptance or unsupported cost-ledger omission;
- failure to prove exact-ID container/network cleanup;
- a requested modification outside infrastructure orchestration and integrity;
- the third failed code-changing repair cycle.

## Evidence and Audit Contract

Every transition writes an append-only, sanitized record. The incident bundle
contains the normalized signature, evidence hashes, selected classification,
repair counter, source/test/commit identities, deployment manifest, canary
manifest, resume command identity, and final resource audit. Captured stdout and
stderr are bounded and redacted before transfer. Provider usage remains sourced
from canonical proxy ledgers; approved timeout exceptions remain explicit lower
bounds and are never converted to zero cost.

## Tests and Acceptance Gates

Implementation begins with failing tests for state transitions, content-addressed
incident deduplication, local locking, retry backoff, repair-budget exhaustion,
safe classification, and every `hard_stop` boundary. Integration tests use a
fake bc transport to cover duplicate events, controller restart, temporary VPN
loss, Codex failure, test failure, canary failure, and idempotent resume.

The real first canary must prove that the `polars-api-migration` worker artifact
set and verifier bundle use the same inclusion contract, including the declared
`.pyc` file. It must use the persisted worker execution, run no worker or model,
keep the verifier offline, and leave zero managed containers and networks.

The formal resume gate then verifies that the existing 63 scores remain
byte-identical, all 62 prior worker executions and canonical audits remain
unchanged, all five persisted official timeouts remain terminal, and the four
reusable no-score workers receive verifier-only continuation. Any unplanned
worker replay, model request, identity change, firewall finding, or residual
resource causes `hard_stop`. Repetitions two through five remain gated until
repetition one and all post-run audits complete.

## Operational Limitations

The Mac is the intelligent control plane, so repair pauses while it is asleep,
offline, or disconnected from the VPN. The bc sentinel still preserves the
incident and may enforce exact-run cleanup, but it cannot repair code by itself.
The shared host is trusted for this experiment; this does not claim microVM-level
administrator isolation. All changes remain on the feature branch until the
user separately authorizes integration.
