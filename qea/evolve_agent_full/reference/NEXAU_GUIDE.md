# NexAU Candidate Guide

The candidate is a file-backed NexAU worker. `agent.yaml` has three native
extension surfaces in this experiment: `tools`, `skills`, and `middlewares`.
Tool descriptions must match their callable signatures and should state inputs,
output shape, and important failure modes.

You may improve the system prompt, tool descriptions, agent declarations, and
local files under `memory/`, `middleware/`, `routing/`, `skills/`,
`tool_descriptions/`, `tools/`, and `validator/`. Creating a directory that does
not yet exist is expected. Runtime, model, resource, tracing, and security
settings are protected by admission policy. Do not add shell, network,
credential, benchmark-test, or solution-reading capabilities.

## Native configuration schemas

Register a local skill folder with a `SKILL.md` containing YAML frontmatter:

```yaml
skills:
  - ./skills/spec-driven-deliverables
```

NexAU exposes each registered skill through its conditional `load_skill` tool.
The skill's frontmatter `description` controls when the worker sees it as
relevant; the body is returned only after the worker loads it.

Register a local middleware module with the plural `middlewares` key:

```yaml
middlewares:
  - import: middleware.completion_guard:CompletionGuard
    params:
      minimum_artifacts: 1
```

The import target must exist and define the named class or function. The
singular key `middleware` is not a NexAU field and will be rejected.

`memory`, `routing`, and `validator` are component roles, not native top-level
NexAU keys. Code in those directories must be imported by a registered tool or
middleware. A file that is only present on disk is behaviorally inert and is
rejected when admission can prove it is unreachable.

Local Python must import under the worker's Python runtime, using only the
standard library plus `nexau`, `numpy`, `pandas`, `pydantic`, `runtime_bridge`,
and `yaml`. When a task-specific Python 3.11 dependency is required, use the
provided bounded `runtime_bridge` interface rather than starting a general
shell. Every subprocess call must use a fixed argv, bounded timeout, fixed
working directory, minimal environment, and bounded output. Use
`smoke_candidate_tool` after changing a tool.

Any module you add under a component directory must be reachable by the worker:
declare tools, skills, or middlewares in `agent.yaml`, and import helper modules
from one of those entrypoints. A component file that nothing calls changes no
behavior and will fail component-reachability admission.

The worker must save requested deliverables in the designated output directory
and verify their existence before finishing. Prefer reusable inspection,
validation, and artifact-construction behavior over benchmark-specific logic.
