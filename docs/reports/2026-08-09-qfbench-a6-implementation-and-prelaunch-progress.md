# 2026-08-09 — QFBench A6 Implementation and Prelaunch Progress

## Status and evidence labels

This is an additive engineering checkpoint. It does not supersede the frozen
[A6 protocol decision](../decisions/2026-08-09-qfbench-a6-expanded-panel-feedback-and-mutation-protocol.md)
and is not an experiment result.

- **[measured]** means observed in local tests, exact local artifacts, or the
  dated read-only `bc-server` audit.
- **[source-audited]** means established by inspecting frozen manifests, source
  code, reports, or deterministic synthetic fixtures without a model call.
- **[proposed]** means preregistered or prepared future work that has not run.
- **[not run]** means explicitly absent as of this checkpoint.

**[measured] Current stop state:** implementation, cross-audit, full local
regression, and one clean local source release are complete. The user asked to
record progress and pause. No source payload was uploaded, the remote final
target does not exist, the external ten-field prelaunch identity was not
materialized, and no A6 model, official score, or paid request ran.

## Research goal and diagnostic position

**[source-audited] User-level objective:** evolve the full harness into a
mechanism that can discover reusable failure types, discriminate competing
causes, demand sufficient evidence before acting, abstain when the evidence is
insufficient, and localize the responsible harness component. More worker
activity, larger diffs, or more task scores are not themselves discovery.

The measured A5 predecessor localized the next bottleneck. Its `failure_only`
arm made a two-component intervention, but its primary prediction and binary
reward gain were falsified. Its matched `contrastive` arm used success-side
counterfactuals and validly `ABSTAIN`ed with writes locked when oracle-convention
uncertainty remained. See the
[A5 report](2026-08-08-qfbench-a5-failure-type-probe-discovery-report.md).

**[source-audited] A6 diagnostic role:** test semantic identifiability, not
claim benchmark benefit. A supported `ACT` must connect an exact public
requirement to an exact artifact/trace observation and discriminate the
selected explanation from a competitor. Honest `insufficient`, calibrated
`ABSTAIN`, false-`ACT`, and unsupported semantic leaps remain first-class
outcomes.

The larger panel responds to the request to use more than five tasks. Sixteen
fixed train tasks improve deterministic breadth, domain coverage, protection
coverage, and task-level resolution. They are not sixteen independent samples,
do not turn one Evolver draw per arm into a significance test, and do not
authorize adaptive task or repetition expansion after outcomes are read.

## Frozen 16-task R/E/EC core

**[source-audited]** The exact protocol is
[`MANIFEST_A6_EXPANDED_CANARY.json`](../../data/qfbench/MANIFEST_A6_EXPANDED_CANARY.json):

| Role | Count | Statistical use |
|---|---:|---|
| repeat-failure targets | 6 | mechanism targets and positive-target advancement count |
| strict protections | 8 | familywise fail-closed safety gate |
| volatile sentinels | 2 | coverage and blast-radius description only |

The all-16 panel spans six domains. Its six-domain macro is descriptive. The
stable advancement panel contains the six targets and eight strict protections
across five domains; both volatile sentinels are excluded from the
strict-protection and stable-domain gates.

The core uses one shared fresh 16-task seed corpus and one matched Evolver
sample per arm:

- `A6-R`: indexed A5-style raw/process evidence, no public-clause corpus,
  `failure_type_v1`, and `constrained_evidence_profile_v1`.
- `A6-E`: the same decision contract plus exact public instructions and a
  deterministic public-clause index. Typed semantic comparison is available
  but is not an `ACT` precondition.
- `A6-EC`: byte-identical semantic evidence, `semantic_contract_v1`, and
  `typed_contract_artifact_trace_v1`; a complete, resolvable, discriminating
  clause-artifact-trace relation is required for `ACT`.

All arms keep the same L1 answer-free public/process outcome exposure, model,
provider route, runtime, panel, component cap, and shared Evolver instruction.
Every admitted `ACT` candidate is evaluated on all 16 tasks; `ABSTAIN` is
terminal for its arm. The first-round core maximum is 64 official scores: 16
shared fresh-seed scores plus at most three 16-task candidates. The frozen
planning estimate is approximately USD 0.98 centrally, with caps of USD 1.50,
1,000 provider requests, and 35 million tokens. These are **[proposed]** limits,
not authorization.

## Sequential feedback and mutation work

**[proposed] Optional A6-F feedback arm:** do not start it with the R/E/EC core.
It may add only the frozen L2 categorical public-clause localization channel,
only after all R/E/EC audits, only on the preregistered evidence-sufficiency
trigger, and only after mapping/sanitizer identity and leak preflights pass.
Raw verifier fragments, masked numeric oracle fragments, hidden tests,
expected/actual values, solutions, gold, and reference material remain
forbidden.

**[proposed] Mutation amplitude and throughput:** they are a separate staged
ablation after a viable discovery regime is frozen. The A6 core retains one
proposal per arm and `max_components=3`; mutation metrics are measurement-only
and cannot select or admit a candidate. A later amplitude manipulation compares
the current three-role envelope with a smallest-causally-complete envelope of
up to five roles at fixed throughput. Only after amplitude is frozen may a
one-versus-three proposal throughput experiment be considered. Sentinel and
full-panel scores cannot be adaptively reused, and all such stages require a
new frozen cost plan and authorization.

## Implementation and cross-audit closure

The following are implementation invariants, not measured benchmark benefit.

### Clean source and ten-field launch identity

**[source-audited]**
[`qea/a6_source_release.py`](../../qea/a6_source_release.py) and
[`scripts/build_a6_source_release_manifest.py`](../../scripts/build_a6_source_release_manifest.py)
implement a canonical sorted exact-member source manifest and recomputed tree
digest. They reject unsafe, duplicate, unsorted, missing, undeclared, or
symlinked members; AppleDouble, `.DS_Store`, secrets, credentials, caches,
results, outputs, runtime roots, and generated evidence are forbidden.

**[source-audited]**
[`scripts/materialize_a6_prelaunch_identity.py`](../../scripts/materialize_a6_prelaunch_identity.py)
derives the exact ten fields from the executing clean release and live pinned
remote inputs:

1. protocol-manifest SHA-256;
2. rootless-config SHA-256;
3. image-set-manifest SHA-256;
4. public-role-manifest SHA-256;
5. trusted-role-manifest SHA-256;
6. scheduler epoch;
7. scheduler-identity SHA-256;
8. provider-route-identity SHA-256;
9. clean source-tree SHA-256; and
10. canonical materialized-launch-identity SHA-256.

The identity record is the source-root-relative external sibling
`../A6_PRELAUNCH_IDENTITY.json`. Keeping it outside the source tree avoids a
self-reference through the source-tree digest. A runner must execute from the
same release root that the source manifest names.

During clean-release validation, an operational mutation was discovered:
Python imports could create `__pycache__` before exact-tree validation.
**[measured]** All release-bound A6 entrypoints now disable bytecode writes
before importing local QEA modules. A subprocess regression confirms that
executing the release manifest builder creates neither `__pycache__` nor
`.pyc`, and the release still validates afterward. The published source tree
is also intended to be made read-only after remote validation.

### Fresh-seed and evidence provenance

**[source-audited]**
[`scripts/run_qfbench_component_pilot.py`](../../scripts/run_qfbench_component_pilot.py)
requires an explicit A6 seed or candidate run kind, the external protocol and
identity records, the exact source root and source manifest, the frozen ordered
16-task panel, primary split, benchmark commit, and pinned seed/candidate
digest. It validates these identities and the scheduler before the first
evaluator call. `--preflight-only` performs no model or score.

**[source-audited]**
[`scripts/build_qfbench_a6_evidence.py`](../../scripts/build_qfbench_a6_evidence.py)
accepts only a completed fresh A6 seed whose plan and report bind the same
materialized launch digest, identity-record digest, protocol, source tree,
config, image set, scheduler, model, provider, benchmark commit, ordered panel,
and seed digest. The old 11-task A5 seed is rejected and cannot be relabeled as
fresh A6 evidence.

**[source-audited]**
[`qea/public_contract_evidence.py`](../../qea/public_contract_evidence.py),
[`qea/qfbench_a6.py`](../../qea/qfbench_a6.py), and
[`scripts/run_qfbench_discovery_pilot.py`](../../scripts/run_qfbench_discovery_pilot.py)
bind A6-E/A6-EC to the complete live verified public-role manifest and a
canonical digest over the exact source path and bytes of all 16 public
instructions. The runner rederives this identity before any model call and
revalidates the complete clause index, task membership, benchmark commit,
source paths, copied instruction bytes, member hashes, and deterministic clause
corpus. A different checkout that is internally self-consistent still fails.
A6-R must carry `null` public source identities and no `contracts/` corpus.

### Decisions and audit semantics

**[source-audited]** Missing or malformed terminal decisions do not default to
`ACT`. Candidate admission opens only on an explicit valid `ACT`; a valid
`ABSTAIN` keeps writes locked and the candidate unchanged.

[`scripts/audit_qfbench_a6_discovery.py`](../../scripts/audit_qfbench_a6_discovery.py)
checks shared seed identities; R/E/EC shared evidence bytes; E/EC semantic
corpus and live public-source equality; R semantic-source absence; calibrated
`ABSTAIN`; unsupported semantic leaps; resolvable grounded comparisons;
digest-bound primary-prediction audits; false-`ACT`; all task/domain vectors;
and the stable advancement gate. Reward non-improvement alone does not prove a
false-`ACT`, and a grounded observable relation does not certify causal truth.

### Formal no-model synthetic cross-audit

**[measured]** The formal A6 wrapper built all three 16-task synthetic corpora
successfully. The auditor observed exactly the eight preregistered contract
difference fields and no unexpected differences:

- three-arm shared-core SHA-256:
  `990b62cfac78c6f4c3f458b8d79ce6a8bc6ad1daf0572a194a31ff1727e8415a`;
- A6-E/A6-EC byte-identical semantic-corpus SHA-256:
  `cb7b131f7b68c910a03b50021596b4793892ba23859f1b95b1253faee94a0ceb`;
- shared fresh-seed launch/record identity: equal and valid;
- E/EC public role/member identity: equal and bound to
  `contracts/index.json#source_identity`;
- R public role/member identity: both `null`;
- `ladder_byte_audit.passed=true`.

The three synthetic terminal decisions were calibrated `ABSTAIN`s. This checks
the formal builder/auditor path only and is not an A6 experimental outcome.

## Final local validation

**[measured]** After all provenance and bytecode-invariance fixes:

- A6-focused tests: `28 passed`;
- full local test suite: `1112 passed, 1 skipped` in 47.45 seconds;
- `git diff --check`: passed;
- frozen A6 manifest JSON/schema/panel/path checks: passed;
- relevant Python compilation: passed;
- source builder, identity materializer, component runner, A6 evidence builder,
  discovery runner, and A6 auditor CLI parsing: passed.

The full test suite was run outside the filesystem/network sandbox solely
because model-proxy unit tests bind a loopback socket. It did not access an
external model, perform official scoring, or make a paid request. These tests
verify implementation invariants only.

## Exact clean local release

**[measured]** The clean release was built twice from its own entrypoint and
reproduced the same member count and digests. Its exact current local records
are:

| Record | Exact value |
|---|---|
| source root | `/tmp/qea-a6-clean-release.ONyWfz/bundle/source` |
| external source manifest | `/tmp/qea-a6-clean-release.ONyWfz/bundle/A6_SOURCE_RELEASE_MANIFEST.json` |
| local upload tar | `/tmp/qea-a6-clean-release.ONyWfz/A6_SOURCE_UPLOAD.tar` |
| member count | 261 |
| member bytes | 2,711,040 |
| external manifest bytes | 47,018 |
| raw source plus manifest bytes | 2,758,058 |
| uncompressed tar bytes | 3,286,528 |
| source-tree SHA-256 | `3b04a5b2257bd8467eea364d16992d22b7ffdeb2c9f688acb17421db716fb20c` |
| external-manifest SHA-256 | `cf8501036b7866429d298fae265290ff0ae15b2db8cf3733a12c2f3b16ec71ba` |
| upload-tar SHA-256 | `e35ddf01dc68b2f8de15d89c765e67064e7eb4ff7fcc1b306aed0300dc38b20b` |

`/tmp` is not durable archival storage. If these exact files disappear, do not
reuse these identities for regenerated bytes; rebuild, recompute every digest,
and record a new release identity.

Top-level payload classification:

| Surface | Members | Bytes | Classification |
|---|---:|---:|---|
| `qea/` | 145 | 1,478,385 | private Evolver, execution, isolation, and coordinator source |
| `scripts/` | 62 | 588,125 | private experiment and operational scripts |
| `docs/` | 40 | 414,990 | project memory, decisions, and research reports |
| `data/` | 11 | 174,713 | QFBench manifests, public feedback, and coordinator criteria |
| `configs/` | 1 | 1,041 | static local rootless canary configuration |
| `run.py` | 1 | 51,556 | repository CLI/orchestration source |
| `pyproject.toml` | 1 | 2,230 | package metadata |

The payload contains two sensitive but non-secret coordinator files,
`VERIFIER_CRITERIA_30.json` and `VERIFIER_CRITERIA_TRAIN_30.json`, whose declared
visibility is `trusted coordinator only; never bundle to worker or evolver`.
They may reside only on the trusted coordinator host and must never enter an
authorized worker/Evolver evidence tree.

**[measured] Exclusions and scans:** credential-material matches were zero and
forbidden-surface manifest paths were zero. The bundle contains no `.env`, key
or token values, credential files, official solutions, official tests,
trusted-verifier role tree, gold/reference data, baseline/result/run payloads,
raw traces, proxy audits, output/artifacts, runtime images, live runtime
configs, cache, bytecode, AppleDouble, `.DS_Store`, or symlinks. Source and docs
do contain credential environment-variable names as code/documentation, not
values.

## Dated read-only remote audit

The following are host observations, not a materialized launch record. They
must be rechecked against the effective plan after an authorized upload.

**[measured] Host and lifecycle:**

- rootless Docker/security checks passed;
- `Linger=yes`;
- no active QEA containers;
- no A6 systemd units;
- no active A5 units;
- all 16 A6 task worker/verifier images were present;
- approximately 46,021,648 KiB disk was free, with the filesystem 87% used;
- approximately 104 GB RAM was available; swap was heavily occupied, but host
  load was light;
- provider token-file metadata was checked without printing its path or
  contents: regular file present, owner `julius:julius`, mode `0600`, size 73.

**[measured] Existing live identities:**

| Input | Path or value | SHA-256 / identity |
|---|---|---|
| rootless config | `/home/julius/qea/runtime/configs/qfbench-base85-official-deepseek-v4-flash-0731-b8c16df-all12x3.json` | `c82e9f0dc139ea6b42ebfb1a4c0b69918e10bcd9b98c2287dc297594c361d975` |
| image-set manifest | `/home/julius/qea/runtime/image-sets/024921eb-base85-deepseek-v4-flash-f62de10.json` | `36be1ec027aa50fbeb6c177c4429bcc0467b096bf982193d60f949911321c51c` |
| image-set internal identity | — | `16df73c4f45c861d88dd11fe286badd043c405bf2ce3010b0dd9fa27abc5f56c` |
| public role root | `/home/julius/qea/runtime/qfbench-public/024921eb-base85` | manifest `eb6f933414b12e62d17b228fa16dd11e8d38c66619be58c055c0658c37e62440` |
| trusted role root | `/home/julius/qea/runtime/trusted-verifier/024921eb-base85` | manifest `005b24e7030147e7edd47d8c0c28cc65fc619118af5cd0894560b6b0a75217ab` |
| scheduler epoch | `repetitions-01-through-05` | `824a2b76c78b0389538de8b5b2234867cd4174093d8fab7db938d6a5c532e5c0` |
| provider route | DeepSeek V4 Flash, no fallback | `88f3d650ad15606378dff20e6fb093bb5ffd7819f40be54275304f437d10c3ba` |
| benchmark commit | `024921eb507fcc0c4ffe3e0a96802724be1ae84a` | source root `/home/julius/qea/runtime/qfbench-source/024921eb` |
| baseline run | `/home/julius/qea/runs/qfbench-rootless-base-85x5-official-deepseek-v4-flash-0731-all12x3-20260804` | result `db70607b56c5241fd00f2b288d9f460d42333d48b488d22c6cf25edc19cd86d1` |
| seed worker | baseline `workers/seed` | `4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c` |

The public role verified 85 tasks and 478 files; the trusted role verified 85
tasks and 291 files. The two older A5 release trees had no source manifest and
each contained 245 AppleDouble `._*` files, so neither is reusable as an A6
source identity.

## Upload refusal and current remote state

**[measured]** The exact intended remote paths were:

- staging leaf:
  `/home/julius/qea/deploy/staging/a6-3b04a5b2257bd846.upload`;
- publish-once final:
  `/home/julius/qea/deploy/releases/a6-3b04a5b2257bd846`.

The first transfer attempt was blocked by the local sandbox before connection.
The required escalation was then denied by the security review because the
payload contains private source, configuration, benchmark, and research
material and the user had not explicitly authorized that exact egress to the
exact remote destination. No workaround or alternate channel was attempted.

**[measured]** No payload bytes were uploaded. The staging leaf was verified
empty and removed. The parent `/home/julius/qea/deploy/staging` directory was
created with mode `0750`; the exact final target remains absent. No identity
record exists at the proposed release, no source tree was published, and no
remote A6 preflight ran.

## Explicitly not run and ledger state

- **[not run]** no A6 shared fresh seed;
- **[not run]** no A6-R, A6-E, A6-EC, or A6-F Evolver call;
- **[not run]** no candidate evaluation or official A6 score;
- **[not run]** no model request, paid request, provider cost, or token use;
- **[not run]** no remote launch, systemd coordinator, watchdog, mirror, or
  `caffeinate` process for A6;
- **[not run]** no materialized `A6_PRELAUNCH_IDENTITY.json`;
- **[not run]** no QuantCode-Bench prompt, score, cache, evaluator, or judge
  contact;
- **[measured]** `results/qfbench-experiment-index.json` remains unchanged at
  14 pre-existing runs, `updated_at=2026-08-07T20:29:09Z`, with zero A6 run
  entries.

Therefore there is no A6 result, no candidate-benefit result, and no basis for
a publication claim from this implementation checkpoint.

## Resume checklist and authorization boundary

The user has requested a pause. Resume requires a new explicit instruction.

1. **[proposed] Reconfirm the payload choice.** Either authorize the exact
   261-member private payload above, including the two coordinator-only
   criteria files, or explicitly request a narrower release. A narrower release
   is a different identity and requires new member, tree, manifest, and tar
   digests.
2. **[proposed] Obtain exact egress authorization** for the chosen payload to
   `bc-server`, staging at
   `/home/julius/qea/deploy/staging/a6-3b04a5b2257bd846.upload` and publishing
   once at `/home/julius/qea/deploy/releases/a6-3b04a5b2257bd846`. The existing
   paths apply only to the current exact tree digest.
3. **[proposed] Revalidate before transfer:** local file presence, 261-member
   equality, all three digests, secret/forbidden-path scan, remote target
   absence, host health, and the effective config/image/role/scheduler/route
   identities.
4. **[proposed] Stage without deletion or broad sync,** recompute every member
   and tree digest remotely, scan for AppleDouble/cache/symlink/credential
   residue, and make the source tree read-only. Publish only if every equality
   check passes; otherwise retain a clearly failed staging artifact or remove
   only the exact empty staging leaf.
5. **[proposed] Materialize the external ten-field identity** as the release
   sibling and revalidate it from the exact published source root. Do not copy
   the dated read-only observations into a record without live equality.
6. **[proposed] Run component seed `--preflight-only`.** It must perform no
   model or official score and must leave zero managed container/network
   residue.
7. **[proposed] If the user separately resumes the model experiment,** start
   the durable coordinator, remote health timer, Mac watchdog, `caffeinate`,
   and additive exact-ID mirror together; never use mirror deletion.
8. **[proposed] Run one fresh 16-task shared seed.** Only after its complete
   identity-bound report exists may the R/E/EC corpora be built. The old A5
   corpus is invalid for this step.
9. **[proposed] Run R/E/EC discovery `--preflight-only`** against those formal
   fresh-seed corpora, then launch the three matched Evolver samples only if all
   equality, firewall, lifecycle, and cost gates pass. Evaluate every admitted
   `ACT`, never a selected winner.
10. **[proposed] Preserve all negative, `ABSTAIN`, timeout, missing, rejected,
    and superseded artifacts.** Do not add A6-F, repetitions, tasks, or proposal
    portfolios after reading core outcomes without the separately frozen
    trigger and authorization.

## QuantCode-Bench boundary

**[source-audited]** The independent
[QuantCode-Bench generalization screen](2026-08-09-quantcodebench-generalization-screen.md)
is **CONDITIONAL GO** only for a separately named, hardened, sealed near-domain
seed-versus-final external transfer protocol after QFBench selection ends and
the final harness is frozen. It is **NO-GO** as the sole blind or
contamination-free generalization benchmark and **NO-GO** with the unmodified
upstream evaluator as publication-grade authority. No QuantCode content or
outcome may reach the Evolver or affect QFBench candidate selection. A separate
hosted/hidden benchmark remains necessary for a blind-generalization claim.

**[not run]** This checkpoint did not run QuantCode-Bench, download its market
data, expose any QuantCode task to the Evolver, or change the A6 protocol based
on its screen.
