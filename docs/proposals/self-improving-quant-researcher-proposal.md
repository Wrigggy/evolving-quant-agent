---
title: "Learning to Become a Better Quantitative Researcher"
subtitle: "Self-Improvement through Research-Method Experimentation"
document: "Active research proposal | ACL target | Adopted 16 September 2026; evidence-centered consolidation 29 September 2026"
date: "6 October 2026"
short_title: "Self-Improving Quantitative Research"
abstract: |
  Quantitative research requires choosing how an economic question is measured, estimated, implemented and evaluated. We propose research-method experimentation: a researcher investigates its own episodes, uses public economic, information and estimation conditions to select informative experiments, and revises its complete persistent harness. Worker and Evolver are execution and method-revision roles with fixed model configurations and a declared revision policy. A separate versioned research memory can preserve lessons independently of candidate acceptance, while retaining the original comparison and applicability. The central empirical result is a complete controlled BacktestBench comparison: the evolved frozen harness scores 16/20 against the initial harness's 14/20, with two task gains and zero regressions across 20 new instances. The Evolver diagnosed that the initial Worker evaluated round-trip performance using full-window daily mark-to-market P&L, conflating unrealized and realized gains across multi-day holds; the accepted revision scopes evaluation to window-only indicators and realized round-trip PNL, with consequential fresh-Worker uptake confirmed in four consumer checks. QuantCodeEval results across the same evolved harness remain mixed (closed twenty-task checkpoint binary 2/9; Pro Evolver fork binary 2/4 to 3/4 with one regression and QF 4/4 ties), which is consistent with the conditional nature of research-method improvement: a backtesting measurement policy does not transfer to tasks requiring different research operations. Executable harness components beyond prompt-level changes and cumulative multi-task benefit remain open empirical targets.
---

# 1. Introduction

An autonomous quantitative researcher should become better at conducting research, not merely produce another artifact. Finding a stronger factor and improving the ability to formulate, implement and assess future factors are related but different achievements. This proposal studies reusable research capability acquired through experience.

Why make methodology a learning object? Menkveld et al. distinguish the data-generating process from the researcher's evidence-generating process: teams analyzing the same financial data and hypotheses produce materially different evidence [1]. Arnott, Harvey and Markowitz likewise emphasize choices about economic motivation, data construction and evaluation [2]. These findings do not make every disagreement an error. They establish that working methods matter beyond information access and code execution.

We ask: **can a quantitative research agent improve its own reusable capabilities by experimenting on the way it conducts research?** Worker and Evolver are execution and method-revision roles of one system. The complete persistent Worker harness carries the evolving capability, including prompts, executable tools and bindings, skills, memory/context handling, middleware, validators, routing and control flow. Models and the declared revision policy stay fixed within a registered condition; historical investigator changes are not one recursively self-improving algorithm.

The proposed mechanism is **research-method experimentation**. The Evolver investigates an observed operation, identifies a limitation or opportunity, chooses evidence that can distinguish explanations, and develops a reusable intervention. Quantitative judgment enters through what is being estimated, which information is admissible and how the result is consumed. A timing check must reach the position decision; a volatility-scale check must reconcile units; an estimator comparison must preserve its target and sample. These are examples, not a compulsory workflow or a new finance theorem.

The sharper operational question is whether the researcher learns both a useful
operation and when that operation answers the current quantitative question.
An operation connects inputs, computation or decision, and a required output;
its applicability depends on the target quantity, sample, information convention
and intended use. Evidence may justify reuse, adaptation, replacement or nonuse.
Writing those conditions into a record does not implement this judgment, and a
checker invocation does not establish its benefit. The condition must change a
real investigation or persistent revision and matter to later Worker behavior.

Two decisions remain separate. Official outcomes determine whether to retain a complete candidate. Methodological evidence determines whether to retain, narrow, revise or defer a lesson. A rejected candidate may reveal an unsupported assumption; a selected candidate need not validate every explanation in its rationale. Research memory therefore needs its original experimental comparison and conditions, not merely a score, success label or generalized advice.

Harness evolution, adaptive memory and evolving quantitative agents are direct precedents [7, 8, 9, 18, 19]. We do not claim novelty from an outer loop, mutable tools, a scalar fitness score or generic memory. The intended contribution is operational and empirical: a quantitative condition changes an experiment or intervention, that change persists in the complete harness, and later research benefits. Generic harness search might also discover this behavior; comparative superiority requires an appropriate control.

For language agents, this connects task-level reasoning with persistent changes in how later instructions are interpreted, methods selected and tools used. Our three evidence targets are a better frozen complete researcher on the same tasks; actual revisions and consequential fresh Worker use, including quantitative cases and negatives; and cumulative multi-task work with measured context, checking and evaluation cost. We claim neither investment profitability nor unrestricted scientific expertise.

**Current evidence boundary.** The central empirical result is a complete controlled BacktestBench comparison: the evolved frozen harness scores 16/20 against the initial harness's 14/20, with two task gains and zero regressions across 20 new instances. The Evolver diagnosed that the initial Worker evaluated round-trip performance using full-window daily mark-to-market P&L, conflating unrealized and realized gains across multi-day holds; the accepted revision scopes evaluation to window-only indicators and realized round-trip PNL. Four fresh-Worker consumer checks confirm consequential policy uptake in the promoted candidate. This demonstrates that research-method experimentation can identify a measurement-methodology limitation and produce a matched initial-to-frozen improvement on backtesting tasks.

QuantCodeEval results across the same evolved harness remain mixed: the closed twenty-task checkpoint gives binary 2/9 on paired QCE tasks; the Pro Evolver fork gives QCE binary 2/4 to 3/4 with a two-check T18 regression and QF 4/4 ties. This is consistent with the conditional nature of research-method improvement — a backtesting measurement policy does not transfer to tasks requiring different research operations. Executable harness components beyond prompt-level changes and cumulative multi-task benefit remain open empirical targets. The Evolver's prompt-skepticism constraint (now requiring executable components for computational failure classes) is the active mechanism improvement targeting these gaps.

The full pre-consolidation chronology is preserved in the [archived proposal](history/2026-09-29-before-evidence-centered-consolidation.md). Relative decision links in that exact archive refer to this original proposal directory; its dated pending/running statements are historical, not current status.

# 2. Foundations: why learning to do quantitative research matters

## 2.1 Research choices shape financial evidence

The evidence-generating-process perspective makes a useful distinction: uncertainty can arise from how data are analyzed, not only from which observations happened to be sampled. The analysis paths documented by Menkveld et al. include measure construction, sampling frequency, treatment of observations, and statistical specification [1]. These are recognizable research operations rather than abstract agent states.

Our inference is that such operations are legitimate learning targets. An agent may improve by selecting a more appropriate measure, implementing an estimator more faithfully, or recognizing that a previous procedure does not answer the current question. The goal is not to minimize disagreement or impose a single methodology. It is to improve the capacity to make and carry out justified research choices.

The distinction persists with AI. Gao and Xiao report substantial methodological variation among 150 autonomous coding agents conducting financial analysis. Their preprint also cautions that convergence after exposure to exemplars need not establish understanding or correctness [3]. We therefore require a learned capability to affect an actual subsequent operation; repeated advice or imitation alone is insufficient evidence of capability improvement.

## 2.2 Quantitative judgment is conditional, not a universal checklist

We use the following synthesis: **quantitative research outcomes depend on how economic questions are translated into measurement, estimation, and evaluation procedures.** This is our formulation of the motivation, not a quotation or a named theorem.

Specific finance results support parts of this view. Hansen and Richard show how conditioning information affects testable asset-pricing restrictions and mean-variance analysis [4]. DeMiguel, Garlappi, and Uppal show, in their studied portfolio settings, that estimation error can offset the advantages of optimization [5]. These results do not prescribe one universal procedure. They motivate attention to what is being estimated, which information is admissible, and whether the chosen method is appropriate for its data and intended use.

For the Evolver, this means that a successful operation is not automatically a universal rule. A full-sample transformation can be legitimate in retrospective description but inappropriate for a prediction restricted to historically available information. A more elaborate estimator can introduce rather than remove error. An intervention should improve the relevant research decision or operation under stated conditions, rather than simply add complexity.

A narrowly scoped T01 investigator case illustrates the distinction. Moskowitz,
Ooi, and Pedersen's published variance equation centers every exponentially
weighted return on one endpoint mean [23]. Executing the unchanged original
expanded-H0 variance, volatility, and sizing functions on 180 complete synthetic
business-day returns yields six eligible months, an actual/reference variance
ratio of 60/61, a volatility ratio of 0.9917694073609298, and an inverse-volatility
position ratio of 1.0082988974836113. The primary source resolves the centering
target, but not finite initialization, calendar, warmup, missing-data treatment,
or any hidden official expectation. The script is investigator-only and is not
an Evolver observation, harness edit, learning result, or benchmark-failure cause;
see the [source and consumer record](../decisions/2026-09-28-t01-endpoint-centering-source-resolution.md).

## 2.3 Economic structure can guide flexible learning

Chen, Pelger, and Zhu incorporate no-arbitrage conditions into the learning criterion of a flexible asset-pricing model and construct informative test assets [6]. The methodological precedent is that economic structure can influence what a learning system searches for and how it evaluates alternatives. It need not appear only as background knowledge.

Our design transfers this principle to research-capability development. Applicable economic or statistical structure should influence the Evolver's next experiment or intervention. The official benchmark objective remains unchanged. We do not impose a universal no-arbitrage loss on heterogeneous tasks, fit a Bayesian posterior without an implemented model, or claim econometric guarantees for harness search.

Together, these sources justify the importance of the problem and motivate the design. They do not prove that autonomous capability revision will succeed. That is the empirical question of this proposal. Elementary identities and numerical examples belong in diagnostic cases, not in a separate theory section presented as an explanation of self-evolution.

## 2.4 The value of an experiment is its decision consequence

Decision theory provides a narrower motivation for choosing the next research
action. Frazier, Powell and Dayanik's knowledge-gradient policy values an
observation through expected terminal decision utility under a specified
Gaussian ranking-and-selection model [26]. Donti, Amos and Kolter train models
against the downstream stochastic-optimization objective rather than an
unrelated prediction criterion [27]. These motivate two questions for our
researcher: could the observation change a justified intervention, and which
consumer makes the distinction matter? We do not implement their algorithms,
estimate a Bayesian acquisition value, differentiate through a downstream
optimizer, or inherit their guarantees. The proposed research-comparison policy
is a qualitative decision rule over executable experiments, whose usefulness
must be measured through actual decisions and fresh Worker outcomes.

# 3. Related work and intended distinction

## 3.1 Harness adaptation

The [October4 adversarial review](../decisions/2026-10-04-comparison-applicability-novelty-and-conditional-tests.md)
further narrows the claim. [HarnessBank](https://arxiv.org/html/2607.13683v2)
already combines diverse harness archives, activation gates and repeated
paired screening with held-out evaluation. AQuA also conducts event/control
comparisons and changes financial conditioning variables. Neither transfer,
conditional memory nor an independently checked edit is standalone novelty.
If an appropriate operation actually evolves, a small conditional test should
ask whether it preserves useful reuse under compatible quantity/support/
information conditions while adapting or declining an incompatible use.
Removing the whole tool only tests tool usefulness; no such effect is assumed.

Agentic Harness Engineering connects editable components, execution experience, edit predictions, and outcomes [7]. Meta-Harness gives an agentic proposer access to full candidate source, scores, and traces, and reports confound diagnosis, targeted experiments, and conditional inference procedures [8]. Evo-Memory benchmarks test-time self-evolving memory; its ReMem baseline interleaves reasoning, action, and active memory refinement [19]. Full-code mutation, evidence-backed revision, adaptive experimentation, and contextual reuse are therefore precedents. Our narrower target is whether experience teaches when an earlier numeric comparison supports a current claim given its requested quantity, realized sample support, and admissible information, and can change later Worker computation—for example, through recomputation, public-source inquiry, or nonreuse. Generic harness search may discover the same behavior; superiority requires a controlled comparison.

Executable memory is also established: Mem²Evolve combines experience with
dynamically created assets [20], while RRSI regularizes harness proposals and
selection using edit sparsity, history, criticism and pruning [21]. Our current
typed research-memory interface is not a new general memory algorithm. Its
empirical question is whether a short experience is later read and revised, or
an operation is rebound, adapted, or rejected, under current measurement,
sample-support, and information conditions—and whether that use changes a later
revision and Worker. Library learning additionally requires behavioral reuse
evidence and compute accounting [22]. A matched final Worker comparison with
separately reported search cost does not by itself establish equal-total-compute
search superiority.

CoEvoSkills co-evolves multi-file skills with an information-isolated surrogate
verifier and documents a false rejection caused by that verifier's own
estimator [24]. These are direct precedents, not our novelty. The narrower
unproven target is a public-condition experiment that changes an operation or
its scope and matters to a fresh Worker. Recent harness-evaluation work also
reinforces the need for matched total search budgets and held-out tasks when
claiming efficiency or generalization [25]; this pilot does not make those
stronger claims.

## 3.2 Evolving quantitative research systems

AQuA retains contextual evidence to revise beliefs and guide factor/model search [9]. AlphaMemo learns success/failure edit motifs conditioned on a parent factor, with confidence-gated residual memory and asymmetric veto [18]. QuantaAlpha evolves alpha-research trajectories; RD-Agent-Quant adaptively coordinates factor and model development; and AlphaAgent regularizes exploration [10, 11, 12]. These establish contextual evidence reuse or suppression and adaptive workflows. We ask whether old evidence supports the current quantity under realized support and admissible information, and whether a persistent operation responds to an inadequate comparison—for example, by recomputing or seeking source evidence—rather than only selecting a factor or model edit. This remains unverified until whole-harness evolution changes a fresh Worker on conditions not encoded by an investigator fixture; it implies no superiority.

## 3.3 Adaptive tests and evidence applicability

Adaptive metamorphic testing already learns context-dependent relation selection from executed feedback [16]. Prior work also studies whether a violated relation indicates a program defect or a relation that is inapplicable to the particular inputs [17]. Neither feedback-based test selection nor questioning a checker is new here. The current investigator-only fixture holds its query and source inputs fixed, checks actual output-key and finite-value support for an investigator-fixed T12 quantity, and routes a computation or public-source lookup. It cannot distinguish different quantities, sources, input values, or information semantics with the same support, and is not learned behavior. The next empirical question is whether an evolved shared harness makes an evidence-validity judgment change a fresh Worker's computation on conditions not encoded by the fixture.

# 4. Problem formulation

Let $M_W$ and $M_E$ denote fixed Worker and Evolver foundation-model configurations. Let $H_k$ be the complete persistent Worker harness after round $k$, through which the changing capabilities deployed to fresh Workers are realized, and $q$ a public quantitative task. A fresh execution produces an artifact $a_k$ and trajectory $\tau_k$:

$$
(a_k,\tau_k)\sim W(M_W,H_k,q;\omega).
$$

Here $\omega$ specifies the declared Worker execution conditions and randomness. The harness contains prompts, tool implementations and descriptions, bindings, executable or textual skills, memory/context operations, middleware, Worker-side validators, routing, and research control flow. Task outputs are not automatically persistent capabilities.

The Evolver uses selected episode evidence $B_k$, an identified observed episode
$\tau_k^{\mathrm{obs}}$, the actual retained parent, and typed research memory
$\mathcal R_k$. The memory may contain optional executable operations and optional
non-executable short experiences. Both retain revisable conditions and evidence;
only an executable operation carries runnable source and rehearsal history. The
Evolver may update this research-time state while proposing a complete Worker
revision:

$$
(\widetilde H_{k+1},\mathcal R_{k+1})\sim
G(M_E,H_k,\mathcal R_k,q,\tau_k^{\mathrm{obs}},B_k).
$$

The observed episode may belong to the current package or an explicitly identified
ancestor when an unscored candidate is being refined. A completed candidate episode
selected as feedback can pair its public method source and task definition, actual
parent-to-candidate diff, actual fresh-Worker trajectory and artifact, and that
candidate's own outcome. When abstention or an infrastructure failure prevents one
or more layers from existing, the record retains only the evidence actually
produced and marks the rest absent or not run. Its behavior and score are not
silently attributed to the current mutation parent.

The outer-loop notation is descriptive, not a new learning theorem. A candidate can add, compose, replace, narrow, or remove a capability. An unchanged parent is also a valid outcome. The revision driver $G$—its declared instructions, interfaces, permissions and execution settings—is fixed within a declared experiment or final campaign. Its effective research behavior can change through an exact-read experience or a program in $\mathcal R_k$ without updating model weights or rewriting that driver. The controller retains the actual $\mathcal R_{k+1}$ independently of whether $\widetilde H_{k+1}$ is accepted, including after ABSTAIN, a rejected candidate, or a qualified failure; neither persistence nor visibility is improvement. Historical development uses successive investigator-authored profiles, settings, evidence projections, and decision interfaces, so it is not retroactively treated as one fixed-policy campaign.

Measurement completeness is distinct from both transitions. A declared task
window retains all task identities even when only a subset has a genuine
official measurement. Its metric mapping contains only that measured subset;
coverage records each task without an official measurement as explicit null
with a reason. An officially evaluated delivery failure retains its actual
result in the measured subset even when no artifact was delivered. Nulls are
neither imputed zeros nor selectable evidence, and a partial window has no
selection key. Independently replayable delivered siblings are
evaluated once, while already failed or partial evaluator outputs are retained
without automatic redraw. In the original expanded campaign, an incomplete
parent window caused the controller to archive it, skip $G$ and candidate
evaluation, and carry both $H_k$ and $\mathcal R_k$ forward. The separately
registered checkpoint condition instead permits investigation from a delivered
active task and observation of an admitted candidate on the original full
windows, even when the parent window is incomplete. It retains all missing
measurements and does not permit promotion from a partial comparison. This
investigator-authored continuation policy is fixed within that condition, not
a learned capability. If a candidate window is incomplete after a revision,
the parent $H_k$ remains, while the actual $\mathcal R_{k+1}$ produced by that
revision is retained. Only complete comparison windows can select a new harness;
an incomplete window is not a complete negative test of its proposed capability.

One shared harness may take different paths under different public conditions. It is neither a mandatory universal workflow nor a task-ID lookup table of best solutions. The final endpoint is a frozen complete package $H^*$ evaluated against the declared initial package $H_0$ on the same task panel.

Neither benchmark Worker receives Evolver research memory $\mathcal R$.
Research-time reuse is evaluated separately through cross-round traces linking a
retained typed item, a later exact read or execution, the subsequent investigation
or harness revision, and fresh-Worker consequence. A final score gain does not
independently identify the memory effect.

The historical QuantCodeEval Worker seed uses ordered S1--S6 telemetry; those labels do not prescribe a universal research procedure, and Evolver diagnosis remains open. The existing QFBench entry point instead uses its separately declared shell-only seed; the two campaigns do not share an identical initial package. **Adopted, locally implemented and measured as a new initial cell:** the September18 minimal-seed follow-up creates a separate QuantCodeEval lineage starting with a functional three-file shell-capable agent and no preinstalled workflow or mandatory state-reporting calls. Its first T12 observation/replay is reported below. This investigator-authored startup choice does not replace the historical measured seed, establish a workflow-removal effect or constitute Evolver learning.

Official evaluators remain outside the mutation surface. The Worker receives public task inputs and the reusable package. In the current registered campaigns, neither Worker nor Evolver receives trusted tests or reference answers; Evolver feedback can include permitted safe official aggregates from completed attempts. Any differently declared historical answer-rich regime remains a separate condition, not evidence for this public-evidence-only setup. Reference material never becomes a task-specific answer patch in the learned package, and protection or separately held-out task evidence is not supplied to development revisions.

# 5. Method: research-method experimentation

## 5.1 Form a hypothesis about the researcher's working method

The method permits agent-proposed targets, but current operation-focused development cases include investigator-selected targets and evidence. These choices are attributed separately from Evolver diagnosis and implementation; the cases do not establish autonomous target discovery.

The Evolver begins with the layers actually produced by an identified research episode: the public question and method source and, when they exist, the parent and actual revision, artifact and trajectory, relevant operations, and candidate outcome. Layers missing after abstention or infrastructure failure are recorded as absent or not run rather than reconstructed. Keeping the available layers together prevents a generic failure label or an ancestor's score from standing in for the evidence produced by the attempted method. It asks which limitation in the current way of working could explain a failure, unnecessary effort, or missed opportunity. This is a hypothesis about capability, not merely a restatement of a wrong answer.

For example, a sequence of inconsistent estimates might suggest that the system lacks an explicit fit-scope interface, not that it needs another formula in its prompt. A correct helper that is repeatedly unused may suggest a selection or binding problem. A method that works for description but fails in prospective analysis may need conditional routing rather than replacement.

A useful capability hypothesis identifies the operation to change, why the change is relevant to the quantitative task, and what observable behavior would differ. These are reasoning obligations, not a compulsory multi-field schema. The Evolver can act on a supported, reversible improvement while unresolved alternatives remain.

## 5.2 Let quantitative judgment choose the next experiment

Our proposed selection criterion is whether an experiment's possible outcomes would change a justified capability decision. The Evolver may inspect a task definition and its public method source, execute an emitted function, construct a small public-data fixture, compare alternative information or estimation scopes, or trace how an estimate enters a downstream decision. The quantitative basis must affect the selected operation or revision, not merely its description.

Applicability is a property to investigate. An incompatible sample may call for recomputing alternatives on the current input; an unresolved definition may call for a targeted public-source inquiry; a discrepancy under an agreed definition may call for implementation repair. A correct estimate used under an incompatible mandate may instead require conditional method selection. These are alternative research actions, not a mandatory sequence or universal failure taxonomy.

Existing public-probe, operation-rehearsal and original-pair review interfaces support these investigations and evidence attribution. They do not themselves choose an informative experiment or establish useful capability learning. The declared revision instructions, interfaces and execution settings remain fixed within each registered experiment; investigator-authored development configurations are reported separately rather than treated as one fixed-policy sequence. Executable-memory interfaces likewise do not turn a stored short experience into a runnable operation.

The financial precedent is conditional interpretation and informative test-object construction: economic or statistical conditions specify which quantities matter and which observations could expose a limitation. Chen, Pelger and Zhu's informative test assets motivate this research question, not the present selection policy or its statistical validity. For example, a public requirement of neutral exposure can justify investigating whether an unused undefined ratio controls the position; it does not establish a universal missing-value rule. Different research quantities may legitimately have different information sets, so an input perturbation does not impose a universal invariance or sensitivity requirement.

Selecting an experiment is distinct from retaining its result. A publicly grounded operation hypothesis can justify a bounded, reversible candidate trial when the intervention is reachable and an observation could falsify its predicted effect; the official score direction can remain unknown. ACT does not assert that the candidate will beat the incumbent. Conversely, unknown evaluator preferences do not create evidence for an arbitrary intervention: if no supported operation or consequential test can be identified, ABSTAIN remains appropriate. These are operational selection criteria, not a calibrated value-of-information model or a new exploration theorem. Current runtime separates permission to investigate, unscored candidate qualification, fresh Worker observation, and later scored selection.

In a definition-sensitive case, the useful chain is:

> **public definition $\rightarrow$ selected independently delivered quantity $\rightarrow$ discriminating public numeric example $\rightarrow$ persistent harness decision.**

The selected quantity is not merely a waypoint on the way to a final sign or portfolio. When the task independently requires it as an output, it is itself a consumer-visible research product. Competing definitions can therefore differ materially at that output even when a sign transformation or later aggregation hides the difference. The resulting decision may revise, narrow, retain or remove an operation or its applicability.

The condition must have an operational consequence. Changing training support may require refitting, whereas a prospective protocol that fixes parameters may require preserving them. Tracing an estimation discrepancy to a required output or portfolio decision can likewise determine whether to investigate it further. These are possible capability targets, not mandatory stages or capabilities already established by the present system.

| Research decision | Quantitative basis | Potential capability consequence |
| --- | --- | --- |
| What should be measured? | Economic target, units, horizon, and public definition | Revise measure construction, interface, or method-selection policy |
| Which observations may inform it? | Information availability and estimation scope | Add or revise alignment, fitting, or state-handling operations |
| Is the method suitable here? | Estimation error, dimension, numerical domain, intended use | Choose or compose a suitable estimator and supporting computation |
| What would change the conclusion? | Downstream economic use and competing explanations | Select a discriminating experiment or revise research control flow |

These are examples of decisions, not four stages imposed on every task. Ordinary runtime or delivery repairs can proceed without a numerical experiment. A first draft that already implements the supported definition is valid evidence of method selection; the method does not require the Worker to make and then repair an error. Conversely, a numerical relation matters only when its applicability and observation influence an actual research choice. A fixture that separates candidate definitions is evidence about the selected quantity, not by itself evidence of official correctness or downstream payoff improvement.

**Proposed, not yet demonstrated as a learned capability:** constructing or reusing a comparison that preserves the requested quantity, realized sample and admissible information may improve investigation or revision. This requires an observed unresolved decision, an observation that could change it, and an actual consumer. Correcting explanatory statistics or repeating confirmation of an already chosen method is insufficient. A fresh Worker must consequentially choose or reconstruct a useful comparison before this supports acquired capability.

The detailed [E9–E12 method-development history](history/2026-10-05-method-development-cases.md) preserves the preceding subsection, including local qualification, actual candidate changes and fresh use, positive controls, official negative pairs, costs and proposed follow-ups. That record does not establish observation-dependent selection, general source adjudication or useful transfer; interface qualification and helper invocation remain distinct from learned research capability.

## 5.3 Develop a capability, including its path to use

The Evolver may modify any part of the complete harness. The user explicitly confirms the design priority: **完整 harness 都可改，优先实际生效**. This is neither prompt-only optimization nor a requirement to generate a tool each round. A coherent revision can span a tool implementation, argument description, binding, and activation policy. Alternatively, the correct intervention may be a context-handling change, a revised decision rule, or composition of existing operations.

Development includes inspection, implementation, and proportionate local tests. When uncertainty concerns a new component's actual behavior, an optional discardable draft can make that behavior available before final component attribution. This is a proposed refinement of the search interface, not a requirement to manufacture executable code. The current system already supports implementation and revision after an ACT decision; the optional change concerns the timing of candidate-behavior evidence. A reusable revision may improve how source evidence is read, how a required intermediate is selected, or how competing definitions are discriminated; it need not add another checker or executable tool.

Prompt revision is a first-class intervention when a public condition should change method selection or use of an existing operation; it is not executable-tool learning by itself. Existing profiles already write Worker prompts, as actual E28 demonstrates. In the minimal-lineage development record, `worker_effect_full_harness_v1`, `semantic_episode_full_harness_v1`, and `experimental_operation_full_harness_v1` are successive investigator-authored revision configurations. They change the requested evidence and decision interface while keeping all nine harness roles available; they are not three learned Worker packages or one policy held fixed across the full history. Within each registered experiment, the named configuration and settings are frozen. None forces a prompt, new tool, or source-code edit in every round, and a prompt-load smoke does not test predicted Worker behavior.

Research-time capabilities must be distinguished from artifact dependencies. A tool may help a Worker test and author a standalone submission without being imported by that submission. What matters is that a fresh Worker can invoke the operation and use its result. A file that is present but unreachable is not an acquired working capability.

## 5.4 Learn from subsequent research, not only from the draft

An admitted complete candidate is loaded by a fresh Worker before scored selection. We then observe whether the proposed operation was used, whether its output influenced research behavior, and what happened under the unchanged official evaluator. Use includes a source-grounded method choice made correctly in the first draft; it is not limited to a validator-triggered post-draft edit. When an intermediate quantity is an independently required output, the Worker's definition and numerical realization of that quantity are a consequential consumer path even if later signs or portfolio returns are unchanged. Local tests support development; they do not substitute for this observation.

The candidate can be retained for further investigation, adopted as the current best package, revised, or rejected. The search parent and the best officially evaluated package need not always coincide. A promising partial improvement may warrant continuation without being declared a binary success. Similarly, a quantitative explanation may be plausible even when the candidate regresses.

The positive target is increased capability: carrying out an operation previously missing, making a better method choice, or completing a quantitative assignment more faithfully. Abstention, validation status, and package admission are possible process outcomes, not the primary learning objective.

## 5.5 Accumulate methodological experience with conditions

Three forms of state are distinct. Complete packages $H$ carry Worker capability. Selected episode evidence $B$ provides actual public inputs, artifacts, traces, revisions and permitted outcomes. Typed Evolver memory $\mathcal R$ stores either an executable operation or a short non-executable experience. The latter can record its question, applicability, observation, lesson, counterevidence and unknowns, but contains no runnable source. Source references preserve provenance; they do not automatically remount old evidence.

The implemented interface indexes and searches both memory types and requires an exact-version read before decision citation. A deterministic bootstrap exposes at most four summaries and 8 KiB without operation source. This bounds initial visibility, not attention or total research work. Optional executable operations retain source and bounded rehearsal summaries. The current single-agent caller serializes mutations; this is not general concurrent-memory correctness.

Actual memory output is carried independently of complete-harness acceptance, including after abstention, rejection or a qualified failure. Missing or invalid output remains explicit. This lets the researcher learn from a rejected candidate without silently adopting that candidate as its Worker. A stored item can be narrowed, replaced or removed; growing the library is not the objective.

**Outcome-linked method review** addresses an observed consumer failure: the checkpoint's R2 substituted a later parent's result for the original experiment, while R6 preserved contradictory provisional lessons. The new opt-in interface attaches exact original parent/candidate facts and missing outcomes to an experience. Sources remain explicitly selectable rather than blended into a favorable comparison. After an exact read, the Evolver may retain, revise under the same ID, or defer the lesson. This is implemented investigator scaffolding with source and real remote-memory qualification, not yet a demonstrated model benefit.

Quantitative applicability should affect that decision. A lesson about a full-sample estimator need not support a point-in-time prediction; a timing check must refer to the same signal/position convention; a numerical comparison should preserve the requested quantity and realized sample. The interface does not provide an automatic correctness oracle, calibrated posterior or learned retrieval policy. A useful episode must show the model actually using those conditions to choose a different investigation, intervention or justified non-use.

The empirical record includes both empty-memory predecessors and real checkpoint formation/read/decision chains. Their detailed chronology remains archived; Section 8 reports current evidence and failures. The six-task method-review successor started from actual four-experience/six-version R6 memory, not a hand-written idealized memory. Its completed frozen-six comparison retains the unchanged initial H and byte-identical R; no memory-induced capability benefit is established. Neither memory persistence, an exact read nor a review receipt alone establishes improved Worker capability.

## 5.6 Algorithm

The following procedure specifies the proposed research loop. Its scientific hypothesis concerns how quantitative reasoning informs decisions within the loop, not the existence of these generic outer-loop steps.

```text
Inputs: fixed models, initial complete H0, public tasks,
        unchanged evaluators, declared execution conditions
State: selected complete parent H, episode evidence B,
       typed Evolver memory R (operations and short experiences)

For each development round:
    Controller selects an episode and history view; record who selected the target.
    Inspect every available episode layer and mark absent/not-run layers explicitly:
        public source/definition, actual diff, fresh-Worker trajectory/artifact,
        and that candidate's own outcome.
    Expose the bounded deterministic R bootstrap; record visibility, not assumed use.
    When useful, search and exact-read an experience, or read/adapt/run an operation.
        Separately stage any original evidence needed beyond its source references.
    Form a hypothesis about a reusable capability to improve.
    When definition-sensitive, select an independently delivered quantity
        and use a public numeric example that discriminates alternatives.
    Use quantitative reasoning to choose an informative observation.
    Revise the hypothesis or intervention using the observation.
    Develop and test a complete candidate, or keep H unchanged.
    If admitted, observe a fresh Worker using the complete candidate for evaluation.
    Record available use, outcome, failures, regressions, cost, and explicit non-runs.
    Record the actor and reason for retention, revision, narrowing, or rejection.
    Select the next complete parent using the declared official comparison rule.
    Retain the actual R output independently of whether the candidate H is accepted.

Freeze one complete H* for the declared campaign.
Compare H0 and H* on the same panel with matched Worker conditions.
Report performance, learning cases, and cumulative operation.
```

# 6. Illustrative capability-learning episodes

These examples explain proposed decisions, not completed experiments or instructions that must be supplied to the Evolver. An experimenter-provided helper cannot later be counted as autonomously discovered.

## 6.1 Learning to choose an estimation operation

Suppose a task asks for a historical quantity under an explicit finite-sample definition. The current Worker repeatedly substitutes a familiar streaming estimator. The Evolver's hypothesis is not simply that one formula is wrong: the harness lacks a reliable connection between the task's estimation target and the estimator it selects.

A small definition-derived fixture can distinguish the alternatives without a hidden answer. Depending on the result, the revision might create an estimator adapter with explicit support and normalization, or repair the policy selecting an existing implementation. A subsequent Worker should choose and use the applicable operation. The capability gain is faithful method selection and execution; local numerical agreement alone is not the whole outcome.

## 6.2 Learning to maintain a coherent fitted procedure

Suppose the Worker changes the public training support but continues using an earlier fitted parameter or cached diagnostic. The Evolver can compare a fixed-parameter sensitivity check with a refitted procedure to determine which operation is missing. A candidate may add fit-state tracking and invalidation, or compose existing fitting operations in a different order.

The lesson is conditional. A mandate that deliberately freezes parameters for prospective evaluation should retain them; one that redefines the training procedure may require refitting. The persistent improvement is the ability to manage that distinction, not an unconditional instruction to recompute everything.

## 6.3 Developing a new comparative research operation

Suppose a portfolio-research assignment permits choosing a risk estimator, but the current Worker can only apply one familiar implementation. When the number of assets is large relative to the available sample, the Evolver may hypothesize that a reusable comparative estimation capability is more useful than another isolated parameter adjustment.

It can develop an operation that fits admissible alternatives on the same information support, propagates them through the same portfolio consumer, and exposes estimation sensitivity and the relevant economic objective. The fresh Worker can then perform a comparison it previously could not carry out reliably. The capability is a new piece of research machinery, not merely a warning or a pass/fail check.

Neither shrinkage nor a simpler estimator is assumed to win. The operation must respect the task's permitted choices: when paper reproduction prescribes an estimator, comparison may inform diagnosis but does not authorize replacing that estimator. The proposed learning is the ability to construct and interpret a controlled quantitative comparison, rather than memorizing a preferred method.

# 7. Experimental design

**Current registered condition (5 October).** The independent
[cumulative-six registration](../decisions/2026-10-05-pro-cumulative-six-registration.md)
starts from the actual selected Pro prompt package **H_start**, with its actual
empty R, not from original simple H0. The fixed six development tasks are QCE
T01/T12/T18 and QF amendment-aware 13F crowding, momentum and corporate-action
adjustment; all are historically exposed. Two rounds target T18 then T01,
each with its own fresh full-six parent and any admitted full-six candidate.
The full harness remains mutable and actual R carries independently of H
selection. After normal H_final freeze, an **unconditional original-simple-H0
six-task postlude** uses the same frozen Worker role/settings, including when
H is unchanged or freeze coverage is partial. This fresh H_final-versus-H0
endpoint is distinct from the process comparison of this condition's initial
H_start with H_final. Its declared order is H_final then H0; neither historical
scores nor a lower intermediate draw replaces an endpoint arm. Any difference
from original H0 includes the inherited Pro prompt and cannot automatically
be attributed to the two new E episodes.

**Completed registered condition (4 October).** The renewed simple-seed
[registration](../decisions/2026-10-04-simple-seed-panel-and-intervention-condition.md)
starts initial measurement and research from the same workflow-free three-file
package with empty memory. Six development tasks span QCE T12/T16/T18 and
QF momentum, earnings surprise and corporate-action adjustment. T19 and Brinson
attribution are excluded from this campaign's revision and selection, but have
historical project exposure and are not called unseen. Each of three fixed
rounds compares all six development tasks, then one complete package is frozen
for the eight-task endpoint. This predispatch amendment removes the earlier
four-task-window omission, not within-benchmark tradeoffs or sampling noise.
An opt-in early compact investigation checkpoint is locally implemented to
retain an ACT/development opportunity;
it is investigator engineering, not a learned quantitative mechanism.
The scheduled main maximum is52 Worker-task cells plus3 Evolver episodes.
If a distinct complete H is frozen, a separate sixteen-cell H0/frozen-H repeat
on all eight tasks is prospectively required regardless of the initial result's
direction. Its actual registration follows the frozen identity; no outcome
feeds selection and all original measurements, nulls and costs are retained.
If H remains unchanged this conditional confirmation does not trigger.
The new profile exposes all six current development episodes through indexed
public members and task-specific computation aliases, while retaining the
active-task alias. Local preparation and real synthetic public-probe consumers
are qualified, including non-active QCE and directory-shaped QF artifacts.
This is investigator-written evidence access, not autonomous diagnosis or
learned capability. Actual native-entry and image qualification pass; R1/R3
public probes now establish scoped autonomous use, not persistent capability
or later memory benefit.
Baseline/frozen evidence for the two evaluation-only tasks is not
included in revision input.
The independent r2 execution now has its [original eight-task initial result](../decisions/2026-10-04-simple-seed-r2-initial-eight-result.md):
QCE T12/T16/T18/T19 score7/16,18/18,16/18,18/18, binary2/4 and equal-task
mean83.1597%; QF momentum/earnings/corporate/Brinson score26/26,8/8,7/7,42/42.
All have zero errors/skips and no contract adjustment. Initial generation is
111requests/2,134,515tokens/USD0.1952487149, complete for that phase only;
logical requests and retries remain unmeasured. The separate r1 terminates
before model execution and remains an unscored engineering failure, not an arm
whose nulls are replaced. No new Evolver or learned endpoint exists at this
initial cutoff. QF and both isolated tasks already score full, so preserving
them is nonregression, not transfer gain; T12/T18 retain official headroom.
Neither pattern is an ability ceiling or a specific diagnosed repair.
The [first parent window](../decisions/2026-10-04-simple-seed-r2-r1-parent-variation.md)
then measures the same complete H at T12/T16/T18=10/16,3/18,16/18,
with fourteen T16 errors, while all three QF development tasks remain full.
This is new-lineage evidence of both upward and downward fresh-run variation
before evolution, not a changed-harness effect. Parent generation uses
202 requests/8,706,270 tokens/USD0.5219293711; the first eight closed stages
total USD0.7171780860, excluding the first Evolver and later work.
An investigator-only [T16 interface diagnostic](../decisions/2026-10-04-simple-seed-r2-t16-public-interface-audit.md)
reproduces an ambiguity in a final returned dataframe despite equal realized
variance values on a tiny public synthetic input. Indexed outputs are permitted;
this is neither an identified official-error cause nor a learned repair, and
the finding is not supplied to the active Evolver. Candidate recovery from a
low parent draw must be separated from persistent improvement through the
registered frozen endpoint and independent confirmation.
The [original first revision and scored consumers](../decisions/2026-10-04-simple-seed-r2-r1-scored-consumer-result.md)
now close: E executes six public probes and authors a two-paragraph prompt
revision about raw/excess semantics and entrypoint numerical verification.
Fresh T18 code implements the conversion and checks all twelve CLI outputs
numerically, but also starts positions after one month rather than the
public ten-year warmup. The official candidate scores9/16,3/18,15/18 versus
parent10/16,3/18,16/18, with QF three full ties; the whole H0 and empty R remain.
This is consequential policy-layer uptake with a negative full-package result,
not executable-harness learning, isolated prompt causality or an identified
official failure cause. R1 costs365requests/USD0.9471286757; the first13stages
totalUSD1.1423773906, excluding the ongoing original R2 and later work.
The [R2 closure](../decisions/2026-10-04-simple-seed-r2-r2-abstention-and-identity.md)
subsequently retains H0/emptyR: E actually receives current T12 9/16 and the
original R1 paired negative, but substitutes T18's16/18 in its accepted
decision and executes no public probe before the pre-ACT deadline. This is
not calibrated scientific abstention or evidence of an ability ceiling.
The [complete r2 endpoint](../decisions/2026-10-04-simple-seed-r2-terminal-result.md)
then closes three rounds/27stages/40Worker-task cells. R3 independently
recomputes the focal corporate-action artifact, corrects its initial comparison
depth through self-review and voluntarily abstains. It saves one provisional
experience with two versions and zero executable operations; no later episode
consumes that memory. Frozen H remains the exact initial H0. QCE binary is2/4
on both panels, with mean83.15972222% to80.38194444% entirely from T18's16/18
to14/18 same-H change; all four QF tasks tie full. All eight outcomes are
measured without errors/skips or contract adjustment. Provider accounting is
823physical requests/24,404,277tokens/USD2.0474074027complete; logical/retry
detail remains incomplete. No learned frozen gain or distinct-H confirmation
follows. The separately registered model-only Evolver fork subsequently selects
a prompt-policy candidate on the original R2 six-task development comparison
(Section8.1), not a frozen improvement or isolated model effect.
The dated conditions below remain evidence of earlier experiments, not this
new lineage's baseline. No initial result is redrawn or used to weaken H0.

## 7.1 Tasks and what the benchmarks can establish

QFBench covers practitioner-style quantitative assignments [13]. QuantCodeEval evaluates strategy-code reproduction from financial papers and task instructions [14]. They provide operational tests of quantitative work; passing them does not establish investment profitability, original alpha discovery, or general scientific expertise. Both the new eight-task condition above and the historical twenty-task campaign below evaluate a whole shared harness through each benchmark's native executor and official metric; QFBench and QuantCodeEval outcomes are never pooled into one checker count.

**Historical twenty-task scope.** The closed September campaign comprises all ten public-data QuantCodeEval tasks in the [existing manifest](../../data/quantcodeeval/MANIFEST_CANARY.json)—T01, T12, T16, T18, T19, T24, T26, T27, T28, and T29—and ten QFBench tasks in the [expanded manifest](../../data/qfbench/MANIFEST_EXPANDED_RESEARCH_20260928.json). QFBench development uses `corporate-action-adjustment`, `earnings-surprise-calculator`, `momentum-backtest`, `swap-curve-bootstrap-ois`, `historical-var-data-prep`, and `bs-greeks-pde`; its cycle-evaluation tasks are `13f-amendment-aware-crowding`, `brinson-sector-attribution`, `credit-spread-decomposition`, and `variance-swap-replication`. QuantCodeEval development uses T01, T12, T16, T18, T24, and T28; T19, T26, T27, and T29 are cycle-evaluation tasks. This selection comes from the larger pinned QFBench inventory rather than redefining that inventory as the active panel. Old Main R2 and its split are not repurposed.

Eligibility follows public-input availability and runnable native evaluation, not whether a task favors the method. Every selected task has historical project exposure, so the four-plus-four evaluation partition provides within-cycle feedback isolation, not unseen or sealed transfer. The registered endpoint is a same-twenty-task initial-versus-frozen comparison with benchmark-specific reporting. Additional restricted-data tasks and unseen-task transfer, if later arranged, are separate claims.

## 7.2 Matched comparison and final freeze

Fix the foundation-model configurations, provider routes, official evaluators, and declared Worker execution conditions within a comparison. The initial harness must receive the same turn, context/output, timeout, and runtime allowances as the evolved harness. Raising or aligning an inference allowance for both arms is a new comparison condition, not an evolved capability.

**Earlier minimal-seed development (historical):** the initial package was fixed by its functional capabilities before its score was observed, retaining shell execution, public task/data access, delivery requirements, and matched inference conditions while removing preinstalled workflow and bookkeeping. A simpler agent can improve by avoiding overhead; lower baseline performance is not a selection criterion. Historical i28 is not a descendant or matched comparator. The original-public T12 initial Worker and unchanged replay form the first measured cell. Subsequent E1, E4, and E6 experiments all keep this minimal H0 as mutation parent and incumbent; they are alternative descendants, not an E1-to-E4-to-E6 parent chain. Their investigator-authored profiles, reasoning settings, evidence projections, and decision interfaces differ and are reported as conditions. Candidate packages that reach observation are copied unchanged into matched fresh Workers and their original artifacts are replayed with the fixed evaluator. Detailed outcomes, interruptions, and costs remain in the retained development appendix rather than defining the general method. The prospective October condition reuses the functional seed design, not these historical measurements or candidates.

**Original expanded setup (now closed), followed by the separately registered checkpoint condition:** the original
campaign materialized unchanged minimal H0 at 120 Worker turns and started research
from the complete retained September 25 E13 package, not from H0 or a task-wise
splice. The preflight-qualified investigator overlay
`workers/e13-complete-worker120-32k-timeout180` changes exactly two inherited
runtime fields: per-call output from 65,536 to the matched 32,000 tokens and client
timeout from 1,800 to 180 seconds. This aligned whole package is the initial
research parent, not an Evolver revision and not a relabeling of older measurements;
the preserved 32k-only copy is superseded for this campaign. After the overlay,
all LLM-configuration fields match H0. Both H0 and the active parent use 120
turns, 200,000 context tokens, 32,000 output tokens,
temperature 0.2, a 180-second client timeout with the existing effective 360-second
minimum, and 128 files/32 MiB of post-generation transport under task-specific
public runtimes and unchanged official evaluators. The initial research-memory
snapshot preserves the observed empty E17 provenance: it contains neither an
investigator-written lesson nor a newly formed model-authored experience.

Six registered revision rounds/windows form three two-round task-pair blocks. Rounds 1--2 compare
QCE T01/T12 and QF corporate-action/earnings; rounds 3--4 compare QCE T16/T18
and QF momentum/swap-curve; rounds 5--6 compare QCE T24/T28 and QF historical-
VaR/BS-greeks. The fixed active targets are R1 QCE/T01, R2 QF/corporate-action,
R3 QCE/T18, R4 QF/swap-curve, R5 QCE/T28, and R6 QF/historical-VaR. These
investigator-registered targets alternate QCE and QF, while each
parent and candidate is evaluated on both two-task benchmark windows. Each
benchmark's window metric is lexicographic: binary-success count, then exact
equal-task mean pass fraction, computed separately for QCE and QF. A complete
candidate replaces its parent only when neither benchmark-specific metric is
worse and at least one is strictly better; ties and mixed gain/regression keep
the earlier whole parent, with no component splicing. The actual memory snapshot
moves forward independently of that harness decision. These are registered
conditions and selection rules. That original campaign has since completed all
six windows without forming a new candidate or nonempty memory, as recorded in
the current result summary; its historical setup is not an assertion of learning.

The original campaign's [partial-measurement amendment](../decisions/2026-09-28-partial-measurement-campaign-continuation.md)
does not shrink those registered windows. Every task ID remains in its declared
window; the official-metric mapping may be sparse, while coverage records each
task without an official measurement as null with its reason. Officially
evaluated delivery failures keep their reported results and denominators.
A partial window is
nonselectable and has no selection key. Eligible delivered siblings are evaluated
once. If either parent benchmark window is incomplete, the window is archived
and its Evolver and candidate stages are skipped, carrying the same $H$ and
$\mathcal R$ into the next prospectively registered round. If a candidate window
is incomplete, it cannot promote: the parent $H$ remains while the actual
$\mathcal R$ already produced by the revision continues independently. Baseline
or final partial measurement on one backend does not prevent measurement of the
other backend, and evaluation-only outcomes never enter a development revision.
These continuation rules are investigator-written orchestration, not an evolved
research capability.

The subsequent [checkpoint condition](../decisions/2026-09-28-checkpoint-condition-registration.md)
retains the same twenty tasks, splits and comparison windows but prospectively
changes the R5 active investigation from T28 to T24. It enables investigation
from a delivered active task despite a partial parent window, permits fresh
candidate observation on the original full windows, and returns the latest
completed candidate window as factual feedback. Incomplete comparisons still
cannot promote a harness. Its own matched H0 is freshly measured; no historical
score is borrowed. The fixed investigator policy, model-authored H/R changes,
and any eventual fresh-Worker gains remain distinct evidence layers.

The registered [T18 applicability pair](../decisions/2026-09-23-t18-frozen-e6-applicability-pair-registration.md) is a separate observation. The unchanged three-file H0 and complete five-file E6 packages, identical original-public T18 inputs, and matched Worker conditions were frozen before either outcome. It measures daily row/key preservation, preceding-month weight use, and appropriate use or non-use of the inherited TSFM validator. The E6 Worker completes 25 requests at USD0.1223553932, and unchanged zero-model replay scores 16/18 (A2/4, B14/14), binary reward 0, with zero errors and skips. Original H0 ends on repeated provider empty responses before artifact creation and has no score; USD0.0557366715 is a known subtotal, not total cost. The separately registered single unchanged H0 r2 replacement completes40requests/USD0.1437449498 with complete billing. Its original-artifact zero-model replay also scores16/18(A2/4,B14/14),binary0, two ordinary failures and zero errors/skips. Recovered H0 thus ties fixed E6; the aggregate null does not prove identical operations, a capability ceiling or reliability gain. All stages are mirrored and closed, with original failure retained. This is not an E7 revision, scale run, or result-dependent second-arm selection.

A post-freeze [investigator diagnostic](../decisions/2026-09-23-t18-first-eligibility-public-diagnostic.md) identifies one public operation-to-consumer contrast without changing either arm. E6 checks the number of prior monthly volatility observations and first enters its quintile branch at ordinal 121. Reading R3a's “at least 120” together with R4's inclusion of the current month permits an ordinal-120 alternative, although R3a's phrase “after the 120-month threshold” remains ambiguous. On the fixed US-market input, the 120th observation is top-quintile: changing only its state from 0 to 1 changes the weight from 1 to 0.6328595691244783 and all 21 following-month daily returns. The same comparison is negative on UMD because its 120th observation is middle-quintile. This is an investigator-selected public counterfactual, not an official failure cause, Evolver-authored revision, useful persistent learning, or E7 result.

The completed [actual-artifact comparison](../decisions/2026-09-23-t18-public-pair-operation-comparison.md) keeps that counterfactual distinct. Recovered H0 already makes ordinal 120 eligible. Both H0 and E6 retain every public key and apply their own preceding-month weights, but the US view exposes two state and weight differences: ordinal 120 and a separate value exactly on the expanding 80th-percentile boundary. They propagate to 21 and 20 daily rows respectively, 41 in total; UMD has zero state, weight, or daily-return differences. These public operation differences coexist with the independent 16/18 official tie. They do not explain either hidden failure, identify a superior convention, constitute a candidate edit or persistent learning, or report an E7 outcome.

The completed [E7 paired continuation](../decisions/2026-09-23-e7-paired-negative-result.md) is the first measured successor to the exact E6 package in this lineage. Its access log and final decision corroborate access to and citation of selected T12/T18 history, the investigator note, and the direct E6 T18 episode, without isolating causal use of any field. E7 adds known-layout dispatch and volatility-targeting checks to a six-file package; both fresh cells are committed before either outcome. On T12, the Worker consumes a 19-pass validator report after its only strategy write and unchanged replay ties E6 at 14/16 (A7/8, B7/8). On T18, two identical 223-pass reports bracket only a warning-handling edit, while replay scores 15/18 (A2/4, B13/14), below E6 and recovered H0 at 16/18. All binary rewards are zero. Public audit finds that E7's neutral classifier state maps to unit weight without a daily position gate, creating 2,447 UMD and 2,449 US-market nonzero warmup rows; the validator does not trace the public warmup-position restriction to that consumer. This is a real public-contract defect, not an attribution of the official regression or a general claim that neutral classification must imply flat exposure. Independent accounting for activation and both Workers is 82 provider attempts/81 logical requests, 5,978,220 tokens, and USD0.4185778294 complete, separate from the frozen through-T18 cutoff. E7 is retained as negative experience; E6 remains the fallback research ancestor and H0 the incumbent. One actual zero-model ingest now archives both E7 own outcomes in a single round and retains that 82-attempt/USD0.4185778294 accounting rather than adding model spend. Its cap-four selected E6/E7 projection contains 20 files/189,493 bytes, using actual E7/T18 as active evidence and E6/T18 as related counter-evidence; this is selected filesystem scope, not a total-work bound.

The [E8 consumer candidate](../decisions/2026-09-23-e8-consumer-candidate-and-paired-workers.md) reuses unchanged E7 source, the fixed high policy and all nine roles. Activation completes ACT/admitted with a six-file package and three changes: prompt, descriptor and 52 executable validator lines checking warmup exposure and later activity. Its activation receipt records 31 requests/USD0.1667607315 complete. Four component smokes cover load/import only, and one selected-probe branch has an import failure. Root's investigator-only two-file matrix gives E6 20/20 checks and retained E7/all-zero 19/20 per file, distinguishing early exposure from missing later activity; it is not fresh Worker use or general applicability evidence. After both preflights pass, the same complete candidate is jointly started in original-public T18 and T12 cells before either outcome. Sole unchanged zero-model replays yield T18 16/18 (A2/4, B14/14), reward 0, recovering E7's aggregate lost property and tying E6/H0; T12 yields 8/16 (A4/8, B4/8), reward 0, with six ordinary failures plus two errors. Neither artifact nor contract is adjusted and neither replay is repeated. Activation plus both Workers is independently reconciled at 66 provider/logical requests, zero retries, 3,246,958 tokens and USD0.2788327733 complete, excluding copied history and evaluator compute.

Fresh T18 audit supplies a narrow positive mechanism case inside that whole-package negative. The first draft already contains the warmup-flat gate and all 24 new eligibility checks pass on the first call, so the new checks do not cause a FAIL-to-repair transition. The Worker instead consumes inherited date-join failures, moving from 199/247 to 247/247, then separately repairs a raw-entrypoint shell failure and obtains a third 247/247 report. On the two fixed public views the final artifact has zero warmup positions, remains active on 11,753/11,661 post-window rows, has zero own preceding-weight mismatches, and retains unit weight for all 329/330 eligible neutral-state rows. This is actual fresh consumer correction relative to E7, not a synthetic result, but prompt/code contributions and official-score causality are not isolated. Fresh T12 audit finds a complete functional first draft followed by two identical 19/19 reports and only a documentation edit. E8's 6,300-row intermediate interface contains 1,416 NaNs, while its 4,884 finite signals and 618 portfolio returns equal E7 because the fixed-input consumer uses only the sign. R7 allows omitted or NaN prehistory, and the public average language is not an explicit API aggregation equation; neither this interface contrast nor downstream equivalence explains 8/16. All stages are closed after 36/36 mirror records and exact resource-absence checks. The complete E8 package is not promoted; E6 remains fallback and H0 incumbent, with no E9 or scale result.

At the end of development, freeze one complete $H^*$ per campaign. Evaluate $H_0$ and $H^*$ on the same panel, with fresh final Workers for $H^*$. A retained H0 cell can be reused only when its setup and declared role match. No task selects its own best historical candidate.

The planned primary comparison is one declared final attempt per arm and task,
retaining every valid outcome. The controller does not automatically redraw a
missing or failed cell. Only a separately preregistered unchanged-condition
recovery can occur under the existing one-replacement limit; its original
failure and cost remain visible, and there is no second replacement. A nonempty
low-scoring artifact is never redrawn. The design is a single-shot descriptive
comparison, not a stability estimate or a reproduction of a multi-attempt
leaderboard protocol. Development attempts, failures, permitted recoveries, and
costs remain visible. Adaptive selection can overfit observed evaluation
criteria [15].

## 7.3 Evidence I: an improved complete researcher

Report native outcomes, fully solved tasks, improved/tied/regressed tasks, and delivery failures. Keep benchmark-specific results separate. Official partial-check counts can explain progress but do not become binary success.

For a panel $\mathcal D_b$, the primary paired endpoint is defined only when
both arms have genuine official measurements for every registered task:

$$
\Delta_b=\frac{1}{|\mathcal D_b|}
\sum_{q\in\mathcal D_b}
\bigl[S_b(H^*,q)-S_b(H_0,q)\bigr],
$$

where $S_b$ denotes officially measured fully solved status under the declared
protocol. A task without an official measurement has a null metric; an
officially evaluated delivery failure retains its actual result, including
13F's empty-delivery result 0/11, rather than becoming null because no artifact exists.
If either arm is partial, we do not fill a missing metric with zero,
evaluate $\Delta_b$, or name a full-panel winner. We instead report each arm's
registered-task coverage, missing reasons, first-attempt and permitted-recovery
delivery, and all costs. A paired summary may additionally be reported on the
intersection of tasks with genuine measurements for both arms, with that
intersection and denominator explicit. It is conditional on joint measurability,
not an unbiased estimate for $\mathcal D_b$; an empty intersection has no
aggregate rather than value zero. Operational delivery failures remain separate
from native official rewards.

Separate Evolver search, local experiments, Worker execution, and official evaluation costs. The performance question is whether the complete learned package improves the declared task outcome, not whether every edit is beneficial.

## 7.4 Evidence II: actual learning of research capability

Retain selected positive, ordinary-repair, null, and negative episodes. A completed candidate episode used as feedback should make it possible to inspect the public method source and task definition, the actual parent-to-candidate diff, the actual fresh-Worker trajectory and artifact, and that candidate's own outcome. For abstention or infrastructure failure, retain every layer actually produced and mark the unavailable diff, fresh-Worker artifact, or official outcome absent or not run. A definition-sensitive case should additionally expose the selected independently delivered quantity, the public numerical example that separates plausible definitions, the Evolver-authored revision, and a fresh Worker's use and outcome.

At least one substantive executable or control-flow capability with fresh use is needed for the proposed full-harness learning account. Policy improvements are legitimate but cannot alone demonstrate tool or executable capability learning. A loaded skill, invoked tool, or passing local test does not establish usefulness without its consumer and task consequence. An independently required intermediate output is itself a consumer: material correction at that output can establish semantic use even when a later sign or portfolio aggregate is invariant. It still does not establish payoff or score improvement.

Quantitative cases should reveal a decision link: for example, evidence about fit scope redirected the revision from estimator replacement to state management. A small counterfactual replay can clarify a case when practical; a large causal-ablation campaign is not a prerequisite. Without a suitable control, these cases support the observed mechanism, not a claim that generic AHE could never find it.

## 7.5 Evidence III: cumulative multi-task work

The third target requires an actual sequential lineage across tasks, not independent single-task successes. Record which complete package was inherited, which experience was selected, and where a capability was reused, combined, narrowed, or removed.

The registered six-round/window mixed campaigns supply the current cumulative evidence. Each
round inherits one complete whole-harness parent and the independently retained
typed memory snapshot; the fixed active target receives the two standardized
benchmark evidence windows rather than only its own task. Auditing must separate
bootstrap visibility, an exact memory read or operation execution, the resulting
revision decision, fresh-Worker behavior, and official consequence. A visible
bootstrap or a source reference alone is not use, and an experience's original
sources are not automatically remounted.

Partial measurement changes continuation, not the evidence standard. In the
original campaign condition, a parent-incomplete window skips the Evolver and
forms no new memory in that round. In the checkpoint condition, revision may
proceed when the active task has delivered evidence; an unavailable active task
still skips revision. A candidate-incomplete round cannot promote its harness, but retains
the revision's actual memory output independently before continuing. Neither case
is a scored loss or a complete capability test, and neither authorizes an
automatic replacement attempt.

Measure inserted history and bootstrap bytes, returned retrieval bytes, actual
context/tokens, probes, checks, Worker/evaluator calls, package size, wall time,
and retained storage as history grows. Current implementation bounds the selected
episode projection and the first-turn memory bootstrap, not all task evidence,
probes, checks, evaluations, or storage. Bounded total per-round research work
therefore remains to be demonstrated; final-panel evaluation need not be constant-
cost. The [September 28 registration](../decisions/2026-09-28-expanded-twenty-task-campaign-registration.md)
authorizes the real twenty-task test. Its original condition subsequently
closes with no admitted revision or memory formation/use, a complete QF freeze,
and partial QCE freeze. Registration and source readiness are not empirical
validation, and missing QCE coverage remains null rather than a completed
twenty-task comparison.

## 7.6 Optional extensions

Generic harness search, prompt-only evolution, removal of quantitative guidance, and alternative allocations of inference compute can support stronger comparative claims. They are optional extensions, not prerequisites for the agreed performance, learning, and cumulative-operation evidence. We do not claim to isolate every mechanism or establish compute optimality with the basic design.

# 8. Current evidence and anticipated results

**New eight-hour condition, source checkpoint 6 October, 02:41:14 UTC.** [BacktestBench](https://arxiv.org/abs/2605.17937v2) supplies 18,246 tasks in four categories from over six million market records. Our separate development screen uses 12 tasks (8 train/4 validation); only the 8 train tasks enter E. The 4 initially frozen-only tasks are retained in the separately selected 20-task test panel. Workers receive the raw public CSV ZIP/catalogs rather than AutoBacktest's SQL/factor-retrieval pipeline. Upstream comparison operators, a prospectively declared stock-selection alias and answer-file precedence are used, so these measurements are not unmodified upstream OA. The complete inherited H remains mutable, and library lineage overlaps prior campaigns.

The [first candidate terminal record](../decisions/2026-10-05-backtestbench-first-candidate-terminal-result.md) reports initial coverage of 11/12 versus candidate coverage of 12/12: correct answers on the common 11 tie at 3→3, the common 7 train tasks move 3→2, and the 4 validation tasks move 0→1. The initial parameter/provider null remains null. E1's actual PSY contrast yields a 965-byte prompt-only ACT and R at 4 experiences/6 versions/0 operations; the active fresh Worker's single-lag output of 0.480091 matches its prediction but remains scored 0. One metric gain retains the same number with scalar formatting; two strategy regressions retain the same letter in unextractable nested answers. The [public consumer audit](../decisions/2026-10-05-backtestbench-candidate-strategy-consumer-audit.md) additionally finds Longyun's 53 same-day round trips, while Hubei already had the correct PSY lag. This first comparison establishes no overall/stable gain or adoption. E1 costs USD 0.126463612, provider-complete; initial/candidate known costs of USD 0.5170435532/USD 0.5958252142 remain incomplete.

The [second ACT and audit](../decisions/2026-10-05-backtestbench-second-method-act-and-audit.md) records an actual own-pair investigation, two executed public probes (exit 1/exit 0), and a 674-byte prompt-only daily-dollar-PNL rule. Its successful contrast distinguishes realized round-trip PNL, daily portfolio-value differences and daily returns, but does not settle the public metric's intended meaning; WinRate is not probed, and full-history feature computation before the allowed window remains a no-buffer violation. E2 consumes original/current evidence and the E1 probe/H diff, but does not read or review the exact old R experience. R grows from 4/6/0 to 5/7/0 through a categorical new lesson without correcting the six old versions. E costs 37 physical requests/2,581,462 tokens/USD 0.30464632, provider-complete. The [second candidate terminal](../decisions/2026-10-05-backtestbench-second-candidate-terminal-result.md) measures all 12 cells: known correct answers on the original common 11 improve 3→5 (three gains, one regression, seven ties; common train 7: 3→4; validation 4: 0→1). With full candidate coverage, E2 scores 5/12, versus E1's 3/12; the initial provider null is not filled retroactively. All three gains over the initial harness retain the same inner answer—daily-return volatility, a stock name and parameter 20.0—but change from unextractable nesting to an extractable flat object. This is observed answer-production/consumer improvement, not a new numerical solution or isolated daily-PNL effect. The active Worker computes the predicted daily-dollar result 1.183058134472212 yet still scores 0. Candidate accounting is complete at 239 physical requests/4,660,164 tokens/USD 0.5367646907, including six empty-response/retry pairs; it does not complete the earlier unknown bills.

The [family E](../decisions/2026-10-05-family-method-act-and-candidate-registration.md) uses original T26=14/17, T27=14/18, 13F=43/51 and T24/T29 null. It authors a 602-byte sample-start prompt rule with two public probes (first exit 1, second exit 0), one load/admission pass, unchanged R at 3/5/0 and 31 requests/2,051,398 tokens/USD 0.244285624, provider-complete. Same-code sample truncation changes the coefficient norm from 4.5281 to 3.0805; public R5 supports the start, but R1/R3 tension remains. This is sensitivity evidence, not an independent estimator oracle or official failure cause. The [terminal candidate](../decisions/2026-10-05-family-candidate-terminal-result.md) remains partial: T24 null→null; T26 14/17→null through lost delivery; T27 14/18→17/18; T29 null→12/19 as new coverage; 13F 43/51→49/51. Both arms measure three tasks but share only T27 and 13F, so neither intersection gains nor T29 coverage establish an overall five-task gain or adoption. Candidate cost includes the failed deliveries at 356 physical requests/17,753,528 tokens/USD 1.0079069485, provider-complete. Fresh T27 executes a finite first-OOS forecast/weight/portfolio repair, while its DMSPE alignment/input defect remains; 13F uses inherited protective operations, not a new persistent sample-window implementation. The [delivery audit](../decisions/2026-10-05-family-candidate-t26-delivery-failure-audit.md) distinguishes T24's 87 consecutive identical commands from T26's changing, heavily overlapping paper reads: neither saves an implementation before iteration exhaustion. A progress-to-artifact capability is a subsequent research direction, not a learned operation or novelty claim for investigator-authored evidence projection.

The [separate E3 operation-policy branch](../decisions/2026-10-05-backtestbench-operation-act-and-candidate-registration.md) starts from the admitted E1 package, not E2, and closes with a 621-byte prompt-only scalar-answer rule. E3 reads a 3,818-byte trace catalog, not original Worker raw trace parts, and performs no numerical probe or executable-operation change. It does perform a real pre-ACT read/revision of the old short-code experience; R moves 4/6/0→5/8/0. The revised experience retracts the active claimed repair but still assigns an unsupported short-code cause to a format-mediated gain, so the memory correction is partial. E costs 26 physical requests/1,510,598 tokens/USD 0.122528208, provider-complete. Its [original dev12 completes](../decisions/2026-10-05-backtestbench-third-candidate-terminal-result.md) at 19:58:58 UTC with 3/12 correct and no missing cells. On the initial common eleven, correct count ties 3→3, with two gains, two regressions and seven ties; the initial null remains null. All twelve answer values are primitive scalars, but eight selected answer files contain nested sibling objects and remain unextractable. Both gains preserve an original inner answer, so this is consumer recovery rather than a new numerical solution. The candidate bill is provider-complete at 208 physical requests/3,446,089 tokens/USD 0.3873926588. Fresh Longyun removes the earlier same-day pairs but retains full-history indicators before cropping; neither change establishes a persistent executable-H operation or prompt causality.

The [prospective twenty-test selection](../decisions/2026-10-05-backtestbench-twenty-test-selection.md) fixes five released test tasks per category: the four previously frozen tasks plus sixteen public-only additions selected without answers or candidate/test outcomes. Public UUID/text-clone exclusions do not establish template-, market-window- or latent-lineage disjointness. The fixed dev12 ranking uses known successes, then fewer nulls, fewer known initial 1→0 regressions and earlier registration. It selects whole E2 (5/12) ahead of E1 and E3 (3/12 each), with E1 ahead of E3 through the declared tiebreak. E2 freezes at 20:06:10 UTC before test entry; there is no task-wise mixture or component merge. The fresh initial20/frozen20 endpoint starts once at 20:07:26 UTC with the same complete initial H, Worker/runtime allowances, scorer and answer-file precedence. Its [original terminal result](../decisions/2026-10-05-backtestbench-twenty-test-terminal-result.md) at21:06:02UTC is initial9/20→frozen7/20: three gains, five regressions, twelve ties (five positive/seven zero), all40cells scored with no failure or missing result. Metrics tie2/5; parameter1→0/5, strategy4→2/5 and ticker2→3/5. Complete comparison cost is714requests/12,017,339tokens/USD1.4736693616, excluding earlier development/E calls. A public-consumer audit finds one regression with identical scalar answers but new nested siblings, and another with successful independent computation but no top-level answer; it does not assert that all failed outputs would pass after reformatting. This negative official-compatible endpoint does not confirm development improvement or stable benefit. The test remains closed and never enters the separate active Worker-unit E.

The [failed-family research condition](../decisions/2026-10-05-family-failure-research-registration.md) closes admitted ACT at 20:08:55 UTC with a 1,065-byte prompt-only delivery/read-efficiency rule, one prompt-load pass, no numerical probe and no executable operation. It reads actual portions of T26's failed trace, not the complete history, and does not read T24's raw trace. R grows 3/5/0→4/6/0 through a provisional lesson without exact prior-experience review. Its complete bill is14requests/769,292tokens/USD0.083503288. The [fresh parent-five/candidate-five terminal and recovery](../decisions/2026-10-05-family-fresh-pair-terminal-and-qf-delivery-recovery.md) records T2414→15/17, T26fresh-parent null→16/17, T2716→17/18 and T2912/19tie. The QF Worker delivers normally, but original evidence projection rejects a compiled Python file before scoring. A separate zero-model sidecar at21:16:05–21:16:15UTC performs that unchanged delivery's first official evaluation:48/51 versus fresh parent45/51, zero errors/skips and no contract adjustment. The original controller failure/null remains; no Worker redraw or evaluator change occurs. The four common tasks have three check improvements and one tie, alongside newly delivered T26; all five candidate binary outcomes remain0. Fresh Workers save/import runnable drafts before finishing numerical research, and T26 proceeds past comparison work rather than the fresh parent's83terminal identical commands. These are actual delivery and local check improvements, not isolated prompt causality, stable/frozen gain, automatic adoption or persistent executable-operation learning. The full paired Worker bill is540requests/27,271,747tokens/USD1.9674154474 including the projection-failed QF stage; the separate E bill is not counted twice, and the original stage-local ledger is not rewritten.

The [original research-unit branch](../decisions/2026-10-05-backtestbench-worker-units-registration.md) starts once at21:07:30UTC from exact E3 H and actual R5/8/0, train-only original source/execution/consumer units and the unchanged old guide. Its [ACT audit](../decisions/2026-10-05-backtestbench-worker-units-act-and-audit.md) closes the original E at21:20:36UTC: only an822-byte/one-line prompt addition, proposing daily mark-to-market PNL for Profit/Loss Ratio, with no executable H change. Three public probes execute; E acknowledges and corrects the first probe's signal/price indexing bug despite its exit0. Later probes establish daily-versus-trade and window contrasts from public data and E's own portfolio-value ledger, not an oracle-confirmed definition or resolved no-buffer issue. One prompt-load smoke passes. Actual consumption covers1of5selected units (24,709bytes); catalogue/search activity is not complete-trace reading. Generic review guidance and the full R snapshot are read, but there is no exact experience review, write or rehearsal, and R stays byte-identical5/8/0. E costs37physical/37unique logical requests, no retries,2,739,782tokens/USD0.319736912, complete. The separate original fresh E3-parent12/candidate12 comparison starts once at21:25:30UTC/PID1823806/invocation4720ae90d2d04d5c8bd46c6c2c950a89/restarts0; the [original pair closes](../decisions/2026-10-05-backtestbench-worker-units-pair-terminal-result.md) at22:03:35UTC with all24cells retained. Parent has2correct/11scored and1missing delivery; candidate has1correct/12scored. On the11common scored tasks,2→1 comprises0gains/1regression/10ties; parent full-panel accuracy remains unknown, and candidate0 on the parent-null task is not a paired numerical gain. The [active consumer](../decisions/2026-10-05-backtestbench-worker-units-active-consumer.md) actually computes daily PNL and executes an independent-loop implementation reproducing1.183058, but the official result ties0→0. The sole common regression retains answer A in both arms; nested candidate diagnostics conflict with unchanged first-file extraction. A post-hoc pure-extractor check on unchanged original bytes confirms the nested selected candidate yields no prediction, while the flat parent and lower-priority fallback parse. This calls neither grading, trusted targets nor a model; it is not a persisted official parser trace, new score or isolated daily-PNL causal effect. Pair accounting is397physical/391derived logical requests/6retry rows; raw known USD0.8031258092 is incomplete because2parent usage/billing rows are missing, versus controller-known USD0.7328632478. The preceding E bill is separate. No adoption or stable gain follows. Unit selection remains explicit investigator supervision without a supplied discrepancy, repair or oracle designation; validation4 is historically measured development data withheld from E, not newly unseen data. The [native-hook guide](../decisions/2026-10-05-native-hook-guide-local-qualification.md) is excluded from this condition and is engineering evidence, not a learned H component. The fresh Worker establishes policy uptake, not official improvement, oracle correctness or executable-operation learning. Fixed20test outcomes never enter this condition. The full-H objective and historical positives/negatives remain unchanged.

The separately registered [family own-pair refinement](../decisions/2026-10-05-family-own-pair-refinement-registration.md) passes actual zero-model native qualification at22:09:54UTC and starts one E at22:11:56UTC. Its fixed inputs are the actual delivered whole family candidate, own fresh pair, R4/6/0 and neutral native-interface documentation. The [authoritative terminal/dispatch record](../decisions/2026-10-05-family-dtype-act-and-fresh-pair-dispatch.md) closes E at22:21:59UTC/exit0/no restarts with admitted ACT: only a529-byte systemprompt addition requiring an explicit `datetime64[ns]` cast and exact dtype check when required. Agent binding and tool description are unchanged; the component pass is a prompt load, not executable-operation learning. Five actual public probes retain two missing-relative-data failures and three successful schema/library-semantic/value-preserving cast checks in pandas3.0.5. The first invalid ACT payload and later undeclared component smoke also remain recorded. Before ACT, E reads the complete9510-byte outcome-linked review,14555-byte R snapshot and selected original Worker trace slices; the previous Worker checks a dtype prefix rather than the exact unit. These are actual evidence reads, not proof of the official failure's identity or a numerical-estimator repair. Returned R grows4/6/0→5/7/0 through a new post-ACT provisional date experience, leaving all six old versions unchanged. E billing is complete at36physical/36logical requests, zero retries,3,281,003tokens/USD0.298323652; all36finishHTTP200 without erasing payload/probe failures.

The separately registered fresh complete parent-five then candidate-five comparison starts once at22:52:56UTC after four actual zero-model graph loads of both full H packages in both original Worker images, with owned cleanup. The [original pair terminal and first-evaluation record](../decisions/2026-10-05-family-original-pair-terminal-and-first-evaluation.md) closes the original at23:23:37UTC/exit0/PID0/restarts0, with unchanged invocationb545ecbff9494316a7903e7c223cd317 and both arms partial. All eight QCE Workers deliver normally, but both evaluation stages fail before scoring because the investigator's E-only source clone omits `scripts/replay_quantcodeeval_verifier.py`. These original deployment failures/nulls are preserved, not Worker failures or official zero scores. A separately registered zero-model sidecar starts once at23:28:36UTC and completes the unchanged original QCE deliveries' first official evaluation at23:31:09UTC using the existing scorer and original configurations. It generates no Worker, model request or new task draw. The fresh scores are T2414/17→15/17, T2615/17→13/17, T2717/18→16/18, T2912/19tie and QF13F42/51→45/51, all binary0/errors0/skips0. Two check-count improvements, two regressions and one tie are mixed development evidence, not stable whole-H or executable-operation gain; no adoption occurs. Both arms retain the same five tasks, Flash0731/120iterations/200kcontext/32koutput/.2temperature and original routes/evaluators, without live source patch, restart, historical-score substitution, extra E or redraw. An independent raw census of all ten original Worker audit files accounts completely for416physical/414logical requests,2provider retries,19,541,132tokens/USD1.6038562218. The controller's unknown logical/retry aggregate is not actual zero; this bill excludes the preceding E's USD0.298323652, and first scoring adds zero provider cost. Both fresh T26 arms already cast and assert exact ns dtype and implement a monthly function-2 utility with a daily-times-21 final coefficient consumer. The candidate repairs a real monthly/daily beta inconsistency but also differs in raw versus centered moments and sample start; checks partly reuse implementation helpers. These are actual task-solution differences, not isolated date-rule effects or official failure explanations. The predicted T26 change16/17→17/17 is not the measured15/17→13/17 result. Backtest pair/fixed20 outcomes and the investigator's separate numerical advisory are not E inputs, and actual R remains separate from Worker inputs. Stable benefit and useful memory reuse remain unestablished; the eight-hour minimum is met, not the scientific endpoints.

The [registered training-supervised Backtest refinement](../decisions/2026-10-05-backtest-train-supervised-refinement-registration.md), prospective at the preceding October5 cutoff, closes with unchanged H/R at00:47:30UTC October6. It permits only fixed train8 scalar targets after blind attempts in an E-only namespace, retaining the exact H/R/old guide and full mutation surface; it is supervised optimization, not answer-free discovery. The [original terminal audit](../decisions/2026-10-06-backtest-supervised-abstention-and-pre-act-cap.md) records one start00:27:58UTC/exit0/zero restarts, seven numerical probes, two exact experience reads, unchanged H5311 and R5/8/0, no component check, fresh Worker or evaluation. Its ABSTAIN is imposed by the checkpoint's16additional pre-ACT call limit: checkpointcall17/80052estimated prompt tokens, development33, then terminal ABSTAIN-only. This is not voluntary abstention or an ability ceiling; E200iterations,136kestimated context threshold and3600-second deadline are not the terminal reason. Complete accounting is35physical requests/2849797tokens/USD0.453883892, native35turns88tools/zero tool errors. The original and its unused conditional pair remain permanently closed.

The [separate cap-only condition and actual handoff](../decisions/2026-10-06-backtest-open-window-act-and-pair-handoff.md) now supersede its local-preparation status. The one original E exits01:52:44UTC/0/no restarts with admitted ACT and no formal failure, after43development calls/one compaction. Its checkpoint iscall14/82073estimatedtokens; ACTcall37 follows23postcheckpoint pre-ACT calls, without terminal activation. Fifteen public probes retain12exit0/3exit1, including a final verification that mistakenly masks the PNL array using the last trade's scalar and fails; the successful window-only-history probe is distinct from that failure. Only systemprompt load passes, while the undeclared agent-config graph smoke is guard-rejected. The full mutation surface remains open, but actual H5311→403fa470 is prompt-only:6419→7187bytes/net+768, replacing daily-MTM P/L with window-only indicators and realized round-trip PNL. R5/8/0→6/9/0 adds a lesson, not an executable operation or demonstrated later reuse. Complete E billing is43physical requests/4,995,537tokens/USD0.992034648; native logical/retry counts remain unavailable. Root's complete-package review finds no cached target or task-answer lookup. This remains declared training-supervised development, not identification of the hidden reference program or learned executable capability.

Both arms of the registered conditional fresh parent12 then candidate12 pass actual native zero-model qualification at02:00:01UTC. The original comparison starts once02:00:52UTC and [closes normally at02:37:18UTC](../decisions/2026-10-06-backtest-open-pair-scored-consumers.md), exit0/no restarts. All24cells score with no failure or null: actual parent H5311 scores8/12 and unchanged candidate H403fa470 scores11/12, with3gains/0regressions/9ties; train5/8→7/8 and previously-seen validation3/4→4/4. The same ordered tasks, public consumer clarification, complete packages, Flash0731/120 and evaluator/settings remain matched; Workers remain target/R-free. This is a25-percentage-point development gain, not an initial-to-frozen endpoint, automatic adoption, stable benefit or equal-E-compute causal result. Complete pair billing is443physical requests/8,141,208tokens/USD0.9522991267 (parent USD0.4937009587; candidate USD0.4585981680). A separate raw audit derives436logical requests and7provider retries, not new task draws or replacements for native unknown fields. E plus pair is USD1.9443337747, not the whole lineage's cost. All72owned resources are absent before the final02:41:14UTC mirror; exact observers close and files remain retained.

Four original consumer checks establish actual numerical-policy uptake, with byte-identical paired public messages and already-flat JSON in both arms. Train08417 changes window-dependent trades and selects realized round-trip PNL (0→1). Train05973 changes window, VPT and share sizing together (0→1), but its final code still overwrites residual cash on sale. Seen validation14911 changes window-dependent exit timing and selects trade-based WinRate (0→1); its parent already computes a trade-based alternative, and candidate final portfolio value worsens from about4.396million to3.809million. Train98403 actually crops before factors yet remains wrong (0→0); its requested KPI is daily-return volatility, not trade PNL. These are consequential fresh-Worker method choices, not formatting recovery or isolated window-rule effects. Same-ledger recomputations are not independent simulators. The persistent H change remains prompt-only, E's probe program is not a persisted operation, and the new R6/9/0 lesson has no demonstrated later benefit. Failed verification, cash-accounting defects and the first-valid-MA wording remain unrepaired.

**Separate prospective record, after the evidence cutoff.** The [initial-versus-frozen20 registration](../decisions/2026-10-06-backtest-initial-frozen20-registration.md) is local only, with no upload, model or evaluator execution. It fixes actual complete initial H `fe81e756` versus unchanged candidate `403fa470`, not parent `5311`, on20 additional released test instances (five per category), selected by public-only deterministic order and the existing text-clone filter after excluding all32 prior declared instances. Both arms must receive the same clarified public consumer contract and Worker settings. This can distinguish cumulative improvement from repair of an earlier revision's rule, but supplies no result yet; the instances are not claimed template-, security-, regime- or time-disjoint. The earlier negative fixed20 stays closed.

The separate [closed-pair correction](../decisions/2026-10-06-backtest-closed-pair-history-scope-audit.md) shows that the earlier active parent selected JSON is unextractable despite its bare scalar answer and that file-first precedence prevents fallback; this is distinct from the sole regression's flat-parent evidence and changes no score. The [T27 public paired-OLS audit](../decisions/2026-10-06-t27-paired-ols-public-consumer-audit.md) independently exposes inconsistent slope/intercept samples in the latest family candidate, while the old17/18 submission and fresh parent already fit the paired sample correctly. Both audits are investigator-only, not official-cause explanations or inputs injected into this E or its unchanged candidate. Validation/test targets, SQL and reference programs remain excluded.

## 8.1 Completed comparisons

These are distinct registered comparisons, not a pooled learning curve. Equal-task means average official passed/total fractions; benchmarks remain separate.

| Comparison | Paired coverage | Binary | Equal-task mean | Interpretation |
| --- | --- | --- | --- | --- |
| Cap-only Backtest development | All12; fresh immediate parent/candidate | 8/12 → 11/12 | 66.6667% → 91.6667% | Three gains, zero regressions; supervised train8 and previously seen validation4, not initial-to-frozen |
| Pro prompt, QCE fresh confirmation | All four; fixed fresh H0/candidate | 2/4 → 3/4 | 94.0972% → 94.4444% | T12 gains two checks; T18 loses two |
| Pro prompt, QF fresh confirmation | All four | 4/4 → 4/4 | 100% → 100% | Four full ties; historically exposed tasks |
| Pro E fork, QCE development | All three; original R2 parents reused | 1/3 → 1/3 | 81.7130% → 92.1296% | Prompt candidate selected on development |
| Pro E fork, QF development | All three | 3/3 → 3/3 | 100% → 100% | Three full ties; no transfer claim |
| Twenty-task checkpoint, QCE | 9 of 10 | 2/9 → 2/9 | 78.0090% → 77.0074% | No aggregate gain; T28 null |
| Twenty-task checkpoint, QF | All 10 | 9/10 → 8/10 | 98.8235% → 94.8459% | Two regressions, eight ties |
| Method-review, QCE | All four | 0/4 → 0/4 | 61.6524% → 66.0641% | Same whole R4; fresh-run variability, not evolution gain |
| Method-review, QF | Both tasks | 2/2 → 2/2 | 100% → 100% | Same whole R4; no gain |
| Earlier expanded, QCE | Four common; arm coverage 8/10 and 5/10 | 1/4 → 2/4 | 60.1307% → 74.8162% | Historical unchanged E13, no new H/R |
| Earlier expanded, QF | All 10 | 8/10 → 9/10 | 95.4902% → 98.2353% | Historical-package comparison, not new learning |
| September 25 QCE pilot | Six, with disclosed recoveries | 1/6 → 1/6 | 72.1609% → 79.3913% | Development-only difference; evaluation ties, memory empty |

The [Pro six-task result](../decisions/2026-10-05-evolver-pro-six-task-result.md)
selects the whole three-file prompt candidate: original R2 T12 9/16 becomes
14/16, T16 18/18 and T18 16/18 tie, and QF momentum26/26, earnings8/8 and
corporate7/7 tie. Only E's model changes; original H0/emptyR/R1history and
Worker/profile/deadline/evaluator conditions remain fixed, with no baseline
redraw. E adds1,103prompt bytes/five lines, no executable H operation and no
memory update. Its two probes include one partial exit1, not universal passes.
Fresh T12 reads the source and writes a mean-based first draft; independent
trailing values agree approximately but portfolio agreement remains false:
near-zero opposing signs in one month yield a0.0208667 return difference.
That is not an official failure cause or isolated prompt/model effect; final
prose overstates agreement. E uses33requests/2,850,113tokens/USD0.318421708;
complete new execution is126requests/4,554,129tokens/USD0.5629576273, provider-
complete with logical/retry detail unknown. Reused parent work retains its old
cost.

The [fixed fresh confirmation](../decisions/2026-10-05-pro-frozen-eight-confirmation-result.md)
then evaluates original H0 and the unchanged selected candidate on all eight
tasks with the same Flash Worker, no E/reselection/retry. QCE T12 rises14/16
to16/16, T16 18/18 and T19 18/18 tie, while T18 falls16/18 to14/18. Binary
success rises2/4 to3/4; equal-task mean271/288 to272/288 increases only
0.34722222percentage points. QF momentum26/26, earnings8/8, corporate7/7 and
Brinson42/42 all tie full; all sixteen evaluations have zero errors/skips and
no contract adjustment. Eight stages/sixteen Worker cells use227physical
requests/4,147,258tokens/USD0.4180613746, provider-complete, separately from
the screen; logical/retry detail remains partial. This is one complete
frozen-panel aggregate gain with a disclosed regression, not statistical
stability, unseen transfer or isolated model causality. All eight tasks are
historically exposed; QCE raw passed-check totals are66/70 in both arms.
Fresh H0 already chooses mean, so that choice is not
unique prompt uptake. An investigator-only [matched synthetic contrast](../../inspection/pro-t12-calendar-support-20261005/matched-findings.md)
finds candidate excluded-month invariance for a factor-specific gap but not a
globally absent month, where both artifacts propagate an excluded return into
positions. That bounded behavior is not an E-authored executable component,
an official failure cause or a learning attribution; H remains prompt-only
and R unchanged empty.

The separate [cumulative-six initial panel](../decisions/2026-10-05-pro-cumulative-six-initial-result.md)
now retains QCE T01 2/17, T12 11/16 and T18 16/18 (binary0/3, equal-task
mean56.4679%), and QF 13F43/51, momentum26/26 and corporate7/7
(official reward2/3, check mean94.7712%). All six have zero errors/skips and
no contract adjustment. Its four initial stages use159physical requests,
7,101,173tokens andUSD0.5667245317, provider-complete for the initial panel
only; logical/retry detail remains partial. These are fresh **H_start**
measurements, not original H0 or new E-induced gain/regression. The earlier
confirmation T12 16/16 remains a separate draw. The fixed final freeze and
original-H0 postlude are still needed for this condition's primary endpoint.
Its same-H first parent changes T18 16/18 to14/18 and 13F43/51 to51/51,
with four ties, before any new ACT; this variation is not new E learning.
The subsequent [R1 granularity ACT](../decisions/2026-10-05-pro-cumulative-r1-granularity-act.md)
executes one public shape probe on its own T18 parent:126daily inputs become
six month-end outputs, contrary to daily scaled-return delivery under monthly
weights. E adds707bytes of conditional prompt guidance and one provisional
experience, with zero executable operations. Its extra numerical contrast
omits the ten-year warmup, so it does not prove a formula defect or official
failure cause. E alone uses19physical requests/1,000,734tokens/USD0.159773504,
provider-complete. The numerical limitation remains in the original ACT record.

The subsequent [R1 scored-consumer result](../decisions/2026-10-05-pro-cumulative-r1-scored-consumer-result.md)
closes the actual own-parent/full-candidate comparison: QCE T01 2/17 to3/17,
T12 11/16 to14/16 and T18 14/18 to16/18; binary0/3 ties while equal-task mean
rises52.7642% to64.6786%. QF 13F falls51/51 to40/51, with momentum26/26 and
corporate7/7 tied; official reward3/3 to2/3 and check mean100% to92.8105%.
All six candidate measurements have zero errors/skips and no adjustment.
The declared per-benchmark rule retains the whole H_start parent, while R
carries independently; local QCE gains are not a whole-package win.
The fresh T18 Worker emits daily returns in its first draft, then repairs
a repeated last-day exclusion, previous-month weights and warmup during public
checks. Its delivered UMD/US rows are14,348/14,223daily versus684/678monthly
in the parent. An investigator-only122-month public integration contrast
returns20candidate rows with exact daily dates in month122 versus one parental
calendar-end row; recombination with the candidate's own prior-month estimators
has zero residual. Early119months contain2,586candidate daily rows, all zero.
This verifies the scoped output/application behavior, not independent estimator
validity, official failure attribution or isolated prompt/memory causality.
The first13closed initial-plus-R1 stages use487requests/18,323,810tokens/
USD1.5735731473; R1's parent/E/candidate increment is328requests/
11,222,637tokens/USD1.0068486156, provider-complete for that cutoff.
One provisional experience/one version/zero executable operations is carried;
R2's parent lacks the rejected R1 paragraph. Second-round parent generation
subsequently fails before E, leaving later decision consequences, final freeze
and original-H0 postlude unmeasured.
The [transport-terminal record](../decisions/2026-10-05-pro-cumulative-r2-transport-terminal.md)
retains all three native post-accept transport failures and the partial
artifacts; these are not official task failures or an Evolver abstention.
The original condition is closed without a restart or redraw.

The separate [rejected-branch r1/source-correction record](../decisions/2026-10-05-rejected-branch-native-source-correction.md)
retains a pre-model native QF source-admission failure: the historical scored
source and new output root violate a same-root identity assumption. No E,
Worker or evaluator runs; zero stages and no revision outcome are retained.
Passed networkless graphs/direct preparation had not tested this native path.
This failure remains closed; it establishes neither a capability ceiling nor
a memory negative. The separately corrected r2 ACT is recorded below.

The [rejected-branch r2 ACT/memory review](../decisions/2026-10-05-rejected-branch-r2-act-and-memory-review.md)
now admits a prompt-only descendant of the original rejected R1 package.
Three lines/1,291bytes add exact-string identifier preservation, raw-row
reconciliation before aggregation and half-L1 weight turnover guidance; no
executable code changes. The first turnover probe fails on JSON serialization;
the corrected probe discriminates name-count and weight formulae using the
candidate's own holdings. This is real conditional recomputation, not raw-filing
reconstruction or proof of the required formula. Separate count columns do not
logically imply a non-redundant turnover output, so the deployed rule exceeds
the public instruction's formula specificity.
E exact-reads the correct original R1 pair, reviews its experience with
`retain`, and cites that review in its decision to preserve daily granularity.
R remains one provisional experience/one version/zero executable operations.
This is an observed review/decision connection; the explanation's causal
exclusion of the old rule from the 13F regression is unsupported. Inherited
prompt and ordinary paired evidence remain available alongside R, preventing
an isolated memory-effect claim. E accounts22completed physical requests/
1,478,340tokens/USD0.140490328, provider-complete for E only. The fixed eighteen
fresh Worker-task cells compare original H0, deployment H_start and H_new.
The [fixed fresh QCE panel](../decisions/2026-10-05-rejected-branch-r2-qce-fixed-panel.md)
now closes all three arms: T01 2/17 and T18 16/18 tie across H0/H_start/H_new;
T12 changes7/16 to14/16 to16/16. Binary success is0/3,0/3,1/3; equal-task
means48.1345%,62.7179%,66.8845%, respectively, all nine with zero errors/skips
and no adjustment. This is one observed QCE win against fresh H_start, not
whole-package promotion or isolated causality of the three new rules. The
registered fresh H0 is not a selected lower baseline; historical draws and
H_start's earlier T12 16/16 remain separate. New H's QF arm returns13F46/51,
momentum26/26 and corporate7/7, errors/skips0/no adjustment. Fresh H_start
returns13F0/11 and the same two full QF scores, also errors/skips0/unadjusted.
Its 13F attempt exhausts iterations after119turns/120providerrequests with
zero delivered artifacts. The measured0/11 is not an inferior delivered
formula, and differs in test total from H_new46/51; no fresh H_start holdings
book exists for that formula contrast. Original-H0 QF also returns13F0/11,
momentum26/26 and corporate7/7, unadjusted/errors/skips0, with iteration
exhaustion and zero delivered artifacts. Both controls'0/11 are actual failed
measurements, not nulls or matched delivered-formula comparisons. All three
QF binary totals are2/3, with check means66.6667% for controls and96.7320%
for new H. The complete eighteen-cell development comparison selects whole
H_new under the declared benchmark-level Pareto rule. This observes delivery
reliability and a QCE gain in the fixed comparison, not independent
confirmation, stable expected gain, unseen transfer, isolated new-rule/memory
causality or cumulative executable H learning.
The [separate local zero-model outbound consumer test](../decisions/2026-10-05-13f-repeated-work-diagnostic.md#subsequent-zero-model-outbound-consumer-test)
preserves assistant/tool roles, IDs and result contents through the actual
installed Agent-to-proxy path without reproducing message loss.
Historical outbound requests were not captured, so this does not establish the
original loop's cause or model utilization; no advisory has been tested for
benchmark benefit.
The [terminal result](../decisions/2026-10-05-rejected-branch-r2-terminal-result.md)
retains all13stages/587completed requests/23,341,922tokens/USD1.6296198719,
provider-complete; logical/retry detail remains unknown.
The consumer audit finds inherited T12 mean in new H's first draft, versus
H_start's later repair after reading inherited guidance, and5,004versus4,884rows because new H
retains undefined warmup. Warmup omission is permitted; these differences
do not identify the official gain's cause. T01 removes a full-sample mean
dependency with a running mean but remains2/17. T18 preserves daily support
and previous-month weighting, but an investigator-only four-case public
function diagnostic returns neutral weight1 in H0 versusNaN in H_start/H_new
when volatility is zero; all finite controls pass. All official scores remain
16/18. This isolated function discrepancy does not identify hidden failures,
post-warmup reachability, daily-return loss or isolated new-rule effects;
it is not E discovery or learned capability. The script is
[compare_neutral_weight.py](../../inspection/rejected-branch-r2-t18-neutral-public/compare_neutral_weight.py).
The fresh 13F implementation consumes all three rules: string identifiers,
pre-aggregation kept-row audit and half-L1 turnover feeding the summary.
Literal RESTATEMENT replacement already existed in rejected R1, so this is
not new state-resolution capability. Its55passing checks mostly compare
book-derived outputs, not independent effective raw-state reconstruction or
required-formula correctness.

The separately registered [T18 date-key ACT](../decisions/2026-10-05-t18-date-key-act-and-memory-review.md)
adds one prompt line/403bytes to selected whole H, with no executable change;
E uses27completed provider requests/2,321,423tokens/USD0.290279572, complete
for E only. Its real public `eq_au` probe calls five public functions on
8,948daily/425monthly rows and observes string daily versus datetime monthly
dates, without an independent estimator oracle, normalization intervention or
demonstrated failed join. The public contract does not require one date dtype;
the proposed explanation of the remaining failures is unverified. ACT/edit
precede the exact granularity-memory read/review: an incorrect14to18 retain is
rejected, then source-linked14to16 is retained unchanged. R grows from one to
two experiences/two total versions/zero operations, but the new date item's
earlier misinterpretation of the old diagnosis remains. This is actual
intervention and post-ACT review, not memory-caused selection or useful
cumulative learning. The [completed paired QCE/date-consumer record](../decisions/2026-10-05-t18-qce-regression-and-date-consumer.md)
now gives incumbent to candidate T01 2/17 to5/17, T12 16/16 to14/16 and T18
16/18 to12/18, all errors/skips0/no adjustment; binary falls1/3to0/3 and
equal-task mean66.8845%to61.1928%. Both fresh first drafts already normalize
dates and both delivered artifacts return uniform datetime dates on the same
small fixture; the candidate's ordinary StringDtype-check repair does not
identify the new policy's effect or explain the official regression.
The [terminal/own-pair handoff](../decisions/2026-10-05-t18-terminal-result-and-own-pair-handoff.md)
records fresh paired QF13F47/51 to50/51, with momentum26/26 and corporate7/7
ties; binary2/3 ties and equal-task check mean149/153 (97.3856%) to152/153
(99.3464%). Formal whole-package selection retains the parent because this
QF gain does not offset the QCE regression under the registered rule.
Nine completed stages/zero controller failures use308requests/10,252,286tokens/
USD1.2181060929, provider-complete with logical/retry detail unknown.
The original main exits23:39:58UTC/0/restarts0; no new own-pair paid run had
started at that terminal cutoff, and no redraw or investigator injection occurred.
The separate [investigator-only T01 signal-consumer audit](../decisions/2026-10-05-t01-independent-signal-consumer-diagnostic.md)
finds a doubled-compounding expression with10/10 wrong negative-window signals
and a0.535586 own-sizing portfolio residual despite copied-algebra PASS and an
independent positive-sign spot-check PASS; this is a public fixture consumer
consequence, not E discovery, a new candidate, a volatility oracle, official
failure attribution, evaluator blindness, market loss or date-policy causality,
and none of its inputs or conclusions enter the live own-pair condition.

The subsequent [own-pair terminal](../decisions/2026-10-05-own-pair-terminal-and-memory-identity.md)
returns ABSTAIN with unchanged H, no fresh Workers/evaluations and zero public
probes/component tests;25physical requests/1,848,761tokens/USD0.27235494,
25turns/50tools/zero native errors, one stage/zero controller failures and
original exit00:19:08UTC/0/restarts0. R reaches two experiences/three versions/
zero operations, but trace70--76 records a rejected exact-source review,
ABSTAIN before the exact read and a subsequent date v2 that falsely overturns
an old true probe using a different fresh artifact under the same H.
Self-review only softens single-sample phrasing without repairing v2; reserve
does not activate and two pre-ACT calls remain, so this establishes neither
useful memory learning nor a capacity ceiling.

The [assisted T01 ACT audit](../decisions/2026-10-05-t01-assisted-ewma-act-and-audit.md)
records a subsequent investigator-assisted condition: a public diagnostic and
source/trace pointers are supplied without a repair, formula or fixture. The E
correctly assigns the supplied signal discrepancy to the rejected artifact,
then proposes available-window EWMA normalization. ACT/admission changes only
the prompt (+778 bytes), with no executable component change. One prompt load
passes; the graph check is rejected for an undeclared role; no numerical probe
executes despite the NEW_PROBE label. R reaches three experiences/four versions/
zero operations and preserves erroneous date v2. The completed E uses 26 requests,
1,927,428 tokens and USD 0.248971008, excluding Worker accounting; seven pre-ACT calls
remain, so this is not a capacity-ceiling result.

The normalization explanation is unverified and partly incorrect: pandas
`adjust=False` initializes at the first input, and its complete finite recursive
weights including that seed sum to one. The parent's zero first squared
residual arises because its first return equals its first mean. Retained seed
mass alone does not establish a variance-bias percentage; changing the mean
also changes the squared-residual inputs. The public infinite weighted
definition with permitted warmup/bootstrap does not uniquely select
`adjust=True`. A separate root-repeated investigator computation on the original
observed artifact yields both higher and lower variance than a both-stage
normalized finite comparator when only the initial return changes, rejecting
a claim of universally 37% lower variance without establishing an official
oracle or entering live H/R.

The [complete original assisted comparison](../decisions/2026-10-05-assisted-terminal-and-worker-reuse-direction.md)
measures QCE T01 5→3/17, T12 14→14/16 and T18 16→16/18; binary 0/3 ties,
equal-task fraction 2519/3672→2375/3672 (−3.92156863 percentage points),
and QF 13F 29→47/51 with full momentum 26/26 and corporate-action 7/7 ties.
QF binary 2/3 ties; equal-task fraction 131/153→149/153 (+11.76470588 points).
All twelve official cells have zero errors/skips and no adjustment. The unchanged
benchmark-level Pareto selector retains the complete parent: QF improvement
does not offset QCE regression. Actual R is retained independently at three
experiences/four versions/zero operations, including erroneous date v2 and the
unverified EWMA lesson.

The [actual fresh Worker comparison](../decisions/2026-10-05-t01-assisted-qce-regression-and-worker-comparison.md)
shows the candidate T01 Worker explicitly
computes a finite weighted central moment before its first source write:
`ewm(...,adjust=True).var(bias=True)` agrees within 1.0842e−19, whereas the
double-EWM discrepancy is 2.76974e−5. Corrected missing-observation decay
matches all instruments within 1.2490e−16; a warmup repair is followed by actual
sizing, next-month holding and portfolio consumers. This is real independent
computation and required-output execution, despite official regression. The
candidate changes normalization, centering, decay grid and warmup together, so
the fixed-seed identity below is not its ratio to the incumbent. It does not
validate the E's premise, isolate prompt causality or establish an E numerical
probe, official oracle, reusable executable-H learning or EWMA transfer. The
observed 13F increase likewise does not isolate an EWMA-policy effect or prove
whole-H improvement.

Candidate QCE generation uses 189 requests/9,395,479 tokens/USD 0.6364770198
versus incumbent 101/3,119,819/USD 0.3617777078; T01 uses 108 turns/115 tools
versus 40 turns/50 tools, observed costs rather than causal policy overhead.
The complete registration uses 500 completed requests/25,812,483 tokens/
USD 1.9499594911, provider-complete for E and all four fresh arms, not the
project-wide search; logical request/retry detail remains partially unqualified.
Original exit is 02:07:59 UTC/zero/no restarts, nine stages/zero controller
failures. All 57 owned resources are absent; final additive mirror at 02:10:21 UTC
has zero errors and exact observers are closed, with artifacts retained.
Independent investigation can occur in either role; qualifying and retaining
actual Worker-authored research for consequential reuse through complete H
and/or R is prospective, not a requirement that every E probe before ACT or
make a code edit. A stored R operation remains E-side unless candidate H gives
Workers a usable call path and fresh consequential use is observed.
No successor has been uploaded or dispatched by this closure
record; new paid work requires separate registration and native qualification.

The separate investigator-only [centering audit](../../inspection/t01-ewma-centering-audit-20261005/README.md)
preserves complete-data first-input-seeded weights, mean and initialization:
both actual artifacts give running-residual variance q=(60/61)v relative to
variance v about one current mean, volatility ratio 0.9917694 and inverse-volatility
sizing ratio 1.0082989. Holding signals and returns fixed changes 13 required
portfolio observations per artifact through unchanged actual consumers. This
centering distinction is separate from normalization and establishes no
official finite oracle, official failure cause or new Evolver mechanism.

**Worker-research reuse ends in ABSTAIN.** The separately registered
[Worker-reuse condition](../decisions/2026-10-05-worker-reuse-abstention-and-research-evidence-gap.md)
retains the complete r2 parent, its own fresh six-task observations and actual
R, while supplying investigator-selected navigation to the assisted Worker's
research. The original ends normally at 03:00:23 UTC, one stage/zero controller
failures/no restarts: ABSTAIN, unchanged H, no conditional Workers or official
evaluations. One real probe executes the parent's existing chain and reports
22 assets, 315-by-22 matrices and a 315-row portfolio Series with 12 NaNs.
The E reads the navigation note, final source and original paired metrics,
but none of the selected Worker research trace parts. It does not reconstruct
the independent numerical comparison or retain an executable research operation.

Actual R remains three experiences/zero operations; versions increase four
to five solely through EWMA v2. The revision corrects original pair facts but
still attributes 13F improvement to normalization and infers oracle conventions
from a confounded comparison. Erroneous date v2 remains unchanged; self-review
softens claims only in prose. Factual correction and conservative H retention
do not establish useful memory learning, numerical reuse or an ability ceiling.
Eight pre-ACT calls remain and the reserve never activates.

Complete provider accounting is 13 physical requests, 1,219,170 input and
65,390 output tokens (1,284,560 total), USD 0.692777184; logical requests/retries
remain unknown. Native accounting is 13 turns/35 tools/zero errors/654.23 seconds.
Two repeated full-directory listings return 148,133 bytes each, about 55.7%
of 531,496 returned access bytes; prepared input is 171,997,396 logical bytes
across 1,247 files. These are distinct work measurements, not bounded total
research work. Investigator navigation establishes neither autonomous discovery
nor a new formula, and the original conservative H-selection policy is unchanged.
The final three-root additive mirror has zero errors; all three owned lifecycles
are cleaned with native IDs absent, exact observers closed and artifacts retained.

Subsequent local, investigator-authored delivery engineering qualifies default
100-path pagination capped at 32 KiB for the complete listing JSON and a
[28,146-byte research-entry note](../../inspection/research-trace-units-local-20261005-r1/selected-worker-units-r3.md)
preserving 24,091 bytes of original Worker JSONL. Local r2's unreadable extended
references remain a retained failure; r3 points to existing readable catalogs/parts
and passes actual reader consumption. In the existing local native-preparation
fixture, the 59,667-byte/741-line prepared note exposes both original units in a
44,496-byte default first-400-line read. These are zero-model, undeployed
engineering checks, not learned research reuse, correction of R, a new benchmark
result or a total-work bound. This condition is closed; any future experiment
requires separate registration, and no next dispatch has been made.

The [twenty-task checkpoint terminal record](../decisions/2026-09-29-checkpoint-campaign-terminal-result.md) freezes whole R4. QCE improves T12/T18 but regresses T01/T26/T29; four measured tasks tie. QF corporate action falls 7/7 to 6/7 and 13F 45/51 to 32/51. Known 2,238 requests, 119,142,236 tokens and USD8.4764523924 are incomplete subtotals because R6 candidate T24 lacks complete audit accounting, not a final bill.

The separate [BLAS1 frozen replay](../decisions/2026-09-29-frozen-blas1-partial-delivery-amendment.md) completes on nine eligible original frozen artifacts, with the same scores and no redraw. Its initial side has ten measurements; only the common nine are paired. It does not fill the original null or justify comparing ten- and nine-task means.

## 8.2 Observed learning links and failures

- **R1:** executable TSMOM checks cause a fresh T01 Worker to repair monthly mapping and lag. Official T01 nevertheless falls 5/17 to 4/17 and T12 14/16 to 13/16. Local repair is not package improvement.
- **R4:** an executable EMA timing tool is used twice; its complete window improves momentum 19/26 to 26/26 with three ties. Timing is already correct before the first call, the unchanged parent previously scored 26/26, and frozen momentum ties 26/26. This is a selected local package gain and confirmation, not an isolated tool effect.
- **R6:** an executable VaR cleaning operation confirms an already compliant draft. VaR/BS tie; QCE comparison is partial, so whole R4 remains retained. Invocation does not establish utility or transfer.

R1 forms an experience; R2 reads it and its outcome, abstains and writes a revision; R3 uses the lesson during an investigation. These are memory-to-decision and memory-to-investigation consequences. Yet R2 substitutes a later parent's T12 result for the original pair, R5 does not assimilate the exact R4 outcome, and R6 retains contradictory provisional lessons. Terminal R has four experiences, six versions and no executable-memory operations.

The new outcome-linked review addresses this consumer gap through original-pair facts, explicit source selection and retain/revise/defer. Source tests and real remote memory reconstruction qualify access, not beneficial model use. A first host graph check fails because the coordinator lacks NexAU; a corrected check passes in all three registered Worker images and the Evolver image, with four networkless qualification containers cleaned and zero model/evaluator calls. The separately registered successor starts once at 18:18:51 UTC September 28, PID 33287, and its first four QCE initial Workers are observed live. No new official scores or review-mechanism benefit are established at that checkpoint. See the [six-task registration](../decisions/2026-09-29-qr-method-review-six-task-registration.md).

## 8.3 Anticipated evidence, not promised results

**Fresh successor initial result.** The new four-task QCE baseline has now normally delivered and received its first fixed-BLAS1 official evaluation: T01 2/17, T12 13/16, T18 16/18, T24 11/17; binary 0/4, equal-task mean 61.6523692810%. T12 has two errors; all four have zero skips and no contract adjustment. Generation retains 110 completed provider requests, 4,111,717 tokens and USD0.4169686159, excluding active QF and subsequent work. These are initial measurements, not new mechanism gains. The same main invocation is observed running the QF baseline at 18:42 UTC; see the [fresh baseline and independent public audit](../decisions/2026-09-29-method-review-initial-qce-and-public-audit.md).

The QF initial panel subsequently completes at momentum 26/26 and OIS 19/19, both binary 1 with zero errors/skips and no adjustment. All six initial cells are now measured. Combined initial generation is 125 completed provider requests, 4,444,020 tokens and USD0.4588465460; official evaluation adds zero model calls. At 18:46 UTC the same main is in the first registered round's parent observation. This is complete baseline coverage, not a new candidate result or demonstrated improvement.

**First actual successor candidate, R2.** Its original complete comparison now
ties all same-round parents: T01 2/17, T12 13/16 (two errors), momentum26/26
and OIS19/19. All skips are zero. Whole R4 stays selected. The original strict
attribution failure and explicit unchanged-candidate qualification amendment
are retained. E actually reads the historical experience twice, investigates
decay on public data and adds an executable TSMOM branch; R is unchanged.
Fresh T01 calls it three times and changes dates, units and initialization,
temporarily empties its portfolio, then repairs the join. Its remaining
numeric disagreement is rejected using a self-comparison and a misparameterized
contrast, not a valid independent reference. Correct decay and incorrect
local-residual centering already occur in the first draft, without a new
checker-source read; these choices are not established as tool-induced.
The candidate's 74 Worker requests cost USD0.2249699495. Through 17 closed
campaign stages, known USD1.6459820976 remains incomplete owing to original
R1T24 billing. See the
[scored consumer record](../decisions/2026-09-29-method-review-r2-scored-consumer-result.md).

**R3 and complete frozen-six measurements.** The [R3 audit](../decisions/2026-09-29-method-review-r3-abstention-and-context.md) shows an actual independent expanding-versus-trailing quintile contrast on twelve public files. The parent matches the tested public recomputation; the contrast does not reach the checker or downstream consumer. The actual terminal middleware closes mutation after a second 136k context crossing and one compaction, not an iteration ceiling. Two map returns of 128,458 bytes each are avoidable input contributors, not a proven sole cause. R3 is ABSTAIN, with no H/R change, 28 requests and USD0.2127456249.

The [frozen panel](../decisions/2026-09-29-method-review-frozen-six-and-terminal-boundary.md) is fully measured: T01 5/17, T12 13/16 (two errors), T18 16/18, T24 11/17, momentum26/26 and OIS19/19. QCE binary stays0/4; its mean rises to66.0641339869% entirely from T01. Because the complete selected harness remains the exact initial R4, this is fresh-run variability, not evolution gain. R is byte-identical at four experiences/six versions/zero executable operations. Frozen generation is112requests/USD0.4076602530complete; campaign26stages/651knownrequests/USD2.5819269159 is incomplete. The native controller then fails terminal reporting by requiring distinct harness IDs. A separately qualified zero-model correction closes that descriptive endpoint at21:40:13UTC, retaining both original failures, all stages, costs and H/R. No model, Worker, evaluator or main invocation is rerun, and no package is promoted.

The observed research gap motivates a separately tested next condition:
independent, condition-matched numerical comparisons that can change an
intervention or a check's scope. A copy of the tested output is not an
independent reference, and excluded dates do not by themselves explain
disagreement on common support. Existing public-probe and component-call
interfaces are now also qualified in the actual Evolver image by a separately
recorded, networkless zero-model normal-ACT diagnostic. Its focal controls return
pass/fail/pass while unrelated failed checks remain visible. This is scripted
investigator qualification, not autonomous construction or fresh Worker benefit.
The opt-in research-comparison policy and scoped32KiB paginated map were
subsequently deployed and tested in the single registered September29 Evolver
episode. It completed ABSTAIN after68 provider requests,6,280,065tokens and
USD0.4614849495 with complete billing. Native telemetry records107tool calls,
but no numerical probe, component test, harness edit or conditional Worker.
The second context crossing atiteration65 permitted only ABSTAIN. H and R
remained unchanged. Its rationale also mismatched an old R2 candidate2/17
with a later frozen parent5/17; the actual original R2 pair was2/17→2/17.
This is a retained investigation/decision failure, not an ability ceiling,
beneficial memory use or new score comparison. See the
[terminal audit](../decisions/2026-09-29-research-comparison-one-e-abstention-and-closure.md).
The map bounds one rendered response, not cumulative research work.

That [registered condition](../superpowers/plans/2026-09-29-independent-research-comparison-next-condition.md)
fixed activeT01 before access to the frozen outcomes, based on the R2 consumer
failure. One E uses actual selected wholeH/R and the entire frozen-six reused
baseline. Only an admitted complete candidate receives one new six-task panel;
ABSTAIN does not redraw Workers. No taskwise baseline selection or hidden-answer
guidance is permitted. The combined policy/map treatment is not an isolated
policy ablation, and useful quantitative decisions still need actual evidence.

The successor starts initial and research-parent roles from identical whole R4 packages with unchanged R6 memory. Its four QCE/two QF tasks are historically exposed development/protection tasks. Fresh initial measurement, three windows and frozen-six measurement provide a matched whole-package comparison and an opportunity to observe the mechanism chain. The registered condition also includes a revision profile and selected historical evidence; it is not an isolated causal test of outcome-linked review, a held-out evaluation, or a twenty-task main result.

Outcome-linked review repairs the evidence available to the researcher; it is not the proposed scientific contribution by itself. The broader question is whether quantitative conditions change which experiment is conducted, which reusable operation is developed, or when an existing method is adapted or withheld. Correctly recovering an old comparison can support such subsequent judgment, but does not itself establish a useful quantitative intervention. Any official gain remains a whole-package result unless further evidence isolates its cause.

| Remaining endpoint | Required evidence |
| --- | --- |
| Better complete researcher | Same-task initial/frozen official scores, regressions and cost |
| Useful quantitative intervention | Domain condition changes investigation/revision and a fresh Worker consequence |
| Better method review | Exact original-pair read, supported lesson revision and later decision |
| Cumulative operation | Actual later use/non-use and per-round context/check/evaluation work |

No effect size or successful ACT is assumed. Negative, abstaining, missing and interrupted outcomes remain visible, not replaced with new draws. A local capability without frozen improvement remains local evidence; a score difference without a traced learning chain remains a package result. The broader twenty-task objective remains open.

# 9. Limitations

The framework can select an inappropriate economic interpretation, mistake sensitivity for correctness, or inherit an overbroad rule. A local experiment may fail to distinguish the relevant alternatives. Even an exact quotation from a public paper and a discriminating public fixture do not reveal a hidden evaluator's intended equation or establish the cause of an official score. These are risks in the learning mechanism, not automatically reasons to forbid action.

The distinction from generic harness evolution depends on the operational contribution of quantitative reasoning. The proposed framing alone does not establish novelty or comparative superiority. Nor does system-level self-improvement establish that the fixed Evolver becomes a better revision algorithm.

Same-panel adaptive improvement is not unseen transfer. A single final realization does not establish stability. Restricted benchmark inputs and deterministic reproduction requirements cover only part of professional quantitative research. In particular, the proposal neither reproduces a many-researcher NSE experiment nor assumes that ambiguity is the dominant cause of every benchmark failure.

Incomplete measurement adds a further selection boundary. Sparse official
metrics preserve what was actually measured but cannot establish a full-panel
gain, regression, tie, or capability failure. A paired intersection can describe
jointly measurable tasks only; delivery and evaluator failures can make that
intersection nonrepresentative. Continuing later registered windows avoids
discarding independent evidence, but does not repair the missing cells or turn
them into zeros.

The completed September 25 pilot remains a qualified single-draw result. Whole E13 is selected on three development cells; the three evaluation cells are historically exposed rather than sealed held out. H0 and E13 T18 rely on separately retained recovery paths, and later Workers use a 128-file post-generation allowance rather than H0's 20-file allowance, although the 32 MiB cap is unchanged. The evaluation aggregates are null and T26 property families trade off. These conditions preclude claims of identical end-to-end reliability, no regression, unseen transfer, stability, significance or completed cross-benchmark evaluation.

Finally, memory relevance and executable uptake remain implementation risks. A persistent archive can accumulate misleading advice, and a larger tool library can worsen selection. The system must be able to revise and remove experience rather than equate growth with learning. The current deterministic bootstrap proves only that a bounded view can be placed in first-turn context; it does not prove attention, exact reading, citation, or causal use. A source reference also does not guarantee that its original artifact or public source will be mounted again. Bounds on selected projection do not bound total probing, evaluation, storage, or wall time, and independent retention of $\mathcal R$ does not mean that a rejected $H$ was accepted. A source-grounded change in an upstream intermediate cannot be reported as payoff or benchmark gain when downstream decisions remain unchanged; evidence must be stated at the consumer actually affected.

# 10. Conclusion

We study a quantitative researcher that experiments on its own working methods. Finance methodology motivates this object because measurement, information and estimation choices change the evidence produced. The complete persistent harness carries deployed capability, while versioned research memory can retain a conditional lesson without accepting a failed candidate.

The record establishes executable revision, fresh Worker use, some local repairs and cross-round experience use. It does not establish aggregate frozen improvement: the closed twenty-task checkpoint is negative in mean on both benchmarks, with a missing QCE cell and incomplete accounting. Earlier favorable development comparisons and R4's local gain do not replace that endpoint. The subsequent six-task method-review comparison uses an unchanged harness and shows fresh-run variation, not a learned improvement.

The method-review successor also retains its unchanged initial whole harness;
its T01 score difference is fresh-run variability, not evolution gain. The
subsequent one-E comparison-oriented condition reaches no numerical experiment
or intervention before its context boundary. The prospective simple-seed
condition tests whether an early checkpoint improves the opportunity for a
supported intervention; its initial and research-parent roles use the same
complete seed, enabling an own-lineage initial/frozen comparison. Its
substantive hypothesis remains a consequential
quantitative research operation that is reused, adapted or rejected under
changed conditions. Original-pair memory supports that judgment but does not
replace it. A score, memory schema or quantitative label alone is not the
contribution. This remains an empirical hypothesis with retained negative
evidence, not a completed self-improvement claim.

# Appendix A. Historical evidence, not results of this proposal

The following are separate retained development observations. They cannot be pooled into the initial or final score vector of the proposed campaign.

| Retained episode | Measured observation | Supported scope |
| --- | --- | --- |
| Restricted T26 policy pilot | 6/17 to 14/17 official checks; both binary rewards 0 | Historical policy-layer gain |
| Aligned 120-iteration T27 pair | H0 and supporti4 both 17/18; rewards 0 | Matched single-task null |
| T01 supporti4 to i9 | 3/17 to 5/17; rewards 0 | Development gain with skill-text uptake |
| T01 i9 to i12 | 5/17 to 3/17; rewards 0 | Retained negative candidate |
| T01 E13 | Unchanged abstention; no fresh Worker score | Search outcome only |
| T01 E14 | Skill-only ACT/admission; no Worker or official replay | Unscored revision |
| T01 E15 | Parent and related strategy probes executed; skill-only ACT, +28 lines, unscored | Related-evidence consumption and endpoint-policy revision; no executable learning established |
| T01 i15 fresh Worker/replay | 5/17, A4/7 and B1/10, reward 0; same aggregates as i9 | Endpoint uptake and check-driven repair, aggregate development null; no executable harness mutation |
| T01 E16 | Three successful public artifact probes, unchanged ABSTAIN; no Worker or replay | Search negative; protocol label does not establish calibrated reasoning or useful capability |
| T01 E17 | Direct ACT, skill-only +36 lines / 1,988 bytes; enabled self-review not offered | Unscored policy recurrence; no measured review effect, Worker, or replay |
| T01 E18 | ACT adds an executable onset checker, descriptor, binding and skill guidance; four files, +160 lines / 6,822 bytes | Executable generation with support-proxy limitations; no fresh Worker/replay or demonstrated usefulness |
| T01 E19 and original-i19 Worker/replay | Executable onset refinement, three fresh tool calls with two format failures; unchanged replay 5/17, A4/7 and B1/10, reward 0 | Actual uptake and scoped confirmation, aggregate null versus i9/i15; no tool-caused repair |
| Authentic aligned T01 H0/i19 pair | Initial H0 and original i19 both 5/17, A4/7 and B1/10, reward 0 under matched Worker conditions | Matched single-task aggregate null; no identical-property, capability-ceiling or main-panel claim |
| Minimal T12 initial and E1 | Initial replay 12/16 (A6/8,B6/8), reward 0; E1 ACT adds a 353-line TSFM checker; fresh Worker calls it, receives 15 passes, then replays at 8/16 (A4/8,B4/8), reward 0 | Real model-authored executable mutation and fresh use, but a matched single-task score regression; no post-report artifact edit or checker-caused repair, and no causal attribution of the regression |
| Minimal T12 E2 | R1/r2 end in provider interruptions with incomplete cost; same-frozen r3 reads selected negative history/source and public evidence, then returns unchanged `ABSTAIN` after 31/31 requests at USD0.1788511283 | Actual failed-episode evidence use and one self-review correction; zero mutation/component tests, no fresh Worker/replay/score, and no validated calibration, capability effect, gain or ceiling |
| Minimal T12 E6 interface experiment | An investigator-authored decision-interface treatment receives one `$.discovery` rejection and then an accepted ACT; the Evolver authors a five-file candidate whose four changes include a 440-line executable `validate_tsfm`. The matched Worker calls it after writing a compound/datetime first draft | Unchanged-artifact replay scores 14/16 (A7/8,B7/8), reward 0: +2 checks/+12.5 percentage points versus H0 12/16, while E1 8/16 and E4 7/16 remain negatives. This is a single-task partial check-count gain with fresh use, not checker-caused repair, binary gain, causal isolation, frozen-panel completion or multi-task learning |

Sources are the [T26 checkpoint](../decisions/2026-09-11-t26-mechanism-complete-and-scale-checkpoint.md), [aligned T27 record](../decisions/2026-09-13-retention-deployment-and-aligned-t27-pair.md), [T01 i9 record](../decisions/2026-09-14-t01-intervention-candidate-worker.md), [T01 i12 record](../decisions/2026-09-14-t01-compounding-candidate-worker.md), [E14 report checkpoint](../decisions/2026-09-15-t01-e14-policy-recurrence-and-report-checkpoint.md), and [E15 related-evidence checkpoint](../decisions/2026-09-17-t01-related-evidence-capability-validation.md). These records retain individual setup, artifacts, and accounting.

The i9 improvement does not establish new executable harness source. The i12 regression co-varies with several implementation changes and does not isolate one quantitative rule. E14's skill-only change and probe sensitivity do not supply a new score or useful executable capability. These episodes motivate studying how the Evolver chooses and tests its own methodological revisions.

E15 reproduces an investigator-specified public endpoint diagnostic: changing only March's final daily return leaves April volatility unchanged in i9 but changes it by 0.22033310690395128 in i12, consistent with T01's inclusive daily endpoint followed by a monthly lag. This exposes an operation-level success in the globally worse candidate without promoting it. The Evolver adds only a 1,747-byte skill section; admission and one skill-load smoke do not test fresh Worker use. Its repeated rejection of research-time tools is inconsistent with the available interface, and its proposed two-month fixture omits sufficient warm-up. The revision episode costs USD 0.1502948939 over 22 accounted requests and produces no new official score.

The separately registered [i15 fresh Worker and replay](../decisions/2026-09-17-t01-endpoint-policy-worker.md) supply that subsequent observation: the Worker implements the inclusive endpoint, repairs its inadequate fixture and initial estimator/alignment mistakes, and executes sizing and portfolio consumers. The public paired-return diagnostic changes April volatility by 0.20711093891181417 while leaving March unchanged. The unchanged official replay returns 5/17 (A4/7, B1/10), reward 0, with no errors, skips, or contract adjustment: an aggregate null versus i9, not proof of identical passed properties. Worker cost is USD 0.1364681080; combined E15 plus Worker cost is USD 0.2867630019. EW normalization, month indexing, price treatment, and signal-history eligibility also change, precluding isolated score attribution. The shortened signal lookback support motivates a horizon-specific eligibility hypothesis, not a verified next capability or an explanation of hidden failures. This is policy uptake into task code, not an Evolver-authored executable harness addition.

[E16's support-operation search](../decisions/2026-09-17-t01-support-operation-evolution.md) uses complete i15 as exploratory parent and i9 as independent related evidence. The investigator-led public diagnostic exposes directional signals and holding returns below the declared signal horizon; startup encoding, interior-gap treatment, and permitted volatility bootstrap remain separate questions. E executes three public artifact probes but incorrectly infers scorer insensitivity from equal A4/7 and B1/10 counts. Aggregate equality does not identify equal passed properties or invalidate an operation-level repair; its nonaligned timestamps also leave paired portfolio statistics undefined. The run ends with zero mutations, 23 turns, 36 tool calls, 449.228 seconds, and 23 accounted requests totaling 2,109,948 tokens and USD 0.1975412084. No Worker or replay follows. `CALIBRATED_ABSTAIN` is the protocol label, not validated calibration. Provisional ACT and research-time tools were already available; the evidence does not establish a runtime obstruction or an ability ceiling.

The [E17 review-enabled episode](../decisions/2026-09-17-t01-decision-review-evolution.md) directly chooses ACT and adds only fixed-window signal-support advice, with one passed skill-load smoke. It uses 24 turns, 36 tool calls, zero tool errors and 240.261 seconds; 24 accounted requests consume 1,758,283 tokens and USD 0.1033432447. The audit records self-review enabled but not offered: no review effect is measured. No fresh Worker or official replay follows. The decision again incorrectly rejects research-time tools because the final artifact must be standalone. The new text's prescribed summation, mandatory NaN/exclusion, and first-defined-row test risk overgeneralizing beyond support alone; separately permitted bootstrap is preserved. These are untested risks, not observed downstream harm or a new score.

[E18](../decisions/2026-09-17-t01-operation-development-evolution.md) changes the development brief and uses E17's decision as feedback while retaining complete i15 as parent. It adds a 107-line / 4,018-byte executable tool, a 21-line / 1,282-byte skill addition, descriptor and binding. The tool compares the first nonmissing signal position with global `lookback - 1`; it does not receive raw observation support or consumer inputs. E18 uses 35 turns, 53 tool calls, zero tool errors and 430.937 seconds; all 35 requests are accounted, with 2,832,870 input plus 53,880 output tokens (2,886,750 total), costing USD 0.135821862. Trace/access records contain three legacy tool-smoke invocations and the final self-report mentions partial/full cases; retained component tests are graph/load/import. This does not justify saying E never called the function or claiming broad behavioral coverage. Investigator follow-up calls at lookback 12 accept onset 11 and all-null output, but reject onset 0, a valid late onset 15 and neutral-zero startup. T01 explicitly has staggered instrument starts, so output onset alone does not establish input-support eligibility. These are local investigator diagnostics, not E-authored tests or measured downstream harm. Self-review is again not offered; no fresh Worker, official replay or new score exists. The result establishes executable generation, not yet useful capability learning.

# Appendix B. Implementation delta and adoption checkpoint

This dated snapshot runs through archived E12. The detailed paragraphs below retain historical implementation and source evidence rather than a newer current checkpoint.

| Element | Existing status | Implementation work remaining |
| --- | --- | --- |
| Full-harness surface | Complete persistent harness mutation and frozen whole-package loading are implemented | Preserve package lineage; attribute mutation, uptake, and outcome separately |
| Minimal matched baseline | H0 scores T12 12/16 and recovered T18 16/18; both binary rewards are 0 | H0 remains incumbent; historical i28 is not its matched comparator |
| E1–E8 development | Historical alternatives; E6 is the strongest complete package at T12 14/16 and T18 16/18, with binary rewards 0 | Keep E6 as fallback and E7/E8 as whole-package negatives; do not splice task-wise winners |
| E9–E12 whole pairs | Retained whole-pair T12/T18 scores: E9 11/16,16/18; E10 14/16,16/18; E11 11/16,16/18; E12 13/16,16/18; every binary reward is 0 | No new best official outcome; diagnostic-parent choices are recorded separately, and E12 is archived with no successor |
| Code and fresh behavior | Real Evolver-authored code reaches fresh Workers; observed cases include source-supported first-draft use and post-write confirmation | Neither pattern alone proves tool-caused repair, adaptive selection, transfer, or official gain |
| Scored closure and accounting | Four scored closures archive E9–E12; activation-plus-Worker traffic totals 324 provider attempts and USD1.7738101895 | Successive investigator-authored policies mean this is not one fixed-policy campaign or total project cost |
| History selection | Selected-history and archive handoffs operate, but entries remain investigator-selected | Learned retrieval, applicability, and cumulative use remain unproven |
| Local execution context | 157 tests pass in 3.99 seconds, plus five fixture tests | Qualified locally only; not deployed, learned, or evidence of saved computation |
| Earlier T01/T26 evidence | Retained as historical source and operation evidence | Not the current baseline, current checkpoint, or an E12 outcome |
| Three main evidence objectives | Partial | Complete missing QCE paired coverage, a learned fresh-Worker mechanism, and an actual cross-round memory-use chain; QF freeze and bounded multi-task execution are measured |

The next-state handoff module, [`quantcodeeval_continuation_revision.py`](../../qea/quantcodeeval_continuation_revision.py), and its CLI have passed 78 local neighboring checks. They consume persisted search state, an explicit parent and selected history without adding a selector or making model calls. After a narrow loader repair, real zero-model preparation retains complete i19 with its own observation/replay, i18's unknown mutation-parent score and H0 as official incumbent. It adds related i21 negative observation/replay and explicitly selected i19/i21 history: two entries, 30 files and 148,312 projected bytes, measuring selected history only, not total context. The preserved r1 preparation defaults to an intervention-directed profile and omits i21 trace content. The [r2 handoff](../../results/qce-quant-full-harness-t01-artifact-operation-handoff-20260917-r2/CONTINUATION-REVISION-HANDOFF.json) repairs trace projection before dispatch, and the actual E22 runtime preserves E21's decision-review profile and low reasoning effort. This corrects unintended condition drift; it is not a tested scientific change. E22 subsequently completes the skill-only revision recorded below. The handoff remains experimenter-written scaffolding, not itself an acquired Worker capability or proof of useful experience reuse.

The [current intervention-directed profile](../../qea/evolve_agent_full/profiles/intervention_directed_full_harness_v1/systemprompt.md) already permits tools, policies, memory, routing, and control-flow changes. The [behavior-feedback caller](../../qea/quantcodeeval_behavior_feedback.py) supplies prior decisions, investigator notes, and one independent related observation without replacing the parent. Its optional unscored-revision mode preserves the complete admitted package as the mutation parent while labelling older observation/replay as ancestor evidence, not current-package behavior. Its [selected-history source path](../decisions/2026-09-17-selected-history-behavior-revision-source-checkpoint.md) accepts explicit entry IDs and a recorded maximum (default four), projecting only those read-only closures and preserving their scores/costs. Reload reuses prepared evidence. The latest local source adds index-capacity and selected-closure byte limits, including the integration repairs detailed below. Automatic applicability retrieval and cumulative multi-task learning remain unestablished; the real one-round ingest is recorded below. Existing [experience ranking](../../qea/quantcodeeval_experience.py) is heuristic, not a calibrated Bayesian memory policy.

The [once-only self-review source checkpoint](../decisions/2026-09-17-abstain-evidence-review-source-checkpoint.md) preserves the original decision and offers the same Evolver one evidence reassessment before closing an unchanged ABSTAIN, while ordinary development allowance remains. Tests exercise real guarded ABSTAIN-to-ACT, candidate writing and component calls; old profiles leave the option off. This is experimenter-authored revision-policy engineering informed by E16, not a learned Worker capability, independent reviewer, or validated calibration mechanism. The separately [registered E17 episode](../decisions/2026-09-17-t01-decision-review-evolution.md) deploys it with the original E16 parent, related observation, note and inference settings, without selected history or an additional E16 critique. Its direct ACT does not trigger the review; deployment and local tests therefore remain distinct from real review-effect evidence.

The [promotion-subtype source checkpoint](../decisions/2026-09-17-history-promotion-subtype-source-checkpoint.md) preserves optional accepted-selection subtypes and derives distinct official/state/diagnostic/legacy wording and reuse operators. It leaves raw scores, coarse labels, binary tie selection, ranking, and whole-archive costs unchanged. This locally tested engineering change was not deployed to E16 and establishes neither learned capability nor cumulative multi-task success.

The subsequent [imported-parent card repair](../decisions/2026-09-17-imported-parent-experience-source-checkpoint.md) preserves the explicit continuation role of a measured archived candidate selected as a research parent. Cards suggest CONTINUE/NEW_PROBE, not official support or REUSE; raw archived status, rewards, ranking and incumbent selection remain unchanged. Actual bridge-to-card tests pass, but this is source-only scaffolding and is excluded from E17. Local generic-live append/preflight/telemetry wiring is now tested; bounded selected text and archive bytes still do not establish bounded total evidence work or real cumulative use.

The [scored-continuation source checkpoint](../decisions/2026-09-17-scored-continuation-source-checkpoint.md) provides a locally tested zero-model handoff from completed revision, Worker observation and replay into durable history/search state. It preserves actual research-parent versus incumbent lineage, raw results and stage costs; component activation is not inferred from completion. Caller-supported diagnostic continuation remains distinct from official promotion. The [current-source review](../decisions/2026-09-17-current-source-and-benchmark-review.md) verifies that retained E/Worker usage is added once to search totals, with incomplete billing explicit in paired episode accounting; the numeric subtotal alone is not necessarily a complete bill. Two successive unit-fixture handoffs pass, not two live learning rounds. A separate [real local bootstrap result](../../results/qce-quant-full-harness-t01-scored-bootstrap-20260917-r1/SCORED-CONTINUATION-BOOTSTRAP.json) now imports measured H0 as official incumbent and measured i19 as the explicit research parent. It archives actual i18-to-i19 lineage while preserving i18's unknown score and i15 as observed ancestor only. No scored selector is invoked and no uptake is inferred from completion. The initialized state contains zero rounds, zero new model requests and zero new cost; imported historical E19-plus-i19 accounting remains separate at 93 requests and USD 0.2850098623. This is actual initial import, not a completed scored-selection round, later experience-card consumption or cumulative multi-task learning. The engineering source was not part of E18's runtime treatment.

The separate [E19 unscored-parent handoff](../decisions/2026-09-17-t01-operation-refinement-evolution.md) is implemented, locally tested, deployed and exercised by actual preparation and one completed evolution: complete original i18 remains unscored, with i15 observation/replay and independent i9 evidence separately labelled. E19 completes at 2026-09-16T20:51:33Z under the unchanged qualified revision policy, refining executable tool, descriptor and guidance (31 requests, USD0.1026270612). Its retained call distinguishes late strict/partial/undefined onset; investigator direct calls of unchanged i19 on the public panel correct i18's16 false-partial columns and detect all22 i15 partial signals. The computation counts cumulative underlying observations at first signal definition, not trailing support or downstream validity; missing-input, stale-window, neutral-zero and all-null aggregate limitations remain. The separate [original-i19 Worker](../decisions/2026-09-17-t01-operation-refinement-worker.md) completes under matched qualified settings (62 requests, USD0.1823828011). It calls the tool three times with underlying observations; two split-format inputs fail, then a column-list call succeeds after source inspection and supplies a scoped reconciliation confirmation. Strict-window code and independent panel checks preceded these calls, and no subsequent strategy edit follows. This is real fresh uptake and interface recovery, not demonstrated tool-caused repair. Its unchanged zero-model replay completes at 2026-09-16T21:34:48Z with 5/17 (A4/7, B1/10), reward0, no errors/skips or contract adjustment: an aggregate tie with i9/i15, not identical-property proof. The separate authentic aligned H0 comparison is recorded below. The unscored-parent handoff does not exercise the distinct scored-continuation API.

The [codebase review](../decisions/2026-09-17-codebase-review-h0-completion-and-bounded-history.md) reaffirms capability-first development. The i19 trace exposes invalid/undefined endpoint comparisons and an overbroad verification summary. A plausible next target is constructing and interpreting valid quantitative experiments, not presuming another endpoint strategy defect or adding a checker by default. Local bounded-history source limits final selected entries to four, the index to 1 MiB/10,000 entries, and unique selected closure content to 256 MiB before content reads. After the review's 152-test checkpoint, both diagnosed integration defects are repaired locally: empty selected-history projection preserves its root, and scored-continuation and bootstrap appends pass the shared index-capacity limits. Root independently runs 90 focused tests after these fixes. These source repairs are not an E20 runtime overlay or a scale deployment; they do not establish scale readiness, bounded whole-evidence/context cost or multi-task learning. The dated review preserves the earlier open-defect state.

The authentic matched T01 H0 has completed and delivered `strategy.py`: 35 requests, 690,615 tokens, USD 0.0681428008 with complete accounting, normal exit and no restart. Its separately registered unchanged official replay now returns 5/17 (A4/7, B1/10), reward 0, with zero model requests and no errors, skips or contract adjustment. The retained result is [REPLAY-RESULT.json](../../results/bc-mirror/qce-quant-full-harness-t01-aligned-h0-eval-20260917-r1/REPLAY-RESULT.json). This is a matched single-task aggregate null versus original i19, not identical-property proof, a capability ceiling or the final frozen-panel comparison. The i19 Worker uses 62 requests and USD 0.1823828011; E19's USD 0.1026270612 search cost is separate. Its actual tool use still does not establish tool-caused repair. E20 has no retained capability result here. The completed local bootstrap preserves historical i18 as an unscored mutation parent without borrowing i15's score or inventing old search rounds.

[E20's experiment-construction attempt](../decisions/2026-09-17-t01-experiment-construction-evolution.md) has now failed with terminal model-call budget exhaustion: 33 requests, 2,779,469 input and 54,507 output tokens (2,833,976 total), USD 0.1516153644 with complete accounting. The retained working snapshot is not admitted; there is no fresh Worker, official replay or new score. Smoke argument errors are observed, while the upstream cause remains under review. This is a retained development negative, not useful capability or an ability ceiling.

[E21](../decisions/2026-09-17-t01-answerable-experiment-continuation.md) completes ACT/admitted/revised_unscored from original i19 with eight candidate files, changing the signal-support tool and descriptor to repair the observed split-JSON input crashes. It uses 33 turns, 50 calls, zero reported errors and 391.614 seconds; 33 requests, 3,535,458 tokens and USD 0.1507707095 are fully accounted. Root's direct same-input test fails with ValueError in i19 and returns a report in i21. Records-list works in Python but remains blocked by the object-only schema. This is an ordinary executable interface repair; the experiment-construction target is unmet. Structured component records are import smokes, distinct from actual tool calls and the direct comparison. The experimenter-repaired finalization path completes one restricted action and one reserved final report. E19 entry/CATALOG/RELEVANT are actually read, without proof that memory caused the repair or improved an outcome. The separate original-i21 Worker result follows.

The [original i21 Worker](../decisions/2026-09-17-t01-input-serialization-worker.md) delivers a scorable strategy with the unchanged eight-file package, no seed and matched H0/i19 runtime, but ends with context overflow: 223,087 tokens against a 200,000-token limit. Wrapper status complete/exit zero does not establish normal research completion. All four support calls fail: two incomplete split payloads omit data/observations; two supply invalid truncated column strings. The strategy is written before these calls and is never edited afterward. The single unchanged zero-model replay returns 2/17 (A2/7, B0/10), reward 0, without errors/skips or contract adjustment: a check-count regression from H0/i19's 5/17 and a binary tie, not proof that the tool caused the decline. This does not refute the locally verified complete-split repair. The observed next capability gap is transferring large computed frames through a usable artifact or execution path, rather than reconstructing them as model-generated JSON. Worker accounting is complete: 92 requests, 8,454,550 input plus 269,644 output tokens (8,724,194 total), USD 0.4924535776 and 2055.121 seconds. Reported 92 turns/93 calls/11 errors remain distinct from 92 parsed trace calls (79 shell, 8 state, 4 support, 1 skill load). E21 search plus this Worker totals 125 requests and USD 0.6432242871; these costs are separate from earlier development.

The subsequent [real scored ingest](../../results/qce-quant-full-harness-t01-input-repair-scored-continuation-20260917-r1/SCORED-CONTINUATION.json) completes with zero new model requests. Its [persisted search state](../../results/qce-quant-full-harness-t01-input-repair-scored-continuation-20260917-r1/SEARCH-STATE.json) contains one actual E21-plus-Worker round, 125 requests and USD 0.6432242871 with complete accounting. The experimenter-controller explicitly sets new information true but continuation from i21 false: the selector proposes diagnostic promotion, while the final selection archives the negative episode and keeps H0 as official incumbent and i19 as research parent. This preserves the failed frame-transport/context evidence without making i21 the next parent. It is explicit controller judgment, not automatic applicability retrieval or Bayesian memory. The next handoff and E22 revision have now run; useful subsequent Worker consumption and cumulative multi-task learning remain unestablished.

The [preserved r1 preflight](../../results/qce-quant-full-harness-t01-artifact-operation-handoff-20260917-r1/BEHAVIOR-REVISION-PREFLIGHT.json) has no i21 trace parts because one event exceeds the guarded read bound. The [r2 preflight](../../results/qce-quant-full-harness-t01-artifact-operation-handoff-20260917-r2/BEHAVIOR-REVISION-PREFLIGHT.json) contains five related trace parts with that event replaced by bounded public projections, not a full lossless trace; i19's own trace has two parts. E22 reads the selected i19/i21 entries, catalog/relevant views, related strategy and outcome summaries, but its access record contains no reads of the repaired related trace parts. Available evidence and actual consumption remain distinct.

[E22](../decisions/2026-09-17-t01-artifact-operation-evolution.md) completes ACT/admitted/revised_unscored from complete original i19. Its eight-file package changes only the skill: 24 added lines / 1,407 bytes on month-end index precision, with no executable mutation and only a skill-load component smoke. Public-data probes observe 315 end-of-day monthly labels and a one-row DataFrame from a date-string lookup; normalization changes the lookup to a Series and reports unchanged return/portfolio values on that fixture. The initial probe's ambiguous-array truth error is repaired. These are scoped observations, not a theorem of value neutrality or attribution of official failures. E22 cites the archived i21 negative when rejecting another parser repair, without isolating memory's causal effect. It uses 29 turns, 47 calls, three reported errors and 636.23 seconds; all 29 requests are accounted at 2,309,484 input plus 62,805 output tokens (2,372,289 total), USD 0.1842625372. Subsequent public-data qualification defers the original i22 Worker; i22 remains an unscored branch, not the replacement research parent. This policy-only result does not implement artifact-backed transport or establish new useful executable capability. Historical changes to revision profiles/controller plumbing are not retroactively one fixed-policy campaign; the final campaign's fixed-policy requirement remains.

The retained [zero-model index qualification](../../output/qfbench-supervisor/qce-quant-full-harness-t01-artifact-operation-20260917-r1/MONTH-END-INDEX-QUALIFICATION.json) reproduces i19's lookup defect on the full 315-row, 22-instrument public panel and verifies unchanged values after normalizing its six output indices. Matched H0 already emits midnight month-end labels and retains the same 5/17 aggregate, without establishing equal failed properties or index precision as their cause. Converting a monthly PeriodIndex at its start alone yields month-start dates; MonthEnd alone preserves the time component of an existing end-of-day label. Thus the skill's slash-separated alternatives are economically ambiguous. The original i22 Worker is not uploaded or dispatched; this is a local qualification outcome, not a new official negative or benchmark gain. The next capability investigation remains actual research-operation usability from i19 plus related i21 evidence, not merely revising date wording.

[E23](../decisions/2026-09-17-t01-artifact-consumer-evolution.md) completes once at 10:11:25 local, ACT/admitted/revised_unscored, from complete original i19 under the investigator-selected operation brief. Its eight-file candidate changes the support tool, descriptor and skill to accept CSV signal/observation paths and adds an input converter: 104 added / 21 deleted lines, 5,228 added / 1,074 deleted bytes (4,154 net). The operation remains cumulative observation count at first signal definition, not rolling-window or downstream validity. The primary real-data probe uses 315-by-22 frames and reports equal inline support results across CSV round-trip, with 179,436 JSON versus 178,002 CSV bytes; it does not execute the final candidate or demonstrate compression. The intended benefit is avoiding model retranscription. Structured component tests record imports/load only, while four legacy tool-smoke calls also occur; trace rows 68–83 show fixture correction, path-call and cleanup with model claims but no detailed stdout sufficient to certify full real-data candidate behavior. Both history entries, the brief, related outcomes and i21's first projected trace part are read, not proof of autonomous target discovery or causal memory benefit. Accounting is complete: 34 turns, 57 calls, zero reported errors, 466.325 seconds; 34 requests, 2,895,854 input plus 49,696 output tokens (2,945,550 total), USD 0.2000632521. Terminal reserve is not triggered and execution is cleaned up. Independent qualification now calls the unchanged final candidate on the actual 315-by-22 public intermediates: absolute CSV paths across cwd reproduce i19's full in-memory report (22 full, zero partial/undefined). Dates, columns and missingness match; signal values are exact and observation values numerically equivalent. Missing paths raise FileNotFoundError; relative paths succeed in the matching cwd and fail across cwd. Two local tests pass. This investigator qualification is retained in [I23-ARTIFACT-CONSUMER-QUALIFICATION.json](../../output/qfbench-supervisor/qce-quant-full-harness-t01-artifact-consumer-20260917-r1/I23-ARTIFACT-CONSUMER-QUALIFICATION.json), not learning or uptake. The [original i23 Worker](../decisions/2026-09-17-t01-artifact-consumer-worker.md) subsequently completes normally with no retained failure: 70 completed/accounted requests, 2,430,563 input plus 67,082 output tokens (2,497,645 total), USD 0.1652981616 complete, separate from E23 search. Its execution summary reports 69 turns, 69 calls, eight errors and 703.37 seconds; these reported counts are not provider request counts. It delivers an 11,190-byte strategy, persists its actual 315-by-22 intermediates to signal.csv and monthly_obs.csv (trace rows 77–78), and makes one successful absolute-path support call (81–82): 22 full, zero partial/undefined columns. Strategy creation/last modification occur at rows 51/53; state and final text at 129/139 cite the report, with no subsequent strategy edit. The call precedes S5 entry, not a prescribed S5-ordering demonstration. This is real artifact-backed fresh uptake and post-code report-level confirmation, not tool-caused repair, rolling validity or score gain. The target and independent qualification remain investigator-provided; the persistent revision is Evolver-authored. The unchanged zero-model [official replay](../../results/bc-mirror/qce-quant-full-harness-t01-artifact-consumer-eval-20260917-r1/REPLAY-RESULT.json) completes at 11:17:23 local with 2/17 (A2/7, B0/10), reward 0, no errors/skips or contract adjustment. This is a check-count regression versus matched H0/i19 at 5/17 and the same aggregate as i21, not evidence of identical passed properties or tool-caused damage. Actual zero-model [scored ingest](../../results/qce-quant-full-harness-t01-artifact-consumer-scored-continuation-20260917-r1/SCORED-CONTINUATION.json) archives the complete code/use/negative-outcome episode as new information while explicitly retaining i19 as research parent and H0 as official incumbent. E23 plus Worker uses 104 requests and USD 0.3653614137, fully accounted. The sibling SEARCH-STATE.json now contains two actual ingested episodes, 229 requests and USD 1.0085857008; this covers E21/i21 plus E23/i23, not all historical development or cumulative multi-task learning.

A separate investigator-only [public calendar diagnostic](../../inspection/t01-calendar-operation-20260917/calendar-composition-result.json), reproduced by the sibling `analyze_calendar_composition.py`, calls unchanged H0/i19/i23 strategies on the same 22 CSVs. Holding each target's Close fixed, alone versus the full panel, and aligning numeric values by Period(M), i23 volatility and position change for 22/22 instruments; H0 and i19 each change for 0/22 (absolute tolerance 1e-12). Timestamp labels also change for 17/22 i23 instruments, separately from numeric differences. At each instrument's first eligible holding, it already has 12 own monthly returns and 189–238 valid own daily returns through the prior month end: insufficient warm-up availability is not the observed gap on this panel. The diagnostic identifies estimation-calendar sensitivity, not a proof that the union calendar is wrong or the cause of i23's 2/17. It uses no model, new Evolver/Worker or official evaluation and changes no candidate; it is investigator evidence, not learned capability or gain.

A subsequent investigator-only [current-i19 horizon diagnostic](../../inspection/t01-return-horizon-20260917/return-horizon-result.json) varies summed versus compounded lookback returns while retaining the actual monthly data, volatility, sizing, labels and next-row consumer. It changes 214 of 6,080 finite signal cells and 214 of 6,058 common finite holding cells across 22 instruments. The public paper's cumulative-index definition supplies the operational basis; its separate sum-based mean decomposition does not replace the trading definition. E12 already tested compounding advice with a negative whole-candidate result, and E14 remained unscored. This confirms a known distinction on the current parent, not a new discovery, score/profit gain or learned capability. The next operation must be judged by actual computation and fresh use, not by repeating the advice.

[E24's retained result](../../results/bc-mirror/qce-quant-full-harness-t01-horizon-return-activation-20260917-r1/BEHAVIOR-REVISION-RESULT.json) is ACT/admitted/revised_unscored from original i19 under the investigator-selected horizon-return brief. Four changed files add the executable compounded-return operation, descriptor, agent binding and skill guidance; 34 requests cost USD 0.1917781696 with complete accounting. This is an actual operator addition beyond repeated compounding advice. Its [public probe log](../../results/bc-mirror/qce-quant-full-harness-t01-horizon-return-activation-20260917-r1/evolutions/iteration-0024/probe-log.jsonl) retains a failed actual-tool import followed by successful inline arithmetic, which bypasses the new callable's output interface. Structured component records cover graph/load/import; legacy fixture smoke calls have limited retained outputs. The decision also incorrectly attributes E12's 20x position cap to i23; the related i23 sizing implementation has no such cap. Neither negative official outcome can be attributed to compounding from these records.

Independent [qualification of original i24](../../inspection/t01-e24-horizon-qualification-20260917/qualification-result.json) calls the unchanged final tool on the actual 315-by-22 public frame. Its 6,080 finite horizon values and signs match the tested public definition, and CSV/direct numerics agree. However, the [tool's date-only output](../../results/bc-mirror/qce-quant-full-harness-t01-horizon-return-activation-20260917-r1/evolutions/iteration-0024/candidate/tools/horizon_return.py) loses the parent's month-end time component: reconstructing the returned series gives zero exact matching labels and zero holding rows through the unchanged i19 consumer. Investigator-only reattachment of the original index restores 315 rows and 6,058 finite holding cells, including 214 changes versus i19; that comparison is not an evolved repair. The full serialized report is 179,943 bytes, an interface limitation rather than observed Worker overflow. This identifies output compatibility with its actual consumer as the next operation gap. The original i24 Worker remains deferred, with no fresh use, replay or official score for that candidate. The separately recorded E25 continuation follows below; the original negative remains preserved.

[E25](../../results/bc-mirror/qce-quant-full-harness-t01-horizon-consumer-activation-20260917-r1/BEHAVIOR-REVISION-RESULT.json) continues actual unscored i24, with i19's 5/17 as observed-ancestor evidence and i23's 2/17 as separate related evidence. Under the investigator-selected interface target, it changes one Python file to preserve full timestamps: 9 added/2 deleted lines, unchanged arithmetic and remaining package. It ends ACT/admitted/revised_unscored after 22 requests at USD 0.0669946888, fully accounted. Its [before/after public probes](../../results/bc-mirror/qce-quant-full-harness-t01-horizon-consumer-activation-20260917-r1/evolutions/iteration-0025/probe-log.jsonl) call the actual candidate on the public monthly frame, reconstruct and reindex its returned signal, then invoke the ancestor holding function with unit positions. Exact label matches rise from 0 to 315 and non-missing holdings from 0 to 6,058 across 303 active rows. These are not total DataFrame row counts; the decision's prediction of 315 finite holding rows exceeds the measured 303. A 2-by-2, lookback-one component call separately checks timestamp output. This is a locally verified Evolver-authored ordinary interface repair, not autonomous target discovery or isolated causal memory benefit. There is no i25 fresh Worker, replay or official score at this checkpoint, and neither i24 nor i25 borrows an ancestor's score.

Independent [original-i25 qualification](../../inspection/t01-e25-horizon-qualification-20260917/qualification-result.json) verifies DataFrame/CSV agreement and 6,080 finite horizon values/signs against the public compounded reference. All 315 returned labels reconstruct exactly without source-index reattachment or signal reindexing. Through actual i19 volatility, sizing and holding functions, this yields 315 total rows, 303 active rows and 6,058 finite holdings, matching the compounded reference with 214 changes versus i19. This qualification preserves the original candidate and is separate from the Evolver's unit-position probes; it establishes the tested consumer repair, not fresh Worker behavior or official improvement. The report remains a full-frame output of 185,335 bytes, not observed context overflow.

The subsequent [original-i25 fresh Worker](../../results/bc-mirror/qce-quant-full-harness-t01-horizon-consumer-observation-20260917-r1/WORKER-OBSERVATION-RESULT.json) completes with a 10,728-byte standalone strategy, 52 requests and USD 0.2764243917, fully accounted. E25 plus Worker totals 74 requests/USD 0.3434190805, not all development. In the retained attempt `ac0cbb4cba5e79c905d681d8c866f094e2f8d3775b5acfd1e2f8626f2e4253c0`, `raw-trace.jsonl:29` already implements compounded momentum; rows 60--63 show a successful horizon-tool call followed by independent recomputation and confirmation, not returned-series consumption by holdings. The Worker uses midnight trading-date labels, so this call does not itself test the non-midnight precision defect isolated in the earlier qualification. Inherited EWMA guidance separately exposes finite-history weight normalization and prompts a strategy repair/recheck (rows 47--55), not an E25-specific gain. Three support-tool schema rejections precede direct-import/DataFrame recovery (rows 64--83); the summary's four tool errors are heuristic, not an exhaustive failure count. These observations establish fresh research-time use and a separate inherited-guidance decision link, not useful horizon-induced correction or autonomous target discovery.

The subsequent [unchanged official replay](../../results/bc-mirror/qce-quant-full-harness-t01-horizon-consumer-eval-20260917-r1/REPLAY-RESULT.json) returns **3/17 (A3/7, B0/10), binary reward 0**, with zero errors/skips, `contract_adjusted=false` and zero model requests. This is a check-count regression versus matched H0/i19 at 5/17, with binary reward tied. It neither erases the independently verified interface repair nor attributes the whole-candidate regression to the horizon operation or inherited EWMA revision. Replay adds no model requests to the scoped E25-plus-Worker subtotal above. Scored-history ingestion and parent promotion remain separate operations; neither is established by this replay result.

The separate [actual i25 scored ingest](../../results/qce-quant-full-harness-t01-horizon-consumer-scored-continuation-20260918-r1/SCORED-CONTINUATION.json) is now complete with zero new model requests. It archives the negative descendant under explicit controller judgment, retaining i19 as research parent and H0 as incumbent. The actual chain remains i19 -> unscored i24 -> scored i25, with i24's own evaluation null. E24 plus E25 plus Worker accounts for 108 requests/USD 0.5351972501, complete, distinct from E25 plus Worker above. The sibling `SEARCH-STATE.json` contains three ingested rounds totaling 337 requests/USD 1.5437829509; the archive has four entries including bootstrap. Neither subtotal is all development. This establishes actual archival and lineage/accounting continuity, not learned applicability retrieval, cumulative multi-task learning or improvement over the retained 3/17 result.

A subsequent investigator-only [public initialization diagnostic](../../inspection/t01-initialization-operation-20260918/initialization-operation-result.json), reproduced with the sibling `analyze_initialization_operation.py`, calls unchanged i19/i25 moment helpers: first-observation shocks and nonzero constant returns distinguish first-return from zero initialization, while the zero-prefix shock does not. Public R4 permits warmup/bootstrap and does not uniquely specify the recursion seed or unobserved prehistory. On real public data, the full volatility pipelines differ in 1,111/6,240 common finite cells after monthly alignment; substituting aligned i19 volatility into fixed i25 signal, sizing and holding operations changes 958/6,058 finite holdings. The synthetic helper comparison isolates the seed distinction, but the real pipelines also differ in loading/monthly paths, so those counts measure sensitivity rather than isolated seed causality. This is neither an official result, a learned capability nor an explanation of 3/17; it supports clarifying the finite procedure before selecting any estimator intervention.

The [E26 revision](../../results/bc-mirror/qce-quant-full-harness-t01-experience-reuse-activation-20260918-r1/BEHAVIOR-REVISION-RESULT.json) ends ACT/admitted/revised-unscored: 22 requests/USD 0.1032311825, complete. It reads archived i23 source and reuses its executable support-tool body in retained i19, modifying the Python tool and descriptor (102 added/22 deleted lines). This is ordinary interface repair, not a new estimator. The access summary and trace rows 35/44 establish source access and use; row 67 acknowledges the supplied i23 2/17 negative, but independent reads of its diff/score entry are not established. Related i25 failures inform the choice; the target and selected history remain investigator-supplied. The structured component result retains import PASS; detailed legacy smoke outputs are absent from the exported trace. Records lists remain excluded by the object-valued frame schema despite Python acceptance.

Independent [investigator qualification](../../inspection/t01-experience-reuse-20260918/qualification-result.json) loads unchanged i26 through `AgentConfig.from_yaml -> Tool.execute`: CSV paths, split objects and column-dict objects on retained 315-by-22 frames each return 22 full-support columns, matching an independent calculation. Records lists and DataFrames are rejected before implementation; omitting observations returns 22 partial columns. The tested dates and columns align, while the tool itself slices observations positionally without enforcing index alignment. This qualifies the stated callable routes, not fresh-Worker uptake, a research-decision consequence or official utility.

The subsequent [original-i26 Worker](../../results/bc-mirror/qce-quant-full-harness-t01-experience-reuse-observation-20260918-r1/WORKER-OBSERVATION-RESULT.json) completes a 13,058-byte strategy at 52 requests/USD 0.1240597468; E26 plus Worker totals 74 requests/USD 0.2272909293, complete, not all development. Trace85--88 persist actual frames and consume the support report through both CSV-path parameters without format failure or direct-import bypass. Rows89/97/105 use it as confirmation: strategy creation59 and numerical repair77 precede the call, with no later strategy edit. An investigator-only [consumer diagnostic](../../inspection/t01-experience-reuse-20260918/diagnose_i26_signal_support_consumer.py) finds that STOXX's all-missing first return month becomes zero upstream; the tool counts twelve supplied months despite only eleven source-defined return months. That premature signal reaches a finite holding and portfolio aggregation. The report is internally consistent with its inputs, not a validation of their provenance. [Unchanged official replay](../../results/bc-mirror/qce-quant-full-harness-t01-experience-reuse-eval-20260918-r1/REPLAY-RESULT.json) yields **3/17 (A3/7, B0/10), reward 0**, 14 failed checks, no errors/skips or contract adjustment, and zero model requests. This is a regression versus matched H0/i19's 5/17, not evidence identifying which operation caused failed properties. Actual reuse and smooth uptake do not establish useful capability or learned retrieval; scored ingestion and promotion are separate, not established by replay.

The separate [actual i26 scored ingest](../../results/qce-quant-full-harness-t01-experience-reuse-scored-continuation-20260918-r1/SCORED-CONTINUATION.json) is complete with zero new model requests. Explicit controller judgment archives i26 as new operation evidence, does not continue from it, and retains i19/H0. The sibling search state contains four ingested rounds totaling 411 requests/USD 1.7710738802 and five history entries including bootstrap. These scoped totals exclude other development; the actual archive update does not establish learned retrieval, cumulative multi-task learning or task improvement.

The subsequent [E27 revision](../../results/bc-mirror/qce-quant-full-harness-t01-source-validity-activation-20260918-r1/BEHAVIOR-REVISION-RESULT.json), still from i19 with i26 related evidence, completes ACT/admitted/revised-unscored: three files, 110 added/20 deleted lines, 31 requests/USD 0.1578079236, complete. It adds optional caller-supplied validity-mask counting, split parsing and guidance, not source-to-mask construction or corrected return/holding computation. Actual selected-history access remains investigator-scaffolded. Two public probes affirm i19's correct construction; a helper probe fails import, while later legacy smoke transitions are reported without retained tool payloads. The structured test retains import PASS. The decision inconsistently eliminates `h2_parent_correct` despite its successful probes and counterevidence affirming it. Independent [actual-wrapper qualification](../../inspection/t01-source-validity-20260918/qualification-result.json) derives a mask from all 22 public CSVs without manual panel-cell patching. Through `AgentConfig.from_yaml -> Tool.execute`, split/column-dict inputs on retained 315-by-22 i26 frames change 22 full columns to 21 full and one partial, STOXX count12 to11. Source-grounded small fixtures distinguish genuine zero (count1/full) from the one-price undefined case (count0/partial). CSV paths and native DataFrames are rejected. This is investigator-supplied information changing a report, not candidate-generated validity or a repaired consumer.

The subsequent [original-i27 Worker](../../results/bc-mirror/qce-quant-full-harness-t01-source-validity-observation-20260918-r1/WORKER-OBSERVATION-RESULT.json) ends `worker_failed` before strategy delivery or support-tool use. Its 20-row trace contains skill loading, S1 entry and eight public-paper/listing shell calls; the command records 502 `empty_model_response_after_fallback`. [Read-only generation metadata](../../output/qfbench-supervisor/qce-quant-full-harness-t01-source-validity-20260918-r1/WORKER-EMPTY-RESPONSE-METADATA.json), adding no model requests, records BaseTen `stop` with 4,096/4,098 native completion tokens counted as reasoning and GMICloud fallback `length` with all 8,192 tokens counted as reasoning; neither response has visible content or a tool call. The unchanged low-effort recovery caps the fallback at 8,192; it does not explain the first stop or establish primary-budget exhaustion. Twelve requests/USD0.0248142045 are complete; E27 plus Worker totals43 requests/USD0.1826221281, only this episode. The failed attempt is mirrored and closed, with no artifact for official replay, no score, promotion or scored ingest. This first attempt does not test the method question and is neither a quantitative negative nor evidence of a capability ceiling. The [episode record](../decisions/2026-09-18-t01-source-validity-worker.md) preserves its execution and closure.

The separately registered [second i27 observation](../../results/bc-mirror/qce-quant-full-harness-t01-source-validity-observation-20260918-r2/WORKER-OBSERVATION-RESULT.json) completes with the unchanged original candidate and the same 120/200000/65536 Worker settings: 66 requests and a 12,175-byte strategy. Trace rows 3--4 load source-validity guidance; write 39 and final rewrite 59 precede all successful helper calls. The Worker applies its own `counts >= 2` mask to monthly returns before signal and holding consumption, and aligns calendars, expanding the public-data portfolio from 12 to 303 defined months. The mask addresses the retained initial-price case; it is not a general necessary condition, since a later one-price month may contain a defined cross-month return. Row 97 fails for missing `lookback`; rows 123/125/127 successfully confirm three representative column payloads after the final edit. Rows 129--130 check all 22 columns using ordinary shell code. These observations establish case-specific construction-to-consumer behavior and post-edit helper confirmation, not helper-caused repair, isolated guidance benefit or transfer.

[Unchanged official replay](../../results/bc-mirror/qce-quant-full-harness-t01-source-validity-eval-20260918-r2/REPLAY-RESULT.json) yields **3/17 (A3/7, B0/10), reward 0**, 14 failed, no errors/skips, verifier exit 0, no contract adjustment and zero model requests. It is below matched H0/i19's 5/17; equality with related i26's aggregate does not identify shared failed properties or causes. The subsequent [zero-model scored ingest](../../results/qce-quant-full-harness-t01-source-validity-scored-continuation-20260918-r2/SCORED-CONTINUATION.json) is complete: explicit controller judgment archives new operation evidence without continuing from i27, retaining i19/H0. This does not establish promotion, learned retrieval or cumulative multi-task learning.

The [cost-reconciliation sidecar](../../output/qfbench-supervisor/qce-quant-full-harness-t01-source-validity-20260918-r2/WORKER-COST-RECONCILIATION.json) retains the original audit's one missing cost and adds metadata-only billing evidence: 65 charges subtotal USD 0.2559148004 plus USD 0.032315998 yields r2 USD 0.2882307984. The original audit/result remain unchanged and cost-incomplete; reconciliation adds no model requests. E27+r2 totals 97 requests/USD 0.4460387220, while the full episode including failed r1 totals 109/USD 0.4708529265. These scoped totals are not all development and preserve the unsuccessful observation. The scored continuation retains them in its scoped public evidence, while its canonical cost projection stays incomplete; its booked subtotal is not the reconciled episode cost.

The subsequent [single original-i19 T26 observation](../../results/bc-mirror/qce-quant-full-harness-t26-i19-observation-20260918-r1/WORKER-OBSERVATION-RESULT.json) uses the complete unchanged package, original public task and fixed120/200000/65536 settings, without a seed or investigator brief. It ends `worker_failed` before strategy delivery:33 requests/USD0.0514935884, complete. The62-row trace reaches public training-window/fold computation, then two empty responses terminate execution. Metadata-only GETs identify BaseTen `stop` on both,4098 completion tokens each with4096/4094 reasoning tokens; no new generation is submitted. This does not establish the provider-side cause or exhaustion of the declared primary cap. The completed observation is mirrored and closed, with no eligible artifact, official score or automatic replay. Historical support-i4's T26 13/17 is not i19's score; historical aligned H0 remains failed/unscored. The episode motivates execution-reliability diagnosis, not a new quantitative rule, a transfer claim or a capability ceiling. See the [execution record](../decisions/2026-09-18-t26-i19-observation-preparation.md).

The subsequent [execution-reliability repair](../decisions/2026-09-18-actual-provider-recovery-image-qualification.md) excludes the recognized actual failed provider from the existing single empty-response retry. A separate proxy image passes installed JSON/SSE fake-server checks. A [single public-greeting wire diagnostic](../decisions/2026-09-18-actual-provider-wire-metadata-canary.md) then returns complete usable SSE with BaseTen metadata recognized by the installed parser: one request/USD0.00001612, complete. It is mirrored and closed. This verifies one real metadata response, not live recovery, benchmark completion, quant capability or Evolver learning. The original failed T26 observation remains unchanged; any future H0/evolved comparison must align this investigator-written execution condition.

The separately registered [second original-i19 T26 observation](../../results/bc-mirror/qce-quant-full-harness-t26-i19-observation-20260918-r2/WORKER-OBSERVATION-RESULT.json) completes with the unchanged eight-file package, original public task and same 120/200000/65536 settings: 78 requests/USD0.2290816872, complete, and a 20,521-byte strategy. Only the investigator-written proxy image differs from failed r1; no empty response or retry occurs, so the recovery path is not exercised and completion does not establish its benefit. The Worker writes its strategy at trace89, detects a different cross-validation optimum from its own prototype at91--92, repairs full-panel versus training-fold indexing and duplicate de-marketing at93--94, and obtains prototype agreement at95--96. This is within-task self-repair, not an Evolver-authored persistent revision or an independent numerical oracle.

The inherited support helper is called at133 and139, both returning partial support. The 374-month training length is not a rolling signal horizon; `strategy_ret` does not match the supplied factor-observation columns, so the helper falls back to counting one first-row signal value. The Worker reconciles training support through ordinary shell counts at141--142, with no strategy edit after93. This is actual cross-task invocation with an applicability/input-mapping mismatch, not useful helper transfer. Public outputs also display microsecond dates despite R15's nanosecond contract; that observed concern does not by itself identify an official failure. The actual public training inputs have no missing-value beta failure. These observations guide operation-level diagnosis without attributing hypothetical defects to this execution.

[Unchanged official replay](../../results/bc-mirror/qce-quant-full-harness-t26-i19-eval-20260918-r2/REPLAY-RESULT.json) returns **14/17 (A6/7, B8/10), binary reward 0**, three failed checks, zero errors/skips, verifier exit0, `contract_adjusted=false` and zero model requests. This is i19's own T26 result, not a matched improvement: historical aligned T26 H0 remains failed/unscored, and support-i4's13/17 belongs to another package. Neither the aggregate nor the helper calls isolate causes of failed properties. T01's i19 research parent and H0 incumbent remain unchanged at their own5/17. The [r2 record](../decisions/2026-09-18-t26-i19-recovery-observation.md) and [Worker closure](../../output/qfbench-supervisor/qce-quant-full-harness-t26-i19-20260918-r2/CLOSURE.json) retain the original execution, final mirror, unchanged package and exact cleanup. The first failed observation and wire diagnostic remain separate costs; this r2 subtotal is not all development.

The separate [replay closure](../../output/qfbench-supervisor/qce-quant-full-harness-t26-i19-20260918-r2/REPLAY-CLOSURE.json) records completion23:17:21UTC and closure23:19:43UTC, final additive mirroring and exact container absence. Both completed registrations remain closed; no successor or scale execution follows from this result.

The subsequent [E28 revision](../decisions/2026-09-18-t26-method-applicability-evolution.md) uses this own-scored i19 parent and completes ACT/admitted/revised_unscored:24 requests/USD0.0975565164, complete. It adds27 lines across skill/systemprompt, conditionally enforcing and exactly checking a public nanosecond date contract; the complete eight-file package and inherited executable remain unchanged otherwise. Synthetic pandas3.0.5/NumPy2.5.1 probes support the conversion/check mechanism; the first scalar/path probe does not execute the strategy, and two component load tests do not demonstrate fresh Worker use. This is an ordinary interface repair, not quantitative-method novelty or an official improvement. Its assertion that repairing a research-time helper cannot affect the delivered artifact is stronger than its evidence: a report can change a later Worker decision. The retained decision is not a causal exclusion of alternatives. Finalmirror/exactcleanup pass and the original invocation is closed; [fresh i28 T26 verification](../decisions/2026-09-18-t26-i28-fresh-worker.md) is separately registered, with no Worker or official outcome at this checkpoint.

The subsequent [fresh i28 T26 observation](../../results/bc-mirror/qce-quant-full-harness-t26-i28-observation-20260918-r1/WORKER-OBSERVATION-RESULT.json) uses the unchanged complete eight-file E28 candidate and original public task, without seed, brief or history, under the same declared 120/200000/65536 settings and runtime as i19 r2. The actual materialized package matches E28. Its original invocation runs 00:21:54--01:21:59 UTC on September 18, with no restart, and ends `worker_failed`: `SandboxWorkerTimeout` reports the 3600-second official agent timeout; the retained command has exit 124 and `timed_out=true`. All 54 requests are accounted, with 2,312,863 input / 62,828 output tokens and USD 0.1755591797. E28 plus this Worker totals 78 requests / USD 0.2731156961, a scoped episode subtotal, not all development.

No strategy, raw trace or WorkerExecution is retained, so the attempt does not establish fresh policy use, task-level edits or the underlying timeout cause. Absence from the retained record does not prove that no draft or trace existed in the sandbox before cleanup. It is an observed delivery failure, not evidence that the date policy failed, a quantitative capability is missing or the model reached a ceiling. Official evaluation remains `not_run`, with null score and reward, not zero; i19's 14/17 remains the parent's own result. The [closure receipt](../../output/qfbench-supervisor/qce-quant-full-harness-t26-i28-20260918-r1/CLOSURE.json) confirms final safe mirroring, supplemental package preservation and exact two-container/network absence; three units close at 01:25:15 UTC. The [observation record](../decisions/2026-09-18-t26-i28-fresh-worker.md) retains this unsuccessful attempt. Its locally prepared replay is ineligible and not started; authentic H0 remains local preparation, with no new H0 observation or automatic follow-up.

The subsequent [zero-model event-journal canary](../decisions/2026-09-18-worker-event-journal-runtime-qualification.md) qualifies an investigator-written runtime evidence path: installed NexAU Agent.run/ToolExecutor with synthetic response middleware retains 15 journal events and two partial files across a 15-second external timeout. Completed and unfinished tool execution are distinguishable; command124/timed_out, absent canonical trace/final/WorkerExecution and null score remain. Exact cleanup and mirroring pass. This is engineering qualification, not recovery of i28 behavior, benchmark gain or learned capability.

The separately registered [second i28 observation](../../results/bc-mirror/qce-quant-full-harness-t26-i28-observation-20260918-r2/WORKER-OBSERVATION-RESULT.json) completes at 03:11:39 UTC without failure or restart, using the unchanged complete E28 candidate, original public T26 and the same declared model/120/200000/65536 allowances and official 3600-second deadline. Only investigator runtime diagnostics change. It retains the original 17,072-byte strategy, canonical trace/WorkerExecution and a distinct event journal: 50 requests, 2,276,548 input / 140,797 output tokens, USD 0.1849391708, fully accounted, and 2254.868 Worker seconds. There is no empty response or retry, so provider recovery is not exercised. E28 plus both observations totals 128 requests / USD 0.4580548669, not all development; the first failed observation and E28+r1 subtotal remain unchanged. Final mirror, actual package equality, exact cleanup and direct-loader `contract_adjusted=false` pass; completed Worker units close at 03:14:18 UTC. This is not a new Evolver revision or measured instrumentation benefit.

The fresh Worker loads the skill (journal19--21), implements an explicit `datetime64[ns]` cast in `_as_ns`, and verifies exact MVE/strategy output units at trace81--82 and107--108. This is policy-consistent uptake, but public R15 independently requires the same unit, so guidance causality is not isolated. The original i19's microsecond output discrepancy is corrected; other strategy choices also differ, including covariance ddof0 versus ddof1. The [unchanged official replay](../../results/bc-mirror/qce-quant-full-harness-t26-i28-eval-20260918-r2/REPLAY-RESULT.json) yields **14/17 (A6/7, B8/10), binary reward 0**, with three failed checks, no errors/skips, verifier exit0, `contract_adjusted=false` and zero model requests. This ties i19's own T26 aggregate; it does not establish identical failed properties, isolate the date-policy effect or measure improvement over an aligned H0. No support-tool call occurs, and useful support-tool transfer or quantitative-method gain is unproven. The [completion/replay record](../decisions/2026-09-18-t26-i28-r2-complete-and-official-replay.md) preserves the independent execution and evaluation stages.

The [replay closure receipt](../../output/qfbench-supervisor/qce-quant-full-harness-t26-i28-20260918-r2/replay/CLOSURE.json) records completion at 03:19:46 UTC, successful final mirroring, and exact strategy/verifier container absence with all three units closed at 03:21:29 UTC.

The separately registered [authentic aligned H0 observation](../../results/bc-mirror/qce-quant-full-harness-t26-aligned-h0-20260918-r2/WORKER-OBSERVATION-RESULT.json) naturally completes at 03:42:36 UTC without failure or restart. Its actual six-file initial package preserves the original learned content with only the declared inference-allowance overlay, and its actual runtime matches completed i28 r2; no i28 learned content is imported. The original 14,920-byte strategy, canonical execution/trace and journal are retained. All 55 requests are accounted: 1,984,148 input / 43,839 output tokens, USD 0.1297368896 and 442.624 Worker seconds. Final mirror, exact cleanup and deployed-loader `contract_adjusted=false` pass; completed Worker units close at 03:45:02 UTC. The [separate unchanged official replay](../../results/bc-mirror/qce-quant-full-harness-t26-aligned-h0-eval-20260918-r2/REPLAY-RESULT.json) completes at 03:50:06 UTC with **14/17 (A6/7, B8/10), binary reward 0**, three failed checks, no errors/skips, verifier exit0, `contract_adjusted=false` and zero model requests. This is a matched single-task aggregate null versus i28, not proof of identical passed properties, a model ceiling or a final-panel result. The historical failed H0 remains separate.

H0's actual artifact retains microsecond outputs and checks only the datetime type, while i28 explicitly casts/checks nanoseconds. Public-contract inspection also finds that H0's daily cross-validation complement excludes held-out fold months from the full daily panel, retaining out-of-sample dates that feed covariance, validation scores, selected gamma and final coefficients; i28 restricts that complement to training periods. These observed computation/consumer contrasts do not identify an official failed property or prove which persistent Evolver change caused them. H0 and i28 Worker costs are USD 0.1297368896 and USD 0.1849391708, respectively; E28 search adds 24 requests / USD 0.0975565164, and failed i28 r1 adds 54 requests / USD 0.1755591797 separately. This single-execution cost comparison is not a general efficiency result or all-development accounting. The [aligned comparison record](../decisions/2026-09-18-t26-aligned-h0-r2-complete-and-replay.md) retains the setup, independent stages and claim limits.

The subsequent [investigator-only fit-scope diagnostic](../../inspection/t26-matched-fit-scope-20260918/OPERATION-EVIDENCE.md) changes only daily OOS factor values with all training, monthly and market inputs fixed. H0 includes 3,272 OOS rows in every CV complement: selected kappa changes from 0.1584893192 to 0.7943282347, with downstream coefficient and return changes. i28 includes zero OOS rows and its complete tested outputs remain exactly invariant. Four independent uninstrumented executions reproduce the diagnostic's numerical outputs. This strong scope stress is not a calibrated economic scenario: inference is within each unchanged artifact, without attributing their differing training lower bounds or baseline values to this defect. It does not identify an official failed property, prove E28 causality or establish evolved capability. The tested i28 path exposes no new repair target; no E29 revision follows from this case.

The [independent T26 local bootstrap](../../results/qce-quant-full-harness-t26-scored-bootstrap-20260918-r1/SCORED-CONTINUATION-BOOTSTRAP.json) now retains this measured pair: H0 remains official incumbent and i28 is the explicit research parent, not an official winner. A small source extension preserves E28's known own-scored i19/T26 mutation parent without borrowing ancestor evidence; the earlier unknown-parent path remains. Root35focused tests and the real history closure validate. New rounds/requests/cost are zero; historical E28-plus-i28 Worker accounting is74requests/USD0.2824956872, separate from H0 and failed i28 r1. This is actual local import, not later experience use, a task transition or cumulative multi-task learning.

The [actual local T26 handoff](../decisions/2026-09-18-t26-continuation-handoff-and-t12-screen.md) now prepares unchanged complete i28 and its own T26 score through the existing prepare-only adapter, keeping H0 incumbent. One selected history entry occupies 19 files/75,650 bytes; this is selected closure, not a total-work bound. New requests/cost are zero. The four supplied stages retain 183 requests/USD0.5877917565, including failed i28 r1, not all development expenditure. No later Evolver consumption or cumulative multi-task learning is established.

The same record retains an investigator-only historical T12 counterexample: changing only t−13, outside the declared prior-12-month window, moves the old fresh-panel artifact's trailing value from −0.008175103914 to 0.032307544906, signal from −1 to +1 and consumed portfolio return from −0.02 to +0.02; v2 remains exactly invariant. The old artifact and its passing probe both compute an expanding product. This does not adjudicate arithmetic versus geometric aggregation, attribute its historical 12/16 score or establish an i28 defect.

The [subsequent unchanged-i28/T12 observation and original replay](../decisions/2026-09-18-t12-i28-complete-and-official-replay.md) complete normally: the Worker uses 53 requests/USD0.103064663 with complete accounting and retains its original 7,535-byte strategy; zero-model replay scores **13/16 (A7/8,B6/8), reward0**, with three failed checks, no errors/skips or contract adjustment. The unchanged current artifact is exactly invariant to the same outside-window perturbation through trailing value, signal and portfolio return, closing the historical window target. Two inherited support-helper calls follow strategy construction; after an input-orientation correction, one factor is confirmed fully supported and another undefined, with no subsequent strategy edit. This is scoped uptake/confirmation, not helper-caused repair, new evolution, E28 causal benefit or gain against an aligned T12 H0. Remaining official failure causes are not identified. No new revision or comparison is selected; further experiments pause for user progress review.

The separate [minimal T12 initial observation and replay](../decisions/2026-09-18-minimal-t12-h0-complete-and-replay.md) supplies the first cell of the new lineage. The original-public, no-seed/no-history Worker completes at 07:30:33 UTC with an 11,695-byte strategy, 31 requests, 611,668 input/41,066 output tokens and USD0.0653270257, all accounted; its execution records 31 turns, 41 tool calls and 4 tool errors. Its unchanged zero-model replay completes at 07:37:20 UTC with **12/16 (A6/8,B6/8), reward0**. Each family contains one ordinary failure and one errored check, for two ordinary failures plus two errored checks overall; there are zero skips, verifier exit0 and `contract_adjusted=false`. The error labels do not identify an infrastructure cause. This is an initial measurement, not a matched comparison with historical i28, an effect of removing workflow scaffolding or an evolution result.

The lineage's [own-evidence E1](../decisions/2026-09-18-minimal-t12-e1-complete-and-fresh-worker.md) completes ACT/admitted/revised-unscored at 08:04:38 UTC, using 35 requests, 3,073,173 input plus 61,209 output tokens and USD0.2106140812. Four changed files add a 353-line/13,621-byte executable `validate_tsfm` tool, a 28-line descriptor, agent binding and prompt activation; the admitted package contains five files including the original shell descriptor. The checker imports a draft strategy and reports public callable, universe, trailing-return, signal and common-denominator portfolio checks. This is a real model-authored mutation, but narrow and fallible. The E1 trace records five validator-smoke calls, including a descriptor-path failure followed by a code repair, while the structured component ledger retains only four import/graph/load results and no detailed functional-smoke output. E1 also miscounts the initial result as two failures plus one error per family, versus the actual one plus one, and its own formula probe finds 48 signal differences and a 0.04293333333333333 maximum portfolio-return difference between compounded and arithmetic variants, contradicting its claim that the choice is immaterial. These are errors in the Evolver's own evidence interpretation, not an investigator-authored capability target or a reason to patch the admitted package silently.

The unchanged five-file fresh Worker `qce-minimal-harness-t12-e1-observation-20260918-r1` completes with a 6,306-byte strategy after 12 requests, 124,203 input/14,473 output tokens, USD0.0185831545 and 97.386 seconds. Its trace directly calls `validate_tsfm`, retains all 15 check results as passing, acknowledges the report and then runs an independent end-to-end sanity analysis. No later artifact edit occurs. This is actual activation and report consumption, but not validator-caused repair: the call reports no failure to fix. The Worker's one tool error is retained, and its final prose incorrectly says 16 rather than the 15 emitted checks.

The unchanged zero-model replay completes normally at 08:19:55 UTC with **8/16 (A4/8,B4/8), binary reward0**. Each family has four passes, three ordinary failures and one errored check: six ordinary failures plus two errors overall, zero skips, verifier exit0 and `contract_adjusted=false`. Relative to the matched initial cell's 12/16, E1's descendant loses four passed checks while retaining the same two-error count; both rewards remain zero. The all-pass public-validator report therefore coexists with an official check-count regression. It does not follow that the report, checker, formula choice or any particular artifact difference caused the regression. E1 plus the fresh Worker uses 47 requests/USD0.2291972357; including the initial Worker's 31 requests/USD0.0653270257, this measured minimal lineage uses 78 requests/USD0.2945242614, excluding prior lineages and other development.

The subsequent public-only semantic diagnosis does not change those measured results. The paper passage actually read by the fresh Worker describes the factor as the **average return over the prior year**, while the fresh artifact computes a rolling sum and the initial H0 artifact computes a compounded return. On the same public T12 input and twelve-month window, replacing the fresh artifact's sum with the mean changes 4,881 of 4,884 non-null required `trailing_ret` values, while changing zero signal values and zero of 618 portfolio-return values. A toy series of twelve monthly one-percent returns separates the definitions: mean $0.01$, sum $0.12$, and compound approximately $0.126825$. Because `trailing_ret` is independently required, its scale is a real consumer-visible semantic difference even though the later sign and portfolio aggregation hide it; the public task contract requires the column but supplies no explicit equation. The public wording and fixture do **not** establish the hidden evaluator's intended formula, official correctness, or the cause of either score; downstream invariance also forbids a payoff-gain claim from this diagnosis alone.

The adopted [paired-episode semantic revision](../decisions/2026-09-22-paired-episode-semantic-revision-adopted.md) and [bounded evaluation plan](../superpowers/plans/2026-09-22-paired-episode-semantic-evaluation-plan.md) authorize exactly one E2 using the unchanged minimal H0 as mutation parent and E1 only as negative same-task history/related evidence. The `semantic_episode_full_harness_v1` profile presents the full failed episode and the single conditional chain from public definition through independently delivered quantity and discriminating public example to a reusable harness decision. After 107 focused qualification tests, r1 ends before an Evolver turn on an ambiguous upstream HTTP 429, retaining one request, zero completed requests, no candidate and unknown cost. The identical-input/settings r2 recovery runs for 340.482 seconds and retains seven requests/six completed, four turns, eleven tool calls and fifteen trace rows before the same terminal classification; it also has no decision/candidate and incomplete unknown cost. Its last three reads return `path does not exist: candidate`; these payload errors are not counted by the trace's zero tool-error summary and are distinct from the terminal 429. The six completed requests' known cost subtotal is USD0.0043302384, not total cost. The access summary establishes reads of contract, task, current/related observations and own aggregates, but not of the selected history entry, source tree or raw probe. These interruptions do not evaluate evidence learning, reasoning improvement or a semantic-method effect. The conditional Worker and replay remain local, unuploaded and unrun; no further retry, route/model change, or scale action follows. This remains a researcher-selected target and investigator-authored revision-policy change, not autonomous target discovery or a measured gain.

The preceding interruption paragraph records the 22 September closure. The [23 September authorized recovery](../decisions/2026-09-23-e2-abstain-complete.md) supersedes its stop checkpoint: the frozen third activation completes 31/31 requests at USD0.1788511283, consumes selected history/source/public definitions, and revises a confounded explanation during same-model review. It retains unchanged ABSTAIN with no persistent edit or new score. Five conditional Worker operational files are uploaded after new authority, but no candidate copy/preflight/Worker/replay occurs. All exact runs and owned supervision are now closed. This local reasoning correction does not establish a calibrated final explanation, useful capability or score gain.

The user adopted the quantitative researcher as the high-level learning object and research-method experimentation as the method framing on 16 September 2026, and changed the intended venue from ICLR to ACL. The active manuscript is [paper/acl/](../../paper/acl/); the precise ACL edition, ARR cycle, and submission track remain undecided. This writing adoption does not make the proposed runtime refinements implemented.

This active proposal supersedes the September 12 proposal and the September 15 QOE review as the writing direction. Dated drafts and the ICLR source remain historical records, not competing active manuscripts. The [September 16 writing adoption](../decisions/2026-09-16-acl-researcher-framing-adopted.md) changed no runtime or remote state and dispatched no experiment. The September22 decision separately authorized E2. After two infrastructure interruptions, the September23 user-authorized recovery completed with unchanged ABSTAIN and no persistent capability gain; those exact registrations remain closed.

The renewed user goal subsequently authorizes an [eight-hour evidence-led continuation](../superpowers/plans/2026-09-23-evidence-led-eight-hour-research-plan.md). Its [E3 policy experiment](../decisions/2026-09-23-e3-abstain-complete.md) front-loads experiment selection while holding the H0/E1 corpus and runtime fixed. It completes 30 requests at USD0.1992401974 and returns unchanged ABSTAIN: three H0 files unchanged, zero component tests, admission not required, and no fresh Worker, replay or score. The Evolver reads the E1 patch and related trace, corrects H0's counts, and runs one public counterfactual with 48 signal differences; that synthetic variant receives no official evaluation. Final prose retracts the confounded claim that H0's higher score makes compounding closer to the hidden reference, but the sole persisted decision retains that preference and an unsupported unrun-reproduction guarantee. The final prose also retains unsupported required-output and error-identity inferences. This is partial evidence use and verbal reconsideration, not useful persistent capability, gain, or a capacity ceiling.

The [completed E4 episode](../decisions/2026-09-23-e4-date-policy-and-fresh-worker.md) freezes the exact E3 prompt/profile, corpus, tools, H0, model route and one-review path and changes only requested reasoning effort from low to high. Search completes 21/21 requests at USD0.1344478935 and returns ACT/admitted. The three-file candidate changes only `systemprompt.md` from 910 to 2,099 bytes, adding homogeneous datetime month-end keys, input normalization and a plain-merge self-check; one prompt-load test passes, with no executable edit or functional validation. Its public probe shows that H0 string dates fail a merge against an E4-constructed datetime consumer. R6 nevertheless permits strings, that consumer is not a demonstrated public requirement, the return-convention inference remains confounded, and month-end enforcement may overgeneralize. The archive contains 15 E1 validator checks rather than E4's claimed 16.

The matched fresh Worker then completes 18 requests at USD0.0462581934. It converts every required stage to datetime and executes the proposed QA plain merge, but its first three checks deduplicate dates and therefore do not establish complete `(date, factor_id)` row preservation. Its only artifact patch follows an earlier QA error; the merge later confirms the final artifact without causing that repair. The artifact also switches H0's compounded return to a shifted twelve-observation sum. Unchanged zero-model replay scores **7/16 (A3/8, B4/8), reward 0**, with nine ordinary failures and zero errors or skips, versus H0's 12/16 and E1's 8/16. The error count falls from two to zero, but date handling, aggregation and other artifact choices co-vary, so neither the score nor changed failure profile isolates date-policy causality. E4 is retained as an ordinary interface-policy negative: real uptake, no useful capability or gain, no whole-reasoning or fixed-policy campaign result. Search plus Worker accounts for 39 requests and USD0.1807060869, excluding earlier development. All stages are closed; no scale execution/simulation or old MainR2 change is authorized.

An [investigator-only public-output diagnostic](../decisions/2026-09-23-t12-public-output-comparison.md) narrows that interpretation. Unchanged E1/E4 strategies produce exactly equal numerical values, full row keys and normalized order on the original public CSV after investigator-only date normalization: 4,884 finite trailing returns plus 120 paired NaNs, identical signals, and 618 identical portfolio returns. Their native date types differ. H0 instead differs on 48 signal rows and 46 portfolio dates. Thus numerical co-variation relative to H0 must not be conflated with E1/E4 equality on this dataset. The CSV has no internal missing calendar months within a factor's own endpoints. This local Python diagnostic is not an official replay, a score-cause attribution or an E5 input; other admissible inputs and zero/tie behavior remain outside its measured scope.

The [E5 continuation](../decisions/2026-09-23-e5-negative-experience-registration.md) freezes E4's revision configuration and adds its measured negative alongside E1 experience, retaining H0 as parent. It completes 52 requests at USD0.3737901275 (4,287,797 total tokens) and returns unchanged ABSTAIN, with no fresh Worker/replay/new score. After one development compaction, iteration 49 reaches the context-triggered terminal phase where a new ACT is forbidden; this is not exhaustion of 200 iterations or a provider timeout. The final rationale also retains uncertainty about an untested fused date/formula policy. This is an observed control-conditioned negative, not calibrated abstention, useful cumulative learning, a capacity ceiling or evidence that simply increasing limits would help. The completed source/trajectory diagnosis is summarized below; selected-history bounds do not establish bounded total research work.

The [completed E5 trajectory audit](../decisions/2026-09-23-e5-decision-interface-diagnosis.md) finds a more specific failure: four public probes (eight audit records), initially incorrect related-path/module imports, then six rejected preterminal decisions after a concrete hypothesis. Optional/null fields, diagnostic-reference inclusion and provenance kinds cause serial submission repairs before the correctly enforced context boundary. This motivates a minimal interface repair with unchanged reasoning/context allowances; it does not certify the proposed date/formula intervention. Full failed ACT arguments are unavailable, so regression fixtures are not exact payload replays.

The [E6 interface experiment](../decisions/2026-09-23-e6-executable-validator-and-fresh-worker.md) holds E5's research prompt, H0/E1/E4 evidence corpus, model settings, context and one-compaction allowance fixed while changing the investigator-authored decision interface. After one development compaction, the first decision submission is rejected at `$.discovery`; the second is accepted at iteration 29, before any hard-terminal transition. All 43 requests complete at USD0.3227913652. This is observed interface traversal in one stochastic run, not a causal estimate for the bundled engineering treatment or proof of improved reasoning. Separately, the Evolver authors a complete five-file candidate with four changed files, including a new 440-line/17,616-byte executable `validate_tsfm`, descriptor, binding and invocation policy. Its trailing-return aggregation check is deliberately formula-neutral, but its range, perturbation and date-join checks remain incomplete; R6 permits strings, the datetime consumer is constructed, and E4's error change co-varies with other artifact changes. The unchanged package passes actual matched-Worker preflight, and the registered Worker completes 11 requests at USD0.0265994392 with a 9,937-byte strategy. Raw-trace audit confirms one validator call and 19 passing checks, including four datetime joins over 5,004/5,004/5,004/618 rows. The Worker had already written its compound/datetime first draft before the call and makes no later repair. This is real uptake and confirmation, not validator-caused repair. Replay r1 is retained as an operational startup failure before evaluator execution; the separately registered same-artifact r2 replay completes 14/16 (A7/8,B7/8), with two ordinary failures, zero errors/skips, reward 0 and no contract adjustment. That is +2 passed checks, or +12.5 percentage points, versus matched H0's 12/16 while E1 8/16 and E4 7/16 remain negatives. E6 search plus Worker uses 54 requests/USD0.3493908044, excluding broader work. This is a single-task partial check-count gain, not binary-reward gain, isolated validator/date-policy causality, frozen shared-panel completion or cumulative multi-task learning. The E6 costs remain separate from the audited through-E5 totals below.

An [investigator-only comparison](../../inspection/t12-e6-public-comparison-20260923/FINDINGS.md) on the original public CSV narrows, but does not causally identify, that gain. After date normalization, E6 and H0 have the same complete keyed numerical values at all four required stages: 5,004 universe rows, 4,884 finite trailing values plus 120 paired NaNs, 4,884 finite signals plus 120 paired NaNs, and 618 portfolio returns with maximum absolute difference zero. Their native date representations differ (H0 strings, E6 `datetime64[us]`), and trailing/signal row order differs. Against the numerically equal E1/E4 pair, E6 differs on 4,884 finite trailing values, 48 finite signals and 46 portfolio dates. The unchanged E6 validator fails H0 only on its four constructed date joins while E4/E6 pass all 19 checks. This local Python environment is not the frozen remote evaluator; the public CSV exercises no duplicate, internal-gap or null-return branch. The comparison therefore supports an operation-level date-interface contrast, not official failure attribution, exact causal credit or general transfer.

The [minimal-lineage accounting audit](../decisions/2026-09-23-minimal-t12-development-accounting.md) separates atomic provider spend from derived history subtotals. Through E5, complete-cost runs total 230 requests, 14,495,675 tokens and USD1.2271118015. Two interrupted E2 attempts add a known partial USD0.0043302384, but ambiguous billing prevents an exact all-attempt total; the known floor is USD1.2314420399. This is not full investigator or all-project cost: local engineering, writing, supervision, researcher time and runtime/evaluator compute remain unpriced.

# Appendix C. Citation provenance and interpretation

The sentence that research procedures depend on the research object, available information, and estimation conditions is a synthesis, not a quotation, theorem, or exhaustive taxonomy. Its parts have different sources and scopes.

| Source claim | Supporting source | Role here, and limit |
| --- | --- | --- |
| Analysis choices affect financial evidence | Menkveld et al., introduction and analysis paths [1] | Motivates learning research methods; disagreement is not automatically error |
| Research practice matters in investment research | Arnott et al., protocol and discussion [2] | Motivates domain-aware research decisions; not a proof of agent learning |
| AI researchers vary in methodological choices | Gao and Xiao, abstract and discussion [3] | Direct contemporary motivation; a preprint and not a correctness oracle |
| Information affects asset-pricing implications | Hansen and Richard [4] | Supports conditional interpretation in its domain, not universal routing correctness |
| Endpoint variance uses one common endpoint mean | Moskowitz, Ooi, and Pedersen, p. 233, Eq. 1 [23] | Resolves T01's centering target; not its finite seed, calendar, warmup, or hidden scorer |
| Estimation error can offset optimization gains | DeMiguel et al. [5] | Supports data-aware method choice, not a blanket rule against complexity |
| Economic structure can enter flexible learning | Chen et al., learning criterion [6] | Design precedent, not a harness-evolution guarantee |

The proposed step from these findings to a self-improving quantitative research system is our research hypothesis. The main method contains no new consistency, convergence, or regret theorem. Concrete quantitative relations are used as guidance and case evidence when applicable.

# References

[1] Menkveld, A. J., Dreber, A., Holzmeister, F., Huber, J., Johannesson, M., Kirchler, M., Neususs, S., Razen, M., Weitzel, U., et al. (2024). *Nonstandard Errors*. Journal of Finance 79(3), 2339-2390. [Published article](https://onlinelibrary.wiley.com/doi/10.1111/jofi.13337).

[2] Arnott, R., Harvey, C. R., and Markowitz, H. (2019). *A Backtesting Protocol in the Era of Machine Learning*. Journal of Financial Data Science 1(1), 64-74. [Author-hosted published article](https://people.duke.edu/~charvey/Research/Published_Papers/P138_A_backtesting_protocol.pdf).

[3] Gao, R., and Xiao, S. C. (2026). *Nonstandard Errors in AI Agents*. arXiv preprint, version 2. [arXiv:2603.16744](https://arxiv.org/abs/2603.16744v2).

[4] Hansen, L. P., and Richard, S. F. (1987). *The Role of Conditioning Information in Deducing Testable Restrictions Implied by Dynamic Asset Pricing Models*. Econometrica 55(3), 587-613. [Author publication page](https://larspeterhansen.org/lph_research/the-role-of-conditioning-information-in-deducing-testable-restrictions-implied-by-dynamic-asset-pricing-models/).

[5] DeMiguel, V., Garlappi, L., and Uppal, R. (2009). *Optimal Versus Naive Diversification: How Inefficient is the 1/N Portfolio Strategy?* Review of Financial Studies 22(5), 1915-1953. [Published article](https://doi.org/10.1093/rfs/hhm075).

[6] Chen, L., Pelger, M., and Zhu, J. (2024). *Deep Learning in Asset Pricing*. Management Science 70(2), 714-750; published online in 2023. [Published article](https://doi.org/10.1287/mnsc.2023.4695); [author manuscript](https://arxiv.org/abs/1904.00745).

[7] Lin, J., et al. (2026). *Agentic Harness Engineering: Observability-Driven Automatic Evolution of Coding-Agent Harnesses*. arXiv preprint. [arXiv:2604.25850](https://arxiv.org/abs/2604.25850).

[8] Lee, Y., Nair, R., Zhang, Q., Lee, K., Khattab, O., and Finn, C. (2026). *Meta-Harness: End-to-End Optimization of Model Harnesses*. arXiv preprint. [arXiv:2603.28052](https://arxiv.org/abs/2603.28052).

[9] Guo et al. (2026). *AQuA: Recursively Self-Improving Quantitative Trading Research Agents*. arXiv preprint. [arXiv:2608.12841](https://arxiv.org/abs/2608.12841).

[10] Han et al. (2026). *QuantaAlpha: An Evolutionary Framework for LLM-Driven Alpha Mining*. arXiv preprint. [arXiv:2602.07085](https://arxiv.org/abs/2602.07085).

[11] Li, Y., Yang, X., Yang, X., Xu, M., Wang, X., Liu, W., and Bian, J. (2025). *R&D-Agent-Quant: A Multi-Agent Framework for Data-Centric Factors and Model Joint Optimization*. [arXiv:2505.15155](https://arxiv.org/abs/2505.15155).

[12] Tang, Z., et al. (2025). *AlphaAgent: LLM-Driven Alpha Mining with Regularized Exploration to Counteract Alpha Decay*. [arXiv:2502.16789](https://arxiv.org/abs/2502.16789).

[13] Anonymous authors (2026). *QuantitativeFinance-Bench: Benchmarking AI Agents on Real-World Quantitative Finance Tasks*. Preprint. [Project](https://qfbench.com/); [official repository](https://github.com/QF-Bench/QuantitativeFinance-Bench).

[14] Anonymous authors (2026). *QuantCodeEval: Benchmarking Quantitative Strategy Code Reproduction from Finance Papers*. [Official methodology](https://www.quantcodeeval.cloud/methodology/); [versioned task release](https://huggingface.co/datasets/quantcodeeval/task_data).

[15] Cawley, G. C., and Talbot, N. L. C. (2010). *On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation*. Journal of Machine Learning Research 11, 2079-2107. [Published article](https://www.jmlr.org/papers/v11/cawley10a.html).

[16] Spieker, H., and Gotlieb, A. (2020). *Adaptive Metamorphic Testing with Contextual Bandits*. Journal of Systems and Software 165, 110574. [Author manuscript](https://arxiv.org/abs/1910.00262); [published article](https://doi.org/10.1016/j.jss.2020.110574).

[17] Duque-Torres, A., Pfahl, D., Klammer, C., and Fischer, S. (2023). *Bug or not Bug? Analysing the Reasons Behind Metamorphic Relation Violations*. [Author manuscript](https://arxiv.org/abs/2305.09640).

[18] Yu, H., Zheng, Z., Pan, J. Z., Liu, T., Wang, Z., and He, F. (2026). *AlphaMemo: Structured Search-Process Memory for Self-Evolving Alpha Mining Agents*. arXiv preprint, version 1. [arXiv:2606.20625v1](https://arxiv.org/abs/2606.20625v1).

[19] Wei, T., Sachdeva, N., Coleman, B., He, Z., Bei, Y., Ning, X., Ai, M., Li, Y., He, J., Chi, E. H., Wang, C., Chen, S., Pereira, F., Kang, W.-C., and Cheng, D. Z. (2025). *Evo-Memory: Benchmarking LLM Agent Test-time Learning with Self-Evolving Memory*. arXiv preprint, version 1. [arXiv:2511.20857v1](https://arxiv.org/abs/2511.20857v1).

[20] Cheng, Z., et al. (2026). *Mem²Evolve: Towards Self-Evolving Agents via Co-Evolutionary Capability Expansion and Experience Distillation*. ACL, 20784–20831. [Published article](https://aclanthology.org/2026.acl-long.952/).

[21] Xia, P., et al. (2026). *RRSI: Regularized Recursive Self-Improvement of Agent Harnesses*. arXiv preprint, version 1, September 21. [arXiv:2609.24972v1](https://arxiv.org/abs/2609.24972v1).

[22] Berlot-Attwell, I., Sesterhenn, T., Rudzicz, F., and Si, X. (2026). *Is This LLM Library Learning? Evaluation Must Account For Compute and Behaviour*. EACL, 3534–3568. [Published article](https://aclanthology.org/2026.eacl-long.163/).

[23] Moskowitz, T. J., Ooi, Y. H., and Pedersen, L. H. (2012). *Time Series Momentum*. Journal of Financial Economics 104(2), 228–250. [DOI](https://doi.org/10.1016/j.jfineco.2011.11.003); [author-hosted published PDF](https://docs.lhpedersen.com/TimeSeriesMomentum.pdf).

[24] Zhang, H., et al. (2026). *CoEvoSkills: Self-Evolving Agent Skills via Co-Evolutionary Verification*. arXiv, version 3. [Current paper](https://arxiv.org/abs/2604.01687v3).

[25] Wang, Y., et al. (2026). *Rethinking the Evaluation of Harness Evolution for Agents*. arXiv, version 2. [Current paper](https://arxiv.org/abs/2607.12227v2).

[26] Frazier, P. I., Powell, W. B., and Dayanik, S. (2008). *A Knowledge-Gradient Policy for Sequential Information Collection*. SIAM Journal on Control and Optimization, 47(5), 2410–2439. [Author-hosted published paper](https://optimallearning.princeton.edu/Papers/FrazierPowellDayanik_KnowledgeGradientSICON.pdf).

[27] Donti, P., Amos, B., and Kolter, J. Z. (2017). *Task-based End-to-end Model Learning in Stochastic Optimization*. Advances in Neural Information Processing Systems, 30. [Official proceedings](https://papers.nips.cc/paper_files/paper/2017/hash/3fc2c60b5782f641f76bcefc39fb2392-Abstract.html).
