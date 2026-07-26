import io
import importlib
import json
import os
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest


def _tar_bytes(files, *, symlink=None):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, payload in sorted(files.items()):
            data = payload.encode() if isinstance(payload, str) else payload
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        if symlink:
            info = tarfile.TarInfo(symlink[0])
            info.type = tarfile.SYMTYPE
            info.linkname = symlink[1]
            archive.addfile(info)
    return buffer.getvalue()


def _roots(tmp_path):
    candidate = tmp_path / "candidate"
    evidence = tmp_path / "evidence"
    evolver = tmp_path / "evolve_agent"
    (candidate / "tools").mkdir(parents=True)
    (candidate / "agent.yaml").write_text("name: worker\n")
    (candidate / "systemprompt.md").write_text("Solve carefully.\n")
    (candidate / "tools/__init__.py").write_text("")
    evidence.mkdir()
    (evidence / "contract.json").write_text('{"mode":"rich"}\n')
    (evolver / "tools").mkdir(parents=True)
    (evolver / "agent.yaml").write_text("name: evolver\n")
    (evolver / "tools/__init__.py").write_text("")
    return candidate, evidence, evolver


def test_evolver_bundle_is_deterministic_and_has_only_three_roots(tmp_path):
    from qea.executors.bundles import build_evolver_input_bundle

    candidate, evidence, evolver = _roots(tmp_path)
    first = build_evolver_input_bundle(
        candidate, evidence, evolver, tmp_path / "first.tar"
    )
    second = build_evolver_input_bundle(
        candidate, evidence, evolver, tmp_path / "second.tar"
    )

    assert first.sha256 == second.sha256
    assert {name.split("/", 1)[0] for name in first.members} == {
        "candidate",
        "evidence",
        "evolve_agent",
    }


def test_evolver_bundle_rejects_secret_names_and_values(tmp_path):
    from qea.executors.bundles import BundleError, build_evolver_input_bundle

    candidate, evidence, evolver = _roots(tmp_path)
    (evidence / "note.md").write_text("accidental sk-live-secret")
    with pytest.raises(BundleError, match="forbidden value"):
        build_evolver_input_bundle(
            candidate,
            evidence,
            evolver,
            tmp_path / "secret-value.tar",
            forbidden_values=("sk-live-secret",),
        )
    (evidence / "note.md").unlink()
    (candidate / ".env").write_text("TOKEN=x\n")
    with pytest.raises(BundleError, match="secret-like"):
        build_evolver_input_bundle(
            candidate, evidence, evolver, tmp_path / "secret-name.tar"
        )


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_tar_bytes({"../escape.py": "pass\n"}), id="traversal"),
        pytest.param(
            _tar_bytes({}, symlink=("tools/escape.py", "/etc/passwd")),
            id="symlink",
        ),
    ],
)
def test_candidate_output_rejects_traversal_and_links(tmp_path, payload):
    from qea.executors.bundles import BundleError, extract_candidate_archive

    with pytest.raises(BundleError, match="unsafe candidate member"):
        extract_candidate_archive(payload, tmp_path / "output")


class FakeFiles:
    def __init__(self):
        self.data = {
            "/opt/qea/nexau-requirements.lock": "nexau==0.3.9\n",
        }

    def write(self, path, data, **kwargs):
        self.data[path] = data.read() if hasattr(data, "read") else data

    def read(self, path, format="text", **kwargs):
        value = self.data[path]
        if format == "bytes" and isinstance(value, str):
            return value.encode()
        if format == "text" and isinstance(value, bytes):
            return value.decode()
        return value


class FakeCommands:
    def __init__(self, sandbox, *, fail=False):
        self.sandbox = sandbox
        self.fail = fail
        self.calls = []

    def run(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if "remote_evolver.py" in command:
            if self.fail:
                return SimpleNamespace(
                    exit_code=19,
                    stdout="",
                    stderr="provider failed with sk-live-secret",
                    error="",
                )
            self.sandbox.files.data["/qea/result/candidate.tar"] = _tar_bytes({
                "agent.yaml": "name: worker\n",
                "systemprompt.md": "Solve, inspect, and validate.\n",
                "tools/__init__.py": "",
            })
            self.sandbox.files.data["/qea/result/raw_trace.jsonl"] = (
                '{"role":"assistant","content":"updated"}\n'
            )
            self.sandbox.files.data["/qea/result/final.txt"] = (
                '{"summary":"added validation"}\n'
            )
            self.sandbox.files.data["/qea/result/prediction.json"] = json.dumps({
                "summary": "added validation",
                "predicted_fixes": ["schema"],
            })
            self.sandbox.files.data["/qea/result/access-summary.json"] = json.dumps({
                "records": 3,
                "evidence_reads": 2,
            })
            self.sandbox.files.data["/qea/result/summary.json"] = json.dumps({
                "turns": 2,
                "tool_calls": 4,
                "model_usage": None,
                "model_usage_reason": "not exposed by NexAU tracer",
            })
        return SimpleNamespace(exit_code=0, stdout="ok", stderr="", error="")


class FakeSandbox:
    def __init__(self, *, fail=False):
        self.sandbox_id = "sandbox-evolver-1"
        self.files = FakeFiles()
        self.commands = FakeCommands(self, fail=fail)
        self.killed = False

    def kill(self):
        self.killed = True


class FakeFactory:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.created = []

    def create(self, **kwargs):
        sandbox = FakeSandbox(fail=self.fail)
        self.created.append((kwargs, sandbox))
        return sandbox


def _executor(tmp_path, factory):
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_evolver import E2BEvolverConfig, E2BFullHarnessProposer

    return E2BFullHarnessProposer(
        E2BEvolverConfig(template="evolver-template@sha256:abc", timeout_seconds=300),
        sandbox_factory=factory,
        lease_pool=E2BLeasePool(tmp_path / "leases", max_leases=2),
    )


def test_evolver_uses_secure_header_injected_network_and_candidate_only_output(tmp_path):
    candidate, evidence, evolver = _roots(tmp_path)
    factory = FakeFactory()
    result = _executor(tmp_path, factory).propose(
        candidate_dir=candidate,
        evidence_dir=evidence,
        evolver_dir=evolver,
        diagnosis="Improve artifact validation without sk-live-secret.",
        iteration=1,
        run_id="qfbench-rich",
        run_dir=tmp_path / "run",
        model_env={
            "LLM_API_KEY": "sk-live-secret",
            "LLM_BASE_URL": "https://model.example/v1",
            "LLM_MODEL": "example/model",
            "E2B_API_KEY": "must-not-enter-evolver",
        },
    )

    kwargs, sandbox = factory.created[0]
    assert kwargs["template"] == "evolver-template@sha256:abc"
    assert kwargs["secure"] is True
    assert kwargs["allow_internet_access"] is True
    assert kwargs["metadata"]["qea_role"] == "evolver"
    assert kwargs["envs"]["LLM_API_KEY"] == "e2b-header-injected"
    assert kwargs["network"]["allow_out"] == ["model.example"]
    assert kwargs["network"]["rules"]["model.example"][0]["transform"][
        "headers"
    ]["Authorization"] == "Bearer sk-live-secret"
    assert sandbox.killed is True
    assert result.cleaned_up is True
    assert (result.candidate_dir / "systemprompt.md").read_text() == (
        "Solve, inspect, and validate.\n"
    )
    assert "sk-live-secret" not in result.command_log_uri.read_text()
    lifecycle = json.loads(result.lifecycle_uri.read_text())
    assert lifecycle["sandbox_id"] == "sandbox-evolver-1"
    assert lifecycle["cleaned_up"] is True
    uploaded = sandbox.files.data["/tmp/qea-evolver.tar"]
    assert b"sk-live-secret" not in uploaded
    assert "sk-live-secret" not in next((tmp_path / "run").rglob("diagnosis.txt")).read_text()
    assert set(sandbox.files.data) >= {
        "/qea/remote_evolver.py",
        "/tmp/qea-evolver.tar",
    }


def test_evolver_failure_still_kills_and_records_cleanup(tmp_path):
    from qea.executors.e2b_evolver import E2BEvolverError

    candidate, evidence, evolver = _roots(tmp_path)
    factory = FakeFactory(fail=True)
    with pytest.raises(E2BEvolverError, match="evolver command failed"):
        _executor(tmp_path, factory).propose(
            candidate_dir=candidate,
            evidence_dir=evidence,
            evolver_dir=evolver,
            diagnosis="Improve artifact validation.",
            iteration=2,
            run_id="qfbench-rich",
            run_dir=tmp_path / "run",
            model_env={
                "LLM_API_KEY": "sk-live-secret",
                "LLM_BASE_URL": "https://model.example/v1",
                "LLM_MODEL": "example/model",
            },
        )
    _, sandbox = factory.created[0]
    assert sandbox.killed is True
    lifecycle = json.loads(next((tmp_path / "run").rglob("lifecycle.json")).read_text())
    assert lifecycle["cleaned_up"] is True
    command = json.loads(next((tmp_path / "run").rglob("command.json")).read_text())
    assert "sk-live-secret" not in json.dumps(command)
    assert "[REDACTED]" in command["stderr"]


def test_remote_evolver_inserts_asset_root_and_archives_only_candidate(
    tmp_path, monkeypatch
):
    from qea.executors import remote_evolver

    candidate = tmp_path / "candidate"
    evidence = tmp_path / "evidence"
    evolver = tmp_path / "evolve_agent"
    result = tmp_path / "result"
    candidate.mkdir()
    evidence.mkdir()
    (candidate / "agent.yaml").write_text("name: worker\n")
    (candidate / "systemprompt.md").write_text("before\n")
    (evidence / "contract.json").write_text('{"mode":"rich"}\n')
    (evolver / "tools").mkdir(parents=True)
    (evolver / "agent.yaml").write_text("name: evolver\n")
    (evolver / "tools/__init__.py").write_text("")
    (evolver / "tools/guarded_workspace.py").write_text("BOUND = True\n")

    class FakeConfig:
        @classmethod
        def from_yaml(cls, *, config_path):
            assert config_path == evolver / "agent.yaml"
            imported = importlib.import_module("tools.guarded_workspace")
            assert imported.BOUND is True
            return cls()

    class FakeAgent:
        def __init__(self, *, config):
            self.full_trace = []

        def run(self, *, message, context):
            assert "Improve validation" in message
            (candidate / "systemprompt.md").write_text("after\n")
            return '{"summary":"changed"}'

    monkeypatch.setitem(
        sys.modules,
        "nexau",
        SimpleNamespace(Agent=FakeAgent, AgentConfig=FakeConfig),
    )
    sys.modules.pop("tools", None)
    sys.modules.pop("tools.guarded_workspace", None)
    monkeypatch.setenv("LLM_API_KEY", "e2b-header-injected")
    monkeypatch.setenv("LLM_BASE_URL", "https://model.example/v1")
    monkeypatch.setenv("LLM_MODEL", "model")

    assert remote_evolver.run(
        candidate_dir=candidate,
        evidence_dir=evidence,
        evolver_dir=evolver,
        result_dir=result,
        diagnosis="Improve validation",
        iteration=1,
    ) == 0

    assert "LLM_API_KEY" not in os.environ
    with tarfile.open(result / "candidate.tar") as archive:
        assert sorted(archive.getnames()) == ["agent.yaml", "systemprompt.md"]
    assert json.loads((result / "prediction.json").read_text())["summary"] == "changed"
    assert json.loads((result / "summary.json").read_text())["model_usage"] is None
