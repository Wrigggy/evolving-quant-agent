# ICLR 2027 Research and Writing Direction: Quantitative Research Agent Evolution

Status: accepted research and writing direction, 2026-08-19. This document
defines the paper idea and vocabulary. It intentionally does not prescribe the
main experiment matrix, task counts, seeds, or scheduling system.

## Immediate scope decision

The ICLR 2027 submission sprint uses the original fixed outer evolution loop.
The coordinator runs a declared task panel, collects Worker trajectories,
provides accumulated evidence to the Evolver, evaluates one proposed harness
candidate under a fixed protocol, and accepts or rolls it back. A material
harness change defines the next candidate version and a completed candidate
evaluation defines the iteration boundary.

The more open-ended scenario in which the Evolver autonomously decides when to
call Workers, which experiments to run, how long to search, and when to submit
an incumbent is deferred. It remains a possible future extension, but it is not
part of the submission-critical method and is not required for the current
paper claim.

## Central research idea

Many recent quantitative agents keep the agent scaffold fixed while searching
over the artifacts it produces, such as factors, strategies, model
configurations, or executable research code. This project studies a different
evolutionary object: the effective capabilities of the quantitative research
agent that produces those artifacts.

The task-solving agent is named the **Quant Research Worker Agent**, shortened
to **Worker** after its first mention. The base language model remains frozen.
The Evolver changes the surrounding prompt, tools, memory, middleware,
validation, routing, and research workflow. Because an agent is treated as the
coupled system of a model and its harness, changing the harness creates a new
Worker Agent version with different operational capabilities without claiming
that the model weights were trained.

The paper's central contrast is therefore:

```text
output-level quant evolution
    fixed agent -> many factors, strategies, models, or programs

agent-capability evolution
    many harnessed Worker Agent versions -> improved future research behavior
```

The two levels are complementary. A better Quant Research Worker Agent may
later perform factor or strategy discovery, but this paper studies the outer
agent-capability evolution problem rather than proposing another alpha-mining
algorithm.

## Relationship to prior concepts

The method should attribute its conceptual foundations directly.

- From [Agentic Harness Engineering](https://arxiv.org/abs/2604.25850), it
  borrows the view that prompts, tools, middleware, memory, and related runtime
  components form an editable agent harness, and that observed trajectories can
  support component- and decision-level harness evolution.
- From [TTT-Discover](https://arxiv.org/abs/2601.16175), it borrows the broader
  idea of accumulating evaluated attempts during problem-time discovery and
  using that experience to improve later attempts. TTT-Discover updates model
  policies; this project instead adapts the harness around a frozen model.
- From quantitative evolution systems such as
  [QuantaAlpha](https://arxiv.org/abs/2602.07085),
  [RD-Agent(Q)](https://arxiv.org/abs/2505.15155), and
  [QuantEvolve](https://arxiv.org/abs/2510.18569), it borrows the use of
  executable quantitative feedback and multi-round research trajectories. The
  distinction is that those systems primarily evolve factors, strategies, or
  factor-model configurations, whereas this project treats the Worker Agent's
  harness-mediated capability as the persistent evolutionary state.

The novelty claim must not be that harness evolution, runtime experience, or
quantitative-agent iteration was invented here. The intended contribution is
their combination around a quantitative research process representation and an
agent-capability evolutionary object.

## Conceptual model

Let the fixed base model be \(M\), the harness at candidate version \(i\) be
\(H_i\), and the resulting Quant Research Worker Agent be

\[
A_i = \operatorname{Agent}(M, H_i).
\]

The model remains fixed while the harness changes:

\[
M_i = M_0, \qquad H_i \rightarrow H_{i+1}, \qquad A_i \rightarrow A_{i+1}.
\]

When \(A_i\) executes quantitative-research task \(q_j\), it produces a
**Quant Research Trajectory** \(\tau_{i,j}\). The trajectory is the complete
observable research episode rather than only the final answer. It may contain
the public task contract, tool use, artifact revisions, local checks, execution
failures, final deliverable, and evaluator feedback available under the
declared evidence split.

The task and trajectory must remain distinct:

- a **Quant Research Task** is the research problem and its environment;
- a **Quant Research Trajectory** is one Worker Agent execution of that task;
- a **Worker Agent version** is the frozen model instantiated under one harness
  candidate;
- a **candidate version** is created by a material harness modification.

An evolution episode can be represented as

\[
e_{i,j} = (q_j, H_i, \tau_{i,j}, z_{i,j}, r_{i,j}),
\]

where \(z_{i,j}\) is a Research-State Diagnosis and \(r_{i,j}\) is the
official outcome. Accepted and rejected episodes remain available as
accumulated Evolver experience.

## Quant Research State

The **Quant Research State** is the Evolver's structured interpretation of a
Worker trajectory. It is an open representation of the parts of a
quantitative workflow that are relevant to the observed failure or success,
not a closed list of benchmark answers or task-specific error patches.

Possible state dimensions include:

- data source, lineage, frequency, sample, and universe;
- observation time, information time, windows, and temporal alignment;
- target quantity, units, grouping, aggregation, and missing-data semantics;
- estimator, parameters, annualization, and uncertainty treatment;
- signal mapping, portfolio normalization, rebalance, execution, and costs;
- artifact construction, validation, finalization, and delivery state.

The intended reasoning chain is:

```text
observed trajectory
    -> relevant Research-State mismatch
    -> missing or unstable Worker capability
    -> target harness component
    -> predicted change in Worker behavior
    -> next evaluated Worker trajectory
```

Research State is useful only if it helps the Evolver localize or construct a
better intervention. It must not be presented as a contribution solely because
the fields have quant-related names.

## What it means to evolve Agent capability

The paper uses **Agent capability** to mean an observable, harness-mediated
ability of the Quant Research Worker Agent. Examples include the ability to:

- inspect and bind a public quantitative definition before implementation;
- distinguish information time from observation or execution time;
- select and apply the relevant estimator or aggregation semantics;
- retrieve prior positive and negative research experience;
- invoke a specialized executable tool when its preconditions hold;
- revise an artifact after a failed check and validate the revised version;
- complete and deliver the exact artifact required by the task.

Different harness components may implement different capabilities:

| Harness component | Example Worker capability |
|---|---|
| Prompt | General research policy and prioritization |
| Tool | Executable inspection, estimation, or validation operation |
| Memory | Retrieval of previous accepted and rejected experience |
| Middleware | State retention, revision, and completion behavior |
| Validator | Semantic and artifact checking |
| Routing | Selecting a relevant capability for the current task |
| Workflow | Sequencing research, implementation, validation, and delivery |

The paper may say that it evolves the Quant Research Worker Agent or its
operational capabilities. It must also state that the base model is frozen and
that adaptation occurs in harness space. It should not claim model training,
weight evolution, or fully autonomous self-improvement.

## Fixed evolution narrative

The submission-critical method follows this bounded narrative:

```text
Quant Research Task panel
    -> Quant Research Worker Agent A_i
    -> Quant Research Trajectories
    -> accumulated experience and Research-State Diagnosis
    -> Evolver proposes a component-level harness change
    -> Quant Research Worker Agent A_i+1
    -> fixed candidate evaluation
    -> accept or rollback
```

The outer coordinator, rather than the Evolver, schedules Worker runs and
defines the iteration boundary. This choice is both a scope reduction for the
submission sprint and a clearer scientific setup: candidate versions,
evaluation samples, and final selection rules remain explicit.

The future open-ended self-evolve scenario may be discussed as an extension in
which the Evolver also chooses experiments, Worker calls, branching, and
stopping. It must not be described as part of the method evaluated in the
current paper.

## Proposed paper title and thesis

The preferred working title is:

> **Evolving Quantitative Research Agents through Harness Adaptation**

An alternative that emphasizes the evidence source is:

> **Evolving Quantitative Research Agents from Runtime Trajectories**

The working thesis is:

> Most quantitative agents primarily optimize the artifacts they produce while
> keeping the agent scaffold fixed. We instead evolve the effective
> capabilities of a Quant Research Worker Agent: each harness version produces
> quantitative-research trajectories, and an Evolver uses those trajectories
> to improve the tools, memory, validation, middleware, and workflows of the
> next Agent version.

## Writing outline

### Abstract

1. Quantitative agents produce increasingly complex research artifacts.
2. Many existing systems search over outputs while keeping the agent scaffold
   fixed.
3. Introduce the Quant Research Worker Agent as a frozen model under an
   evolvable harness.
4. Explain trajectory accumulation, Research-State Diagnosis, and
   component-level harness adaptation.
5. Summarize the eventual cross-benchmark evaluation and measured result once
   the submission experiments are complete.

### 1. Introduction

- Motivate the dependence of quantitative-agent performance on tools, memory,
  validation, and workflow rather than model knowledge alone.
- Contrast output-level evolution with Agent-capability evolution.
- Ask whether evaluated research trajectories can improve the Worker Agent that
  generates later outputs.
- State the three intended contributions: the evolutionary formulation, the
  trajectory-to-capability method, and cross-benchmark empirical evaluation.

### 2. Related Work

- Quantitative agents that evolve factors, strategies, programs, or
  factor-model configurations.
- General agent harness evolution, with AHE explicitly acknowledged as a
  conceptual and architectural foundation.
- Test-time and runtime-experience discovery, with a clear distinction between
  TTT-Discover's parameter update and this method's harness adaptation.

### 3. Problem Formulation

- Define the fixed model, versioned harness, Quant Research Worker Agent,
  quantitative-research task, Worker trajectory, evaluator outcome, and
  accumulated experience archive.
- Clarify that the persistent evolutionary state is the harnessed Worker Agent,
  not a single factor or strategy artifact.
- Define the evidence boundary between Evolver-visible optimization experience,
  answer-blind Worker inputs, and frozen final evaluation.

### 4. Evolving the Quant Research Worker Agent

- Quant Research Worker Agent: frozen model plus evolvable harness.
- Quant Research Trajectories as evolution experience.
- Research-State Diagnosis as an open quant process representation.
- From diagnosed failure to missing Agent capability.
- Full-harness capability adaptation across prompt, tools, memory, middleware,
  validation, routing, and workflow.
- Cumulative experience across accepted, rejected, inactive, and unstable
  component attempts.
- The fixed outer evolution loop and explicit candidate-version boundary.

### 5. Empirical Evaluation

This section is intentionally left at the level of research questions. The
main experiment protocol will be designed separately after the idea and method
are frozen.

- Does harness adaptation improve a frozen Quant Research Worker Agent?
- Do structural harness components provide value beyond prompt-only evolution?
- Does Research-State Diagnosis improve intervention localization beyond
  domain-general trajectory feedback?
- Does cumulative positive and negative experience improve later evolution?
- Which capabilities remain task-specific, and which recur across quantitative
  tasks or benchmarks?

### 6. Analysis and Limitations

- Distinguish a proposed component from one actually activated by the Worker.
- Analyze which operational capabilities were added, reused, unstable, or
  rejected.
- Separate benchmark adaptation from broader quantitative-research transfer.
- State that Worker experiment scheduling is externally fixed in the current
  method.
- Treat autonomous Worker-call selection, long-horizon search, and cost-aware
  scheduling as future work.

### 7. Conclusion

- Restate the shift from evolving quantitative outputs to evolving the Worker
  Agent that produces them.
- Emphasize frozen-model, harness-space adaptation from accumulated research
  trajectories.
- Avoid claims beyond the final measured benchmark evidence.

## Suggested main figure

The first figure should show the research idea rather than infrastructure:

```text
Quant Research Task
        -> Quant Research Worker Agent A_i
        -> Quant Research Trajectory
        -> Research-State Diagnosis
        -> Evolver
        -> harness adaptation H_i -> H_i+1
        -> Quant Research Worker Agent A_i+1
```

An experience archive connects prior trajectories, component changes, and
outcomes to the Evolver. A caption should state that the model remains frozen,
Worker execution is externally scheduled, and the next Agent version differs
through its harness.

## Claim boundaries

The writing may claim, once supported by the final experiments:

- harness-mediated evolution of a Quant Research Worker Agent;
- use of accumulated quantitative-research trajectories as evolution
  experience;
- component-level changes beyond prompt mutation;
- observable changes in Worker behavior and official task performance;
- cross-task or cross-benchmark reuse only where measured.

The writing must not claim without separate evidence:

- evolution or training of base-model parameters;
- real-market alpha or live-trading performance;
- universal quantitative-research capability;
- fully autonomous experiment scheduling or stopping;
- out-of-sample generalization from a task that influenced candidate selection;
- novelty merely from renaming generic failure classes with finance terms.

## ICLR writing constraints

The current official ICLR 2027 guidance sets a nine-page main-text limit,
excluding references, and requires double-blind submission and an AI-use
statement. Core method and evidence must therefore remain in the main paper;
complete task tables, prompts, trajectory schemas, component records, runtime
configuration, and additional cases can be placed in the appendix. The writing
should remain centered on a machine-learning question---whether runtime
experience can adapt an Agent's effective capabilities in harness space---with
quantitative research supplying the structured domain and empirical setting.

This document freezes the idea construction only. The main experiment design
will be recorded separately rather than retrofitted into this writing outline.
