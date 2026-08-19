# Story Mainline: Research-State-Guided Evolution of Quant Research Agents

## 1. Starting point

Quant agents increasingly execute complete research assignments rather than
only answer finance questions. They inspect task materials, work with data,
represent a quantitative problem, perform estimation, pricing, calibration,
backtesting, risk analysis, or another research operation, check the result,
and produce an executable artifact.

Existing quant-evolution systems commonly keep the research agent fixed while
searching over what it produces:

```text
fixed quant agent
    -> factor / strategy / model / research-program candidates
    -> quantitative evaluation
    -> select or refine the research output
```

Our object of evolution is one level higher. We ask whether a quantitative
research agent can improve how it performs future research tasks by adapting
the harness around a frozen model.

We call the task-solving agent the **Quant Research Worker Agent**, or
**Worker**. At candidate version $i$,

```text
A_i = Quant Research Worker Agent(M, H_i)

M   = frozen base model
H_i = prompts, tools, memory, middleware, validators, routing, and workflow
```

The Evolver changes $H_i$, not the model weights and not the benchmark
verifier. A new harness version therefore defines a new effective Worker Agent
version.

## 2. A minimal quant-aware starting point

All compared evolution methods start from the same **Quant-H0**. Quant-H0 is
deliberately small but domain-calibrated. It contains only:

- the Quant Research Worker Agent identity;
- the names and short explanations of six Research States;
- one shell tool; and
- the basic ability to read inputs, run code, and produce the requested
  deliverable.

It contains no evolved component library, prior candidate history, failure
classifier, task answer, component-selection policy, or state-transition
diagnosis.

The six Research States are:

1. **Research Mandate & Contract** --- what research task and deliverable are
   required;
2. **Research Evidence & Data** --- what information and data support the
   work;
3. **Quantitative Representation** --- what quantitative objects, assumptions,
   and relationships represent the problem;
4. **Research Operation** --- what task-appropriate research operation is
   carried out;
5. **Evaluation & Reconciliation** --- how intermediate and final results are
   inspected and reconciled; and
6. **Research Artifact & Completion** --- how the requested executable
   artifact or other deliverable is assembled and completed.

These are states of a research process, not the fixed stages of a trading
strategy. A task may revisit a state or mark one as not applicable. A
QuantCodeEval strategy can instantiate Research Operation as feature
construction, estimation, signal generation, portfolio construction, and
execution. A QFBench task can instead instantiate it as derivative pricing,
curve calibration, risk decomposition, simulation, attribution, or another
quantitative operation. The outer state representation remains the same.

## 3. A Worker run becomes research experience

One Worker attempt on a task produces a **Quant Research Trajectory**: the
observable sequence of task interpretation, evidence inspection, tool calls,
artifact construction, checks, revisions, and completion behavior. It also
produces a final artifact and an official benchmark outcome.

The Evolver does not treat a failed trajectory only as a scalar score or a
generic bug report. For the relevant part of the task, it reconstructs:

```text
task-conditioned expected Research State
    versus
Research State realized by the Worker trajectory and artifact
```

It then locates the earliest consequential mismatch for which the available
evidence can distinguish at least two plausible explanations. The representation
is open inside each state: the Evolver is not restricted to a closed list of
finance failure types.

## 4. Research-State-guided harness search

For an intervention, the Evolver must make the following chain explicit:

```text
Worker trajectory and artifact
    -> expected Research State
    -> observed Research State
    -> competing explanations of the mismatch
    -> selected harness component
    -> predicted target Research State
    -> concrete transition observable
    -> candidate harness H_i+1
```

The six states narrow the search question without determining the answer. A
Mandate mismatch may require retrieval, memory, or a prompt policy; a Research
Operation mismatch may require a tool, skill, or validator; an Artifact &
Completion mismatch may require middleware, routing, or agent configuration.
The Evolver chooses among the full harness mutation surface from actual
trajectory evidence.

A task-conditioned quantitative invariant can be used as the transition
observable. Examples include temporal-prefix consistency, estimator fit-scope,
quantity relations, portfolio accounting, cost monotonicity, or fresh artifact
replay. Invariants are therefore not a separate benchmark and not the complete
method. They are executable observations used when they can discriminate
whether the predicted Research State transition occurred.

For this to be a method rather than an annotation layer, the transition
contract must affect control flow. The Evolver must predeclare the component
activation predicate and transition observable before the fresh Worker run.
Candidate retention, refinement, or rollback must then use activation and
state-transition evidence independently of the official score. If the six
states appear only in an explanatory report while candidate selection remains
unchanged, the system is only AHE with a quant-specific debugger vocabulary.

## 5. Intervention verification

The candidate is evaluated by a fresh Worker. We keep four observations
separate:

1. **Component activation:** did the Worker actually reach and use the changed
   harness component?
2. **Research State transition:** did the expected mismatch change toward the
   predicted target state, measured through trajectory, artifact, or an
   applicable invariant?
3. **Official outcome:** did the unchanged benchmark verifier report a property
   or binary task improvement?
4. **Stability and scope:** did the effect repeat, preserve a protection task,
   or appear on a task with a matched Research State mismatch?

An activated component with no predicted state change is a mislocalized
intervention. A predicted state transition without an official gain is useful
mechanism evidence but not benchmark improvement. Only the official verifier
supports a benchmark claim; repeat, protection, or matched transfer supports a
stronger reusable-capability claim.

Positive, negative, inactive, and unstable interventions all remain in
Evolver experience. Later candidate versions can retrieve which Research State
was involved, which component was attempted, whether it activated, which state
transition occurred, and what official outcome followed.

When ordinary evidence inspection cannot locate the mismatch, the Evolver may
later receive an optional callable Quant Research Reviewer. The call is an
investigation operation rather than a second decision maker: it searches the
authorized runtime evidence for the expected and observed Research State,
cites the evidence supporting the mismatch, maintains competing explanations,
and proposes a discriminating observation. The Evolver still decides whether
to intervene, which component to modify, and whether the returned evidence is
sufficient. Reviewer calls and their useful or unhelpful results become part of
the accumulated search experience.

## 6. Relationship to prior work

We adopt the outer harness-evolution object from
[Agentic Harness Engineering](https://arxiv.org/abs/2604.25850): a frozen
model's prompts, tools, memory, middleware, and workflow are editable, and
execution histories inform later harness versions. We do not claim to invent
harness evolution, trajectory accumulation, candidate rollback, or frozen
evaluation.

Our proposed difference is the search and verification representation. AHE
uses domain-general layered execution reports, root-cause hypotheses, edit
predictions, and downstream task deltas. We represent a quant task as an open,
task-conditioned Research State process. The Evolver searches for a component
that should mediate one explicit expected-to-observed-to-target state
transition, and later experience separates component activation, state
transition, and official quantitative outcome.

Relative to AQuA, QuantaAlpha, RD-Agent(Q), and similar quant-research systems,
we do not primarily evolve the factor, strategy, model, or experiment proposal.
Those artifacts remain Worker outputs. The persistent evolutionary object is
the harness that determines how the Quant Research Worker Agent performs later
assignments.

The controlled comparison must start AHE-on-quant and our method from the same
Quant-H0, with the same editable surface, models, optimize tasks, answer policy,
and evaluation budget. Otherwise a gain could come from the quant-aware seed or
additional sampling rather than Research-State-guided search.

## 7. Compact story

> Quant research agents fail not only because a final answer is wrong, but
> because the research process enters the wrong task-conditioned state: it may
> represent the mandate, evidence, quantitative object, operation, evaluation,
> or final artifact incorrectly. We initialize a minimal Quant Research Worker
> Agent with only this general state vocabulary. An Evolver reconstructs the
> expected and observed Research State from Worker trajectories, selects a
> harness component intended to mediate a specific state transition, and tests
> that intervention in a fresh Worker through component activation, observable
> state correction, and unchanged official outcomes. The model remains frozen;
> the Worker Agent improves through accumulated harness adaptations.

The intended contribution is not a renamed AHE loop or a six-stage strategy
taxonomy. It is the hypothesis that an open quantitative Research State
representation, coupled to executable state-transition observations, can make
full-harness evolution more diagnostic and evaluation-efficient than generic
trajectory-to-task-delta search.

This remains a proposed method until a matched AHE-on-quant comparison and the
Research-State search ablations are measured.

Implementation status on 2026-08-19: Quant-H0, the proposal-side structured
`research_state_transition` contract, and the outcome-side dual-parent
selection are implemented and locally tested. A supported transition with real
component activation can advance the search parent without changing the
official incumbent; inactive or unsupported transitions are retained without
promotion. The Evolver-callable Reviewer is recorded but not implemented. No
benchmark benefit is claimed from the current implementation.
