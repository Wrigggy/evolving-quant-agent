# QuantCodeEval five-round canary result

> Date: 2026-08-12
>
> Status: measured engineering result; supersedes the launch-readiness state in
> `2026-08-12-quantcodeeval-canary-and-property-guided-search.md`

## Decision

Accept the QuantCodeEval T16/T24 adapter, isolated canary runtime, shell-only
H0 record, and five-round Property-Guided Bidirectional Harness Search (PGBHS)
ledger as completed **engineering evidence**.

Do not claim a QuantCodeEval score gain.  Every candidate was rolled back and
the final official incumbent remains H0 with reward vector `[1, 0]`.  The fifth
mutation did, however, repair the observed resource-termination phenotype: it
converted a T24 run that exhausted 59 requests without an artifact into an
early importable checkpoint and a complete 15/17 checker execution, while
preserving T16 at 18/18.  This is evidence that the failure-class-to-component
evolution mechanism can produce a legal, activated, useful intervention; it is
not yet evidence that it improves benchmark reward or generalizes.

The next experiment should promote early artifact checkpointing from a prompt
instruction to deterministic middleware and test it against prompt-only and
shell-only controls over independent model seeds.  Quant correctness should be
handled separately through public-clause-to-artifact self-checks rather than by
adding more global prose.

## Frozen identities

- Official QuantCodeEval source commit:
  `9bdacc4898aeec08813764290b12d356e0a011d1`.
- Public-role manifest SHA-256:
  `d3a2b4c2e6869e12788a0e2d31ec354a39f66f742ce36d8ad05a590175e1a2d2`.
- Trusted-role manifest SHA-256:
  `1ebe7cbfc9e1d8a878142b88c7881849ad6e724c8389dca60792aee5e1661b0f`.
- Worker image:
  `sha256:20bf2b69268d375c8b3df0998bfb26fc1cdd8fd10ae672da20081d8226134bb6`.
- Verifier image:
  `sha256:f2512a05e926a0dc86d8b2c4fa2a49b72d48ebe24831ba14ab3a5570b9b20c26`.
- Proxy image:
  `sha256:950280b19b6215c9a48ae81d5d9fdc6b69fa2192706ff4920efbb0981e33beae`.
- Model and route: `deepseek/deepseek-v4-flash-0731`, provider
  `DeepSeek`, fallbacks disabled, worker/verifier concurrency `1/1`.
- H0 worker digest:
  `4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`.
- Fixed panel identity:
  `60a3a61ffcb6c58f842cd7b8764a1310ffe98a4a540baf2c6e7c0358cc72d904`.
- H0 evaluation identity:
  `d42b12416c46e46311cc5076409f7fdf83a55c4fcb25c5990aa7bd4f42878f06`.
- Five-round result identity:
  `d79597a68eecc8c2a70a9d2968aaf86db82083036c70cd6011fd059364a3d5dd`.
- Published release identity:
  `4d3813bfc58afb48ad0eb25f9e028a8529f5d4159bd2803cd4fe175f744c5499`;
  release manifest SHA-256
  `658b79356179d09cdda0770c9f6cedb17a61e8c0ed8b728f0c9811ef10a69199`.

## Runtime, parity, and firewall result

The measured no-model audit is retained at remote artifact
`quantcodeeval/audits/parity-577bd3f1-v8/RESULT.json`.  It established:

- T16 golden parity: 18/18 properties pass;
- T24 golden parity: 17/17 properties pass;
- missing and deliberately wrong strategies receive official reward zero;
- malicious candidates attempting to inspect the trusted checker/oracle
  surface receive zero and cannot see trusted contents;
- model workers receive only the public role and write only
  `/app/output/strategy.py`;
- the strategy executes in a separate sandbox/RPC process without the trusted
  `/tests` mount, while the no-network verifier retains the checker and golden
  dependencies;
- completed runs leave zero managed Docker containers.

Across the retained QuantCodeEval run corpus, all 60 unique lifecycle records
have `cleaned_up=true`; final inspection found zero running managed containers
and zero `qea-*` Docker networks.

The verifier is a measured engineering-canary image, not a formal full-lock
reproduction.  It pins Python 3.11.15 and the checker-relevant NumPy/Pandas
versions and passed golden parity.  A later formal release should rebuild from
the complete official lock on a host with sufficient image storage rather than
silently treating this canary derivation as equivalent.

## H0 shell-only baseline

Run `qce-h0-shell-only-20260812-r2` used the immutable minimal worker: one
one-line system prompt, one `run_shell_command` tool description, its NexAU
configuration, no skill, middleware, memory, finance tool, or task-specific
code.  It is therefore an operational shell-only baseline.

| Task | Official reward | Type A | Type B |
|---|---:|---:|---:|
| T16 | 1 | 6/6 | 12/12 |
| T24 | 0 | 6/7 | 9/10 |

H0 used 34 completed requests, 537,527 tokens, and exact reconciled provider
cost `$0.0332853304`.  The five-round search references this evaluation with
`resampled=false`; it never reran H0 as the first round of a later iteration.
The superseded H0-r1 negative remains preserved and was not rewritten.

## Five-round measured ledger

All five rounds used the same fixed T16/T24 panel.  Every ACT changed only
`systemprompt.md`, produced a non-empty content-addressed diff, passed
admission, and received a complete panel record.  Artifact-zero attempts were
recovered without model resampling and represented as all-property SKIP, not as
invented checker failures.

| Iteration | Routed failure / candidate | T16 | T24 | Requests | Tokens | Exact cost | Selection |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | quant-definition guard, `4ee8b932…707e` | 18/18 | artifact zero, 17 SKIP | 68 | 2,329,367 | `$0.0414607144` | rollback: skips increased |
| 2 | broad resource guard, `99225698…4900` | 3/18 | 13/17 | 16 | 209,660 | `$0.0183973496` | rollback: T16 regression |
| 3 | unit plus early-artifact prose, `09e1189c…ef0` | 18/18 | artifact zero, 17 SKIP | 17 | 220,742 | `$0.0199430728` | rollback: skips increased |
| 4 | one-sentence percent/decimal rule, `cc78b8d9…788f` | 18/18 | artifact zero after 59 T24 requests | 76 | 3,055,978 | `$0.0518120960` | rollback: skips increased |
| 5 | minimal checkpoint plus unit rule, `9159713d…250f` | 18/18 | 15/17 | 23 | 336,758 | `$0.0216726832` | rollback: no predicted family gain over H0 |

Search-only accounting is 200 completed requests, 5,776,677 input tokens,
375,828 output tokens, 6,152,505 total tokens, and exact cost
`$0.1532859160`.  H0 accounting is separate and must not be counted as a fresh
search sample.  Iteration evaluation identities, respectively, are:

1. `056e0bcfa2c0aef428fdf07073b20ba0e8cd42c3e5f86cf2ec244130e01a4247`;
2. `d1041aa28995faaac611f8819204198f408b683a6c0216f621ca07a0e7b13b0c`;
3. `886f19178334a2f916ab76072f65bf1ca0d15f242cd26f52328185462e019798`;
4. `fdb03b08413342c6c99cc5d72a1ba9ed606190a47397b194e0cbbad0d9fe23f6`;
5. `f9c729467a637f3a1842328f2fd4441c9d61d328ca8ced22665ed1d96ff22096`.

Iteration 2 has an explicit coordinator-source identity gap caused by the then
missing `_source_sha256` return.  Its route, requests, cost, artifacts, official
scores, and rollback are real and retained, but it must not be represented as
having the same complete source provenance as iterations 3-5.

## What worked and what did not

Measured mechanism progress relative to A6:

```text
public evidence -> competing hypotheses -> legal ACT
  -> non-empty harness diff -> admission -> fixed candidate panel
  -> prediction check -> rollback
```

This full path occurred in all five rounds.  The most useful intervention was
the fifth resource-termination mutation.  Relative to the immediately observed
fourth-round phenotype, T24 changed from 59 requests, no artifact, and 17 SKIP
to an early importable artifact, 15 checker passes, no skip/error, and ten T24
requests; total two-task panel requests fell from 76 to 23.  T16 remained
18/18.  Because these are distinct stochastic samples and there is no matched
seed repetition, this is mechanism-localization evidence rather than a formal
causal effect estimate.

The quant-definition mutations did not improve the H0 property vector.  T24
returned to exactly H0's 6/7 Type-A and 9/10 Type-B counts.  The official
incumbent and diagnostic search parent therefore both remain H0; the archive is
empty.  The experiment establishes an activated search-and-rollback mechanism,
not a benchmark-performance benefit.

## Complete evidence release

The content-addressed release contains seven independently rehashed surfaces:
source, public role, trusted role, measured images, no-model audit, complete H0,
and the complete run corpus including superseded negatives and all five
iterations.  It contains 1,255 files and 39,465,784 bytes.  Independent
validation reproduced the release identity, and a second publish reused the
existing release rather than overwriting it.

Remote path:

```text
/home/julius/qea/runtime/quantcodeeval/releases/published/
  4d3813bfc58afb48ad0eb25f9e028a8529f5d4159bd2803cd4fe175f744c5499/
```

## Next experimental direction

1. Implement deterministic early-checkpoint middleware that creates and
   continuously validates the artifact contract independently of model
   compliance.  Compare shell-only, prompt-checkpoint, and middleware arms over
   at least three preregistered model seeds.
2. Separate resource reliability from quant correctness.  Keep the checkpoint
   mechanism fixed, then add one executable public self-check at a time for
   units, lag/timing, and portfolio accounting.  Do not add another bundle of
   global prose.
3. Expand answer-free evidence from only aggregate A/B counts to a public
   criterion taxonomy derived from the instruction, with clause, artifact, and
   trace facts.  Hidden property IDs, expected values, checker messages, and
   golden code remain verifier-only.
4. Run a public-track sensitivity screen before choosing held-out tasks.  A
   benchmark-gain or transfer claim requires a frozen split, matched control,
   independent repetitions, and compute/cost fairness.
5. Keep finance-specific routing as the special point of PGBHS: artifact and
   resource failures should reach middleware; unit/estimation failures should
   reach numerical self-checks; timing and execution failures should reach
   dedicated causal and accounting validators.  A universal free-form search
   algorithm is not required for the next engineering milestone.
