import json
import shutil
from dataclasses import asdict
from pathlib import Path

import pytest


AGENT_YAML = """\
type: agent
name: qea_worker
max_context_tokens: 200000
system_prompt: ./systemprompt.md
system_prompt_type: jinja
tool_call_mode: openai
max_iterations: 60
llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  max_tokens: 32000
  temperature: 0.2
  stream: true
  api_type: openai_chat_completion
  timeout: 180
tools:
  - name: run_shell_command
    yaml_path: ./tool_descriptions/run_shell_command.tool.yaml
    binding: nexau.archs.tool.builtin.shell_tools.run_shell_command:run_shell_command
tracers:
  - import: nexau.archs.tracer.adapters.in_memory:InMemoryTracer
"""


SHELL_TOOL = """\
type: tool
name: run_shell_command
description: Run a command in the task workspace.
input_schema:
  type: object
  properties:
    command: {type: string}
  required: [command]
  additionalProperties: false
"""


def _seed_candidate(tmp_path: Path):
    seed = tmp_path / "seed"
    candidate = tmp_path / "candidate"
    (seed / "tool_descriptions").mkdir(parents=True)
    (seed / "agent.yaml").write_text(AGENT_YAML)
    (seed / "systemprompt.md").write_text("Solve the public task carefully.\n")
    (seed / "tool_descriptions/run_shell_command.tool.yaml").write_text(SHELL_TOOL)
    shutil.copytree(seed, candidate)
    return seed, candidate


def _add_local_tool(candidate: Path, *, code: str | None = None):
    (candidate / "tools").mkdir(exist_ok=True)
    (candidate / "tools/__init__.py").write_text("")
    (candidate / "tools/calc.py").write_text(code or """\
def add(left: float, right: float) -> dict:
    return {"value": left + right}
""")
    (candidate / "tool_descriptions/add.tool.yaml").write_text("""\
type: tool
name: add
description: Add two numeric values.
input_schema:
  type: object
  properties:
    left: {type: number}
    right: {type: number}
  required: [left, right]
  additionalProperties: false
""")
    path = candidate / "agent.yaml"
    path.write_text(path.read_text().replace(
        "tracers:\n",
        "  - name: add\n"
        "    yaml_path: ./tool_descriptions/add.tool.yaml\n"
        "    binding: tools.calc:add\n"
        "tracers:\n",
    ))


def test_admits_prompt_and_complete_local_tool_binding(tmp_path):
    from qea.candidate_admission import AdmissionPolicy, admit_candidate

    seed, candidate = _seed_candidate(tmp_path)
    (candidate / "systemprompt.md").write_text(
        "Solve the public task carefully and validate every artifact.\n"
    )
    _add_local_tool(candidate)

    record = admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())

    assert record.admitted is True
    assert len(record.candidate_digest) == 64
    assert len(record.policy_digest) == 64
    assert {item.path for item in record.files} >= {
        "agent.yaml",
        "systemprompt.md",
        "tools/calc.py",
        "tool_descriptions/add.tool.yaml",
    }
    assert "protected_config" in record.checks
    assert "local_bindings" in record.checks
    assert asdict(record)["failure"] is None


@pytest.mark.parametrize(
    ("old", "new", "field"),
    [
        ("${env.LLM_MODEL}", "other/model", "llm_config.model"),
        ("${env.LLM_BASE_URL}", "https://evil.example/v1", "llm_config.base_url"),
        ("${env.LLM_API_KEY}", "literal-secret", "llm_config.api_key"),
        ("max_iterations: 60", "max_iterations: 80", "max_iterations"),
        ("max_tokens: 32000", "max_tokens: 64000", "llm_config.max_tokens"),
        ("temperature: 0.2", "temperature: 0.9", "llm_config.temperature"),
    ],
)
def test_rejects_protected_config_changes(tmp_path, old, new, field):
    from qea.candidate_admission import (
        AdmissionPolicy,
        CandidateAdmissionError,
        admit_candidate,
    )

    seed, candidate = _seed_candidate(tmp_path)
    path = candidate / "agent.yaml"
    path.write_text(path.read_text().replace(old, new))

    with pytest.raises(CandidateAdmissionError, match=field.replace(".", r"\.")):
        admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())


def test_rejects_symlink_and_secret_like_file(tmp_path):
    from qea.candidate_admission import (
        AdmissionPolicy,
        CandidateAdmissionError,
        admit_candidate,
    )

    seed, candidate = _seed_candidate(tmp_path)
    (candidate / "tools").mkdir()
    (candidate / "tools/outside.py").symlink_to(tmp_path / "outside.py")
    with pytest.raises(CandidateAdmissionError, match="symlink"):
        admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())

    (candidate / "tools/outside.py").unlink()
    (candidate / ".env").write_text("OPENROUTER_API_KEY=secret\n")
    with pytest.raises(CandidateAdmissionError, match="secret-like"):
        admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())


def test_rejects_binary_extensionless_and_unknown_top_level_files(tmp_path):
    from qea.candidate_admission import (
        AdmissionPolicy,
        CandidateAdmissionError,
        admit_candidate,
    )

    seed, candidate = _seed_candidate(tmp_path)
    (candidate / "tools").mkdir()
    (candidate / "tools/blob.py").write_bytes(b"\x00\xffbinary")
    with pytest.raises(CandidateAdmissionError, match="UTF-8 text"):
        admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())

    (candidate / "tools/blob.py").unlink()
    (candidate / "tools/runner").write_text("#!/bin/sh\nexit 0\n")
    with pytest.raises(CandidateAdmissionError, match="extensionless"):
        admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())

    (candidate / "tools/runner").unlink()
    (candidate / "answers.md").write_text("task-specific answer\n")
    with pytest.raises(CandidateAdmissionError, match="top-level"):
        admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())


def test_rejects_syntax_error_unknown_dependency_and_missing_binding_function(tmp_path):
    from qea.candidate_admission import (
        AdmissionPolicy,
        CandidateAdmissionError,
        admit_candidate,
    )

    seed, candidate = _seed_candidate(tmp_path)
    _add_local_tool(candidate, code="def add(:\n")
    with pytest.raises(CandidateAdmissionError, match="syntax"):
        admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())

    (candidate / "tools/calc.py").write_text(
        "import fitz\n\ndef add(left, right):\n    return {'value': left + right}\n"
    )
    with pytest.raises(CandidateAdmissionError, match="undeclared import.*fitz"):
        admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())

    (candidate / "tools/calc.py").write_text(
        "def not_add(left, right):\n    return {'value': left + right}\n"
    )
    with pytest.raises(CandidateAdmissionError, match="binding function.*add"):
        admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())


def test_rejects_local_binding_signature_that_cannot_accept_tool_schema(tmp_path):
    from qea.candidate_admission import (
        AdmissionPolicy,
        CandidateAdmissionError,
        admit_candidate,
    )

    seed, candidate = _seed_candidate(tmp_path)
    _add_local_tool(candidate, code="""\
def add(left):
    return {"value": left}
""")

    with pytest.raises(CandidateAdmissionError, match="binding signature.*right"):
        admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())


def test_rejects_subprocess_without_timeout_or_with_shell_true(tmp_path):
    from qea.candidate_admission import (
        AdmissionPolicy,
        CandidateAdmissionError,
        admit_candidate,
    )

    seed, candidate = _seed_candidate(tmp_path)
    _add_local_tool(candidate, code="""\
import subprocess

def add(left, right):
    subprocess.run(["python3", "-c", "print(1)"])
    return {"value": left + right}
""")
    with pytest.raises(CandidateAdmissionError, match="subprocess.*timeout"):
        admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())

    (candidate / "tools/calc.py").write_text("""\
import subprocess

def add(left, right):
    subprocess.run("python3 -c 'print(1)'", shell=True, timeout=5)
    return {"value": left + right}
""")
    with pytest.raises(CandidateAdmissionError, match="shell=True"):
        admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())


def test_accepts_subprocess_with_argv_and_timeout(tmp_path):
    from qea.candidate_admission import AdmissionPolicy, admit_candidate

    seed, candidate = _seed_candidate(tmp_path)
    _add_local_tool(candidate, code="""\
import subprocess

def add(left, right):
    subprocess.run(["python3", "-c", "print(1)"], timeout=5, check=False)
    return {"value": left + right}
""")

    record = admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())

    assert record.admitted is True
    assert "subprocess_timeouts" in record.checks


def test_accepts_worker_tool_using_uploaded_runtime_bridge(tmp_path):
    from qea.candidate_admission import AdmissionPolicy, admit_candidate

    seed, candidate = _seed_candidate(tmp_path)
    _add_local_tool(candidate, code="""\
from runtime_bridge import task_python

def add(left, right):
    return task_python(
        ["-c", f"print({left} + {right})"],
        cwd="/app",
        timeout_seconds=5,
    )
""")

    record = admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())

    assert record.admitted is True


def test_rejects_forbidden_answer_canary_before_paid_scoring(tmp_path):
    from qea.candidate_admission import (
        AdmissionPolicy,
        CandidateAdmissionError,
        admit_candidate,
    )

    seed, candidate = _seed_candidate(tmp_path)
    (candidate / "systemprompt.md").write_text(
        "Use PRIVATE_REFERENCE_CANARY as the exact answer.\n"
    )
    policy = AdmissionPolicy.qfbench_full(
        forbidden_content=("PRIVATE_REFERENCE_CANARY",)
    )

    with pytest.raises(CandidateAdmissionError, match="forbidden content"):
        admit_candidate(seed, candidate, policy)


def test_policy_digest_is_stable_and_changes_with_forbidden_content():
    from qea.candidate_admission import AdmissionPolicy

    first = AdmissionPolicy.qfbench_full()
    same = AdmissionPolicy.qfbench_full()
    changed = AdmissionPolicy.qfbench_full(forbidden_content=("canary",))

    assert len(first.digest()) == 64
    assert first.digest() == same.digest()
    assert first.digest() != changed.digest()


def test_admission_record_round_trips_as_json(tmp_path):
    from qea.candidate_admission import AdmissionPolicy, admit_candidate

    seed, candidate = _seed_candidate(tmp_path)
    record = admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())

    payload = json.loads(json.dumps(asdict(record)))
    assert payload["admitted"] is True
    assert payload["files"][0]["path"] == "agent.yaml"
