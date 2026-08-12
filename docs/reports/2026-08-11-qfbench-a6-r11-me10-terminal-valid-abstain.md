# QFBench A6 R11 ME10 terminal-valid ABSTAIN

Date: 2026-08-11  
Run ID: `qfbench-a6-discovery-e-flash-high-20260811-r11-me10`  
Status: terminal-valid calibrated `ABSTAIN`; nonformal engineering result

## Outcome

ME10 completed the bounded multi-epoch mechanism with a real, evidence-bound,
model-produced `ABSTAIN` decision. The final checkpoint was ready, the decision
was persisted through the simplified adapter and immutable guarded validator,
the candidate remained locked and byte-identical, and the runner accepted the
terminal closure. This closes ME9's case-sensitive hypothesis-ID schema bug and
is the first result in this sequence to exercise the valid terminal decision
path rather than merely reach a checkpoint.

This is not the complete A6 engineering-feasibility success bar. ME10 produced
no `ACT`, no non-empty full-harness mutation, no candidate validation or
admission, and no candidate-panel evaluation. It therefore provides no
candidate-benefit, causal, transfer, or statistical claim. The measured result
is a calibrated fail-closed abstention under insufficient causal evidence.

## Frozen mechanism identity

The paid run used the reviewed ME10 package without any post-launch mechanism
byte changes:

- readiness SHA-256:
  `a6fbc59c685f4f64b4555ba30b4f25248f12beed9c3c53bc935fc37112c0f274`
- package SHA-256:
  `7c0ad4a4e1cd96c9e973088397e58cc40dc8dc3d79b6a4ff00288091e4efa31c`
- runner SHA-256:
  `c724e32d7521e1006f7c5e94c262720e398b71f6642374968a16c1c43195d3da`
- overlay tree SHA-256:
  `b2896111229583bbdc6e48227055464626bb45f7c3e402118b2b68760a43116d`
- systemd unit SHA-256:
  `8cb932e41c50296f4a934c8ecf2c4aea599b8d99e3321af5a4fc750536e48f35`

## Exact provider accounting

The append-only proxy ledger contains 22 unique logical, request, and provider
request identities. All 22 rows completed HTTP 200 on exact
`deepseek/deepseek-v4-flash-0731`, all at retry index zero, with null failure
class and no fallback. Accepted usage was 1,032,205 input tokens, 69,335 output
tokens, 1,101,540 total tokens, and USD `0.0718470312`.

The ledger interval was `2026-08-11T06:47:28.699938+00:00` through
`2026-08-11T06:57:42.267141+00:00`. The proxy audit is 13,740 bytes with
SHA-256
`762ca3c29ac9a880e2e1017327ff7797d3cec6fa8366b2874d6aa2bff62dfb97`.
The terminal audit reported 614.844755 seconds, below the 1,800-second wall
bound. The exact wire-phase distribution was 16 exploration calls, two
checkpoint-repair calls, three decision calls, and one final call, totaling 22.
The terminal audit's reset-derived phase counter reported exploration as ten;
that field is non-lifetime state and is not used as the wire-call distribution.

## Measured discovery and terminal state

The run traversed three exploration epochs, numbered 0, 1, and 2, with two
rollover transitions, three real schema-1 probes, and three probe-bound
checkpoints. The latest checkpoint was reload-verified and ready for decision
under branch `ABSTAIN_DERIVED_V1`; its SHA-256 is
`6f2addb02b9cce44173be4bf41192a5c5347d3587dab9d35d2bbd1bae137ad6c`.
The three probe records were:

1. `trace-activity-target-vs-protection`, result SHA-256
   `e55b31151d975f8132172c855b2bcad34b06ab60229756c8d86e39fa2845be4d`;
2. `target-divergence-phase-profile`, result SHA-256
   `8d86d55a241f4c8b0294f96e2882c23bd3c79e508e1ca17ddc0f15c1795d4caf`;
3. `path-mismatch-recurrence-coverage`, result SHA-256
   `73476c889156e256ddf05390d008709afcde57cbfad01efc9099d6dca8743777`.

The final decision is `ABSTAIN`, with decision SHA-256
`6a29a5b88c11d6621d03fc36377fe6201d315a8a8c36bc5adf4527f6919f2e00`.
The immutable decision-state file SHA-256 is
`d0e6a3003d25c3982ce0e31e1e02bd0574e1056db10d60b293f5eab90334e230`,
and `unlocked=false`. The terminal audit ended at event sequence 139, whose
kind is `after_agent`, with `phase=complete`, `complete=true`, and the same
`ABSTAIN` decision. The audit is 88,673 bytes with SHA-256
`eb96d54db6f0ca4dfdda353a7953a9dbca5ece8f0f2398d4f7dcd0371d7839b6`.

Two decision-validation errors occurred and were repaired within the bounded
decision path before final closure. The first required any claimed matched
success to have accessed public-evaluation plus task evidence and a verified
reward-1 protection role. The second required each hypothesis to include
either a success counterfactual or `insufficient_contrast=true`. The final
state has no current exact error.

The last compact payload was 65,288 bytes against a 131,072-byte cap, leaving
65,784 bytes of headroom. Its SHA-256 is
`2b20350cb9af0e29932d9b1620be52a256daaae00472f9e441c9969e7618cd5e`.
This is live evidence that ME9's bounded projection and ME10's terminal path
coexisted without the ME8B compact-overflow failure.

## Exact ABSTAIN rationale

The discovered failure type was `early_input_inventory_path_mismatch`. The
probe observed an early `SHELL_EXECUTE_ERROR` against a nonexistent
`/app/<file>`, followed by recovery through `ls` or `find` to `/app/data`, in
three of five readable failed target traces:
`zero-coupon-bootstrapping`, `earnings-surprise-calculator`, and
`corporate-action-adjustment`. The same marker appeared in zero of the two
readable reward-1 protection traces,
`credit-spread-decomposition` and `brinson-sector-attribution`.

That contrast was not sufficient for an intervention. In
`corporate-action-adjustment`, the agent recovered, computed, and self-verified
its output, yet still failed four of seven verifier tests. Two other failed
targets, `swap-curve-bootstrap-ois` and
`13f-amendment-aware-crowding`, lacked the early path-mismatch marker entirely.
The failure population was therefore heterogeneous, and the observed path fix
was at most a plausible process improvement rather than a reward-causal repair.

The run also had not accessed public-evaluation plus task evidence for two
declared target members and performed no same-task schema-2
clause/artifact/trace discriminator. Consequently the exact ACT prerequisites
were unmet. The honest bounded decision was to abstain and keep writes locked,
not to infer a candidate mutation from a recurring but non-discriminating
phenotype. The source prediction containing this rationale is 10,630 bytes
with SHA-256
`b8312b24c0747fd59f4be3843dbf8d6a8a234c875c217434a9d098c8130331cd`.

## Candidate, admission, and claim boundary

The initial and final candidate tree SHA-256 were both
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`.
The diff was zero bytes; write count, candidate-validation count, and candidate
evaluation count were all zero. Admission is not applicable because the
Evolver recorded `ABSTAIN` and the immutable write lock remained closed.

Accordingly, ME10 is positive engineering evidence for the following narrow
claims only: the case-capable hypothesis grammar works in the real tool path;
the multi-epoch evidence/checkpoint loop can reach a ready checkpoint; the
model can repair bounded validation feedback; a genuine model-produced
ABSTAIN can be persisted through the immutable validator; and the runner can
close truthfully with exact accounting and locked writes.

ME10 does not establish that A6 can yet produce a valid ACT, a non-empty
full-harness change, successful validation/admission, or a candidate-panel
benefit. It must not be reported as a successful evolution, a causal discovery,
or a formal benchmark result.

## Closure and source artifacts

The service exited zero with result `success`, `NRestarts=0`, and no automatic
restart. The service is inactive; the health timer is disabled and inactive.
Run-scoped container and network/lease residue counts are zero. The local
monitor and mirror labels both returned `launchctl` code 113 after unloading,
and the final additive mirror sync completed at `2026-08-11T07:36:14Z`.

Selected frozen source hashes are:

- model boundary:
  `b62dfbd4acfbba02d360c6d9144ce8a0fb814e80b9d44d0a4e8c2df6843d167a`
- request registry:
  `18211a1ed9368602fb24e27164d79217282a6c997aba7ca27ba7c4c67b20ea11`
- raw trace:
  `1a5cde3cfad40f17440d4b5ad1dbebd5a7b79dccd393a770b9586bf8a837aae6`
- summary:
  `17bb0e191a751250db657af942caf2fdedfe100da20a6a0f45768dd04b0523ba`
- result:
  `e96f81d512eb17771752e67efa8b25d14e62fcdc7c2a8cbe9db59f600493b50e`
- pilot report:
  `70bdb0e94bb2e8b3b0f3e66b43b28deaa2afd0851b6814e784a2702a83813e87`
- proposal report:
  `22438577308fb701cf1ca6a86c69ae8e88fc0924ed753d442d826503baa7afcd`

Machine-readable record:
`output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me10-continuation/r11-me10-engineering-terminal-abstain-20260811.json`.
