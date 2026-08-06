import json
from pathlib import Path

import pytest


@pytest.fixture
def guarded_roots(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    evidence = tmp_path / "evidence"
    reference = tmp_path / "reference"
    runtime = tmp_path / "runtime"
    candidate.mkdir()
    evidence.mkdir()
    reference.mkdir()
    runtime.mkdir()
    (candidate / "systemprompt.md").write_text("Solve carefully.\n")
    (evidence / "overview.md").write_text(
        "task-a failed its public deliverable requirement.\n"
    )
    (evidence / "counterexample.md").write_text(
        "task-b succeeded without the proposed workflow.\n"
    )
    (reference / "NEXAU_GUIDE.md").write_text("Use skills and middlewares.\n")
    (runtime / "runtime_bridge.py").write_text(
        "def marker():\n    return 'worker-runtime'\n"
    )
    access_log = tmp_path / "access_log.jsonl"
    monkeypatch.setenv("QEA_CANDIDATE_ROOT", str(candidate))
    monkeypatch.setenv("QEA_EVIDENCE_ROOT", str(evidence))
    monkeypatch.setenv("QEA_REFERENCE_ROOT", str(reference))
    monkeypatch.setenv("QEA_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("QEA_ACCESS_LOG", str(access_log))
    return candidate, evidence, reference, runtime, access_log


def _unlock(component="tools"):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        read_workspace,
        unlock_candidate,
    )

    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(source="evidence", file_path="counterexample.md")
    return unlock_candidate(
        hypothesis={
            "hypotheses_considered": [
                "the worker lacks a deterministic operation",
                "the worker is misreading the deliverable contract",
            ],
            "selected_mechanism": "a deterministic operation removes repeated error",
            "evidence_refs": ["overview.md", "counterexample.md"],
            "counterevidence": "task-b succeeded without the operation",
            "uncertainty": "only two public traces are available",
            "discriminating_probe": "compare artifact construction in both traces",
            "component": component,
            "prediction": {"task-a": "artifact construction becomes deterministic"},
            "risk_tasks": ["task-b"],
        }
    )


def test_read_write_replace_and_list_candidate(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        list_workspace,
        read_workspace,
        replace_candidate,
        write_candidate,
    )

    candidate, _, _, _, _ = guarded_roots
    listing = list_workspace(source="candidate", pattern="**/*")
    assert listing["paths"] == ["systemprompt.md"]
    assert read_workspace(
        source="candidate", file_path="systemprompt.md"
    )["content"] == "Solve carefully.\n"
    assert _unlock()["unlocked"] is True

    written = write_candidate(
        file_path="tools/calc.py",
        content="def add(a, b):\n    return {'value': a + b}\n",
    )
    assert written["path"] == "tools/calc.py"
    assert (candidate / "tools/calc.py").is_file()

    replaced = replace_candidate(
        file_path="systemprompt.md",
        old_string="carefully",
        new_string="carefully and validate artifacts",
        expected_replacements=1,
    )
    assert replaced["replacements"] == 1
    assert "validate artifacts" in (candidate / "systemprompt.md").read_text()


def test_evidence_reads_and_searches_append_access_audit(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        read_workspace,
        search_evidence,
    )

    _, _, _, _, access_log = guarded_roots
    read = read_workspace(source="evidence", file_path="overview.md")
    search = search_evidence(pattern="deliverable", max_hits=10)

    assert "task-a failed" in read["content"]
    assert search["hits"][0]["path"] == "overview.md"
    records = [json.loads(line) for line in access_log.read_text().splitlines()]
    assert [record["operation"] for record in records] == ["read", "search"]
    assert all(record["source"] == "evidence" for record in records)
    assert records[0]["relative_path"] == "overview.md"


def test_reference_is_read_only_and_audited(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        list_workspace,
        read_workspace,
    )

    _, _, _, _, access_log = guarded_roots
    assert list_workspace(source="reference")["paths"] == ["NEXAU_GUIDE.md"]
    assert "middlewares" in read_workspace(
        source="reference", file_path="NEXAU_GUIDE.md"
    )["content"]
    records = [json.loads(line) for line in access_log.read_text().splitlines()]
    assert [record["source"] for record in records] == ["reference", "reference"]


@pytest.mark.parametrize(
    "source,file_path",
    [
        ("candidate", "/etc/passwd"),
        ("candidate", "../outside.txt"),
        ("evidence", "/etc/passwd"),
        ("evidence", "../outside.txt"),
    ],
)
def test_read_rejects_absolute_and_parent_paths(guarded_roots, source, file_path):
    from qea.evolve_agent_full.tools.guarded_workspace import GuardedWorkspaceError, read_workspace

    with pytest.raises(GuardedWorkspaceError, match="unsafe relative path"):
        read_workspace(source=source, file_path=file_path)


def test_rejects_symlink_read_and_write_escape(guarded_roots, tmp_path):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        read_workspace,
        write_candidate,
    )

    candidate, evidence, _, _, _ = guarded_roots
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n")
    (candidate / "escape.txt").symlink_to(outside)
    (evidence / "escape.txt").symlink_to(outside)
    _unlock()

    with pytest.raises(GuardedWorkspaceError, match="symlink"):
        read_workspace(source="candidate", file_path="escape.txt")
    with pytest.raises(GuardedWorkspaceError, match="symlink"):
        read_workspace(source="evidence", file_path="escape.txt")
    with pytest.raises(GuardedWorkspaceError, match="symlink"):
        write_candidate(file_path="escape.txt", content="overwrite\n")


def test_replace_requires_exact_expected_count(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        replace_candidate,
    )

    _unlock(component="systemprompt")
    with pytest.raises(GuardedWorkspaceError, match="expected 2 replacements, found 1"):
        replace_candidate(
            file_path="systemprompt.md",
            old_string="carefully",
            new_string="safely",
            expected_replacements=2,
        )


def test_smoke_candidate_tool_imports_calls_and_times_out(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        smoke_candidate_tool,
        write_candidate,
    )

    _unlock()
    write_candidate(file_path="tools/__init__.py", content="")
    write_candidate(
        file_path="tools/fixture.py",
        content=(
            "import time\n\n"
            "from runtime_bridge import marker\n\n"
            "def echo(value):\n    return {'value': value}\n\n"
            "def runtime():\n    return {'value': marker()}\n\n"
            "def sleep(seconds):\n    time.sleep(seconds)\n    return {}\n"
        ),
    )

    result = smoke_candidate_tool(
        module="tools.fixture",
        function="echo",
        args_json='{"value": "ok"}',
        timeout_seconds=5,
    )
    assert result["exit_code"] == 0
    assert json.loads(result["stdout"])["value"] == "ok"

    runtime = smoke_candidate_tool(
        module="tools.fixture",
        function="runtime",
        timeout_seconds=5,
    )
    assert json.loads(runtime["stdout"])["value"] == "worker-runtime"

    with pytest.raises(GuardedWorkspaceError, match="timed out"):
        smoke_candidate_tool(
            module="tools.fixture",
            function="sleep",
            args_json='{"seconds": 5}',
            timeout_seconds=1,
        )


def test_tool_descriptions_expose_only_guarded_operations():
    root = Path(__file__).resolve().parents[1] / "qea/evolve_agent_full"
    config = (root / "agent.yaml").read_text()

    assert "guarded_workspace" in config
    assert "run_shell_command" not in config
    assert "builtin.file_tools" not in config
    assert "run_code_tool" not in config
    assert {
        path.stem.removesuffix(".tool")
        for path in (root / "tool_descriptions").glob("*.tool.yaml")
    } == {
        "compare_evidence",
        "inspect_candidate",
        "list_workspace",
        "map_evidence",
        "read_workspace",
        "replace_candidate",
        "search_evidence",
        "smoke_candidate_tool",
        "trace_slice",
        "unlock_candidate",
        "write_candidate",
    }


def test_candidate_writes_require_evidence_backed_unlock(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        read_workspace,
        unlock_candidate,
        write_candidate,
    )

    with pytest.raises(GuardedWorkspaceError, match="writes are locked"):
        write_candidate(file_path="memory/note.md", content="note\n")

    read_workspace(source="evidence", file_path="overview.md")
    with pytest.raises(GuardedWorkspaceError, match="read or inspected"):
        unlock_candidate(
            hypothesis={
                "hypotheses_considered": ["one", "two"],
                "selected_mechanism": "one",
                "evidence_refs": ["overview.md", "counterexample.md"],
                "counterevidence": "two",
                "uncertainty": "limited evidence",
                "discriminating_probe": "compare",
                "component": "memory",
                "prediction": "fewer repeated derivations",
                "risk_tasks": [],
            }
        )

    _unlock(component="memory")
    assert write_candidate(
        file_path="memory/note.md", content="note\n"
    )["bytes_written"] == 5


def test_discovery_queries_map_slice_and_compare_authorized_evidence(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        compare_evidence,
        map_evidence,
        trace_slice,
    )

    mapped = map_evidence()
    assert mapped["file_count"] == 2
    assert mapped["categories"] == {"other": 2}
    assert [item["path"] for item in mapped["files"]] == [
        "counterexample.md",
        "overview.md",
    ]

    sliced = trace_slice(
        file_path="overview.md", pattern="deliverable", context_lines=0
    )
    assert sliced["matches"][0]["match_line"] == 1
    assert "task-a failed" in sliced["matches"][0]["content"]

    compared = compare_evidence("overview.md", "counterexample.md")
    assert "--- overview.md" in compared["diff"]
    assert "+task-b succeeded" in compared["diff"]


def test_inspect_candidate_reports_components_bindings_and_syntax(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import inspect_candidate

    candidate, _, _, _, _ = guarded_roots
    (candidate / "agent.yaml").write_text(
        "tools:\n"
        "  - name: calc\n"
        "    yaml_path: ./tool_descriptions/calc.tool.yaml\n"
        "    binding: tools.calc:add\n"
        "skills:\n"
        "  - ./skills/quant-contract\n"
    )
    (candidate / "tools").mkdir()
    (candidate / "tools/calc.py").write_text(
        "def add(a, b):\n    return a + b\n"
    )
    (candidate / "tool_descriptions").mkdir()
    (candidate / "tool_descriptions/calc.tool.yaml").write_text(
        "type: tool\nname: calc\n"
    )
    (candidate / "skills/quant-contract").mkdir(parents=True)
    (candidate / "skills/quant-contract/SKILL.md").write_text("# Quant contract\n")

    report = inspect_candidate()
    assert report["valid"] is True
    assert report["issues"] == []
    assert "tools/calc.py" in report["components"]["tools"]
    assert {item["kind"] for item in report["declarations"]} == {"tool", "skill"}
