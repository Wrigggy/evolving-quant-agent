# Decision Record: QFBench Rootless Backend Canary Gate

> Date: 2026-07-30<br>Status: not accepted for formal scoring<br>Scope: shared `bc-server` rootless Docker worker/verifier backend<br>Preserves: E2B as the only measured formal-scoring backend<br>Evidence run: `qfbench-rootless-canary-20260730-r6`

## Context

The 2026-07-27 provider plan requires any E2B replacement to prove immutable runtime identity, exact resources, credential non-exposure, hard offline verification, official-test parity, artifact-only handoff, exact-ID recovery, and durable cost evidence. The user authorized a self-hosted rootless canary on the shared `bc-server`, including verifier-only use of official tests and reference data from QFBench commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a`. Official solutions remained prohibited.

The canary used source commit `5d3aa5fcd5ea66a02042ddafd003f651b78149a3`, immutable base/worker/verifier images, and a rootless Docker daemon owned by UID 1013. Tests and reference data were materialized only under `/home/julius/qea/runtime/trusted-verifier/024921eb-five-task`, with directory mode `700` and file mode `600`.

A final post-run audit found three upstream-executable `test.sh` files had initially retained mode `0700`. They were normalized to `0600`; the final remote tree now contains only `0700` directories and `0600` files. Follow-up commit `dbff80d` enforces those modes before future trusted snapshot promotion. The correction did not change bytes, hashes, verifier isolation, or the completed parity result because the verifier invokes its isolated script copy through `bash`.

## Decision

The self-hosted rootless backend is **not accepted for formal QFBench scoring**. E2B remains the only measured formal-scoring backend.

The backend is accepted only as a **verifier-parity and isolation candidate**. It may be developed and rerun under a new preregistered canary, but results from the current run must not be represented as fresh end-to-end model performance or E2B backend parity.

Do not run a 30-task or five-iteration repetition on this backend. Do not silently retry with another model or route. A new paid attempt requires a new run identity and an explicit preregistered choice between:

1. preserving `openai/gpt-5` and routing only the model-proxy through a compliant supported egress; or
2. selecting a region-available model and treating the result as an infrastructure canary rather than a matched E2B performance comparison.

## Evidence

The following gates passed in r6:

- Immutable base, worker and verifier image identities plus dependency locks.
- Rootless cgroup/resource inspection, read-only roots, bounded tmpfs and minimum executable tmpfs declarations.
- Worker deny-by-default route through the model proxy, tested first with a synthetic upstream.
- Independent verifier containers with `--network none`, including raw DNS/TCP/HTTP/HTTPS denial.
- Artifact-only handoff and zero worker-visible official-test, reference-data, secret or solution-path matches.
- Force-kill, exact-ID reaper/resume and final zero managed container/network cleanup.
- Historical `historical-var-data-prep` parity: official reward `1.0`, 12 passed and 0 failed, matching the E2B anchor.

The fresh paid stage did not pass. One request to `openai/gpt-5` through OpenRouter returned HTTP 403 because the model was unavailable in the shared server region. The proxy and worker lifecycles were cleaned, but no worker execution artifact and no verifier lifecycle were produced. This is an infrastructure/model-availability failure, not official reward zero. Exact provider and sandbox cost totals were not exposed and remain unknown.

Evidence artifacts:

- `/home/julius/qea/runs/qfbench-rootless-canary-20260730-r6/gate-summary.json`, SHA-256 `74524a79114cd25862dbb8aeb7f65dba295ddfdbffeca65714360425eafad491`
- `/home/julius/qea/runs/qfbench-rootless-canary-20260730-r6/image-firewall-audit.json`, SHA-256 `679457dfdb92bc7afa8f3371cedec3bff55fdd3ca23cc4c6a4a80ab11fe9afef`
- `/home/julius/qea/runs/qfbench-rootless-canary-20260730-r6/exposure-cleanup-audit.json`, SHA-256 `3c7956e4213ca5913618d5b7d1b30febae34588413a27479e53912012788102d`
- Full bilingual report: [2026-07-30 QFBench rootless backend canary report](../reports/2026-07-30-qfbench-rootless-backend-canary-report.md)

## Consequences

- Formal QFBench runs continue on E2B until a new backend completes the full worker-to-verifier path under matched identities.
- The rootless implementation and passed firewall/recovery evidence are retained; the 403 does not invalidate the verifier parity result.
- r4-r6 remain immutable failure lineage: r4 exposed read-only uv cache behavior, r5 exposed host PyYAML coupling, and r6 exposed provider-region availability.
- Official tests/reference remain verifier-only. No official solution may be downloaded, uploaded, checked out or run in a retry.
- Shared-host administrator access remains an accepted but explicitly documented residual risk.
- Publication/research readiness remains `NOT_READY`; no performance or cost advantage may be claimed from this canary.

## Acceptance Gate for a Superseding Decision

A future decision may accept the backend only after a separately identified run records all of the following:

1. successful fresh model generation under a preregistered model and egress identity;
2. worker completion and artifact-only transfer with no trusted-data exposure;
3. independent offline official verification with matching test and dependency-lock hashes;
4. exact cleanup plus force-kill/reaper/resume evidence;
5. authoritative provider-token/cost and worker/verifier lifecycle telemetry; and
6. a matched five-task comparison against the E2B reference before any larger repetition.
