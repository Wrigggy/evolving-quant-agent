# QFBench A6 R5 Discovery Launch Quarantine

> Status: measured infrastructure failure; A6-R/E/EC r5 discovery IDs frozen.
> No proposal, ACT/ABSTAIN decision, candidate evaluation, A6-F, or mutation
> result exists from this launch.

## Outcome first

The r5 shared 16-task seed and formal R/E/EC wrapper corpus passed their frozen
accounting, identity, provenance, and isolation gates. The subsequent three-arm
proposal-only launch did not produce a scientific discovery result. A host-side
Docker container naming defect allowed the A6-R proxy to start, then caused the
A6-E and A6-EC proxies to collide with its name. The run was stopped in the
frozen monitor-first order and all exact resources were reaped.

The three r5 discovery IDs are permanently quarantined. A6-R has one
unreconciled Evolver attempt: its accepted request count has measured lower
bound zero, but its actual accepted requests, tokens, and cost are unknown and
must remain `null`. A6-E and A6-EC made exactly zero provider calls. No arm wrote
a proposal, candidate, decision, score, or canonical proxy audit.

The complete machine-readable incident record is
[r5-discovery-concurrent-launch-incident.json](../../output/qfbench-supervisor/a6-881ee7f14a1b2c46-r5/r5-discovery-concurrent-launch-incident.json).

## Valid measured prerequisites

The infrastructure failure does not invalidate the earlier r5 seed measurement
or the byte-level corpus audit:

- Release root:
  `/home/julius/qea/deploy/releases/a6-881ee7f14a1b2c46`
- Source tree SHA-256:
  `881ee7f14a1b2c46fa5f03dc7a85ec66f6a58b0c95331c68db66e7aded25155e`
- External identity-record SHA-256:
  `f93ab7a6b326fad6a363cbb9995daec0003c71e4429285e41df8f8762c332475`
- Materialized launch identity:
  `c5f04fde685c8903cb55e06910feeaeba516a7570fa69bfa0df4b35787629bc3`
- Seed ID: `qfbench-a6-seed-evidence-flash-20260810-r5`
- Seed report SHA-256:
  `a16e84b802486af408e7a5d75b9b6a447627049c3840b1a90e63a4c93a80a2b1`
- Seed result: 16/16 scores; 211/211 completed unique pinned-Flash
  requests; 5,687,613 tokens; USD `0.1798568072`; canonical
  `cost_complete=true`, `provider_cost_is_lower_bound=false`, and zero
  unreconciled attempts.
- Formal wrapper-corpus audit SHA-256:
  `ac58def19f5c35531fe5c122417edde53bd8c193cd6f4bb3d2966bde96125eb4`
- Three-arm no-model preflight audit SHA-256:
  `5fe70e4261287612c72bb524a898e697bad81e3130bdbd0dbeafd72458881b2a`

These are measured engineering and seed-corpus facts. They are not an A6
discovery benefit claim.

## Ordered incident evidence

At `2026-08-09T20:54:13Z`, the three exact r5 discovery services were queued in
the independently approved concurrent window:

- A6-R unit SHA-256:
  `0ceec6754f54b4614e637c7a92a26a79e5242d6ef09752bc7c4f7b73682064a1`
- A6-E unit SHA-256:
  `51e8304ae461a6d4b1522d1b3a86a5847b25ae0a7e6f18d2568ba6b5db1af476`
- A6-EC unit SHA-256:
  `0f7890f76426d8c52992c5584390e603b6704922d6cedd2958d9fcd9086bf558`

A6-R created proxy container
`66b2ca5f36ddfa616c62adc6f0212fb4762b672ec03226280e946a760de60ef3`
and Evolver container
`ad9da5da8d681c0ed80f08590b898f3889fb4cba3fb404ed24189fe9d18507bc`.
At `20:54:34Z`, both E and EC failed in `proxy.create` because Docker name
`qea-proxy-evolver-iteration-1` was already owned by R. Each service's frozen
`Restart=on-failure` policy made one restart at `20:55:04Z`; both restarts then
failed closed at `20:55:25Z` on `evolver.resume: stale committed input archive
is ambiguous`. Neither E nor EC ever created a proxy container.

The monitor was unloaded before the timers and coordinators were stopped.
A6-R received SIGTERM at `20:55:29Z`. Because its live proxy was killed before
host-side finalization and audit download, the absence of a host audit cannot
prove zero accepted requests. The exact-ID reaper killed both R containers and
removed R network
`540ad24bbc3451ca2c4cfabdd35ff99e9a0430bcbea7f16b8fc2bc1477979e68`.
E and EC had only their already-cleaned scoped network lifecycle records.

Final dry-run reaping scanned R's two container and one network manifests plus
one network manifest for each of E and EC. Pending IDs, identity mismatches,
failures, and final inventory were all empty. The global managed container and
network counts and r5 lease-file count were zero. A final additive 42-ID mirror
cycle synchronized R, E, and EC at `21:02:21Z`, `21:02:24Z`, and `21:02:27Z`
respectively, exited zero, and had zero stderr bytes. The monitor and mirror
LaunchAgent labels were then absent.

## Accounting boundary

The following claims are measured:

| Arm | Accepted requests | Tokens | Cost | Reconciliation |
| --- | ---: | ---: | ---: | --- |
| A6-R | lower bound 0; actual `null` | `null` | `null` | one unreconciled attempt |
| A6-E | 0 | 0 | USD 0 | complete for the failed launch |
| A6-EC | 0 | 0 | USD 0 | complete for the failed launch |

All three authorized-evidence access logs are zero bytes. Attempt artifact,
proposal, candidate, decision, and score counts are zero. The R input archive
and lifecycle records remain preserved; its missing proxy audit is not
reconstructed and its possible provider traffic is not inferred from an empty
host directory.

## Source-audited cause

`RootlessDockerBackend.create` constructed every container name as
`qea-{role}-{attempt_id}`. `SandboxEvolver.propose` deliberately uses logical
attempt ID `evolver-iteration-1` for iteration one. Network identities and
container labels already include the exact run ID, but the Docker daemon's
globally unique container name did not. Parallel R/E/EC proposal arms therefore
shared the same proxy and Evolver names even though their run IDs and scoped
networks were distinct.

The automatic restart's committed-input rejection was correct fail-closed
behavior. Deleting the input archive or bypassing that gate would erase incident
identity and risk replay; neither action is allowed.

## Offline remediation and recovery boundary

The accepted minimal fix derives a logical container-name identity from exact
canonical bytes `(role, run_id, attempt_id)` and emits
`qea-{role}-{full_sha256}`. The full digest keeps the maximum validated
128-character identifiers below Docker's 255-character name limit without a
truncation collision. It deliberately ignores resource fields: a stale
container with the same logical run/role/attempt continues to collide and fail
closed even if a caller attempts resource drift. Existing labels, sandbox spec
identity, lifecycle records, and exact-ID reaper ownership remain unchanged.

Required deterministic regressions cover different run IDs with the same role
and attempt, same-tuple stability across resource drift, different roles,
maximum-length identifiers, unchanged create labels, a three-arm fake daemon,
and same-logical-ID conflict behavior. The focused rootless/evolver/proxy/
accounting suite passes `236 passed, 1 skipped, 2 deselected` under the system
Python environment. A dependency-minimal `.venv` run separately exposed its
known missing-PyYAML limitation; the tests that could import passed and the
container-name focused subset passed. The complete Python 3.14 NexAU suite,
run with local loopback binding enabled for the model-proxy fixtures, passes
`1142 passed, 1 skipped` in 49.76 seconds. A sandboxed diagnostic run reached
`1110 passed, 1 skipped`; its 32 failures were all expected `PermissionError`
failures at temporary `127.0.0.1` socket binding, not assertion failures.

This remediation is local only until a new content-addressed release and
external identity pass independent review. R5 must not resume. Because the seed
contract binds the source launch identity, recovery requires a fresh r6 source
release, fresh 16-task seed and canonical cost audit, fresh three-arm corpus,
new exact discovery IDs, same-ID no-model preflights, and new independent launch
gates. Candidate evaluations, A6-F, feedback, mutation, and any expansion beyond
the frozen 16-task core remain not run and separately gated.

The user's suggestion to use more tasks or repetitions is retained for the
later statistical protocol. It does not change this localization canary's
frozen panel and cannot turn this infrastructure failure into evidence about
the discovery mechanism.
