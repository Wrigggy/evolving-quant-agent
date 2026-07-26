import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


def test_full_harness_canary_script_is_directly_invokable():
    proc = subprocess.run(
        [sys.executable, "scripts/smoke_qfbench_full_harness.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "import" in proc.stdout
    assert "paid-rich" in proc.stdout
    assert "--evolver-template-manifest" in proc.stdout


def test_synthetic_rich_canary_evidence_contains_only_public_worker_files(tmp_path):
    from qea.evolution_feedback import PublicCriterion, PublicTaskRubric
    from scripts.smoke_qfbench_full_harness import build_synthetic_rich_evidence

    task_root = tmp_path / "task"
    (task_root / "environment" / "data").mkdir(parents=True)
    (task_root / "tests").mkdir()
    instruction = task_root / "instruction.md"
    data = task_root / "environment" / "data" / "input.csv"
    private = task_root / "tests" / "expected.json"
    instruction.write_text("PUBLIC INSTRUCTION\n")
    data.write_text("PUBLIC DATA\n")
    private.write_text('{"PRIVATE_VERIFIER_CANARY": 17}\n')
    task = SimpleNamespace(
        task_id="task-a",
        root=task_root,
        worker_files=(instruction, data),
    )
    rubric = PublicTaskRubric(
        "task-a",
        (PublicCriterion("required_output", "Produce the requested output."),),
    )

    evidence = build_synthetic_rich_evidence(
        task=task,
        rubric=rubric,
        destination=tmp_path / "evidence",
    )
    text = "\n".join(
        path.read_text(errors="replace")
        for path in evidence.rglob("*")
        if path.is_file()
    )
    assert "PUBLIC INSTRUCTION" in text
    assert "PUBLIC DATA" in text
    assert "PRIVATE_VERIFIER_CANARY" not in text
    assert not any("tests" in path.parts for path in evidence.rglob("*"))


class FakeFiles:
    def __init__(self):
        self.data = {
            "/opt/qea/nexau-requirements.lock": "nexau==0.3.9\n",
        }

    def write(self, path, data, **kwargs):
        self.data[path] = data.read() if hasattr(data, "read") else data

    def read(self, path, format="text", **kwargs):
        value = self.data[path]
        if format == "text" and isinstance(value, bytes):
            return value.decode()
        return value


class FakeSandbox:
    sandbox_id = "import-canary-sandbox"

    def __init__(self):
        self.files = FakeFiles()
        self.commands = SimpleNamespace(run=self.run)
        self.calls = []
        self.killed = False

    def run(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return SimpleNamespace(exit_code=0, stdout="IMPORT_OK\n", stderr="", error="")

    def kill(self):
        self.killed = True


class FakeFactory:
    def __init__(self):
        self.created = []

    def create(self, **kwargs):
        sandbox = FakeSandbox()
        self.created.append((kwargs, sandbox))
        return sandbox


def test_import_canary_has_no_model_call_or_network_and_cleans_up(tmp_path):
    from qea.e2b_lease import E2BLeasePool
    from scripts.smoke_qfbench_full_harness import run_import_canary

    factory = FakeFactory()
    result = run_import_canary(
        template_id="worker-template",
        run_id="import-canary",
        run_dir=tmp_path / "run",
        sandbox_factory=factory,
        lease_pool=E2BLeasePool(tmp_path / "leases", max_leases=1),
    )

    kwargs, sandbox = factory.created[0]
    assert kwargs["secure"] is True
    assert kwargs["allow_internet_access"] is False
    assert kwargs["envs"] == {}
    assert "network" not in kwargs
    assert sandbox.killed is True
    assert result["import_ok"] is True
    assert not any("agent.run" in command for command, _ in sandbox.calls)
    assert any("import_canary.py" in command for command, _ in sandbox.calls)
    lifecycle = json.loads(next(
        (tmp_path / "run").rglob("*-sandbox-lifecycle.json")
    ).read_text())
    assert lifecycle["cleaned_up"] is True
