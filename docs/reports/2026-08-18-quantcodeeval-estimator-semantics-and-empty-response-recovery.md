# QuantCodeEval Estimator Semantics and Empty-Response Recovery — 2026-08-18

## Conclusion

This continuation produced one useful property-level improvement and two
negative mechanism results, but it did not produce a new autonomous T26 binary
success. The best fresh blind Worker reached 15/17, improving the previous
14/17 sample and passing all ten Type-B properties. A later refinement added
first-versus-second-moment and public training-scope checks. It passed its
synthetic component contrasts, but its blind Worker produced only 3/17. The
artifact had adopted the intended mean and public-gate changes, then crashed
across eleven properties because a multi-output OLS helper used incompatible
array shapes. Static semantic checks were therefore insufficient to establish
runtime component stability.

The provider work localized a separate failure. NexAU uses SSE streaming, so
the first empty-response fallback handled ordinary JSON but not reasoning-only
SSE responses. After adding SSE recognition, a real run detected an empty
completion and attempted provider fallback. The fallback also exhausted its
reasoning budget, and the combined 252- and 511-second responses exceeded the
downstream client's single-call timeout. Provider switching alone is therefore
not enough: recovery must also bound reasoning and the total retry path.

The final implementation permits one recovery attempt, changes only that
otherwise-lost attempt to low reasoning with an 8,192-token output cap, and
returns a prompt infrastructure error if recovery is also empty. Both paid
empty responses remain valid cost records. This final form passed local proxy
integration tests but has not yet been exercised by another paid Worker.

## Search rounds

### Autonomous estimator-state refinement

Run `qce-t26-estimator-state-evolver-20260818-r3` produced a legal ACT and an
admitted three-surface candidate. It modified the executable quant auditor,
its tool description, and the Worker prompt. It used 79 requests, 8,102,961
tokens, 865.354 seconds, and $0.136398588.

Independent tests rejected it as written: the interval and finite-mask checks
failed both deliberately wrong and intended-correct examples. It was retained
as negative evidence, not promoted.

### Generalized estimator-state repair

The manual R4 repair corrected those observed component faults without adding
T26 dates, property identifiers, expected values, or checker answers. Its
contrast suite produced:

- upper-bound-only interval FAIL and two-sided interval PASS;
- finite mask after estimation FAIL and mask before estimation PASS;
- unused finite mask FAIL.

Blind run `qce-t26-estimator-state-manual-candidate-20260818-r1` scored 15/17:
Type A was 5/7 and Type B was 10/10. It used 44 requests, 1,941,604 tokens, and
$0.084313672. This is a measured property-vector improvement over the earlier
14/17 sample, but official reward remained zero. Its failures were A3 public
training-scope observability and A10 end-to-end numeric identity.

### First/second-moment and public-scope refinement

R5 added two generalized checks:

- reject a quantity used as a first moment when assigned a second-moment
  diagonal;
- require a public model-selection entry point to visibly apply or call the
  training gate before delegating to private helpers.

The suite distinguished synthetic wrong/correct pairs, rejected the 15/17 R4
artifact, and accepted the retained trusted 17/17 repair. The first two blind
attempts returned no artifact after exhausting 32,000 reasoning tokens. They
used 20 requests, 431,381 tokens, and $0.065596604; neither has a score.

Run `qce-t26-estimator-semantics-fallback-candidate-20260818-r2` used the first
JSON-aware fallback proxy. Its initial attempt again returned no artifact. The
single replacement wrote `strategy.py` and was evaluated at 3/17: Type A 2/7
and Type B 1/10. The merged run used 34 paid requests, 1,087,189 tokens, and
$0.127061060.

Trusted diagnosis showed that the artifact had applied arithmetic mean and the
public training-gate idea. Its dominant error was instead a runtime shape bug:
a helper treated a multi-output regression target as one-dimensional, causing
incompatible `(374, 1)` and `(50, 374)` operations. Eleven properties crashed.
The result falsifies the claim that the static contrast suite is sufficient to
make the component stable.

## Provider recovery experiment

Run `qce-t26-estimator-semantics-sse-fallback-candidate-20260818-r3` used the
same frozen R5 harness with SSE empty-response detection. The live proxy audit
observed:

- 14 ordinary completed requests;
- one primary response that completed after about 252 seconds with reasoning
  but no content or tool call;
- one fallback response that completed after about 511 seconds with the same
  empty outcome;
- 16 paid records, 557,902 tokens, and $0.075398272 before timeout.

The run produced no artifact and no score. NexAU timed out while the proxy was
still recovering, so proxy finalization was interrupted and the coordinator
quarantined the incomplete audit. The emitted result incorrectly showed zero
requests and zero cost. This report preserves the live-observed values as a
lower bound and supersedes that zero for accounting. No further paid redraw
was launched.

OpenRouter's official documentation confirms that provider order controls
routing, while the unified `reasoning` object controls effort or a reasoning
budget. The final repair therefore combines provider fallback with a bounded
low-reasoning continuation rather than treating provider choice as the only
intervention.

## Code and validation

Scoped Git changes:

- `947d6b1`: retry completed empty ordinary-JSON responses on fallback routes;
- `dff25b2`: accept QuantCodeEval task-role names and metadata in the generic
  rootless proxy image builder;
- `6aa904e`: recognize empty SSE completions;
- `5020664`: permit one low-reasoning, 8,192-token recovery and stop promptly
  after a second empty response while retaining both paid records.

The final focused proxy tests passed 3 tests. The related proxy,
QuantCodeEval-candidate, and rootless-image suite passed 97 tests with one
skip. The final bounded-recovery code has not yet been deployed into another
paid Worker run.

## Claim boundary

Measured:

- R4 improved one blind property vector from 14/17 to 15/17 and made all
  Type-B properties pass;
- R5's static component contrasts did not predict runtime stability;
- the first SSE-aware proxy intercepted a real reasoning-only empty stream;
- serial full-budget fallback can exceed the downstream client timeout;
- paid attempts are retained with actual or explicit lower-bound cost.

Not measured:

- a fresh blind 17/17 Worker from the current harness;
- a paid success using the final bounded recovery behavior;
- repeat stability, protection, matched transfer, or benchmark-wide gain.

The earlier trusted zero-model 17/17 T26 causal repair remains valid, but it is
not reclassified as an autonomous fresh-lineage harness improvement.

## Next mechanism experiment

Do not add more static failure classes immediately. Add one small executable
runtime-probe component alongside the static quant-contract auditor. It should
exercise public entry points on bounded synthetic or public-input slices,
checking declared output shape, finiteness, and no-crash behavior, and return
the first actionable traceback to the Worker. The hypothesis is that static
semantic localization and runtime contract probing are complementary: the
former directs formula repair; the latter catches array-shape, signature, and
integration faults before submission.

Validate the probe on the observed 3/17 artifact (it must fail on the OLS shape
error) and the retained 15/17 and 17/17 artifacts (they must execute without
that crash). Then allow one blind Worker with the final bounded proxy. A legal
non-17/17 result returns to the Evolver as another answer-rich attempt; an
infrastructure failure stops the round. Do not run protection or transfer
until a fresh blind T26 Worker reaches 17/17 and repeats.
