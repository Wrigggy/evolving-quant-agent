# Activation-first experiment before selective task scheduling

Date: 2026-08-20

Status: accepted next mechanism; not yet run live

## Observed gap

QDR-1 produced and registered `check_quant_relations`, updated its tool
description and Worker prompt, and passed a discriminating local smoke. The
six- and ten-iteration blind Workers nevertheless made zero calls to the
component, left the artifact unchanged, and remained T26 12/17 with reward
zero.

The component was visible. Both the Worker system prompt and the
Evolver-authored experiment directive placed the audit "before finalizing."
The retained trajectories instead spent their available turns reading the
large public contract, paper, and existing artifact and never reached that
late checkpoint. This makes late activation timing and call complexity the
leading explanations; it does not yet prove that either one alone is causal.

## Decision

Defer the complete progressive or selective multi-task scheduler. The next
bounded experiment changes activation and tool selection only.

The Evolver remains responsible for the candidate mechanism. When it adds or
refines a callable component, it must also design a task-conditioned activation
path using the available harness surfaces. For an existing repair artifact, the
first route is an early Worker prompt or tool-description trigger: after a
bounded public-contract and artifact inventory, decide whether the component
applies and call it before broad paper or data exploration when it does. The
candidate prediction should name the first component call and the next Worker
action expected from its output.

Do not hard-code `check_quant_relations` or a T26 relation payload into the
frozen coordinator. If Evolver-authored prompt and tool-description routing
again fail, the next fallback is one generic, one-shot middleware or routing
checkpoint. It may remind the Worker to evaluate and invoke the candidate's
declared applicable component; it must not fabricate task-specific arguments,
automatically claim applicability, or repeatedly interrupt the run. Automatic
execution of the quant audit is a later mechanism alternative, not the first
fallback.

## Measurement ladder

Keep the following outcomes separate:

1. the new component is present and registered;
2. the blind Worker actually calls it at the predicted Research State;
3. its observation changes the Worker's next action;
4. the submitted artifact changes;
5. official property count or binary reward improves.

The first activation-timing canary needs only one retained T26 repair seed and
one blind Worker. It does not need the complete task scheduler, transfer panel,
or full benchmark. A positive component call without an artifact or official
change is activation evidence only. A property or binary improvement is the
stronger mechanism result.

## Deferred scheduler

Research-State-conditioned partial task batches, cached positive anchors,
stable-task sleep/wake rules, asynchronous long-tail execution, and the full
frozen-candidate panel remain on the later scaling route. Revisit them after the
current loop can reliably activate an Evolver-created component and obtains at
least one official improvement, or when measured multi-task breadth makes
full-panel evaluation the active bottleneck.
