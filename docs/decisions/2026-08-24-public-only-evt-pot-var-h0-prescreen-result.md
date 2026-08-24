# Public-only EVT-POT-VaR Quant-H0 prescreen result

Date: 2026-08-24
Status: dependency-invalid `STOP_NO_RESULT`

## Decision

Retain `qf-public-only-evt-pot-var-h0-prescreen-20260824-r1` as one completed
execution record, but not as a mathematical-mechanism observation. The Worker
and verifier completed, and the trusted aggregate was 51/55 with reward,
task mean, and overall score 0.833333. Fresh trace evidence nevertheless shows
that the prescribed `arch` GARCH-EVT path was unavailable and that the Worker
substituted a custom optimizer and recursion.

This exactly matches the frozen `dependency_invalid_when` condition. The
terminal decision is therefore `STOP_NO_RESULT`. The 51/55 aggregate is
retained only as an execution record. It must not be described as a four-
property Quant-H0 capability failure, public mathematical headroom, or a
candidate-mechanism result. No proposal, Reviewer, candidate Worker, repeat,
or protection stage is authorized.

## Frozen scope

Deployment source version `3fc9efc` authorized exactly one unchanged
Quant-H0 Worker and one official verifier on public QFBench task
`evt-pot-var`. The Worker received the public instruction, data, formulas, and
unchanged Quant-H0 harness. The prescreen was adaptive development target
screening, not sealed evaluation.

The predeclared decision order first checks whether the Worker actually used
the public contract's prescribed `arch` implementation. Missing `arch`, an
unavailable installation path, or a substituted custom optimizer or recursion
selects `STOP_NO_RESULT` before any rolling-alignment or Kupiec,
Christoffersen, and conditional-coverage arithmetic can authorize a public-
only proposal. That ordering prevents a runtime mismatch from being relabeled
as a quantitative research mechanism.

## Process and measured execution

The single Worker completed in 27 turns with 32 tool calls and 5 tool errors.
It ran for 655.389 seconds and wrote two public artifacts:

- `results.json`, 2,536 bytes;
- `solution.json`, 906 bytes.

The runner marked the raw Worker execution valid for selection before applying
the separately frozen dependency audit. The official verifier then produced
51 passed of 55 tests, reward 0.833333, task mean 0.833333, overall 0.833333,
and exit code 1. These values establish that a coherent execution reached the
verifier; they do not override the dependency-invalid terminal branch. No
failed-property identity was read into this record or exposed to an Evolver.

All 27 logical provider requests completed on
`deepseek/deepseek-v4-flash-0731`. They used 875,317 input tokens, 44,768
output tokens, and 920,085 total tokens at a provider cost of $0.040374796.
There were zero requests with a retry index above zero, zero rate-limited
retries, zero other nonaccepted requests, and zero unreconciled attempts or
requests. The five Worker tool errors were execution events, not provider
retries.

Every frozen limit was satisfied: one of one Worker, one of one official
verifier, 27 of 50 completed requests, 920,085 of 4,000,000 tokens,
$0.040374796 of $0.20, and 655.389 of 5,400 wall seconds. No replacement model
or provider was used.

## Dependency case study

The fresh Worker trace provides a direct end-to-end dependency diagnosis:

1. The Worker ran a Python import check for `arch`; it failed with
   `ModuleNotFoundError: No module named 'arch'`.
2. The Worker attempted `pip install arch`; name resolution/network access
   failed, and no package could be installed.
3. The Worker implemented a zero-mean GARCH(1,1) directly using custom SLSQP
   optimization, a custom backcast and variance recursion, and a separate
   transformed-parameter Nelder-Mead fit as a numerical cross-check.
4. The final response explicitly disclosed that `arch` was not installed and
   that the direct custom implementation replaced it.

The Worker also produced structurally complete results and performed several
independent numerical checks. Those checks show effort and internal
coherence, but they do not make the substituted path equivalent to the public
contract for this experiment. The frozen gate asks whether the prescribed
implementation was observed, not whether an alternative implementation seems
plausible.

## Interpretation

The dependency-first stop is the main result. It prevents two invalid
inferences. First, the four-test shortfall cannot be attributed to the
Worker's mathematical reasoning under the prescribed runtime because that
runtime was absent. Second, installing `arch` or retaining the custom GARCH
fallback cannot be proposed as a reusable quantitative mechanism; those are
runtime/setup changes, not the predeclared public mathematical relation.

Accordingly, the rolling information-time, strict violation, Kupiec,
Christoffersen, and conditional-coverage public audit is recorded as not
applicable after dependency stop. We do not search those outputs for a second
eligibility argument after the first terminal branch has fired.

A future EVT experiment would require a separately frozen runtime with the
prescribed `arch` dependency present before the Worker starts. This run itself
does not authorize that recovery, a proposal, or a candidate. It is not a
stable baseline, harness gain, repeat, protection result, or main-readiness
result.

## Runtime and cleanup

The main and health systemd units both ended `inactive/dead` with
`Result=success`, exit code 0, and `NRestarts=0`. Worker, proxy, verifier, and
proxy-network lifecycle records all report `cleaned_up=true` using exact-ID
cleanup, and the terminal audit found no matching live container or network
residue.

A temporary loss of the local VPN route interrupted one read-only monitoring
poll. The route recovered without modifying, restarting, replacing, or
intervening in the experiment. The additive local mirror was refreshed after
recovery. Its reports, evaluation, trace, final text, artifacts, lifecycle
records, and empty coordinator lock are retained evidence, not live runtime
residue.

## Next step

No follow-on dispatch belongs to this plan. If EVT-POT-VaR is revisited, the
smallest valid recovery is a new frozen H0 prescreen whose immutable runtime
already contains the prescribed `arch` package. That would measure setup
validity first; only a valid below-full result with direct public mathematical
mismatch could justify a separate proposal and mandatory pre-Worker Review.

## Artifacts

- Compact result:
  `data/breadth/QF_PUBLIC_ONLY_EVT_POT_VAR_H0_PRESCREEN_RESULT.json`
- Frozen plan:
  `data/breadth/QF_PUBLIC_ONLY_EVT_POT_VAR_H0_PRESCREEN_PLAN.json`
- Source mirror:
  `results/bc-mirror/qf-public-only-evt-pot-var-h0-prescreen-20260824-r1`
