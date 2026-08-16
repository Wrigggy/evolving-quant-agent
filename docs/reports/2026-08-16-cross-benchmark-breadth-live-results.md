# Cross-Benchmark Breadth Live Canary — 2026-08-16

## Conclusion

The breadth mechanism worked, but the target-score effect was mixed.

The same component-search interface produced a calibrated no-change decision
on a QFBench task with insufficient answer-free contrast and an admitted,
executable multi-file component on a new QuantCodeEval task with richer runtime
evidence. On QuantCodeEval T26, the autonomously discovered component improved
one sampled Worker from 13/17 to 14/17 properties, but an independent repeat
fell to 12/17. The target improvement is therefore not stable. The T19
protection Worker scored 18/18, improving over the earlier shell-only 16/18
sample, so the component did not damage the protection task.

The most important causal clue is that the T26-specific checker reported two
irrelevant failures on every T19 audit, yet T19 still improved. The transferable
part is more likely the broader workflow—read the public contract, independently
validate, revise, and re-audit—than the hard-coded T26 assertions themselves.
The next experiment should ablate those two parts before adding more tasks.

This is an engineering canary, not a benchmark-wide performance result.

## Experimental question

The experiment tested whether a common answer-free experience interface could
help the Evolver do three things without prescribing a component:

1. decide when the evidence is insufficient and abstain;
2. localize a harness component on an unseen task and implement it across the
   full worker harness;
3. activate the component in real Workers, repeat the target, and preserve a
   known protection task.

The model route was `deepseek/deepseek-v4-flash-0731` through the DeepSeek
provider with fallback disabled. All paid runs used one worker or Evolver at a
time on the personal `bc` machine. T26/T27 public data and checker runtime were
already staged under `/data/qea-julius-storage`; no WRDS account was used.

## QFBench matched proposal arms

The target was `swap-curve-bootstrap-ois`, whose prior baseline was 17/19 in
five repeats. The two proposal-only arms differed only in whether prior
component cards were visible.

| Arm | Run | Result | Requests | Tokens | Cost |
| --- | --- | --- | ---: | ---: | ---: |
| task-only | `breadth-qf-swap-task-only-20260816-r1` | semantic ABSTAIN; no mutation | 22 | 1,737,664 | $0.0404691560 |
| history-enabled | `breadth-qf-swap-history-20260816-r1` | semantic ABSTAIN; no mutation | 13 | 896,523 | $0.0334927488 |

The history arm actually read the two retrieved component cards
`public_quantity_semantic_binding` and `declarative_quant_invariant`. It did
not blindly reuse either. Both arms found that all public contract checks and
stored artifacts were internally consistent, while two remaining hidden-test
failures could arise from either a forward definition or a valuation
convention. Answer-free evidence could not distinguish them, so no component
change was justified and no Worker was launched.

Both models wrote `ABSTAIN` in `prediction.json`, but the old discovery runner
looked only at `discovery_hypothesis.decision` and recorded `decision=null`.
This was a result-registration bug, not a model-decision failure. The runner now
uses an explicit valid decision from either terminal artifact. The original
run records remain unchanged and are interpreted as semantically calibrated,
protocol-registration-incomplete abstentions.

## QuantCodeEval T26 H0

The shell-only baseline was sampled once in
`qce-breadth-t26-h0-20260816-r1` and retained for future reuse.

- score: 13/17, official binary reward 0;
- Type A: 5/7;
- Type B: 8/10;
- Worker process: 36 turns, 46 tool calls, 14 tool errors, about 902 seconds;
- usage: 36 completed requests, 1,644,894 tokens, $0.0408489088.

This was an informative partial solution: all seven required public functions
were present, but four semantic properties failed. The Worker trace showed
only two late, self-written invariant checks after its last main implementation
update.

## Autonomous component discovery

The history-enabled Evolver run was
`breadth-qce-t26-history-20260816-r1`. It read the T26 instruction, paper,
answer-free Type A/B outcome, strategy facts, trace facts, and the prior
component catalog. It chose to synthesize a new component rather than reuse the
two retrieved semantic components unchanged.

The selected mechanism was an independent public-clause audit and revision
loop. The candidate changed five files across four harness roles:

- `tools`: a new `clause_invariant.py` executable checker;
- `tool_descriptions`: registration and usage contract for the checker;
- `agent_config`: tool reachability;
- `systemprompt`: inspect data, run the checker after revisions, fix failures,
  and independently test semantics before finalization.

The candidate passed tool smoke and full-harness admission. The Evolver used 21
completed requests, 801,854 tokens, and $0.0194968480. This establishes an
autonomous ACT, executable multi-file mutation, and activation-ready candidate.
It does not yet establish score benefit.

## Target and repeat

| Run | Type A | Type B | Total | Official reward | Requests | Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| H0 | 5/7 | 8/10 | 13/17 | 0 | 36 | $0.0408489088 |
| candidate target | 6/7 | 8/10 | 14/17 | 0 | 34 | $0.0313506088 |
| candidate repeat | 5/7 | 7/10 | 12/17 | 0 | 32 | $0.0263097184 |

Both candidate Workers invoked the new checker three times. The first Worker
made a code revision and re-ran the checker, satisfying the Evolver's process
prediction. It recovered one Type A property. The repeat also activated the
component but lost one Type B property relative to H0.

The appropriate status is therefore:

- component activation: supported in two independent Workers;
- one sampled property gain: measured;
- repeated T26 benefit: not supported;
- official T26 solution: not achieved.

## T19 protection

`breadth-qce-t19-protection-20260816-r1` scored 18/18 and official reward 1.0.
The earlier shell-only T19 sample scored 16/18, so this sample improved rather
than merely preserving the prior result. It used 25 completed requests,
527,778 tokens, and $0.0181492024.

This result needs a careful causal interpretation. The checker was written for
T26 and reported the same two irrelevant failures on all three T19 calls:
missing T26-specific functions and no T26 de-market helper. The Worker still
completed T19 correctly. Therefore:

- the full candidate did not regress the protection task;
- the general contract-reading and iterative-validation policy may transfer;
- the T26-specific static assertions are not a plausible direct explanation
  for the T19 gain;
- because the T19 comparison is against an earlier shell-only sample rather
  than a simultaneous control repeat, the +2 should be treated as provisional,
  not a causal effect estimate.

## Cost and operational evidence

Across the two QFBench Evolver arms, T26 H0, T26 Evolver, two T26 candidate
Workers, and one T19 protection Worker, the experiment used:

- 183 completed model requests;
- 8,231,008 tokens;
- $0.2101171912 provider cost;
- zero coordinator restarts.

Each long run had a user-systemd coordinator, 30-second remote health record,
60-second Mac monitor, and additive local evidence mirror. All run-scoped
timers and LaunchAgents were stopped after completion. No QEA containers remain
on bc. The machine ended with roughly 100 GB available on `/` and 228 GB on
`/data`; memory pressure was not a blocker.

Machine-readable results are in
`results/cross-benchmark-breadth-20260816/RESULT.json`. The additive mirrors are
under `results/bc-mirror/` using the run IDs listed above.

## What this round says about the method

The cross-benchmark adapter is doing useful methodological work: it did not
force the same behavior everywhere. It supported calibrated abstention on the
ambiguous QFBench task and autonomous synthesis on the more diagnostic
QuantCodeEval task. Prior components were evidence, not mandatory actions.

The remaining weakness is no longer “the Evolver can only edit prompts” or
“the component cannot activate.” It is component attribution and stability.
The candidate bundles a task-specific static checker with a more general
revision workflow, and two T26 samples disagree on score direction. Treating
that bundle as one stable reusable component would be premature.

## Next experiment

Run one small component ablation before expanding breadth:

1. create a workflow-only candidate that keeps contract extraction,
   independent semantic fixtures, and post-revision recheck instructions but
   removes the T26-specific checker and tool registration;
2. run two T26 Workers and one T19 protection Worker;
3. compare activation, revision timing, Type A/B properties, cost, and tool
   errors with the current full component;
4. only if the workflow-only arm loses the useful behavior should we build a
   task-conditioned checker whose clauses are generated from the current
   public task rather than hard-coded for T26.

Promotion should require a target improvement in repeated samples, no
protection regression, and observed component activation. Until then the
ledger status remains unsupported at the binary-reward level with mixed
property evidence.
