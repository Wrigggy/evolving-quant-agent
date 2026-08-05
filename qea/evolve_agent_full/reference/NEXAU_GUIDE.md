# NexAU Candidate Guide

The candidate is a file-backed NexAU worker. `agent.yaml` binds each public tool
name and description to a local Python function. Tool descriptions must match
their callable signatures and should state inputs, output shape, and important
failure modes.

You may improve the system prompt, tool descriptions, agent tool declarations,
and local Python under any of the permitted component directories: `memory/`,
`middleware/`, `routing/`, `skills/`, `tool_descriptions/`, `tools/`, and
`validator/`. Creating a directory that does not yet exist is expected and
allowed. Runtime, model, resource, tracing, and security settings are protected
by admission policy. Do not add shell, process, network, credential,
benchmark-test, or solution-reading capabilities.

Local Python must import under the worker's Python runtime, using only the
standard library plus `nexau`, `numpy`, `pandas`, `pydantic`, `runtime_bridge`,
and `yaml`. When a task-specific Python 3.11 dependency is required, use the
provided bounded `runtime_bridge` interface rather than starting a general
shell. Every subprocess call must use a fixed argv, bounded timeout, fixed
working directory, minimal environment, and bounded output. Use
`smoke_candidate_tool` after changing a tool.

Any module you add under a component directory must be reachable by the worker:
declare tools in `agent.yaml`, and make sure a validator, skill, or middleware
module is actually invoked by the worker's prompt or configuration. A component
file that nothing calls changes no behavior and will score as no change.

The worker must save requested deliverables in the designated output directory
and verify their existence before finishing. Prefer reusable inspection,
validation, and artifact-construction behavior over benchmark-specific logic.

