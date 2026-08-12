# QFBench A6 Standing Operational Authorization

Date: 2026-08-10  
Status: accepted; supersedes per-replacement confirmation requirements within the frozen scope

## Decision

The user grants standing operational authority to continue the already-frozen
QFBench A6 core on the trusted `bc-server` without requesting a new confirmation
for every exact replacement artifact. This authority covers content-addressed
replacements that have passed two-agent independent review and remain within all
of the following fixed boundaries:

- the frozen 16-task A6 core and its R/E/EC attribution protocol;
- the existing `bc-server` host and trusted-coordinator data category;
- the existing model/provider account and fail-closed provider route;
- the existing worker-public/verifier-trusted evaluator-isolation firewall;
- the existing stage order, identity freeze, request ledger, replay policy, and
  scientific ACT/ABSTAIN triggers; and
- the bounded four-layer watchdog: user systemd coordinator, 30-second sanitized
  health timer, 60-second fingerprinted Mac repair monitor, persistent
  `caffeinate`, and additive no-delete evidence mirror.

Within those boundaries, no additional per-item authorization is required for a
fresh replacement seed ID; exact R/E/EC IDs after their scientific gate; exact
systemd unit bytes; exact LaunchAgent plist/code bytes; a corrected additive
mirror and registry; or another content-addressed source/runtime replacement in
the same already-authorized sensitive-data category. The acting agent must still
record and report the exact IDs, paths, hashes, model/provider, task count,
request/token/cost accounting, results, cleanup state, and any negative or
superseded evidence.

This authority immediately removes the prior requirement for a new direct
exact-hash confirmation before installing and preflighting the independently
audited fresh-r3 recovery package. It does not turn `R3 AUTH PACKAGE READY` into
a launch PASS. The live release and ten-field identity must be recomputed, the
fresh same-final-ID preflight must prove zero calls and zero residue, the exact
units must remain disabled/inactive, and a separate independent auditor must
return `FRESH-SEED r3 PASS` before monitor/mirror/timer/coordinator activation.

## Gates that remain mandatory

Standing authority changes authorization cadence only. It does not waive:

1. two-agent independent review of every content-addressed replacement;
2. exact live equality for source tree, protocol, rootless config, image set,
   public/trusted role manifests, scheduler, provider route, and materialized
   launch identity;
3. same-final-ID no-model preflight before a fresh seed or discovery start;
4. worker/public and verifier/trusted role isolation, including no coordinator
   source, trusted criteria, credentials, gold, official tests, or verifier
   inputs exposed to worker/evolver;
5. complete provider request uniqueness, accepted-state, token, and cost
   accounting, with unknown or unsealed use reported as unknown rather than 0;
6. the four watchdog layers starting with the coordinator, active-run mirror
   advancement, no `--delete`, and sensitive/input exclusions;
7. bounded restart semantics: systemd four starts per 15 minutes and Mac repair
   at most three requests per fingerprint at least 15 minutes apart, only after
   live same-fingerprint revalidation;
8. fail-closed shutdown order: unload repair monitor, disable/stop health timer,
   stop coordinator, exact-ID reaper and zero-residue audit, then final mirror
   advancement and unload; and
9. additive dated evidence and ledger maintenance without rewriting or pooling
   interrupted, diagnostic, or superseded results.

Fresh seed completion is still only the prerequisite for building formal R/E/EC
evidence. Discovery remains blocked until the seed is complete and clean, the
formal corpus is built, the three-arm byte-difference and provenance audit
passes, each exact discovery ID passes its own same-ID preflight and independent
launch gate, and all evaluator/firewall/watchdog checks remain live. Candidate
evaluation remains arm-local and requires explicit protocol ACT. A6-F and later
mutation-amplitude/throughput stages remain outside standing operational scope
unless their already-frozen scientific trigger fires; a change to that scope
requires new user direction.

## Changes that still require asking the user

New confirmation is required before any change to:

- the remote host or trust boundary;
- the category of private, trusted, credential, gold, official-test, or other
  sensitive data transferred or exposed;
- the model provider, provider account, credential source, or billing account;
- the systemd or Mac repair restart cap, interval, or automatic-repair category;
- destructive cleanup, deletion, overwrite of preserved evidence, or another
  materially irreversible action; or
- the scientific scope, including task panel, experimental arms, evaluator,
  feedback treatment, model comparison, A6-F admission, mutation stage, or claim
  boundary.

If an identity, isolation, mirror, request-accounting, replay, watchdog, or
lifecycle gate fails, the run must still stop fail closed. Operational standing
authority is not permission to work around a failed gate.

## Relationship to earlier records

This decision supersedes only statements in the 2026-08-09 remote-execution
authorization that demanded a new direct user message for each new exact A6
replacement. It preserves the full r1/r2 incident histories, the r2 no-resume
decision, the fresh-r3 requirement, every exact audit result, and all scientific
and evaluator-isolation constraints in those earlier records.

## Independent live fresh-r3 gate

Later on 2026-08-10, an independent read-only audit returned
**`FRESH-SEED r3 PASS`**, limited to the fresh seed
`qfbench-a6-seed-evidence-flash-20260809-r3`. The live evidence bundle is
`output/qfbench-supervisor/a6-ad26fe36d9539273-r3/r3-live-preflight-evidence.json`,
6,639 bytes, SHA-256
`8275c4e219675c233cbd9e1b2f744db6df5c08896951d20c07af46483e0d4138`.
The auditor independently recomputed or byte-checked the 261-member release tree
`ad26fe36d95392731022c325451504476b99a97fbe820f8c7451c396c9991d23`,
the ten-field identity record
`4679b6fca2d5eba7e328f86ea2eec3b553a6191437488e65aa63a3a65b86da43`,
and materialized launch identity
`3b3dee2cfda952c0528efe66ac9bee4ee7ac5804bd3a8dd533e7fa843ce68376`.
The exact systemd seed/health/timer hashes were respectively
`f9776464a973387f8b39f23c00612a3bd91c466be382d6357da86fbb310367b8`,
`0ca6747650c03e9c902ae1cfead0acd231912c1a98243451d36f3d74716b44b5`,
and `9128139fec4448a8401053e7e02f29da1f025aa35604b2390fc8027a63e1a352`;
they were mode `0600`, loaded, disabled, inactive, and had no prior journaled
start or restart. The exact mirror and monitor plists had hashes
`f75209db8ee9f34ace51b250f9e75802e76c6cf0dce264cc0351643c923dd13a`
and `5bac64e709cd90960608d6d6da8adba47b5785d48998dbd1d93432df04994d83`,
mode `0600`, and neither label was loaded.

The same-final-ID preflight and progress JSON were byte-identical and bound the
frozen 16 tasks in their exact order, `deepseek/deepseek-v4-flash-0731` through
required provider `deepseek`, scheduler epoch `repetitions-01-through-05`, and
worker/verifier concurrency `12/3`. Identity validation occurred before the
evaluator surface. At the gate there were zero model requests, attempts, scores,
workers, verifiers, proxy/cost/token/lifecycle records, coordinator journal
entries, r3 or residual r2 containers/networks/leases, and A6 ledger entries.
The local experiment ledger still contained only its 14 historical runs. The
tar extractor reported only that it ignored a macOS provenance xattr; all
authorized extracted bytes and bound hashes matched, so this is a transport
observation rather than an identity exception.

Launch permission is conditional on one bounded activation window. Load the
exact additive mirror and repair monitor, and verify that the mirror completes
the actual ordered 28-ID registry traversal and materializes/advances the local
r3 preflight destination before starting the exact health timer and seed
coordinator. Recheck the loaded plist/unit hashes and live identities, then
audit the first paid window for pinned route/no fallback, unique and complete
request/cost/token accounting, worker-public/verifier-trusted isolation,
sanitized fresh health, and exact resource/lifecycle matching. Any failure must
use the frozen monitor-first stop order: unload the repair monitor, disable and
stop the health timer, stop the coordinator, run the exact-ID reaper and prove
zero residue, perform final mirror advancement, and only then unload the
mirror. This PASS does not authorize discovery: R/E/EC remain blocked until the
fresh seed completes cleanly, the formal corpus and three-arm byte/provenance
audit pass, and each exact discovery run passes its own preflight and independent
launch gate.

## Fresh-r3 terminal outcome supersedes corpus admission

The prelaunch `FRESH-SEED r3 PASS` above remains an accurate no-model launch
gate, but the terminal run did not pass the separate post-seed corpus gate.
`localvol-barrier` reached the official agent timeout, produced an explicit
timeout/reward-zero score, and left only
`proxy-audit.quarantined.json` (SHA-256
`090cf49413c7dfc8e7b3f04ebd33c6a06f0fe4fdb9eb23025bca1824f3ed0565`)
with reason `audit_download_or_validation_failed`; it has no canonical proxy
ledger or trace digest. The other 15 ledgers contain 146 completed HTTP-200
requests with unique request and provider IDs, known cost USD `0.1195296368`,
and 2,060,117 known tokens. The canonical fixed-checkpoint auditor marks those
values as lower bounds, `cost_complete = false`, and one unreconciled attempt.

Although the systemd run ended successfully with 16 score records, no restart,
all exact lifecycles cleaned, zero resource residue, and a complete final
mirror, the frozen missing-cost/token stop rule applies before evidence
construction. Outcome: **`R3 SEED FAIL/BLOCKED` for A6 corpus admission and
discovery**. Preserve all r3 scores as interrupted/quarantined engineering
evidence; do not build an r3 discovery corpus, resume the ID, rerun only the
timeout task, or describe the known request/cost/token values as totals.

The fresh-r4 advancement gate is defined in the
[r3 seed quarantine report](../reports/2026-08-10-qfbench-a6-r3-seed-quarantine.md).
It requires durable per-attempt accounting across timeout/finalizer failure,
canonical lower-bound/completeness fields in the component report, builder
rejection of every incomplete or quarantined audit, deterministic regressions,
a new content-addressed release and ten-field identity, and a fresh 16-task r4
seed with its own prelaunch and post-seed independent gates. Standing authority
continues to apply because this recovery does not change host, data category,
provider account, restart limits, evaluator boundary, panel, or scientific
scope.
