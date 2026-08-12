# QFBench A6 fresh-r3 seed quarantine report

Date: 2026-08-10  
Status: measured; r3 is complete as an execution artifact but inadmissible as
the A6 shared seed corpus

## Conclusion

Run `qfbench-a6-seed-evidence-flash-20260809-r3` reached a terminal systemd
success state with 16 immutable score records, no restart, all exact lifecycles
cleaned, and zero remaining run-scoped containers, networks, or leases. It does
**not** pass the frozen post-seed evidence gate. `localvol-barrier` hit the
official 2,400-second agent timeout, was scored explicitly as timeout/reward
zero, and did not yield a canonical proxy ledger or raw trace. Its only request
accounting artifact is a quarantine marker with reason
`audit_download_or_validation_failed`.

The deployed canonical fixed-checkpoint cost auditor therefore reports:

- `attempt_count = 16`;
- `request_count = completed_request_count = 146` for the 15 sealed ledgers;
- 146 unique request identities and 146 unique provider request IDs, all HTTP
  200 on `deepseek/deepseek-v4-flash-0731` with no missing accounting inside
  those sealed ledgers;
- known input/output/total tokens `1,754,648 / 305,469 / 2,060,117`;
- known provider cost USD `0.1195296368`;
- `cost_complete = false`;
- `provider_cost_is_lower_bound = true`; and
- one unreconciled attempt, `localvol-barrier` attempt
  `e60417b4f74b5aed09e05070597fd9986460e9a4242c2af5b8c9e3cc4d82aee7`.

The known request, token, and cost values are lower bounds. The missing
localvol ledger means neither its accepted request identities nor its full
token/cost contribution can be reconstructed from the run directory. Network
traffic is not request accounting and must not be used to estimate or invent
the missing values.

## Execution and score evidence

The terminal report contains 16 task records. Nine rewards are one and seven
are zero, for task mean `0.5625`; the six-domain macro is
`0.513888888888889`. These are measured diagnostic artifacts, not an admissible
A6 result or a basis for discovery. The timeout is preserved as an explicit
zero rather than replaced or rerun. The other 15 attempts have canonical proxy
audits and trace digests. All 16 worker, proxy, and scoped-network lifecycle
sets are exact-ID cleaned; 15 verifier lifecycles are clean, with no verifier
created for the timed-out task. Final run-scoped container, network, and lease
inventories are zero. The coordinator ended inactive/dead with result success,
exit status zero, and `NRestarts=0`.

The final report, localvol quarantine marker, and localvol timeout score have
exact remote/local SHA-256 values
`3ac8e47ff70f4e1821a4982eae6dce590ff1c23e386aa19ee405b6d41f3d1e71`,
`090cf49413c7dfc8e7b3f04ebd33c6a06f0fe4fdb9eb23025bca1824f3ed0565`,
and `ae3c02c771e05d4a8739d6ed952538947901fb0e5fe2c9da8189d3897f8abe40`.

The additive mirror completed ordered 28-ID traversals during the run and
materialized the final r3 report, all 16 scores, 15 canonical proxy ledgers,
and the timeout quarantine marker locally. The bounded monitor did not restart
the run. A temporary sanitized `stalled` state while the long task was active
was observed and correctly not auto-repaired; liveness inspection showed the
worker computing until its official timeout, after which the canonical proxy
finalizer and cleanup completed.

Final shutdown followed the monitor-first order: the repair monitor was
unloaded, the timer disabled and stopped, the already-dead seed unit confirmed
inactive, an exact reaper dry run scanned 47 container and 16 network manifests
with no pending, failed, mismatched, or live inventory, the final mirror
completed at 2026-08-09T17:12:27Z, and the mirror was unloaded. Both LaunchAgent
labels are absent after closure.

## Report and builder gap

`scripts/run_qfbench_component_pilot.py::_cost_payload` enumerates only existing
`proxy-audit.jsonl` files. It does not enumerate terminal attempts or quarantine
markers. Consequently `pilot-report.json` says 146 completed requests,
`missing_cost_count = 0`, and `missing_token_count = 0` even though one entire
attempt is unreconciled. Those fields describe completeness only within the 15
downloaded ledgers; they are not completeness claims over the 16-attempt run.

`scripts/build_qfbench_a6_evidence.py` currently requires terminal status and
launch-identity equality but does not require a canonical complete cost audit.
It could therefore accept this quarantined seed. That is a fail-closed gap,
because the frozen manifest requires stop and quarantine before evidence
construction on missing cost or token records. No r3 A6 evidence corpus may be
built and no R/E/EC discovery may start.

## Fresh-r4 advancement gate

R3 remains immutable and must not resume. A fresh r4 seed may advance only
after all of the following are independently audited:

1. Proxy accounting is durably persisted per attempt as requests complete and
   remains recoverable when the worker times out or the finalizer fails. A
   sealed zero-request ledger is required when no request was accepted; absence
   of a ledger is not proof of zero.
2. The component report uses the canonical fixed-checkpoint audit semantics and
   records `cost_complete`, `provider_cost_is_lower_bound`, unreconciled attempt
   and request counts, and known values without calling a lower bound complete.
3. The A6 evidence builder rejects any missing/unsealed/quarantined attempt,
   incomplete canonical audit, lower-bound cost, missing token/cost, duplicate
   accepted request identity, or noncompleted request.
4. Deterministic regressions cover worker timeout plus proxy-finalizer failure,
   durable ledgers with zero and nonzero accepted requests, misleading
   aggregate-report prevention, and builder rejection of the exact r3-shaped
   quarantine.
5. A new content-addressed clean release, external ten-field identity, exact r4
   seed ID, same-ID zero-call preflight, exact units, bounded monitor, and
   corrected full-registry additive mirror pass independent byte and live
   audits. Standing operational authority applies because host, provider
   account, sensitive-data category, restart caps, evaluator boundary, panel,
   and scientific scope remain unchanged.
6. The fresh 16-task r4 seed finishes with a complete canonical request ledger,
   explicit timeout/missingness rather than invented evidence, complete
   token/cost accounting, valid verifier execution for every non-timeout task,
   zero lifecycle residue, final mirror advancement, and a new independent
   post-seed corpus-admission gate.

Discovery, candidates, A6-F, and mutation stages remain blocked until that r4
post-seed gate passes.
