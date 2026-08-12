# QFBench A6 R6 Discovery Context-Exhaustion Incident

> Status: measured three-arm proposal failure; A6-R/E/EC r6 discovery IDs and
> candidate IDs frozen. The terminal-reserve remediation is implemented and
> independently source-audited offline, but has not been deployed or exercised
> against a model.

## Outcome first

The fresh r6 seed and its byte-matched R/E/EC evidence corpus remain valid
engineering prerequisites, but the r6 discovery launch produced no valid
discovery decision. All three Evolvers continued reading evidence after NexAU's
soft remaining-token warning, crossed the configured 200,000-token context
limit, and were hard-stopped before they emitted the required terminal JSON.
The common parse error was therefore downstream of context exhaustion; it is
not evidence that the parser should accept looser output.

All three arms failed closed. Their decisions are `null`/`NONE`, contract scores
are zero, diffs are empty, candidate digests remain the initial digest, and no
proposal was admitted. No candidate evaluation, A6-F, feedback, mutation, or
scientific benefit result exists. The exact machine-readable record is
[r6-discovery-context-exhaustion-incident.json](../../output/qfbench-supervisor/a6-4d5fd85f47525255-r6/r6-discovery-context-exhaustion-incident.json),
5,887 bytes, SHA-256
`712c71762b9a53a3552ae8cfc476b714c1e6140b6f28154e3c4dafc4550334b1`.

## Valid measured prerequisites

The following facts remain measured and are not superseded by the discovery
failure:

- Release root:
  `/home/julius/qea/deploy/releases/a6-4d5fd85f47525255`
- Source tree SHA-256:
  `4d5fd85f475252556a7346c6a7d1cb588198677c96c8bed05074e3f7e238fe7d`
- Release manifest SHA-256:
  `6544ac429332e5dbe4576c4d1eda978fbedf2822123269f329c9204de4594c8a`
- External identity-record SHA-256:
  `8dca6152001d9b7c3415bf413f968edd49e1cf6c05839b64f46b7fba04721b8c`
- Materialized launch identity:
  `7ef40eeca995811dcedf90c4e691d045df9ef92a280283291133ef1ee5aa02aa`
- Seed ID: `qfbench-a6-seed-evidence-flash-20260810-r6`
- Seed report SHA-256:
  `583fa6524901f8ed8d4973950c43fa4f39541ce8c3cd65070fa052831d937862`
- Seed result: 16/16 scores; task mean `0.625`; six-domain macro
  `0.6805555556`; 171 completed unique pinned-Flash requests; 3,728,316
  tokens; USD `0.1409971696`; canonical complete accounting with no lower
  bound or unreconciled attempt.
- Formal wrapper-corpus audit SHA-256:
  `a7ae9a205aa2eb5981eef09438643b492c7cccce4f6cbe623c873c07f3ae7ee2`
- Three-arm same-ID no-model preflight evidence SHA-256:
  `15045b5c6b6583d07f92f9f4eaf9293dbbd6f4e78d95c02dde7e2a1bb951945d`

The seed task mean and domain macro are different aggregations and must not be
substituted for one another. Neither is a discovery-arm effect estimate.

## Measured three-arm result

The three proposal-only arms used the frozen high-reasoning Evolver and pinned
Flash route. Their provider ledgers are complete for the recorded attempts:

| Arm | Requests | Tokens | Cost | Prompt at stop | Overflow | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| A6-R | 23/23 | 2,048,707 | USD `0.0540384656` | 201,959 | 1,959 | invalid / none |
| A6-E | 14/14 | 1,501,762 | USD `0.0530031992` | 233,534 | 33,534 | invalid / none |
| A6-EC | 12/12 | 1,665,742 | USD `0.0538054272` | 221,691 | 21,691 | invalid / none |
| Total | 49/49 | 5,216,211 | USD `0.1608470920` | — | — | no valid arm |

The report and terminal artifact identities are:

| Arm | Pilot report SHA-256 | Proposal report SHA-256 | Final SHA-256 |
| --- | --- | --- | --- |
| A6-R | `1f7c51ae509cf6e0b1f3484d28e09a416cb56841f725bae06d12a1115915c385` | `d3828c3a8e3e0479df5d00713ae92038eab69ee562f0a4414d017a5a875522d0` | `6c980b82e8f1ddfbe3f8fb0da7e0d06c1b4ee88e5025ee62cce4eeda0375faa9` |
| A6-E | `59542ade4052bfb58b52f7349a59d4ccbd4e4f955bf802488bd663d5a449ba15` | `98aec5b76badf3090961e7cb56554b27198a384ed165a3c6ad6d319f80b88c30` | `1f298ee04995d756e2df7dc25bd96c8a91dce4dbca7d73c5d8cb508d67049bdb` |
| A6-EC | `90471beaa72272877e572598e03ec6c11cefc74bb12f0d5b02f18211efd90d22` | `0330ffc51732294a6f79312af837b629bc3ce5d9c0b0dd81aa71f9e6508b6293` | `f582f94bf799c0c09776643223da4009995426a545fcc8fa5387fa0e528ec351` |

Each final artifact has `final_truncated=false` and contains NexAU's explicit
prompt-too-long and insufficient-token stop text rather than a valid decision
object. The common parser error, “final response did not contain a JSON
object,” accurately keeps admission closed but does not identify the upstream
cause by itself. The canonical A6 discovery audit is 58,062 bytes, SHA-256
`8c6b1aa3d03b6008a0b40af1b17997d380ed498cfb91a226f1b6394d2fc37ddc`.

## Source-audited cause

The configured NexAU loop exposed a soft warning when fewer than 49,152 context
tokens remained, but the warning did not prevent the next evidence read, probe,
or provider call. The executor's hard guard ran only after the prompt exceeded
`max_context_tokens=200000`; at that point it appended an error instead of
creating the exact ACT/ABSTAIN terminal state required by A6. R, E, and EC
therefore shared one loop-control failure despite different evidence
representations.

Accepting prose without JSON, recovering a decision from the preceding trace,
or manufacturing ABSTAIN would weaken the frozen contract. The preserved
invalid decisions are the correct scientific record.

## Offline terminal-reserve remediation

The independently accepted patch adds a hard, auditable terminal phase before
the 200,000-token limit:

- a 136,000-token hard trigger reserves 64,000 context tokens;
- a deterministic compact state is limited to 65,536 bytes and its exact
  prompt is checked to retain 32,000 output tokens;
- after every successful pre-model hook, a one-shot guard binds the phase,
  canonical message SHA-256, and exact prompt-token count; the provider wrapper
  must consume that exact guard, so a hook/audit/path/persistence exception at
  any prompt size blocks the provider rather than failing open;
- the decision-only phase disables evidence reads, search, mapping, probes,
  inspection, and writes and exposes only exact `decide_candidate` ABSTAIN when
  no implemented candidate exists; it does not advertise an ACT that cannot be
  written;
- a preterminal ACT may proceed to a tool-free final only if the candidate was
  already changed; otherwise the terminal override remains ABSTAIN-only;
- terminal generation is capped at three model calls of at most 32,000 output
  tokens each; missing or invalid decisions remain invalid and no ABSTAIN is
  synthesized;
- bounded structured probe observations, including typed EC matches, are
  retained even when an old decisive probe would otherwise be displaced by
  many later access records;
- phase transitions, compact-state identity, pre/post token counts, one-shot
  guard consumption, provider usage, and candidate identity are persisted in a
  bounded terminal-reserve audit that the remote result summary schema-validates
  and digest-binds; ordinary discovery and admission gates still enforce
  phase/decision consistency.

The patch leaves the exact ACT/ABSTAIN schemas, the EC semantic comparison gate,
candidate write lock, provider route, evaluator isolation, and evidence-access
firewall unchanged. Its principal implementation file
`qea/evolve_agent_full/middleware/terminal_reserve.py` is SHA-256
`8e45041ca02dbdcb2594b772e842fc4b96546049d1e33a595d4bb48d22f6a553`.

Deterministic regressions cover all three large-evidence arm forms, the exact
136,000 boundary, below-trigger behavior, ignored warning, low- and high-token
pre-model exceptions with zero provider calls, one-shot message drift,
ABSTAIN-only terminal exposure, unchanged ACT rejection, implemented ACT
completion, invalid terminal output, the three-call cap, an old decisive probe
behind 2,000 later reads, exact YAML/Agent wiring, and preserved EC/write-lock
behavior. The focused set passes `86 passed`; the expanded impacted set passes
`162 passed`; an independent cross-review passes `62 passed`; and the final
complete NexAU test suite passes `1159 passed, 1 skipped` in 50.57 seconds with
the loopback and child-process fixtures permitted. Python compilation and
release-entrypoint validation remain part of the r7 package gate.

## Closure and recovery boundary

The r6 monitoring stack was closed in the frozen order: monitor first, then
timers and coordinators, exact-ID resource audit/reaping, final additive mirror,
and mirror unload. All exact lifecycles are clean, managed containers and
networks are zero, leases are zero, and the final mirror cycle exited zero with
zero stderr bytes. The run artifacts, traces, ledgers, invalid final outputs,
and empty diffs are preserved.

Because the terminal middleware changes the Evolver source and launch identity,
r6 cannot resume and its seed/corpus cannot be relabeled for the repair. The
next executable stage requires a new content-addressed r7 release, external
ten-field live identity, fresh r7 exact IDs, fresh 16-task seed and canonical
ledger, fresh R/E/EC corpora, same-ID no-model preflights, and independent gates
at each stage. The offline patch and tests are not evidence that the model will
produce a valid ACT or ABSTAIN under the reserved phase.

Candidate evaluation, A6-F, feedback, mutation, and any larger panel or
repetition design remain **not run**. The user's request for more tasks is
retained as a later statistical-design input; it does not retroactively change
the frozen 16-task localization core or turn this loop-control failure into a
mechanism result.
