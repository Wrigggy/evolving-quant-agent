# NexAU worker harness — modification reference

This is a process reference for editing a NexAU *worker agent* directory. It describes
the substrate FORMAT only — it contains no task answers. Read it before editing so your
changes are valid NexAU configuration/code.

## Worker directory anatomy

```
worker_dir/
  agent.yaml                 # the agent definition: prompt, tools, tracers, llm config
  systemprompt.md            # the worker's system prompt (jinja); agent.yaml points here
  tool_descriptions/*.tool.yaml   # one schema file per tool the agent exposes
  tools/**/*.py              # tool implementations (only for dir-local, non-builtin tools)
```

## agent.yaml structure (annotated)

```yaml
type: agent
name: <worker name>
system_prompt: ./systemprompt.md
system_prompt_type: jinja
tool_call_mode: openai
max_iterations: 40            # max worker turns; too low = can't finish multi-step work
llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  max_tokens: 8000            # output budget per turn; too low truncates long answers
  temperature: 0.2
  stream: true
  api_type: openai_chat_completion
tools:                        # the tools the worker can call (see below)
  - name: <tool name>
    yaml_path: ./tool_descriptions/<tool name>.tool.yaml
    binding: <module>:<function>
tracers:
  - import: nexau.archs.tracer.adapters.in_memory:InMemoryTracer
```

## A tool has THREE parts

1. **An implementation** — a Python function returning a dict, e.g.
   `def fetch_page(url: str) -> dict:` in `tools/<pkg>/<mod>.py`.
2. **A description** — `tool_descriptions/<name>.tool.yaml`:
   ```yaml
   type: tool
   name: fetch_page
   description: Fetch a URL and return its extracted text.
   input_schema:
     type: object
     properties:
       url: {type: string, description: "URL to fetch."}
     required: [url]
     additionalProperties: false
   ```
3. **A binding** — an entry under `tools:` in `agent.yaml` that wires name → yaml → fn:
   ```yaml
   - name: fetch_page
     yaml_path: ./tool_descriptions/fetch_page.tool.yaml
     binding: tools.fab.research:fetch_page
   ```

`binding` is `<module path>:<function name>`. Dir-local modules (e.g. `tools.fab.research`)
are imported relative to the worker dir; built-ins use their full path, e.g.
`nexau.archs.tool.builtin.shell_tools.run_shell_command:run_shell_command`.

## Common harness edits

- **Re-wire an existing-but-unbound tool.** If a `tool_descriptions/<name>.tool.yaml`
  and its implementation already exist but the tool is NOT listed under `tools:` in
  `agent.yaml`, the worker cannot call it. Add the 3-line `tools:` entry to enable it.
- **Add a new tool.** Write the function in `tools/<pkg>/<mod>.py`, add its
  `tool_descriptions/<name>.tool.yaml`, and add the `tools:` entry. Keep the function
  pure and general — never embed a specific task's answer.
- **Adjust the loop budget.** Raise `max_iterations` if the worker runs out of turns
  before finishing; raise `max_tokens` if long answers are being truncated.
- **Sharpen the prompt.** Edit `systemprompt.md` with general process guidance
  (e.g. "decompose multi-part questions", "cite the source you read").
- **Tracer/middleware.** `tracers:` wires observability; only touch if the diagnosis
  points at lost cross-turn state.

## Built-in tools you may wire in

NexAU ships built-ins you can add via `binding:` (each still needs a `tools:` entry +
a description yaml). Useful ones: `nexau.archs.tool.builtin.shell_tools.run_shell_command`,
`nexau.archs.tool.builtin.file_tools.read_file:read_file`,
`...file_tools.write_file:write_file`, `...web_tools.web_fetch:web_fetch`.

## Editing mechanism

You edit with `run_shell_command`: inspect (`cat agent.yaml`, `ls tool_descriptions/`),
then write (`cat > systemprompt.md <<'EOF' ... EOF`, or a small python `open(...,'w')`).
Verify your edit parses (e.g. `python -c "import yaml,sys; yaml.safe_load(open('agent.yaml'))"`).

## Hard rule

Improve HOW the worker works (prompt, tools, bindings, budget) — never WHAT it answers.
Do not embed task-specific answers, numbers, or domain facts into any file.
