# QFBench A6 r7 discovery executor-coupling incident

> Status: measured three-arm infrastructure failure; source-audited zero model
> provider calls; canonical proxy ledgers incomplete and quarantined; R/E/EC r7
> discovery and candidate IDs frozen.

## Conclusion

The fresh r7 seed and its byte-matched R/E/EC evidence corpus remain valid
engineering prerequisites, but the r7 proposal launch produced no discovery
result. All three arms failed at the same first `before_model` boundary because
the terminal-reserve middleware looked for a public `AgentState.executor` that
does not exist in the pinned NexAU runtime. The one-shot provider guard then did
exactly what it was intended to do: it rejected the model call before the base
provider function could run.

Accordingly, the source-audited accepted-request, provider-call, token, and cost
counts are exactly zero. This must not be confused with a complete canonical
cost ledger: every arm has a schema-v2 `accounting_complete=false` quarantine
marker and a zero-byte unsealed prefix, so the canonical proxy accounting fields
remain incomplete/null. The three runs are scientific-invalid infrastructure
failures, not zero-quality proposals, not ABSTAINs, and not evidence about the
relative A6-R/E/EC mechanisms.

The machine-readable record is
[r7-discovery-executor-coupling-incident.json](../../output/qfbench-supervisor/a6-7a57e32dcfa60aea-r7/r7-discovery-executor-coupling-incident.json).

## Frozen identities and prerequisites

- Release tree: `7a57e32dcfa60aeacc7acc369dbb311e852d2ed49518f423e51fdd25afe7db3d`
- Release manifest: `bc9eb959b39df3926ec12e1f6e767011be9c4bf52e2abf2ab5db22c5a040e0a5`
- External identity record: `dad76e90a69d12c71cf0fa7495d1f14a81023a269d5d283f447b75891dc2fa82`
- Materialized launch identity: `9b8a01a5edd799c9210b8708b6ccb11fa4c226d77b430bb8fd79b8e7aa1be92e`
- Terminal middleware presented to each Evolver:
  `8e45041ca02dbdcb2594b772e842fc4b96546049d1e33a595d4bb48d22f6a553`
- Formal corpus audit:
  `fe2e30a16be48796911e92f92ee9544b238a21fd5e688c577074b58aefb6ba29`
- NexAU commit pinned by each attempt:
  `35ee1861546db3cb280a6e17e38a74060d7c96c3`

The r7 seed itself completed 16/16 tasks with 199 unique completed pinned-Flash
requests, 5,441,229 tokens, USD `0.1840006784`, task mean `0.625`, domain macro
`0.6805555556`, canonical complete accounting, and zero residue. Those facts do
not admit or rescue the later broken proposal runs.

## Measured incident sequence

The three proposal-only services entered their first invocation together at
approximately 09:07:43 Singapore time. The initial PIDs were 659322 (R), 659323
(E), and 659324 (EC). At 09:08:11–12 each Evolver emitted the same causal chain:

1. `before_model` raised `executor token counter is unavailable`.
2. NexAU's middleware manager caught and logged the exception, returning the
   original messages.
3. `wrap_model_call` found no successful one-shot guard and raised `model call
   has no successful before-model audit guard` before `call_next`/the base
   provider call.
4. Proxy finalization found no persisted request record and wrote a quarantine
   marker rather than a canonical ledger.

Systemd scheduled one bounded restart at 09:08:42. The monitor was unloaded
first, all three health timers were disabled/stopped, and the second invocations
were terminated at 09:08:53 before they created another lifecycle or request
artifact. Final service state is PID 0, failed/signal 15, `NRestarts=1` for all
three.

The common marker is 243 bytes with SHA-256
`f382d82a5c867fb9a7dbe18cf76378df6203568c353b6ee06caa998ae3f07ac5`.
It declares `accounting_complete=false`, reason
`audit_download_or_validation_failed`, and `unsealed_record_count=0`. The
unsealed file is exactly zero bytes with the SHA-256 of empty bytes,
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
No canonical proxy audit, terminal audit, proposal report, pilot report,
prediction, candidate diff, or score exists for any arm.

All six first-invocation sandbox lifecycles and three networks are exact-ID
clean. Dry reaping found no pending or mismatched resources. The final additive
mirror completed R, E, and EC at 01:15:00, 01:15:03, and 01:15:06 UTC with
zero mirror stderr, after which the mirror was unloaded. Final managed
container, network, and lease counts are zero.

## Source-audited root cause

Pinned NexAU's real `AgentState.__init__` stores the executor as
`self._executor`; it provides no public `.executor` property. The r7 terminal
middleware's tool lookup and token counting used
`getattr(agent_state, "executor", None)`. The unit-test `_State`, however,
invented a public `.executor` attribute. Those tests therefore proved the
middleware logic against a shape that the deployed runtime never supplies.

The generic `E2B SDK not installed` text also appears in the combined sandbox
failure string, but it is not the causal failure: the traceback reaches the
terminal one-shot guard, and no provider or E2B path is invoked. Provider route,
account, firewall, evidence authorization, and container naming identities did
not drift.

## Accepted offline repair

The independently reviewed patch binds the middleware to the exact private
`AgentState._executor` object, requires that same object across `before_model`
and `wrap_model_call`, and validates its callable token counter and structured
tool payload. It does not construct a fallback counter, approximate tokens, or
weaken the one-shot guard.

The regression now exercises the real path:

- exact `AgentConfig.from_yaml` profile;
- real `Agent` and its real executor;
- real `AgentState` with no public `.executor`;
- the actual middleware manager's `run_before_model` then `wrap_model_call`;
- identical executor, token-counter, and tool-payload objects;
- exactly one fake provider invocation after a valid guard;
- zero provider invocations when the counter is absent, the executor identity
  changes, or `before_model` fails.

The patch received independent `TERMINAL PATCH PASS`. This is source and test
evidence only; no repaired remote or model run has occurred.

## Recovery boundary

R7 discovery and candidate IDs are permanently frozen and must not be resumed.
The r7 seed/corpus cannot be relabeled under repaired source identity. Recovery
requires a deterministic content-addressed r8 release, new external ten-field
identity, fresh seven-ID operations bundle, fresh 16-task seed, fresh formal
R/E/EC corpora, same-ID zero-call preflights, and the existing independent
deploy/seed/corpus/per-arm gates.

Candidate evaluation, A6-F, evaluator feedback, mutation, and the user's later
proposal to increase tasks/repetitions remain separately gated and not run.
More tasks may improve cross-task power, but they do not repair an invalid
provider boundary or estimate model-run variance by themselves.
