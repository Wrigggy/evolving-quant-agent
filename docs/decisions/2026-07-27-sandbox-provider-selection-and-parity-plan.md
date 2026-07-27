# Decision Record: Sandbox Provider Selection and Parity Plan

> Date: 2026-07-27
> Status: accepted for post-A/B implementation and canaries; no migration has been run
> Scope: QFBench worker, verifier, and evolver sandbox backends
> Supersedes: the assumption that E2B is the only candidate hosted runtime
> Preserves: the measured E2B architecture and all active experiment identities

## Decision

Finish the active Control/Rich QFBench A/B on E2B. Changing providers mid-arm would confound the evidence-exposure comparison and invalidate the matched runtime identity.

After the A/B is complete, evaluate hosted backends in this order:

1. **Daytona Linux VM** is the first implementation target and the preferred low-migration-cost E2B alternative.
2. **Vercel Sandbox** is the first cost-optimization pilot because LLM wait time is excluded from Active CPU billing.
3. **E2B** remains the measured reference until another backend passes every parity and isolation gate below.
4. **Blaxel** is excluded from official scoring while its domain filter is proxy-environment-based and bypassable.
5. **Modal** remains a secure but higher-cost fallback. **Sprites** is reserved for persistent development agents, not resource-matched benchmark scoring.

No provider is currently approved as E2B-parity based only on documentation.

## Workload Requirements

The pinned 30-task manifest resolves to 26 tasks at 2 vCPU/4 GiB and four at 4 vCPU/8 GiB. Twenty-four worker timeouts are 1,800 seconds and six are 2,400 seconds. Every official scoring attempt uses a worker sandbox plus an independent verifier sandbox; workers may reach only the model provider through external credential injection, while verifiers must have no network. The coordinator also requires immutable image identity, per-attempt lifecycle manifests, an account-wide lease, content-addressed resume, and exact-ID cleanup.

These constraints make a generic container or inexpensive persistent VM insufficient. Resource identity, evaluator isolation, credential non-exposure, and recoverability are correctness requirements.

## Provider Assessment

### E2B: measured reference

E2B is the only backend with repository evidence for published task-role templates, no-network verification, official oracle parity, provider-host-only worker egress, header-injected authorization, and real force-kill/reaper/resume. Keep it as the reference even if a later backend becomes the operating default. Its current public price is $150/month for Pro plus $0.000014/vCPU-second and $0.0000045/GiB-second ([pricing](https://e2b.dev/pricing)).

### Daytona Linux VM: first migration target

Daytona exposes 2-vCPU/4-GiB and 4-vCPU/8-GiB Linux VM shapes, snapshots, pause/resume, exact resource controls, Python SDKs, labels, and lifecycle APIs ([sandboxes](https://www.daytona.io/docs/en/sandboxes/)). Organization secrets remain outside the sandbox as opaque placeholders and are substituted only in HTTPS headers for allowlisted hosts ([secrets](https://www.daytona.io/docs/en/secrets/)). Its active CPU/RAM prices match E2B but it has no $150 base subscription ([pricing](https://www.daytona.io/pricing)). Tier 2 supplies 100 vCPU and 200 GiB after its documented verification/top-up, enough for the current global cap of 12 ([limits](https://www.daytona.io/docs/limits)).

Use Linux VM sandboxes, not the default container runtime, for untrusted worker and verifier code. Daytona supports `networkBlockAll` and domain/CIDR allowlists, but Tier 1/2 organization policy and essential-service behavior require a measured no-egress canary before official tests are uploaded ([firewall](https://www.daytona.io/docs/en/network-limits/)). If `networkBlockAll` permits any essential endpoint, Daytona must not host official verifiers at that tier.

### Vercel Sandbox: cost pilot

Vercel uses Firecracker microVMs, supports deny-all/domain/CIDR policies, and can broker credentials outside the sandbox boundary ([security comparison](https://vercel.com/kb/guide/vercel-sandbox-vs-e2b)). Its 2-GB-per-vCPU shapes exactly cover the two QFBench resource pairs. Pro/Enterprise sessions can run for up to 24 hours, with filesystem persistence separated from session lifetime ([duration and persistence](https://vercel.com/kb/guide/vercel-sandbox-duration-and-persistence)).

For a 2-vCPU/4-GB sandbox, E2B and Daytona cost $0.1656 per wall-clock hour. Vercel costs `$0.0848 + $0.256u`, where `u` is the fraction of wall time billed as Active CPU. The break-even point is therefore approximately 31.6% Active CPU. The same ratio applies to 4-vCPU/8-GB. This makes Vercel promising for model-wait-heavy workers, but only billing telemetry from a matched pilot can establish savings. Its Pro plan and Sandbox allowances are documented on the [pricing page](https://vercel.com/pricing).

Vercel requires more template work than Daytona because the current E2B/Docker-derived task-role templates must be reconstructed and snapshotted. Python SDK and newer persistence/firewall surfaces also require API maturity and exact-ID lifecycle canaries.

### Deferred alternatives

Blaxel's scale-to-zero does not imply savings during the current single long-lived worker command: a sandbox remains active while a control connection is active, and external network connections do not survive standby ([lifecycle](https://docs.blaxel.ai/Sandboxes/Overview)). Its writable layer also reserves approximately half of sandbox memory for `tmpfs`, complicating exact 4/8-GiB parity. Most importantly, domain filtering is a public preview that relies on tools honoring `HTTP_PROXY`/`HTTPS_PROXY`; traffic from tools that ignore those variables is not filtered, and routing-level enforcement is future work ([domain filtering](https://docs.blaxel.ai/Sandboxes/Proxy-domains)). It cannot host the official verifier under the current firewall contract.

Modal provides gVisor isolation and hard outbound blocking, but a 2-vCPU/4-GiB sandbox is about $0.238/hour at published rates, versus $0.1656/hour for E2B/Daytona ([pricing](https://modal.com/products/sandboxes), [networking](https://modal.com/docs/guide/sandbox-networking)). Sprites now offers network policy and external credential connectors, but every Sprite has fixed 8 vCPUs and 100 GB storage, so it cannot reproduce the preregistered resource contract ([lifecycle](https://docs.sprites.dev/concepts/lifecycle/)).

## Required Parity Gates

A backend may replace E2B only after a separately identified canary records all of the following:

1. Immutable base and task-role image/snapshot IDs plus dependency locks.
2. In-sandbox cgroup evidence for exact CPU, memory, and timeout limits.
3. Worker deny-by-default egress limited to the model host, with plaintext credentials absent from environment, filesystem, arguments, logs, and responses.
4. Verifier denial of DNS, raw TCP, HTTP, HTTPS, package registries, cloud metadata, and provider control APIs.
5. Oracle-free `historical-var-data-prep` official-test parity with the measured E2B result; official solutions remain excluded.
6. Independent worker/verifier sandboxes, trusted-only test upload, artifact-only handoff, and zero proposer visibility into verifier inputs.
7. Immediate lifecycle-manifest persistence, exact-ID list/inspect/kill, forced termination, reaper, and idempotent resume.
8. Durable billing evidence for wall time, Active CPU where applicable, memory time, storage, creation count, and worker/verifier attribution.

After the single-task canary, run the same public five-task panel on Daytona VM and Vercel. Do not compare provider performance from different worker candidates or model settings.

## Implementation Boundary

Introduce a provider-neutral `SandboxBackend` above image publication, create, file transfer, command execution, inspect/list, exact kill, and lifecycle metadata. Keep provider-native immutable IDs in manifests; do not erase them behind a generic string. Preserve the current E2B implementation as an adapter and add Daytona before Vercel. A future role-aware deployment may place LLM-wait-heavy workers on Vercel and offline verifiers on Daytona/E2B, but only after single-provider parity establishes the failure and cost baselines.

This decision authorizes design and canary planning, not a provider migration or non-E2B paid run. Record any accepted change in a new dated decision and update `docs/PROJECT_MEMORY.md` without rewriting this history.
