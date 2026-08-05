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
    (reference / "NEXAU_GUIDE.md").write_text("Use skills and middlewares.\n")
    (runtime / "runtime_bridge.py").write_text(
        "def marker():\n    return 'worker-runtime'\n"
    )
    access_log = tmp_path / "access.jsonl"
    monkeypatch.setenv("QEA_CANDIDATE_ROOT", str(candidate))
    monkeypatch.setenv("QEA_EVIDENCE_ROOT", str(evidence))
    monkeypatch.setenv("QEA_REFERENCE_ROOT", str(reference))
    monkeypatch.setenv("QEA_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("QEA_ACCESS_LOG", str(access_log))
    return candidate, evidence, reference, runtime, access_log


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
        "list_workspace",
        "read_workspace",
        "replace_candidate",
        "search_evidence",
        "smoke_candidate_tool",
        "write_candidate",
    }
