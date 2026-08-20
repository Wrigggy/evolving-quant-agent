# QDR-1 bounded causal probe P-v2

Date: 2026-08-20

## Why the earlier probe was not doing its original job

The original probe was meant to be a short, Evolver-designed causal experiment
over a retained artifact: determine whether a new component is applicable,
observe what it finds, act on that observation, and check whether the artifact
or official properties change. It was not meant to approximate a fresh Worker
run.

The preceding component-impact probe reached the component only on assistant
turn six of seven. The component returned actionable errors, but only one turn
remained, so the Worker reread code and stopped. Increasing the nominal budget
alone had already failed to activate the component in earlier runs. The missing
mechanism was therefore phase control: bounded inventory, an explicit decision
point, and enough work after the observation.

## P-v2 design

P-v2 held the T26 task, retained QDR-1 component-impact r2 harness, blind 12/17
seed artifact, model route, and official verifier fixed. It targeted 12 actual
completed model requests. The first two assistant turns were available for
public-contract and artifact inventory. On the next turn, generic middleware
closed inventory and temporarily exposed only the candidate component, while
still allowing the Worker to make an evidence-grounded textual skip. After a
component observation, at least three assistant responses were reserved for
edit, focused smoke, re-audit, and delivery.

The middleware did not infer the task's quantitative relations, fill tool
arguments, run the component automatically, edit code, or see checker answers.
The Worker authored the relation declarations from the public instruction and
current artifact. This preserves the intended division: the harness controls
the research phase transition; the Worker performs the quantitative reasoning.

## Measured trajectory

The Worker completed all 12 model requests in 220.235 seconds.

1. Assistant turns one and two inspected the current artifact and public
   contract.
2. At the turn-three checkpoint, the Worker called
   `check_quant_relations`. It declared six relations and received two errors
   and four warnings. The two errors localized training-boundary and
   metric-weighted-residual observability in `select_gamma_by_cv`.
3. The Worker revised `strategy.py`, including an explicit training-only CV
   boundary and the inverse-metric residual calculation at the declared
   function locus. It then ran syntax and real-data functional smokes.
4. On assistant turn six, the Worker called the component again. All six
   relations were realized with zero errors, zero warnings, and zero measured
   truncation residual.
5. The Worker ran the final artifact end to end and delivered it at the required
   location.

The artifact changed. The official verifier improved from 12/17 to 14/17;
properties A3 and B3 changed from failure to pass, with no observed property
regression. Binary reward remained zero because three properties still failed.
The run cost $0.063367496, had no rate-limit retry, and left no scoped container
or network.

## Conclusion

P-v2 meets the original probe objective. It measured the complete local causal
chain

`registration -> early call -> actionable observation -> edit -> focused smoke
-> re-audit -> official property change`.

This is stronger than component reach or a local synthetic smoke: the blind
Worker acted on a component observation and improved the official property
score. It also shows why the prior probe failed: the decisive defect was not
merely a small total budget, but unbounded inventory and no protected
post-observation phase.

The result remains a seeded, experimenter-scheduled causal probe. It does not
show that a fresh Worker activates the component, that the gain repeats, that
other tasks are protected, that the component transfers, or that binary reward
improves. The next smallest confirmation is one fresh T26 Worker using the
frozen r2 harness plus the generic phase checkpoint. If that reaches 17/17 or
improves reproducibly, follow with one repeat and one matched quant task before
building the deferred multi-task scheduler.

Evidence is mirrored at
`results/bc-mirror/qce-t26-qdr1-causal-probe-pv2-20260820-r1/`; the compact
machine-readable record is
`data/quantcodeeval/QDR1_CAUSAL_PROBE_PV2_RESULT.json`.
