# NexAU Candidate Guide

The candidate is a file-backed NexAU worker. `agent.yaml` binds each public tool
name and description to a local Python function. Tool descriptions must match
their callable signatures and should state inputs, output shape, and important
failure modes.

You may improve the system prompt, tool descriptions, agent tool declarations,
and local `tools/*.py` implementations. Runtime, model, resource, tracing, and
security settings are protected by admission policy. Do not add shell, process,
network, credential, benchmark-test, or solution-reading capabilities.

Local tools must import under the worker's Python runtime. When a task-specific
Python 3.11 dependency is required, use the provided bounded `runtime_bridge`
interface rather than starting a general shell. Every subprocess call must use
a fixed argv, bounded timeout, fixed working directory, minimal environment,
and bounded output. Use `smoke_candidate_tool` after changing a tool.

The worker must save requested deliverables in the designated output directory
and verify their existence before finishing. Prefer reusable inspection,
validation, and artifact-construction behavior over benchmark-specific logic.

