import hashlib
import io
import json
import tarfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from qea.qfbench_images import NEXAU_REQUIREMENTS_LOCK, NEXAU_RUNTIME_PYTHON
from qea.resource_lease import ResourceRequest
from qea.sandbox_backend import (
    KillResult,
    SandboxCommandResult,
    SandboxHandle,
)


def _tar_bytes(files, *, symlink=None):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, value in sorted(files.items()):
            payload = value if isinstance(value, bytes) else value.encode()
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        if symlink is not None:
            info = tarfile.TarInfo(symlink[0])
            info.type = tarfile.SYMTYPE
            info.linkname = symlink[1]
            archive.addfile(info)
    return output.getvalue()


def _roots(tmp_path):
    candidate = tmp_path / "candidate"
    evidence = tmp_path / "evidence"
    evolver = tmp_path / "evolve_agent"
    (candidate / "tools").mkdir(parents=True, exist_ok=True)
    (candidate / "agent.yaml").write_text("name: worker\n")
    (candidate / "systemprompt.md").write_text("Solve carefully.\n")
    (candidate / "tools" / "__init__.py").write_text("")
    evidence.mkdir(exist_ok=True)
    (evidence / "contract.json").write_text('{"mode":"rich"}\n')
    (evolver / "tools").mkdir(parents=True, exist_ok=True)
    (evolver / "agent.yaml").write_text("name: evolver\n")
    (evolver / "tools" / "__init__.py").write_text("")
    return candidate, evidence, evolver


class FakeBackend:
    backend_name = "fake-rootless"

    def __init__(self, events, *, candidate_archive=None, command_error=False):
        self.events = events
        self.candidate_archive = candidate_archive or _tar_bytes(
            {
                "agent.yaml": "name: worker\n",
                "systemprompt.md": "Solve, inspect, and validate.\n",
                "tools/__init__.py": "",
            }
        )
        self.command_error = command_error
        self.specs = []
        self.uploads = {}

    def create(self, spec):
        self.events.append("create:evolver")
        self.specs.append(spec)
        return SandboxHandle(
            backend=self.backend_name,
            native_id="sandbox-evolver-1",
            immutable_image_ref=spec.image_ref,
            spec_sha256=spec.spec_sha256,
        )

    def start(self, handle):
        self.events.append("start:evolver")

    def put_bytes(self, handle, path, payload):
        self.events.append(f"upload:{path}")
        self.uploads[path] = payload

    def read_bytes(self, handle, path):
        self.events.append(f"read:{path}")
        values = {
            NEXAU_REQUIREMENTS_LOCK: b"nexau==0.3.9\n",
            "/qea/result/candidate.tar": self.candidate_archive,
            "/qea/result/raw_trace.jsonl": (
                b'{"role":"assistant","content":"updated"}\n'
            ),
            "/qea/result/final.txt": b'{"summary":"added validation"}\n',
            "/qea/result/prediction.json": (
                b'{"predicted_fixes":["schema"],"summary":"added validation"}\n'
            ),
            "/qea/result/access-summary.json": (
                b'{"evidence_paths":["contract.json"],"records":3}\n'
            ),
            "/qea/result/summary.json": (
                b'{"model_usage":null,"tool_calls":4,"turns":2}\n'
            ),
        }
        return values[path]

    def run(self, handle, argv, *, environment, timeout_seconds):
        command = tuple(argv)
        if command and command[0] == NEXAU_RUNTIME_PYTHON:
            self.events.append(("run:evolver", command, dict(environment)))
            if self.command_error:
                return SandboxCommandResult(19, "", "provider failed", False)
        else:
            self.events.append(("run:setup", command, dict(environment)))
        return SandboxCommandResult(0, "ok", "", False)

    def kill(self, native_id):
        self.events.append(f"kill:{native_id}")
        return KillResult(native_id=native_id, outcome="killed")


class FakeProxyManager:
    def __init__(self, backend, events, proxy_resources):
        self.backend = backend
        self.events = events
        self.config = SimpleNamespace(
            resource_contract=proxy_resources,
            allowed_model="example/model",
            listen_port=8080,
            allowed_path_prefix="/v1",
        )
        self.opens = 0

    @contextmanager
    def open(self, **kwargs):
        self.opens += 1
        self.events.append(("proxy:open", kwargs))
        try:
            yield SimpleNamespace(
                base_url="http://qea-model-proxy:8080/v1",
                network_scope=kwargs["attempt_id"],
                network_name="qea-run-evolver-network",
                network_id="network-1",
                native_id="proxy-1",
                allowed_model="example/model",
            )
        finally:
            self.events.append("proxy:close")


class FakeLease:
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        self.events.append("lease:entered")
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.events.append("lease:released")


class FakeResourcePool:
    def __init__(self, events):
        self.events = events
        self.requests = []

    def acquire(self, key, request, *, timeout_seconds):
        self.requests.append((key, request, timeout_seconds))
        self.events.append("lease:acquired")
        return FakeLease(self.events)


def _resources(*, proxy=False, timeout_seconds=300):
    from qea.executors.sandbox_runtime import SandboxResourceContract

    tmpfs = {"/tmp": 256, "/qea": 512}
    if proxy:
        tmpfs = {"/tmp": 64, "/run/qea-secrets": 8}
    return SandboxResourceContract(
        cpu_count=1 if proxy else 2,
        memory_mb=512 if proxy else 4096,
        pids_limit=64 if proxy else 256,
        timeout_seconds=timeout_seconds,
        writable_tmpfs_mb=tmpfs,
    )


def _proposer(tmp_path, *, backend=None, events=None, image=None, model=None):
    from qea.executors.sandbox_evolver import (
        SandboxEvolverConfig,
        SandboxFullHarnessProposer,
    )

    events = events if events is not None else []
    backend = backend or FakeBackend(events)
    proxy = FakeProxyManager(backend, events, _resources(proxy=True))
    pool = FakeResourcePool(events)
    proposer = SandboxFullHarnessProposer(
        config=SandboxEvolverConfig(
            image_ref=image or "sha256:" + "a" * 64,
            resource_contract=_resources(),
            command_timeout_seconds=180,
        ),
        backend=backend,
        lifecycle_root=tmp_path / "lifecycles",
        proxy_manager=proxy,
        resource_pool=pool,
        model_name=model or "example/model",
    )
    return proposer, backend, proxy, pool, events


def _propose(proposer, tmp_path, **overrides):
    candidate, evidence, evolver = _roots(tmp_path / "inputs")
    values = {
        "candidate_dir": candidate,
        "evidence_dir": evidence,
        "evolver_dir": evolver,
        "diagnosis": "Improve artifact validation.",
        "iteration": 1,
        "run_id": "run-001",
        "run_dir": tmp_path / "run",
        "model_env": {},
    }
    values.update(overrides)
    return proposer.propose(**values)


def test_evolver_uses_atomic_combined_lease_proxy_only_spec_and_structured_argv(
    tmp_path,
):
    proposer, backend, proxy, pool, events = _proposer(tmp_path)

    result = _propose(proposer, tmp_path)

    assert pool.requests == [
        (
            "evolver:run-001:1",
            ResourceRequest(
                cpu_count=3,
                memory_mb=4608,
                pids_limit=320,
                tmpfs_mb=840,
                sandboxes=2,
            ),
            120.0,
        )
    ]
    spec = backend.specs[0]
    assert spec.role == "evolver"
    assert spec.network_policy == "worker-proxy-only"
    assert spec.network_scope == "evolver-iteration-1"
    assert dict(spec.environment) == {
        "LLM_API_KEY": "qea-proxy-placeholder",
        "LLM_BASE_URL": "http://qea-model-proxy:8080/v1",
        "LLM_MODEL": "example/model",
        "SSL_CERT_FILE": "/etc/ssl/certs/ca-certificates.crt",
    }
    assert events.index("lease:entered") < next(
        index for index, event in enumerate(events) if isinstance(event, tuple) and event[0] == "proxy:open"
    )
    assert events.index("create:evolver") > next(
        index for index, event in enumerate(events) if isinstance(event, tuple) and event[0] == "proxy:open"
    )
    assert events.index("kill:sandbox-evolver-1") < events.index("proxy:close")
    assert events.index("proxy:close") < events.index("lease:released")
    commands = [event[1] for event in events if isinstance(event, tuple) and event[0].startswith("run:")]
    assert commands
    assert all(isinstance(command, tuple) for command in commands)
    assert not any(command[:2] in {("sh", "-c"), ("bash", "-c")} for command in commands)
    evolver_command = next(command for command in commands if command[0] == NEXAU_RUNTIME_PYTHON)
    assert evolver_command == (
        NEXAU_RUNTIME_PYTHON,
        "/qea/remote_evolver.py",
        "--candidate-dir",
        "/qea/input/candidate",
        "--evidence-dir",
        "/qea/input/evidence",
        "--evolver-dir",
        "/qea/input/evolve_agent",
        "--result-dir",
        "/qea/result",
        "--diagnosis-file",
        "/qea/diagnosis.txt",
        "--iteration",
        "1",
    )
    assert b"Improve artifact validation." == backend.uploads["/qea/diagnosis.txt"]
    assert set(backend.uploads) == {
        "/qea/evolver-input.tar",
        "/qea/remote_evolver.py",
        "/qea/diagnosis.txt",
    }
    assert result.proxy_sandbox_id == "proxy-1"
    assert result.network_id == "network-1"
    assert result.backend == "fake-rootless"
    assert result.spec_sha256 == spec.spec_sha256
    assert result.cleaned_up is True


def test_evolver_validates_candidate_evidence_lock_lifecycle_and_result_order(tmp_path):
    proposer, backend, _, _, events = _proposer(tmp_path)

    result = _propose(proposer, tmp_path)

    assert (result.candidate_dir / "systemprompt.md").read_text() == (
        "Solve, inspect, and validate.\n"
    )
    assert result.dependency_lock_uri.read_bytes() == b"nexau==0.3.9\n"
    assert json.loads(result.prediction_uri.read_text())["summary"] == (
        "added validation"
    )
    assert json.loads(result.access_summary_uri.read_text())["records"] == 3
    assert json.loads(result.summary_uri.read_text())["tool_calls"] == 4
    lifecycle = json.loads(result.lifecycle_uri.read_text())
    assert lifecycle["schema_version"] == 2
    assert lifecycle["native_id"] == "sandbox-evolver-1"
    assert lifecycle["spec_sha256"] == result.spec_sha256
    assert lifecycle["cleaned_up"] is True
    manifest = json.loads((tmp_path / "run/evolutions/iteration-0001/result.json").read_text())
    assert manifest["sandbox_id"] == "sandbox-evolver-1"
    assert manifest["proxy_sandbox_id"] == "proxy-1"
    assert manifest["network_id"] == "network-1"
    assert manifest["candidate_digest"] == result.candidate_digest
    assert events.index("proxy:close") < events.index("lease:released")


def test_completed_evolver_resume_binds_all_content_identity_fields(tmp_path):
    proposer, backend, proxy, _, _ = _proposer(tmp_path)
    first = _propose(proposer, tmp_path)

    second = _propose(proposer, tmp_path)

    assert second == first
    assert len(backend.specs) == 1
    assert proxy.opens == 1
    result_path = tmp_path / "run/evolutions/iteration-0001/result.json"
    original = json.loads(result_path.read_text())
    for field, bad_value in (
        ("run_id", "other-run"),
        ("iteration", 2),
        ("input_bundle_sha256", "1" * 64),
        ("diagnosis_sha256", "2" * 64),
        ("model_name", "other/model"),
        ("image_ref", "sha256:" + "b" * 64),
        ("spec_sha256", "3" * 64),
        ("backend", "other-backend"),
    ):
        changed = dict(original)
        changed[field] = bad_value
        result_path.write_text(json.dumps(changed, sort_keys=True) + "\n")
        with pytest.raises(Exception, match="identity mismatch"):
            _propose(proposer, tmp_path)
        result_path.write_text(json.dumps(original, sort_keys=True) + "\n")


def test_rejected_resume_drift_does_not_overwrite_committed_input_bundle(tmp_path):
    proposer, _, _, _, _ = _proposer(tmp_path)
    _propose(proposer, tmp_path)
    input_path = tmp_path / "run/evolutions/iteration-0001/input.tar"
    committed = input_path.read_bytes()
    candidate = tmp_path / "inputs/candidate"
    evidence = tmp_path / "inputs/evidence"
    evolver = tmp_path / "inputs/evolve_agent"
    (candidate / "systemprompt.md").write_text("Drifted input.\n")

    with pytest.raises(Exception, match="identity mismatch"):
        proposer.propose(
            candidate_dir=candidate,
            evidence_dir=evidence,
            evolver_dir=evolver,
            diagnosis="Improve artifact validation.",
            iteration=1,
            run_id="run-001",
            run_dir=tmp_path / "run",
            model_env={},
        )

    assert input_path.read_bytes() == committed


def test_quarantined_identity_never_reopens_proxy_or_evolver(tmp_path):
    proposer, backend, proxy, pool, _ = _proposer(tmp_path)
    marker = (
        tmp_path
        / "run/attempts/evolver-iteration-1/proxy-audit.quarantined.json"
    )
    marker.parent.mkdir(parents=True)
    marker.write_text('{"request_state":"quarantined","schema_version":1}\n')

    with pytest.raises(Exception, match="quarantined"):
        _propose(proposer, tmp_path)

    assert backend.specs == []
    assert proxy.opens == 0
    assert pool.requests == []


def test_quarantined_resume_does_not_replace_prior_input_evidence(tmp_path):
    proposer, _, _, _, _ = _proposer(tmp_path)
    _propose(proposer, tmp_path)
    evolution = tmp_path / "run/evolutions/iteration-0001"
    (evolution / "result.json").unlink()
    committed = (evolution / "input.tar").read_bytes()
    marker = (
        tmp_path
        / "run/attempts/evolver-iteration-1/proxy-audit.quarantined.json"
    )
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"request_state":"quarantined","schema_version":1}\n')
    candidate = tmp_path / "inputs/candidate"
    (candidate / "systemprompt.md").write_text("Drifted input.\n")

    with pytest.raises(Exception, match="quarantined"):
        proposer.propose(
            candidate_dir=candidate,
            evidence_dir=tmp_path / "inputs/evidence",
            evolver_dir=tmp_path / "inputs/evolve_agent",
            diagnosis="Improve artifact validation.",
            iteration=1,
            run_id="run-001",
            run_dir=tmp_path / "run",
            model_env={},
        )

    assert (evolution / "input.tar").read_bytes() == committed


def test_ambiguous_candidate_resume_does_not_replace_prior_input_evidence(tmp_path):
    proposer, _, _, _, _ = _proposer(tmp_path)
    _propose(proposer, tmp_path)
    evolution = tmp_path / "run/evolutions/iteration-0001"
    (evolution / "result.json").unlink()
    committed = (evolution / "input.tar").read_bytes()
    candidate = tmp_path / "inputs/candidate"
    (candidate / "systemprompt.md").write_text("Drifted input.\n")

    with pytest.raises(Exception, match="ambiguous"):
        proposer.propose(
            candidate_dir=candidate,
            evidence_dir=tmp_path / "inputs/evidence",
            evolver_dir=tmp_path / "inputs/evolve_agent",
            diagnosis="Improve artifact validation.",
            iteration=1,
            run_id="run-001",
            run_dir=tmp_path / "run",
            model_env={},
        )

    assert (evolution / "input.tar").read_bytes() == committed


@pytest.mark.parametrize(
    "candidate_archive",
    [
        pytest.param(_tar_bytes({"../escape": "x"}), id="traversal"),
        pytest.param(
            _tar_bytes({}, symlink=("tools/link", "/etc/passwd")), id="symlink"
        ),
    ],
)
def test_invalid_candidate_closes_proxy_kills_evolver_and_writes_no_result(
    tmp_path, candidate_archive
):
    events = []
    backend = FakeBackend(events, candidate_archive=candidate_archive)
    proposer, _, _, _, _ = _proposer(tmp_path, backend=backend, events=events)

    with pytest.raises(Exception, match="unsafe candidate member"):
        _propose(proposer, tmp_path)

    assert "kill:sandbox-evolver-1" in events
    assert "proxy:close" in events
    assert events[-1] == "lease:released"
    assert not (tmp_path / "run/evolutions/iteration-0001/result.json").exists()


def test_public_model_environment_rejects_provider_credentials_before_lease(tmp_path):
    proposer, backend, proxy, pool, _ = _proposer(tmp_path)

    with pytest.raises(Exception, match="public proxy environment"):
        _propose(
            proposer,
            tmp_path,
            model_env={"LLM_API_KEY": "real-secret"},
        )

    assert backend.specs == []
    assert proxy.opens == 0
    assert pool.requests == []


def test_proposal_metadata_preserves_legacy_fields_and_adds_backend_identity(tmp_path):
    from qea.loop_benchmark import _proposal_metadata

    proposer, _, _, _, _ = _proposer(tmp_path)
    result = _propose(proposer, tmp_path)

    metadata = _proposal_metadata(result, tmp_path / "run")

    assert metadata["iteration"] == 1
    assert metadata["candidate_digest"] == result.candidate_digest
    assert metadata["input_bundle_sha256"] == result.input_bundle_sha256
    assert metadata["sandbox_id"] == "sandbox-evolver-1"
    assert metadata["cleaned_up"] is True
    assert metadata["backend"] == "fake-rootless"
    assert metadata["spec_sha256"] == result.spec_sha256
    assert metadata["proxy_sandbox_id"] == "proxy-1"
    assert metadata["network_id"] == "network-1"
    assert metadata["lifecycle_uri"].endswith(
        "evolver-sandbox-lifecycle-v2.json"
    )


def test_sandbox_evolver_config_requires_bounded_tmpfs_and_lifetime(tmp_path):
    from qea.executors.sandbox_evolver import SandboxEvolverConfig
    from qea.executors.sandbox_runtime import (
        SandboxInfrastructureError,
        SandboxResourceContract,
    )

    missing_qea = SandboxResourceContract(
        cpu_count=1,
        memory_mb=512,
        pids_limit=64,
        timeout_seconds=300,
        writable_tmpfs_mb={"/tmp": 64},
    )
    with pytest.raises(SandboxInfrastructureError, match="missing tmpfs"):
        SandboxEvolverConfig(
            image_ref="sha256:" + "a" * 64,
            resource_contract=missing_qea,
        )
    with pytest.raises(SandboxInfrastructureError, match="lifetime"):
        SandboxEvolverConfig(
            image_ref="sha256:" + "a" * 64,
            resource_contract=_resources(timeout_seconds=60),
            command_timeout_seconds=180,
        )


def test_candidate_digest_is_content_addressed_and_not_path_addressed(tmp_path):
    proposer, _, _, _, _ = _proposer(tmp_path)
    result = _propose(proposer, tmp_path)
    digest = hashlib.sha256()
    for path in sorted(
        result.candidate_dir.rglob("*"),
        key=lambda item: item.relative_to(result.candidate_dir).as_posix(),
    ):
        if not path.is_file():
            continue
        relative = path.relative_to(result.candidate_dir).as_posix().encode()
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    assert result.candidate_digest == digest.hexdigest()
