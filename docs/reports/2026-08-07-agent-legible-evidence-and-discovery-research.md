# 2026-08-07 — Agent-Legible Evidence and Evolver Discovery Research Note

Status: **source-audited framing plus an exploratory QFBench mechanism test in
progress**. This note is not a paper result and does not claim that more exposed
bytes monotonically improve an agent.

## Conclusion first

There is strong prior support for the narrower claim we need: an agent improves
when relevant state is made *legible and queryable through an interface designed
for the agent*. The evidence does **not** support the crude claim that dumping
more logs into the context improves output. Context is finite; unstructured
exposure can obscure the signal it was meant to reveal.

For QEA, the useful unit is therefore not raw evidence volume. It is a discovery
interface that lets the evolver:

1. map candidate components and their actual registrations;
2. map task outcomes, traces, and candidate history;
3. drill from an anomaly to exact trace spans or comparisons;
4. record competing causal hypotheses and counterevidence;
5. make one intervention with a falsifiable process and task prediction.

The QFBench adaptation should remain quant-specific. It needs to expose task
vectors, artifact/process summaries, skill or tool activation, numerical and
schema failures, and the bindings among prompt, tools, validators, middleware,
memory, and routing. It does not need to reproduce the entire Codex or Claude
Code product.

## Primary sources

### Agent-computer interfaces change performance

[SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering](https://arxiv.org/abs/2405.15793)
argues and empirically demonstrates that a purpose-built agent-computer
interface materially changes an LM agent's ability to navigate repositories,
edit files, and run tests. This is the closest established result to the side
hypothesis that evidence exposure and interaction design affect output quality.
The transferable claim is about interface design, not about copying SWE-agent's
commands.

### AHE makes observability part of the evolution mechanism

[Agentic Harness Engineering](https://arxiv.org/abs/2604.25850) organizes its
closed loop around three matched forms of observability:

- component observability makes the heterogeneous edit surface explicit;
- experience observability distills very large trajectories into a layered,
  drill-down corpus;
- decision observability binds edits to predictions later checked against task
  outcomes.

Its reported ablations localize gains primarily to tools, middleware, and
long-term memory rather than the system prompt. This supports our concern that
a prompt-only or prompt-to-skill study is not a test of full-harness discovery.
AHE is still evidence from coding tasks, so transfer to QFBench must be measured.

### Production agent practice favors maps and progressive disclosure

OpenAI's [Harness engineering](https://openai.com/index/harness-engineering/)
reports that a large monolithic instruction file was ineffective and describes
the successful alternative as a compact map into structured repository
knowledge. It also describes making UI state, logs, metrics, and traces directly
queryable by Codex. This supports progressive disclosure and agent-legible
observability rather than context dumping.

Anthropic's [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
provides the necessary counterweight: context is finite, tools must return
token-efficient information, and overlapping or bloated tool sets create
ambiguous behavior. Its recommended starting point—test a capable model with a
minimal setup, then add context and tools in response to observed failure
modes—matches the decision to restore a strong evolver baseline before treating
debugger output as the main cause.

### Agent-centric debugging benefits from higher-level navigation

[Empowering Autonomous Debugging Agents with Efficient Dynamic Analysis](https://arxiv.org/abs/2604.24212)
reports that line-by-line traditional debugger interaction is inefficient for
LLM agents, while a function-level agent-centric interface produces consistent
gains when added to existing agents. The exact software-debugging interface is
not appropriate for QFBench, but the design lesson transfers: expose meaningful
behavioral units and high-level navigation, while preserving drill-down.

### Traces are an evaluation object, not only a log artifact

Anthropic's [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
defines the trajectory as the complete trial record and recommends evaluating
agent behavior over repeated trials rather than only final answers. For this
exploratory canary, we use the trace to assess discovery behavior and retain the
official QFBench scalar as the outcome; we do not expose private verifier inputs.

## QEA mechanism derived from the sources

The implemented baseline is intentionally “similar in spirit, not identical in
form” to coding agents:

- GPT-5.4 with `xhigh` reasoning is used for the evolver proposal canary;
- the tool loop is expanded from 30 to 200 turns;
- evidence is exposed through a map, contextual trace slicing, and exact-file
  comparison rather than an unrestricted shell;
- the candidate is exposed as a component and binding graph;
- candidate writes stay locked until the evolver records at least two
  hypotheses, exact evidence references, counterevidence, uncertainty, a
  discriminating probe, a component choice, risks, and a falsifiable prediction;
- the independent admission and evaluator firewall remain unchanged.

The debugger is a deterministic evidence librarian. It creates an index and a
change→activation→task-outcome graph but explicitly does not assert the root
cause. The same high-reasoning evolver verifies the index against raw traces and
then edits the harness, avoiding a lossy debugger-to-editor handoff.

## Exploratory test, not paper protocol

The post-A3 mechanism canary uses the A3 candidate as the common backbone and
builds two answer-free evidence arms from the same public outcomes and worker
traces:

| Arm | Underlying public evidence | Added layer |
|---|---|---|
| Raw | A1–A3 history, A3 diff, public scalar outcomes, process summaries, worker finals and traces | none |
| Indexed | exactly the same raw evidence | deterministic debugger overview, task index, and change-outcome graph |

Each arm receives one GPT-5.4 xhigh proposal. Admitted candidates are then
scored in a separate run by the original pinned DeepSeek V4 Flash 0731 worker
route on the four A3 tasks. This separation keeps the worker model fixed without
requiring a production dual-model coordinator for an exploratory result.

The canary is considered useful if it demonstrates the complete observable loop:

- exact evidence is found and cited;
- more than one mechanism is considered;
- activation is not mistaken for causality;
- the selected component follows from the diagnosed mechanism rather than a
  hard-coded skill prior;
- the candidate is admitted and behaviorally testable;
- the output makes a process-level prediction that the next traces can falsify.

No p-value, large repeated panel, or paper claim is required. The result must be
labelled exploratory and negative evidence must be preserved.

## Side-conclusion metrics

The runner records two different notions that must not be conflated:

- **evidence access ratio**: exact evidence files read or inspected divided by
  files available. This measures exposure/engagement, not quality.
- **grounded citation ratio**: exact files cited in the hypothesis/final report
  that were actually read or inspected.

It also records causal-contract completeness, debugger/trace files accessed,
competing-hypothesis count, counterevidence and uncertainty, the discriminating
probe, prediction, and consistency between the write-unlock hypothesis and the
final report. These are process measurements. Official task reward remains the
outcome measurement.

