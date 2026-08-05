# Evolver Prompt v1 — "minimal", archived 2026-08-05

Frozen copy of the evolver system prompt and NexAU guide that ran
`qfbench-rootless-evolution-30x15x40-v4-flash-0731-10iter-20260805`
(iterations 1–4, superseded).

| File | SHA-256 |
|---|---|
| `systemprompt.md` (28 lines) | `f3c9aa4c2969495e0b2eb86772e32b490ce7a74b839e545afebfb60805fa3836` |
| `NEXAU_GUIDE.md` (22 lines) | `d039548af865c18f4831d8839c9d7a83aa100a14b73df7a536222cafe8d7620f` |

## Why this is kept

This version is the **exposure control arm**. It is the measured baseline for
one question: how much of an evolver's search-space usage is determined by what
the prompt enumerates, holding the admission policy, model, gate, and benchmark
fixed?

## Measured behavior

Over four iterations the evolver edited **only `systemprompt.md`**. It created
none of the seven directories the admission policy permits:

```
memory/  middleware/  routing/  skills/  tools/  validator/  tool_descriptions/
```

| Iteration | Edit | Prompt lines | Gate verdict |
|---|---|---|---|
| 1 | rewrite systemprompt.md | 1 → 33 | rejected: domain regression rates_fx_macro |
| 2 | extend systemprompt.md | 33 → 41 | rejected: domain regression derivatives, rates_fx_macro |
| 3 | compress systemprompt.md | 41 → 13 | rejected: domain regression derivatives, rates_fx_macro, systematic_strategy |
| 4 | **empty diff** | — | rejected: candidate made no change |

Iteration 3 is the informative one: after two additive failures the evolver
*shortened* the prompt rather than changing dimension. That is a binary search
along a single axis.

## Why it behaved that way (source-audited)

Three causes, separable and each testable:

1. **No enumeration.** Neither the prompt nor the guide names the seven
   permitted directories. The guide mentions only `tools/*.py`. Five of the
   seven (`memory`, `middleware`, `routing`, `skills`, `validator`) are never
   referenced anywhere the evolver can read, and they do not exist in the seed
   candidate, so nothing in the observation reveals them.

2. **"Smallest coherent change" penalizes structural edits.** Step 4 of the
   required workflow asks for the smallest coherent change. A single-file prompt
   rewrite is strictly smaller than adding a module plus its `agent.yaml`
   declaration plus a smoke test — so the instruction actively selects the
   prompt axis.

3. **Asymmetric cost to add a tool.** Adding a local tool must satisfy: import
   under the worker runtime, `runtime_bridge` for extra dependencies, fixed
   argv / bounded timeout / fixed cwd / minimal env / bounded output for any
   subprocess, a mandatory `smoke_candidate_tool` call, and an AST import-root
   check at admission. Editing the prompt costs nothing.

**The tool layer is not the constraint.** `write_candidate` calls
`path.parent.mkdir(parents=True, exist_ok=True)`, so any of the seven
directories was always writable. The restriction was entirely in what the
evolver was told.

## Confound to respect when comparing against v2

Cause 1 (enumeration) and cause 2 (minimality instruction) were both present
here. A v2 that fixes both cannot attribute a behavior change to either one
alone. If the attribution matters, vary them separately.

See `results/bc-mirror/qfbench-rootless-evolution-30x15x40-v4-flash-0731-10iter-20260805/operator-ledger/20260805T174500+0800-superseded-provider-outage.json`
for the full run record.
