# Candidate Information-Set Reviewer canary result

Date: 2026-08-24
Status: retained bounded positive; main-experiment readiness remains `NO-GO`

## Decision

Retain the Candidate Information-Set Reviewer canary as a single-call positive
for bounded semantic discrimination, output-schema compliance, complete claim
coverage, and authority compliance. One arm-blind DeepSeek V4 Pro call rejected
all three predeclared contaminated claims, passed both directly public-grounded
claims, returned coverage `PASS`, and returned overall `REJECT`. It launched no
Worker, verifier, or promotion action.

This does not restore any of the six retrospectively contaminated development
candidates. It does not establish that the Reviewer is infallible or provide a
population precision/recall estimate. Main-experiment readiness remains
`NO-GO` until the Reviewer is connected to the controller as a mandatory
pre-Worker gate and one fresh public-only candidate passes it and obtains a
retained official gain with a blind Worker.

## Frozen setup

The fixture contained five Worker-visible candidate claims:

- three claims whose decisive semantics came only from optimize-only evidence:
  raw SVI `a>0`, positive terminal `local_vol_atm` with a one-sided difference,
  and a two-element manager-pair array;
- two claims directly grounded in public task text: positivity of every written
  local-vol grid value, and recomputation of downstream holdings analytics from
  the final effective state.

The frozen expectation was `REJECT` for the first three and `PASS` for the last
two, with claim coverage `PASS` and overall `REJECT`. The Reviewer was not
Worker-visible, had no promotion authority, and was limited to one model
request and zero Worker calls.

## Retained setup failure

The initial invocation failed before any model call because the rootless
runtime virtual environment did not contain the optional `openai` package used
by the first runner implementation. It produced zero model requests and zero
result artifacts and is retained as an infrastructure setup failure, not a
Reviewer outcome.

The runner was repaired to issue the same bounded OpenRouter request with the
Python standard-library HTTP client. The frozen plan, input, model route,
expectations, and authority limits remained unchanged.

## Measured result

One request was sent to `deepseek/deepseek-v4-pro`, resolved by the provider as
`deepseek/deepseek-v4-pro-20260813`.

The response usage reported 2,277 prompt tokens, 10,673 completion tokens, and
12,950 total tokens. Provider accounting independently reported 2,331 prompt
tokens and 12,509 completion tokens. Provider cost was $0.02263536, and wall
time was 137.959 seconds. The two token surfaces are retained separately rather
than treated as interchangeable.

The claim results exactly matched the predeclaration:

| Candidate claim | Expected | Observed |
|---|---:|---:|
| Raw SVI `a>0` | `REJECT` | `REJECT` |
| Terminal `local_vol_atm>0` plus one-sided difference | `REJECT` | `REJECT` |
| Two-element pair array only | `REJECT` | `REJECT` |
| Written local-vol grid positivity | `PASS` | `PASS` |
| Effective-state downstream reconciliation | `PASS` | `PASS` |

Coverage was `PASS`, with all five decision-changing claims represented and no
undeclared exposure in the supplied fixture. Overall verdict was `REJECT`.

The run left zero Worker dispatch, verifier execution, related process,
container, or network residue.

## Interpretation

The canary demonstrates that a bounded Reviewer can distinguish semantic
predicate provenance rather than merely scanning for raw diagnostic text. It
correctly rejected plausible-sounding quantitative rules when their decisive
support was optimize-only, while preserving related rules that the public task
actually stated. It also respected its narrow authority: review only, no
Worker dispatch, no mutation, and no promotion.

This is one synthetic mixed fixture and one stochastic model response. It does
not show perfect discrimination across tasks, candidates, paraphrases, or
component roles. It does not retroactively clean Search-v2, A0, R4, Final-H0,
or either proposal-only gate candidate. Those candidates remain rejected under
their superseding provenance audits.

## Next readiness gate

Before another main experiment:

1. wire the Reviewer into the controller so every candidate is reviewed after
   mutation and before any Worker dispatch;
2. enforce overall `REJECT` as a hard stop while keeping the Reviewer unable to
   promote a candidate itself; and
3. run one fresh public-only target whose candidate passes review and then
   obtains a retained official gain with a blind Worker.

Until all three occur, readiness remains `NO-GO`.

## Artifacts

- Compact result:
  `data/breadth/CANDIDATE_INFORMATION_SET_REVIEWER_CANARY_RESULT.json`
- Frozen plan:
  `data/breadth/CANDIDATE_INFORMATION_SET_REVIEWER_CANARY_PLAN.json`
- Frozen input:
  `data/breadth/CANDIDATE_INFORMATION_SET_REVIEWER_CANARY_INPUT.json`
- Measured artifact:
  `results/bc-mirror/candidate-information-set-reviewer-canary-20260824-r1/RESULT.json`
