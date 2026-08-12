# QFBench A6 R11 ME9 uppercase-ID schema negative

Date: 2026-08-11  
Run ID: `qfbench-a6-discovery-e-flash-high-20260811-r11-me9`  
Status: contained engineering negative; not a formal A6 result

## Outcome

ME9 fixed the ME8B compact-overflow and pre-wire guard failure in the live
path, but it did not complete the discovery mechanism. The run reached one
real probe and a reload-verified, decision-ready `ABSTAIN` checkpoint. Four
model-produced `decide_candidate` calls were then rejected by NexAU's
provider-facing JSON schema before the decision adapter or immutable guarded
validator executed. No decision, proposal, candidate write, validation,
admission, or candidate evaluation exists.

Treat ME9 as a nonformal engineering negative. It is positive evidence for the
bounded compact projection and ready-ABSTAIN checkpoint path, but it is not an
end-to-end terminal decision pass and provides no ACT or candidate-benefit
evidence.

## Exact accounting

The append-only proxy ledger contains 14 unique logical, request, and provider
identities. All 14 rows completed HTTP 200 on exact
`deepseek/deepseek-v4-flash-0731`, all at retry index zero, with null failure
class. Accepted usage was 341,345 input tokens, 31,096 output tokens, 372,441
total tokens, and USD `0.0315401464`.

The ledger interval was `2026-08-11T05:51:46.930584+00:00` through
`2026-08-11T05:56:31.967026+00:00`, or 285.036442 seconds. The terminal audit
reported 286.241142 seconds. Its phase accounting was six exploration calls,
four checkpoint-repair calls, and four decision calls.

The mirrored proxy ledger SHA-256 is
`3b9dfe1bc9c7f7cfa398f95764f795d60d46470073b99e8499fa48f801a93206`.

## Measured discovery state

The run recorded one schema-1 probe,
`fail-artifact-schema-vs-value`, comparing artifact profiles and traces for
`zero-coupon-bootstrapping` and `earnings-surprise-calculator`. Its result
SHA-256 is
`811fdf64597f88ecb87399d865051e23c96713f9b14fb7a5c633a99cce6bdabb`.

It then appended one `ABSTAIN_DERIVED_V1` checkpoint with SHA-256
`f294249b71ad66e8dfa8d849c2cfb780aa248deeb441dd0111f3f2e679470447`.
The checkpoint is reload-verified and `ready_for_decision=true`; both
`H1_artifact_shape_failure` and `H2_numeric_value_failure` remain open. Its
abstention is calibrated: the schema-1 probe did not distinguish an
artifact-shape failure from a numeric-value failure, and no candidate
intervention was justified.

ME9's compact repair worked in the live state. The final decision-phase compact
payload was 53,594 bytes against a 131,072-byte cap, leaving 77,478 bytes of
headroom. There was no compact exception or pre-model failure. This is a live
pass for the ME9 compact projection, not for the entire mechanism.

The terminal audit ended `phase=invalid`, `complete=false`, decision null, with
event 91 as the final `after_agent`. The candidate tree remained byte-identical
at `4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`;
writes and validation were never observed.

## Exact failure and causal diagnosis

The full sandbox command record preserves the actual NexAU validation errors.
The causal error was:

`'H2_numeric_value_failure' does not match '^[a-z][a-z0-9_-]{0,63}$'`

This occurred twice for `checkpoint_continue.next_hypothesis_ids` and four
times for
`decide_candidate.hypotheses_considered[*].hypothesis_id`. The generic probe
schema permits arbitrary hypothesis-expectation property names, and the
derived checkpoint faithfully persisted the model's case-sensitive
`H1_...`/`H2_...` universe. However, the later provider-facing tools required
those exact identifiers to begin with a lowercase letter. The model was
therefore required to echo a universe the Tool schema could not accept.

This is a schema-interface contradiction. The four ABSTAIN calls never entered
`tools.engineering_decision.decide_candidate`, and the immutable
`tools.guarded_workspace.decide_candidate` validator did not reject their
semantics because it was never called. The bounded decision budget could not
repair an identifier grammar that required changing checkpoint identity.

The durable validation log's suffix-bounded error messages obscured the leading
JSON Schema diagnostic; the complete error is preserved in
`evolutions/iteration-0001/command.json`, SHA-256
`0d390454a16bd7b7f1263891d6f9de726207eebcef3f6bdbcd53a79114770e19`.
ME10 should preserve the causal schema message directly in compact repair
feedback instead of only the argument tail.

## Containment

The primary service exited nonzero. One automatic restart was scheduled and
was rejected by the existing model-boundary marker before provider
construction. The service and health timer are now disabled and inactive;
run-scoped Docker resources are zero. The marker SHA-256 is
`e8ca5fc908b85dac7ff692989f86a13a68cee11f6e50261f54d612f04c668f1f`.
The exact-ID proxy network, proxy sandbox, and Evolver sandbox lifecycle hashes
are recorded in the machine JSON.

Freeze the ME9 ID and all mirrored/remote artifacts permanently. Do not resume
or reinterpret the ready checkpoint as a completed ABSTAIN decision.

## Proposed ME10, not yet run

The minimal successor should use one bounded case-capable grammar,
`^[A-Za-z][A-Za-z0-9_-]{0,63}$`, across probe expectation IDs before
checkpoint persistence and every exact echo field in CONTINUE, ACT, and the
decision adapter. Matching remains case-sensitive; no lowercasing,
normalization, inference, or autofill is allowed. Unknown, missing, extra,
overlong, or unsafe IDs must fail before a checkpoint becomes ready.

ME10 must replay the exact ME9 uppercase checkpoint and run its real
materialized `decide_candidate` Tool through NexAU to an immutable ABSTAIN
state, exactly bound to the checkpoint, probe, evidence, abstain reason, and
unchanged candidate hash. ACT prerequisites and write locks remain unchanged.
The ME9 compact projection, 131,072-byte cap, 48-call global budget,
1,800-second wall bound, route, isolation, and no-synthetic-decision policy also
remain unchanged.

Finally, an incomplete terminal failure should use a distinct nonzero local
exit that systemd does not automatically restart. It must still produce no
proposal or success report. This avoids a predictable marker-blocked restart
loop without weakening the durable paid-boundary marker.

Machine-readable record:
`output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me9-continuation/r11-me9-engineering-uppercase-id-schema-negative-20260811.json`.
