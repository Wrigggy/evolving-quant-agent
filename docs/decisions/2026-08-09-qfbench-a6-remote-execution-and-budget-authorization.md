# 2026-08-09 — QFBench A6 Remote Execution and Budget Authorization

## Decision and supersession boundary

The user explicitly authorizes a `bc-server` upload and the frozen A6 R/E/EC
core paid experiment in general, and removes the earlier USD 1.50 hard cost
ceiling. This decision records the intended exact egress identity and execution
scope. The first message did not supply the literal exact-value confirmation
required by the security reviewer; the later exact message preserved below now
does. Egress materialization is authorized, while paid/model execution remains
gated on the independent live identity, isolation, watchdog, mirror, and
zero-call preflight audit. The scope supersedes only the earlier pause,
missing-egress-authorization, and financial-cap boundaries. It does **not**
change the panel, arms, evidence, model route, evaluator firewall, admission
rules, trigger rules, statistical interpretation, or claim limits frozen in the
[A6 protocol](2026-08-09-qfbench-a6-expanded-panel-feedback-and-mutation-protocol.md).

Once the literal egress gate is satisfied, this authorization is permission to
execute the frozen protocol; it is never evidence that the protocol has run or
that a candidate is beneficial.

## Historical execution-status clarification after security review

After this scope record was drafted, the security reviewer determined that the
currently available user message did not itself state both the exact upload-tar
SHA-256 and the exact `bc-server` final path verbatim. Therefore this document
records the intended scope but is **not presently executable egress authority**.
Upload, remote identity materialization, paid evaluation, and model calls remain
blocked until a new user message explicitly authorizes both exact values. No
alternate channel, regenerated payload, inferred consent, or broader wording
may substitute for that confirmation.

The rejected transfer escalation stopped before process creation: zero payload
bytes were uploaded. A subsequent read-only check found zero staging entries;
the exact staging leaf was removed, the final release path remains absent, and
no remote A6 identity exists.

## Current exact-value confirmation and executable boundary

Later on 2026-08-09, the user supplied the exact confirmation required by the
security reviewer:

> 我明确授权将本地文件
> `/tmp/qea-a6-clean-release.ONyWfz/A6_SOURCE_UPLOAD.tar`（SHA-256：
> `e35ddf01dc68b2f8de15d89c765e67064e7eb4ff7fcc1b306aed0300dc38b20b`）
> 上传到 `bc-server`，并发布到
> `/home/julius/qea/deploy/releases/a6-3b04a5b2257bd846`。我知悉该包包含私有
> QEA 源代码、配置、研究文档、QFBench manifests，以及两份仅供 trusted
> coordinator 使用的 VERIFIER_CRITERIA 文件；授权这些内容上传至受信任的 BC
> coordinator，但不得将 trusted criteria、源码树或其他协调器材料挂载或暴露给
> worker/evolver。完成上传、身份校验、隔离与 watchdog preflight 后，我授权继续
> 运行 A6-R、A6-E、A6-EC 的 BC 实验；不设 1.5 美元或其他美元硬上限，但仍须
> 遵守冻结协议、分阶段推进、fail-closed 身份检查和 evaluator 隔离要求。

This exact message satisfies the literal tar-SHA/final-path egress gate. The
earlier security hold remains preserved above as historical process evidence,
but no longer blocks transfer of this one exact payload to this one exact
target. It does not waive any subsequent live equality, ten-field identity,
isolation, no-model preflight, watchdog, mirror, or stage trigger.

At the first post-authorization checkpoint, the exact tar had reached only the
staging leaf: remote SHA-256 matched
`e35ddf01dc68b2f8de15d89c765e67064e7eb4ff7fcc1b306aed0300dc38b20b`,
size was 3,286,528 bytes, and mode was `0600`. It had not yet been unpacked or
published, the final identity did not yet exist, and no paid/model attempt had
started. Paid/model execution remains blocked until the materialized remote
release, ten-field identity, evaluator isolation, four-layer watchdog/mirror,
and same-final-ID zero-call preflights independently pass.

## Exact authorized egress and target

The intended payload is the already measured clean local release described
in the [implementation and prelaunch progress report](../reports/2026-08-09-qfbench-a6-implementation-and-prelaunch-progress.md):

- 261 regular members and 2,711,040 source bytes;
- source-tree SHA-256
  `3b04a5b2257bd8467eea364d16992d22b7ffdeb2c9f688acb17421db716fb20c`;
- external source-manifest SHA-256
  `cf8501036b7866429d298fae265290ff0ae15b2db8cf3733a12c2f3b16ec71ba`;
- upload-tar SHA-256
  `e35ddf01dc68b2f8de15d89c765e67064e7eb4ff7fcc1b306aed0300dc38b20b`;
- local upload tar
  `/tmp/qea-a6-clean-release.ONyWfz/A6_SOURCE_UPLOAD.tar`.

The intended exact destination is host `bc-server` through the existing
single-host `bc-ssh` path, staging only at
`/home/julius/qea/deploy/staging/a6-3b04a5b2257bd846.upload` and publishing
once only at
`/home/julius/qea/deploy/releases/a6-3b04a5b2257bd846`. The external source
manifest and `A6_PRELAUNCH_IDENTITY.json` must be siblings of the published
`source/` root, as required by the frozen manifest. Any regenerated payload,
different tree digest, different host, or different final path is a new egress
identity and is not silently covered by this authorization.

The payload includes the two non-secret coordinator-only criteria manifests
recorded in the progress report. They are authorized only onto the trusted
`bc-server` coordinator filesystem. They must never be mounted, copied,
prompted, indexed, or otherwise exposed to a worker or Evolver. No credential
value, token file, `.env`, trusted-verifier tree, official test, solution,
reference value, result corpus, or prior trace is authorized for upload in the
release. Model credentials remain in the existing remote mode-`0600` token
file and may be consumed only by the fixed-route model proxy.

Additive exact-ID result mirroring from `bc-server` back to the local
`results/bc-mirror/` evidence store is authorized. Mirroring must never use
`--delete`, broad replacement, or a target that is not an exact A6 run root.

## Authorized paid core and immutable scope

The authorized paid scope is the frozen A6 core only:

1. one fresh 16-task shared seed run using the pinned baseline seed worker;
2. one `A6-R` Evolver sample;
3. one `A6-E` Evolver sample;
4. one `A6-EC` Evolver sample; and
5. one complete 16-task candidate evaluation for every valid admitted `ACT`,
   with no best-arm selection and at most three candidate evaluations.

The exact task order is the 16-task panel in
`MANIFEST_A6_EXPANDED_CANARY.json`: six targets, eight strict protections, and
two volatile sentinels. All calls use
`deepseek/deepseek-v4-flash-0731`, required provider `deepseek`, no provider
fallback, and Evolver reasoning effort `high`. The run IDs, release identity,
and full effective launch plan must be persisted before the first applicable
call; a duplicate or already completed run ID fails closed.

Only the eight preregistered arm differences may vary: the six existing
contract/semantic exposure fields plus the public-role and public-instruction
member identities required for the R-versus-E/EC evidence representation.
Seed corpus, shared evidence core, model, provider, runtime, task panel,
feedback tier, component cap, and Evolver instruction remain matched.

## Budget interpretation after this authorization

There is no hard USD ceiling for the authorized core, and the old USD 1.50 cap
must not terminate an otherwise valid core run. Cost, tokens, accepted and
noncompleted requests, wall time, retries, and missingness remain mandatory
measured outputs. They must be checked and mirrored after the shared seed,
after each Evolver arm, and after each admitted candidate evaluation.

Removing the financial ceiling does not remove any nonfinancial scope limit:
one seed, one Evolver sample per R/E/EC arm, all 16 frozen tasks, at most three
candidate evaluations, fixed route, no fallback, no adaptive task additions,
no optional stopping, and no unplanned repetitions remain hard constraints.
Unexpected runaway requests, duplicate accepted requests, retry replay,
missing cost records, or lifecycle residue are protocol failures and still
require fail-closed intervention.

## Gates that remain fail closed

Before upload, publication, preflight, and each paid stage, independently
revalidate the exact local and remote member sets and digests; the external
ten-field identity; protocol, source, config, image, public/trusted role,
scheduler, provider-route, model, task-order, and worker/candidate digests; and
the evaluator firewall. The release must execute from its own read-only source
root. A preflight must make zero model and official-score calls and leave zero
managed container or network residue.

The durable coordinator, remote health timer, Mac watchdog, `caffeinate`, and
additive exact-ID mirror start together before the long paid sequence. During a
live attempt, monitoring reads only sanitized progress, request/cost summaries,
unit health, and exact artifact membership at low frequency. It must not read
trusted criteria, raw verifier material, credentials, hidden evaluator state,
or mutate a live attempt. Identity drift, evaluator leakage, provider fallback,
unmatched arm bytes, wrong task order, duplicate acceptance, or missing
identity/cost records requires an immediate fail-closed stop.

## Sequential work remains trigger controlled

This authorization does not start or pre-authorize `A6-F`, a mutation-amplitude
ablation, a proposal portfolio, a throughput comparison, confirmatory
repetitions, or QuantCode-Bench. `A6-F` remains available only after the full
R/E/EC audit satisfies its frozen feedback-sufficiency trigger and its separate
L2 mapping, sanitizer, and leakage preflights. Mutation and throughput stages
remain available only after their own protocol triggers and a separately
frozen plan. The absence of a financial cap is not a scientific trigger.

## Evidence, ledger, and claim discipline

Preserve negative, `ABSTAIN`, timeout, missing, rejected, interrupted, and
superseded artifacts. Do not enter upload, identity materialization, no-model
preflight, or synthetic audits as experiment runs. Add the shared seed,
discovery arms, and any candidate evaluations to
`results/qfbench-experiment-index.json` only with exact unique run IDs and
status/evidence paths after the corresponding real stage exists.

After the core completes or fails terminally, write a dated measured result
report and a dated decision/memory update. Keep measured results,
source-audited implementation facts, proposed next stages, and not-run stages
explicitly separate. One Evolver sample per arm is a localization canary, not a
causal arm-effect or significance result; 16 fixed tasks are not 16 independent
experimental units.

## Independent prelaunch audit while execution is blocked

The following facts are **source-audited or proposed**, not measured A6 run
results. The clean local release revalidated at 261 members with source-tree
SHA-256
`3b04a5b2257bd8467eea364d16992d22b7ffdeb2c9f688acb17421db716fb20c`;
its external manifest and upload-tar SHA-256 values match the exact values
above. The frozen manifest contains exactly ten external launch-identity
fields, the ordered 16-task panel derives exactly as six targets, eight strict
protections, and two sentinels, and the effective route remains
`deepseek/deepseek-v4-flash-0731` on provider `deepseek`, no fallback, with
Evolver reasoning `high`.

The proposed immutable IDs are:

- shared seed: `qfbench-a6-seed-evidence-flash-20260809-r1`;
- discovery: `qfbench-a6-discovery-r-flash-high-20260809-r1`,
  `qfbench-a6-discovery-e-flash-high-20260809-r1`, and
  `qfbench-a6-discovery-ec-flash-high-20260809-r1`;
- conditional candidate evaluations:
  `qfbench-a6-candidate-r-eval-20260809-r1`,
  `qfbench-a6-candidate-e-eval-20260809-r1`, and
  `qfbench-a6-candidate-ec-eval-20260809-r1`.

They are unique, satisfy the runners' exact-ID grammar, and are absent from the
local run ledger and local result roots. They have not been registered or
created remotely. Each conditional candidate ID may exist only after its own
arm emits an admitted `ACT`; arms are never combined and no winner is selected.

The proposed launch order is fail closed: materialize and live-revalidate the
external identity; execute `--preflight-only` under the same final seed ID;
activate the four monitoring layers and exact-ID mirror; then start the seed
coordinator. After the seed completes, build the formal R/E/EC corpora, execute
all three discovery preflights under their final IDs, and only then start those
three proposal coordinators. A candidate repeats the same identity, preflight,
monitor, and launch order only after the applicable admitted `ACT`.

The watchdog design matches the mandatory bounded policy: user-systemd
`Restart=on-failure` permits four starts within 15 minutes; a 30-second remote
timer publishes only sanitized unit/progress health and escalates after restart
budget exhaustion or 20 minutes without progress; a 60-second Mac LaunchAgent
permits at most three repair attempts per alert fingerprint; persistent
`caffeinate` and an additive exact-ID mirror start with the coordinator. The
mirror excludes worker/verifier input archives and credential/token material
and must not contain `--delete`. These A6 unit, timer, LaunchAgent, and mirror
files are still proposed and unmaterialized, so their effective deployed bytes
have not been validated.

Source inspection also preserves the evaluator boundary: the Evolver archive
contains only the candidate, authorized evidence, and Evolver assets; workers
are routed only to the public task root; only verifier routing receives the
trusted root. The coordinator may hash and validate the trusted role identity,
but the criteria manifests and trusted task material must never enter a worker
or Evolver bundle. This is source-audited implementation evidence, not a live
firewall measurement for A6.

At the time of the first independent audit, the exact remote release, external
identity, no-model preflight, and watchdog stack did not exist, so its outcome
was **BLOCKED / NO LAUNCH**. No seed, proposal, candidate evaluation, provider
request, official score, cost record, A6 ledger entry, or measured A6 result
existed. The later exact user message now permits materialization, but it does
not itself convert this old local-only audit into a live PASS. A fresh remote
equality and preflight audit is mandatory before paid/model execution. A6-F,
mutation, throughput, and repetitions remain blocked by their scientific
triggers even after the egress gate is satisfied.

## Live independent fresh-seed launch gate

**Measured infrastructure evidence later on 2026-08-09:** the exact remote
release was atomically published read-only at the authorized final path. An
independent live read-only audit rederived 261 regular source members,
2,711,040 bytes, no symlinks or rejected members, external manifest SHA-256
`cf8501036b7866429d298fae265290ff0ae15b2db8cf3733a12c2f3b16ec71ba`,
source-tree SHA-256
`3b04a5b2257bd8467eea364d16992d22b7ffdeb2c9f688acb17421db716fb20c`,
and exact archive SHA-256
`e35ddf01dc68b2f8de15d89c765e67064e7eb4ff7fcc1b306aed0300dc38b20b`.
The 301 archive entries were only regular files/directories with no unsafe
path or type.

The external 1,037-byte identity record has exact byte SHA-256
`e73771945f54aab172b5a439727aba427a2469d0ea2a3ac711557784a5a136a4`.
The independent audit loaded the live rootless config and role roots, rehashed
the protocol, config, image set, public/trusted role manifests, scheduler,
provider route, and source tree, and rederived materialized launch digest
`af4e6615abe8514b65fb8cc2d9e56515a723500c909f22379581045a714d8712`.
All ten fields matched the record exactly. The panel remained the ordered 16
tasks, the public and trusted roots were disjoint, and the effective route was
`deepseek/deepseek-v4-flash-0731` on exact provider `deepseek`.

The same final seed ID
`qfbench-a6-seed-evidence-flash-20260809-r1` completed the no-model preflight
with runtime identity
`aabe3a697ab5453f5c86b198980f53ef9b813951ab182d3a08588f593905ade8`.
Its run root contained only the coordinator lock, plan, preflight, and progress
records: zero model requests, completed scores, verifier records, proxy audits,
worker executions, or final report. Both exact-ID and all-QEA-managed container
and network counts were zero. Host resource leases are process-local and the
preflight process had exited; no A6 lease artifact existed.

The installed seed service, health service, and 30-second timer matched SHA-256
`e86ee3182b48ba7a5fc7cb881690ce4fe24b89cd8f47e8334f3c456ed763a2e5`,
`7494d31f2b1b88d0f8276fa44500161e6dce12e2124f25813f23a03c001a151d`,
and `59aad2f90e5086aa543b3c8095063a335a6c6adb1916525301a5cbadf406f396`.
Systemd verification passed; the coordinator used four starts per 15 minutes,
`Restart=on-failure`, a 30-second restart delay, exact release working
directory, the 16 manifest tasks in order, the exact seed worker on a single
`seed-evidence` arm, concurrency `12/3`, and all four A6 identity arguments.
The coordinator and timer remained disabled/inactive for the independent gate.

The installed 60-second Mac A6 monitor matched code SHA-256
`d7637b178594c147f9abcb7ee035feada3669a7f16c3b86e097cc8adda919fde`
and plist SHA-256
`96c778f8a11c8ed0564e300e1b4bd5b1573a44e30ce2866d796ca1fcf90b8000`.
It was deliberately not loaded before this gate. It recognizes only the seven
exact proposed A6 IDs, skips uninstalled stages, rechecks the live fingerprint,
repairs only `coordinator_not_running`, and never repairs `stalled` or
`restart_budget_exhausted`; repairs are capped at three per fingerprint with a
15-minute interval. Persistent `caffeinate` was live. The active 60-second
additive mirror matched script SHA-256
`338df7b3327389825c94d1e4f29fb3c63034fff2b000219392797c880159dfcf`
and seven-A6-ID registry SHA-256
`72db626042142e5a36eb27b4c3428ba608fe0bf8be48b430f4006a2ae1cac739`;
it had last exit zero, no `--delete`, strict sensitive/input exclusions, and
mirrored the preflight files at modes `0700/0600`. The experiment ledger still
contained 14 historical runs and zero A6 entries.

**Gate decision: FRESH-SEED LAUNCH PASS.** This PASS authorizes only the one
fresh 16-task shared seed service. In the launch window, load the exact A6 Mac
monitor, enable/start the exact seed health timer, and start the exact seed
coordinator together; immediately recheck the loaded hashes/states, first
sanitized health transition, fixed provider/no-fallback route, first task and
worker identity, evaluator firewall, mirror advancement, and managed-resource
membership. Any drift, source/trusted material exposure, duplicate accepted
request, missing accounting, or unexpected residue stops the seed fail closed.

This is an infrastructure launch gate, not an A6 result or benefit claim, and
it does not create a ledger entry by itself. A6-R/E/EC model calls remain
blocked until the fresh seed completes, the formal evidence corpora are built,
shared and semantic bytes pass the frozen three-arm audit, and each discovery
ID passes its own same-final-ID no-model preflight and independent gate. A6-F,
mutation, throughput, repetitions, and QuantCode-Bench remain not authorized by
this fresh-seed PASS.

## Superseding interrupted-launch incident and renewed block

**Measured immediately after the PASS:** the remote seed service was started,
but activation of the Mac A6 repair monitor was rejected by the security
reviewer because the monitor could later request a paid restart. The coordinator
exited within about one second, before constructing the runtime, model proxy,
worker, verifier, or evaluator. The implementation stopped and disabled the
coordinator and health timer before the 30-second restart delay elapsed. The
service made one start and zero automatic restarts; the Mac A6 monitor remained
unloaded.

Independent artifact and journal review found zero attempts, accepted provider
requests, tokens, cost records, scores, workers, verifiers, proxy records,
lifecycles, managed containers, or managed networks. The run root still
contained only the unchanged coordinator lock, plan, preflight, and progress
files. Therefore this incident is an infrastructure/preflight-transition
failure, not a paid seed attempt, official score, or A6 experimental result. It
does not enter the experiment ledger.

The exact exception was `ValueError: existing pilot plan identity differs`.
There was no identity, worker, admission, task, or runtime byte drift. The
persisted and newly derived worker digest, candidate digest, file records, and
admission values matched. The mismatch was a serialization-type bug:
`asdict(admission)` produces tuples for `checks` and `files`; canonical JSON
writes those tuples as arrays, and `json.loads` returns lists. The next
same-run-ID invocation compared the loaded list-bearing plan directly with the
new tuple-bearing in-memory plan, making equality false even when every value
was identical. Thus the current release cannot transition from its mandatory
preflight to an actual same-ID run.

The earlier **FRESH-SEED LAUNCH PASS is superseded and withdrawn**. Fresh seed,
R/E/EC discovery, and every later stage are **FAIL / BLOCKED**. Deleting or
editing the persisted plan, changing run ID to bypass it, or skipping the
same-ID preflight is not a protocol-valid remediation. The required repair is a
minimal canonical JSON normalization before plan comparison and persistence,
plus a regression that exercises preflight followed by the same final-ID actual
path without permitting an evaluator/model call in the test.

That code repair changes the clean source release and therefore its tree,
manifest, archive, external identity, and content-addressed final path. Rebuild
and revalidate all of them, obtain new literal user authorization for the new
exact upload-tar SHA-256 and exact `bc-server` final path, rerun the complete
no-model identity/preflight/watchdog gate, and obtain a new independent fresh
seed PASS. The old exact egress authorization must not be stretched to the new
payload. The repair-monitor activation must also be explicitly allowed before
any future coordinator start so all four monitoring layers can actually start
together.

## Local replacement-payload audit — NEW EGRESS READY, not authorized

Implementation applied the required minimal fix locally: one helper converts
the complete candidate plan through `json.dumps`/`json.loads` before both the
persisted-plan comparison and write. Relative to the failed remote release, the
runner's only code changes are that six-line canonical JSON helper and one plan
normalization call. No field is removed, ignored, defaulted, or compared
partially. Lists remain order-sensitive and every canonical JSON value remains
subject to exact full-plan equality.

The regression first writes the preflight plan containing tuple-backed
admission data, then invokes the same final ID and proves it reaches a fake
evaluator boundary without any real evaluator/model action. Its strict negative
changes the checkpoint identity, requires `existing pilot plan identity
differs` before the fake evaluator, confirms all evaluator/identity/runtime
counters are unchanged, and confirms the canonical plan bytes are not
rewritten. Independent system-Python and full-dependency-venv runs each passed
all 15 component/source-release tests. Implementation separately reports its
complete suite at `1113 passed, 1 skipped`.

The independently audited replacement payload is:

- source root: `/tmp/qea-a6-clean-release.CJ97NV/bundle/source`;
- external manifest:
  `/tmp/qea-a6-clean-release.CJ97NV/bundle/A6_SOURCE_RELEASE_MANIFEST.json`;
- exact upload tar: `/tmp/qea-a6-clean-release.CJ97NV/A6_SOURCE_UPLOAD.tar`;
- 261 source members and 2,719,916 source bytes;
- tree SHA-256
  `ad26fe36d95392731022c325451504476b99a97fbe820f8c7451c396c9991d23`;
- manifest size 47,018 bytes and SHA-256
  `5620aba6b6cda5791f3cc0e52609eea675388059e0d559abbe257eebc4bf2faa`;
- tar size 2,987,008 bytes and SHA-256
  `777a5eb78b34f54432ca5bcc93e25052afab824e0f724c09a2467815465e981f`.

An independent manifest rebuild was byte-identical. A fresh independent tar
extract revalidated the same 261-member tree and manifest. The tar contained
301 entries: 262 regular files including the external manifest and 39
directories; it had zero unsafe paths/types, PAX/xattr headers, symlinks,
AppleDouble entries, cache/result/runtime roots, or secret/token/credential
markers. Relative to the old 261-member release there were no added or removed
members and exactly four changed members: the runner, `PROJECT_MEMORY`, the
frozen A6 protocol decision, and the separately audited QuantCode screen. The
new `PROJECT_MEMORY` preserves the failed r1 incident and withdrawn PASS.

**Local payload decision: NEW EGRESS READY.** This means only that the new local
payload is reproducible and suitable to present for a new security/egress
decision. It is not upload, publication, identity, watchdog, preflight, or
paid/model authorization. Preserve the old release and r1 run unchanged. The
proposed new staging and final paths are, respectively,
`/home/julius/qea/deploy/staging/a6-ad26fe36d9539273.upload` and
`/home/julius/qea/deploy/releases/a6-ad26fe36d9539273`; the proposed seed ID is
`qfbench-a6-seed-evidence-flash-20260809-r2` so the r1 incident is never
resumed or overwritten.

Before any transfer, a new user message must literally authorize exact local
tar SHA-256
`777a5eb78b34f54432ca5bcc93e25052afab824e0f724c09a2467815465e981f`
to exact final path
`/home/julius/qea/deploy/releases/a6-ad26fe36d9539273`. Before any coordinator
start, security review must also accept loading the exact bounded A6 Mac monitor
even though it can request a paid restart for the exact installed run ID. After
those permissions, repeat remote member/tar equality, a new ten-field identity,
r2 same-ID no-model preflight, all four watchdog layers, and an independent
fresh-seed gate. Until then all A6 execution remains blocked.

## Offline r2 watchdog audit — COMBINED AUTH READY, not activated

An entirely separate r2 monitoring bundle was built offline under
`output/qfbench-supervisor/a6-ad26fe36d9539273/`. Nothing in it was installed,
loaded, uploaded, or executed. Independent checks confirmed that the proposed
remote release, r2 run root, seed service, and health timer were all absent;
the two new LaunchAgent labels were not loaded; and the installed r1 monitor
plist and active global mirror script retained their old exact hashes.

The bundle binds these seven unique r2 IDs, in order, through exact-ID file
SHA-256 `2d00ac3ae59806ac79aaa387a71b8cdd05f52fd2c98c3b422e5e129151cdcee9`:

1. `qfbench-a6-seed-evidence-flash-20260809-r2`;
2. `qfbench-a6-discovery-r-flash-high-20260809-r2`;
3. `qfbench-a6-discovery-e-flash-high-20260809-r2`;
4. `qfbench-a6-discovery-ec-flash-high-20260809-r2`;
5. `qfbench-a6-candidate-r-eval-20260809-r2`;
6. `qfbench-a6-candidate-e-eval-20260809-r2`; and
7. `qfbench-a6-candidate-ec-eval-20260809-r2`.

The monitor code SHA-256 is
`93860837ce77b3a61f995a106a7bc8cfec18280efd5fdf3d832e93895bd81620`;
its plist SHA-256 is
`ec8115718fe8d9178b3136bb1784efd5def3f3797d507084cf27ff756269ae6e`,
with label `com.qea.qfbench-a6-r2-monitor` and a 60-second interval. It has a
new r2-only state/log root, skips every uninstalled ID, reads only the sanitized
r2 health record, treats initial inactive success as a no-op, and can mutate
only a `coordinator_not_running` record after an immediate live same-fingerprint
recheck. `stalled` and `restart_budget_exhausted` cannot reach its restart path.
It permits at most three requests per fingerprint, at least 15 minutes apart.

The replacement additive mirror script SHA-256 is
`c52b67d75dc5a125609c1720a0b420e51bcbd23c47a67b4557a1b6dad8c10889`;
the 21-unique-ID registry SHA-256 is
`a3c44175998f27cfaebcf12c2ed75d51f1b3942b380d5edb8877049fb46b115c`;
and its plist SHA-256 is
`b7a1cfc9914f5cacc7be4ab472183a322e786925ddcb82699a454858728442b3`,
with label `com.qea.qfbench-a6-r2-result-sync` and a 60-second interval under
`caffeinate`. The registry retains seven historical IDs, all seven r1 IDs, and
then the seven r2 IDs. The script has no `--delete`, skips a missing run but
fails on SSH errors, enforces local `0700/0600`, and excludes worker/verifier/
generic input archives, leases, `.env`, credential/token/criteria names, and
trusted-verifier/trusted trees.

The offline seed, health-service, and 30-second timer bytes have SHA-256 values
`e8ebbf3cf38e6de23166ae66149c8e6f3e9710482f06677505eba8209139c68c`,
`f0719c84244eeb250609ff3c85934ab414ce3e1b60e238e55feed7c1025360b5`,
and `163a744c675625174e586782c6ec1232dabb6698381f636dd5fe43c8d99e6414`.
They point only to the proposed new release/identity and r2 seed ID, preserve the
ordered 16 tasks and `12/3` concurrency, and retain four starts per 15 minutes,
`Restart=on-failure`, and a 30-second restart delay. Python compilation, shell
syntax, both plist lints, ID equality/order, and static bounded-restart checks
passed independently.

**Authorization-package decision: COMBINED AUTH READY.** This means the exact
fields are ready for one direct user confirmation; no permission has yet been
exercised. A sufficient confirmation should state, in substance and with every
hash/path/label exact:

> 我明确授权将本地文件
> `/tmp/qea-a6-clean-release.CJ97NV/A6_SOURCE_UPLOAD.tar`（SHA-256：
> `777a5eb78b34f54432ca5bcc93e25052afab824e0f724c09a2467815465e981f`）
> 上传到 `bc-server`，并只发布到
> `/home/julius/qea/deploy/releases/a6-ad26fe36d9539273`。我知悉该包包含私有
> QEA 源码、配置、研究文档、QFBench manifests 和两份仅供 trusted coordinator
> 使用的 VERIFIER_CRITERIA；不得向 worker/evolver 暴露 trusted criteria、源码树
> 或其他 coordinator material。新的 remote release、十字段身份、r2 same-ID
> 零调用 preflight 和独立 seed gate 全部通过后，我同时明确授权安装上述三份
> remote unit bytes，并用 plist SHA-256
> `ec8115718fe8d9178b3136bb1784efd5def3f3797d507084cf27ff756269ae6e`
> 加载/enable/kickstart `com.qea.qfbench-a6-r2-monitor`，以及用 plist SHA-256
> `b7a1cfc9914f5cacc7be4ab472183a322e786925ddcb82699a454858728442b3`
> 替换现有 result-sync job 为 `com.qea.qfbench-a6-r2-result-sync`；旧 r1 evidence
> 必须保留。该 r2 monitor 只能处理 exact-ID 文件 SHA-256
> `2d00ac3ae59806ac79aaa387a71b8cdd05f52fd2c98c3b422e5e129151cdcee9`
> 列出的七个 r2 run ID，只能在 unit 已安装、sanitized health 为
> `coordinator_not_running`、result 非初始 success、立即重读 fingerprint 仍完全
> 相同的情况下执行 `systemctl --user restart qea-<exact-run-id>.service`；
> `stalled` 和 `restart_budget_exhausted` 不得重启，每个 fingerprint 最多三次且
> 间隔至少 15 分钟。我明确授权这一有界 restart 行为，即使协议有效的 restart
> 会继续产生模型请求和费用；不设美元硬上限，但所有冻结的 stage、identity、
> evaluator firewall、request accounting 和 scientific trigger 仍须 fail closed。

The confirmation does not by itself authorize bypassing any identity or
scientific gate. After it is received, upload and publish only the exact new
payload; independently audit live bytes and identity; create r2 preflight and
unit bytes; recheck them against the offline hashes; and only after a new seed
PASS activate the new monitor, replacement mirror, remote health timer, and seed
coordinator in one launch window. Discovery and candidate units remain absent
until their own protocol triggers and independent gates.

## Combined r2 authorization activated — live seed gate still pending

Later on 2026-08-09, the user directly confirmed the complete exact package
above. The confirmation activates egress of only
`/tmp/qea-a6-clean-release.CJ97NV/A6_SOURCE_UPLOAD.tar` with SHA-256
`777a5eb78b34f54432ca5bcc93e25052afab824e0f724c09a2467815465e981f`
through staging path
`/home/julius/qea/deploy/staging/a6-ad26fe36d9539273.upload` to final path
`/home/julius/qea/deploy/releases/a6-ad26fe36d9539273`, subject to the stated
trusted-coordinator/worker boundary. It also activates, but only after a new
live independent fresh-seed PASS, the three exact remote unit bytes and the
bounded r2 monitor and additive replacement mirror identified above. The user
explicitly accepted that a protocol-valid bounded restart can produce further
model requests and cost, while retaining every frozen identity, evaluator
firewall, accounting, stage, and scientific-trigger gate and no USD hard cap.

This is an authorization record, not launch evidence. Exact egress is in
progress. Before any r2 model attempt, an independent auditor must verify the
atomic read-only release, freshly materialized ten-field identity, same-final-ID
zero-call preflight, exact installed unit bytes while disabled/inactive, clean
runtime residue, and unchanged r1 incident evidence. The r2 monitor, mirror,
health timer, and seed coordinator remain unactivated until that auditor returns
an explicit `FRESH-SEED r2 PASS`. Discovery, candidate evaluation, A6-F, and
mutation remain blocked behind their later protocol gates.

## Independent live r2 fresh-seed gate — PASS

An independent read-only audit then recomputed the deployed release rather than
accepting the implementation report. The remote source validator found exactly
261 members and tree SHA-256
`ad26fe36d95392731022c325451504476b99a97fbe820f8c7451c396c9991d23`;
the external manifest was 47,018 bytes with SHA-256
`5620aba6b6cda5791f3cc0e52609eea675388059e0d559abbe257eebc4bf2faa`.
The final archive was 2,987,008 bytes with exact authorized SHA-256
`777a5eb78b34f54432ca5bcc93e25052afab824e0f724c09a2467815465e981f`,
contained 262 regular files and 39 directories with no unsafe path, special
type, PAX header, symlink, AppleDouble, or undeclared source member, and the
upload staging directory had been removed. Source files were all `0444`, source
directories all `0555`, the manifest was `0444`, and the final archive was
`0400`.

Using the deployed validation code and the live rootless config, image-set
manifest, public role root, trusted-verifier role root, scheduler, and provider
route, the auditor independently validated identity-record SHA-256
`4679b6fca2d5eba7e328f86ea2eec3b553a6191437488e65aa63a3a65b86da43`
and materialized-launch SHA-256
`3b3dee2cfda952c0528efe66ac9bee4ee7ac5804bd3a8dd533e7fa843ce68376`.
All ten frozen fields matched, including model
`deepseek/deepseek-v4-flash-0731`, provider `deepseek`, both role-manifest
digests, scheduler identity, and source tree. Static deployed routing still
uses the public task root for workers, the disjoint owner-only trusted root for
verifiers, and `include_evolver=False` for the seed; the coordinator source tree
and trusted criteria are not worker/evolver inputs.

The exact r2 run root contained only the empty coordinator lock and canonical
plan, preflight, and progress JSON. Preflight and progress were byte-identical;
status was `preflight_complete`, runtime SHA-256 was
`aabe3a697ab5453f5c86b198980f53ef9b813951ab182d3a08588f593905ade8`,
and `validated_before_first_evaluator_call=true`. There were zero model
requests, attempts, scores, workers, verifiers, proxy records, coordinator
journal entries, exact-ID containers, networks, or leases. The experiment
ledger remained at 14 historical runs with zero A6 entries.

The installed seed, health-service, and timer bytes independently matched
SHA-256 values
`e8ebbf3cf38e6de23166ae66149c8e6f3e9710482f06677505eba8209139c68c`,
`f0719c84244eeb250609ff3c85934ab414ce3e1b60e238e55feed7c1025360b5`,
and `163a744c675625174e586782c6ec1232dabb6698381f636dd5fe43c8d99e6414`;
systemd verification passed, all three were `0600`, the seed and timer were
disabled/inactive, restart count was zero, and linger was enabled. The exact r2
monitor and mirror hashes and seven-ID bindings remained unchanged and their
labels were not loaded; the monitor state directory did not exist. Persistent
`caffeinate` remained running. The r1 release, identity, preflight root, stopped
coordinator, and stopped timer retained their old bytes and state.

The first evidence JSON had named the now-removed upload-staging tar path even
though the exact archive had moved into the final release. This reporting-only
error was corrected without remote mutation: the canonical evidence now names
`/home/julius/qea/deploy/releases/a6-ad26fe36d9539273/A6_SOURCE_UPLOAD.tar`,
records cleaned staging, and has SHA-256
`b67e280d1b7886c3735fb2bdb1943b88a4d4609f38b52cb1ee9257f18bd759c5`.

**Gate decision: FRESH-SEED r2 PASS.** This PASS is limited to launching
`qfbench-a6-seed-evidence-flash-20260809-r2`. In one bounded launch window,
replace the old result-sync job with the exact authorized additive r2 mirror,
load the exact authorized r2 repair monitor, enable/start the exact r2 health
timer, and start the exact seed service. Immediately re-audit loaded hashes,
unit states, the first sanitized health fingerprint, exact model/provider with
fallbacks disabled, request uniqueness/accounting, worker-public and
verifier-trusted routing, mirror exclusions/modes, and resource residue. Any
identity, source, role, route, replay, firewall, accounting, watchdog, or
lifecycle drift must stop fail closed.

This is not a measured seed score and not permission for discovery. R/E/EC
remain blocked until the fresh seed completes cleanly, its evidence is built,
the three formal arm corpora pass the byte-difference audit, and each exact
discovery ID passes its own same-ID preflight and independent launch gate.
Candidate evaluation requires arm-local explicit ACT; A6-F and mutation remain
blocked behind their frozen scientific triggers.

## Superseding r2 interruption — mirror defect, stop race, and fresh-r3 requirement

The r2 seed started at 2026-08-09 21:44:27 CST only after the live PASS. Its
first-window model route, worker/verifier firewall, request uniqueness, and
accounting checks were clean. Independent monitoring then found that the exact
authorized additive mirror was not actually traversing its 21-ID registry: the
shell loop read the registry on standard input, while its child `ssh` and the
`ssh` used by `rsync` inherited that same input. The child consumed subsequent
run-ID lines. Repeated live observations showed only the first historical run
being synchronized, occasionally the second, while the r2 seed mirror directory
remained absent. The `--delete` and sensitive-input exclusions were intact, but
the mandatory additive evidence-mirror layer was not functioning.

That defect triggered a fail-closed stop at 21:50:33. The stop ordering exposed
a second operational defect: before the Mac repair monitor was unloaded, it
observed the intentional stop as `coordinator_not_running`, recorded one repair
against fingerprint
`60c075a1aa2b083bd2e2a87d3c5aa44762f4015caed7c3935377d7fcf2a7af44`,
and issued its one authorized bounded restart at 21:50:41. The second service
invocation reached no new proxy/model request; at 21:51:06 it failed on an exact
network-name collision with a still-running first-invocation network. The
monitor and mirror were unloaded, the service was stopped again before its
30-second systemd retry, and the health timer was disabled/stopped. There were
exactly two service starts and no further automatic restart.

At containment, the host had 12 of 16 completed scores and 103 persisted proxy
records. All 103 were HTTP-200 `completed`, used only
`deepseek/deepseek-v4-flash-0731`, had unique request identities and unique
provider request IDs, and had complete accounting: USD `0.063910588`, 761,199
input tokens, 148,395 output tokens, and 909,594 total tokens. These values are
measured lower bounds, not complete r2 cost. Four first-invocation worker/proxy
pairs were still running after the coordinator stop. The deployed exact-ID
reaper killed eight persisted container IDs and removed four exact internal
networks; secondary dry-run/apply verification found nothing further. Final
lifecycle state is 16/16 worker, proxy, and network records clean (12 exact-ID,
four reaper), 12/12 verifier records clean, and zero exact containers, networks,
inventory, or leases. The service and timer are disabled/inactive, both r2
LaunchAgents are unloaded, no final pilot report exists, and discovery never
started.

The four interrupted tasks cannot be classified as zero-request. In the
deployed proxy manager, request audit bytes remain private to the proxy until
the coordinator exits the proxy context and the `finally` block finalizes,
downloads, validates, and atomically writes them to the run root. The hard
coordinator termination bypassed that block while all four proxies remained
live, and the exact reaper later removed the only remaining proxy-local audit
surface. Therefore additional accepted requests, tokens, and cost for those
four tasks are unknown. Their absence from host audit files is not evidence of
zero provider activity.

Same-ID r2 resume is prohibited. Although the evaluator would reuse the 12
completed scores and schedule the four tasks lacking scores, replaying those
four could duplicate unknown accepted requests. It would also overwrite their
current reaper-marked lifecycle documents when new sandbox/network lifecycles
are created, weakening incident preservation. Freeze r2 unchanged as
interrupted infrastructure evidence, exclude its 12 scores from the A6 seed
corpus and every formal comparison, and report only the measured 103-request
lower bound plus explicitly unknown additional use.

The earlier `FRESH-SEED r2 PASS` is consequently superseded for continuation.
Recovery requires a fresh r3 run ID and task attempts, a corrected additive
mirror whose child SSH processes cannot read the registry input, a regression
that proves all registered IDs are traversed, new exact monitor/mirror/unit/ID
hashes and direct authorization, a new zero-call preflight, and a new independent
fresh-seed gate. The shutdown order is now frozen as: unload the repair monitor,
disable/stop the health timer, stop the coordinator, run the exact-ID reaper,
and only then unload the mirror after its final safe sync. R/E/EC discovery,
candidate evaluation, A6-F, and mutation remain blocked.

The ordered local incident record is
`output/qfbench-supervisor/a6-ad26fe36d9539273/r2-seed-stop-and-reaper-incident.json`,
8,023 bytes with SHA-256
`838d3845f345ed71c59817a2a22f0784904511262d791594e589c0a07e63171e`.
It distinguishes the first exact reaper apply, which killed eight containers
and removed four networks, from root's later empty dry-run/apply verification;
the latter is not evidence of spontaneous cleanup.

## Offline fresh-r3 recovery package — AUTH READY, not activated

A fresh-r3 package was built locally without installing, loading, uploading, or
executing it. The seven new IDs are:

1. `qfbench-a6-seed-evidence-flash-20260809-r3`;
2. `qfbench-a6-discovery-r-flash-high-20260809-r3`;
3. `qfbench-a6-discovery-e-flash-high-20260809-r3`;
4. `qfbench-a6-discovery-ec-flash-high-20260809-r3`;
5. `qfbench-a6-candidate-r-eval-20260809-r3`;
6. `qfbench-a6-candidate-e-eval-20260809-r3`; and
7. `qfbench-a6-candidate-ec-eval-20260809-r3`.

Their ordered exact-ID file has SHA-256
`463f447676bc5ef17f7dcdb62434641adf89a46f8372cbcc4cd9b3049332644f`.
The additive registry retains all historical, r1, and r2 IDs before the seven
r3 IDs, contains 28 unique entries, and has SHA-256
`95cdbd5776066133d985fd9ceaa827a1809c0c572900712bd6841c96c4dd1bf0`.

The corrected mirror script has SHA-256
`b3f95a6e37a127c200559c65e6769e2c712197782f0300c30f3a733eddbdc508`;
its plist has SHA-256
`f75209db8ee9f34ace51b250f9e75802e76c6cf0dce264cc0351643c923dd13a`
and label `com.qea.qfbench-a6-r3-result-sync`. The registry is opened on a
private file descriptor, every child closes that descriptor, the availability
SSH uses `-n`, and rsync receives `/dev/null` on standard input. A deterministic
regression made both fake children actively consume standard input and proved
that the script still visited and mirrored the actual ordered 28-entry registry.
Separate tests preserve missing-ID continuation, SSH-error fail-closed behavior,
no `--delete`, sensitive/input exclusions, and `0700/0600` modes. Five mirror
tests passed independently in the full environment; system-Python targeted
mirror/watch/component checks also passed.

The r3 monitor code has SHA-256
`8d440a2507d44e4012b4f188b35c2ef2b7ab529cf9b47d74eb523ca350270663`;
its plist has SHA-256
`5bac64e709cd90960608d6d6da8adba47b5785d48998dbd1d93432df04994d83`
and label `com.qea.qfbench-a6-r3-monitor`. Its repair semantics are otherwise
unchanged: installed exact IDs only, immediate live same-fingerprint recheck,
only `coordinator_not_running`, never initial success, `stalled`, or
`restart_budget_exhausted`, and at most three requests per fingerprint at least
15 minutes apart. The frozen intentional-stop-order file has SHA-256
`69268fe2cc295abbc05d6ed4238e736dcf1620b0265fac9a72fdffee97220a64`
and places monitor unload before any remote coordinator-state change.

The local-only r3 seed service, health service, and timer have SHA-256 values
`f9776464a973387f8b39f23c00612a3bd91c466be382d6357da86fbb310367b8`,
`0ca6747650c03e9c902ae1cfead0acd231912c1a98243451d36f3d74716b44b5`,
and `9128139fec4448a8401053e7e02f29da1f025aa35604b2390fc8027a63e1a352`.
They reuse only the already-published content-addressed release and external
identity, change the run/health namespace to r3, and retain the frozen 16-task
order, `12/3` concurrency, four starts per 15 minutes, and 30-second restart
delay. Shell syntax, Python compilation, both plist lints, ID equality/order,
and unit-difference inspection passed.

Independent absence checks found the remote r3 run root and all three r3 units
absent, both local r3 labels and destination plists absent, and no r3 monitor
state. Frozen r2 remained at zero exact containers and networks.

**Recovery authorization decision: R3 AUTH PACKAGE READY, not activated.** A
new direct user message must authorize the exact hashes, labels, and seven r3
IDs above, including the monitor's bounded paid-restart capability. The existing
source release and ten-field identity may be reused only after live equality is
recomputed. After direct authorization, install only the exact bytes, create the
fresh r3 same-final-ID zero-call preflight, independently audit it, and obtain a
new explicit `FRESH-SEED r3 PASS` before loading the r3 monitor/mirror or starting
the timer/coordinator. Nothing here authorizes discovery or any later A6 stage.

## Superseded authorization cadence on 2026-08-10

The requirement above for a new direct exact-hash confirmation per replacement
is superseded by the accepted
[QFBench A6 standing operational authorization](2026-08-10-qfbench-a6-standing-operational-authorization.md).
That later decision permits independently audited content-addressed replacements
within the frozen host, sensitive-data category, provider account, evaluator
firewall, restart caps, and scientific scope. It does not waive live identity,
zero-call preflight, independent launch, watchdog, seed-to-corpus, or per-arm
discovery gates.
