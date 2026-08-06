import base64
import hashlib
import io
import json
import tarfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from qea.qfbench_images import NEXAU_REQUIREMENTS_LOCK, NEXAU_RUNTIME_PYTHON
from qea.resource_lease import ResourceRequest
from qea.evolution_evidence import EvidenceRecord
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


def _evidence_record(root):
    digest = hashlib.sha256()
    members = []
    for path in sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.name != "access_log.jsonl"
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        encoded = relative.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        members.append(relative)
    return EvidenceRecord(root=root, sha256=digest.hexdigest(), members=tuple(members))


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
    (evidence / "access_log.jsonl").write_text("")
    (evolver / "tools").mkdir(parents=True, exist_ok=True)
    (evolver / "agent.yaml").write_text("name: evolver\n")
    (evolver / "tools" / "__init__.py").write_text("")
    return candidate, _evidence_record(evidence), evolver


class FakeBackend:
    backend_name = "fake-rootless"

    def __init__(
        self,
        events,
        *,
        candidate_archive=None,
        command_error=False,
        oversized_path=None,
        echo_secret=None,
    ):
        self.events = events
        self.candidate_archive = candidate_archive or _tar_bytes(
            {
                "agent.yaml": "name: worker\n",
                "systemprompt.md": "Solve, inspect, and validate.\n",
                "tools/__init__.py": "",
            }
        )
        self.command_error = command_error
        self.oversized_path = oversized_path
        self.echo_secret = echo_secret
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
        values = self._download_values()
        return values[path]

    def _download_values(self):
        return {
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

    def run(self, handle, argv, *, environment, timeout_seconds):
        command = tuple(argv)
        if (
            len(command) == 5
            and command[0] == "/usr/local/bin/python3"
            and command[1] == "-c"
            and "QEA_BOUNDED_READ_V1" in command[2]
        ):
            remote_path = command[3]
            self.events.append(f"run:bounded:{remote_path}")
            if remote_path == self.oversized_path:
                return SandboxCommandResult(
                    73, "", "bounded read limit exceeded", False
                )
            payload = self._download_values()[remote_path]
            return SandboxCommandResult(
                0, base64.b64encode(payload).decode("ascii"), "", False
            )
        if command and command[0] == NEXAU_RUNTIME_PYTHON:
            self.events.append(("run:evolver", command, dict(environment)))
            if self.command_error:
                detail = (
                    self.command_error
                    if isinstance(self.command_error, str)
                    else "provider failed"
                )
                return SandboxCommandResult(19, "", detail, False)
            if self.echo_secret:
                return SandboxCommandResult(0, self.echo_secret, "", False)
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
            image_ref="sha256:" + "c" * 64,
            resource_contract=proxy_resources,
            token_file=Path("/never/read/model-token"),
            upstream_base_url="https://openrouter.ai/api/v1",
            allowed_model="example/model",
            listen_port=8080,
            allowed_path_prefix="/v1",
            timeout_seconds=120,
            expect_request=True,
        )
        self.opens = 0
        self.tamper_attempt_identity = None

    @contextmanager
    def open(self, **kwargs):
        from qea.model_proxy import build_model_proxy_sandbox_plan
        from qea.sandbox_lifecycle import (
            create_lifecycle,
            mark_cleaned,
            mark_finished,
            mark_started,
        )

        self.opens += 1
        self.events.append(("proxy:open", kwargs))
        plan = build_model_proxy_sandbox_plan(
            run_id=kwargs["run_id"],
            attempt_id=kwargs["attempt_id"],
            task_id=kwargs["task_id"],
            image_ref=self.config.image_ref,
            upstream_base_url=self.config.upstream_base_url,
            allowed_path_prefix=self.config.allowed_path_prefix,
            listen_port=self.config.listen_port,
            cpu_count=self.config.resource_contract.cpu_count,
            memory_mb=self.config.resource_contract.memory_mb,
            pids_limit=self.config.resource_contract.pids_limit,
            timeout_seconds=self.config.resource_contract.timeout_seconds,
            network_scope=kwargs["attempt_id"],
            allowed_model=self.config.allowed_model,
            audit_path="/run/qea-secrets/proxy-audit.jsonl",
            denied_request_identities_sha256=(),
            writable_tmpfs_mb=self.config.resource_contract.writable_tmpfs_mb,
        )
        public_plan_sha256 = hashlib.sha256(
            json.dumps(
                plan.public_payload(), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        public_config_sha256 = hashlib.sha256(
            json.dumps(
                plan.config_payload(), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        attempt_identity_sha256 = hashlib.sha256(
            json.dumps(
                {
                    "public_config_sha256": public_config_sha256,
                    "public_plan_sha256": public_plan_sha256,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        lifecycle_uri = (
            Path(kwargs["run_dir"])
            / "lifecycles"
            / kwargs["attempt_id"]
            / "proxy-sandbox-lifecycle-v2.json"
        )
        handle = SandboxHandle(
            backend=self.backend.backend_name,
            native_id="proxy-1",
            immutable_image_ref=plan.spec.image_ref,
            spec_sha256=plan.spec.spec_sha256,
        )
        create_lifecycle(
            lifecycle_uri,
            handle=handle,
            spec=plan.spec,
            attempt_identity_sha256=attempt_identity_sha256,
        )
        mark_started(lifecycle_uri)
        try:
            yield SimpleNamespace(
                base_url="http://qea-model-proxy:8080/v1",
                network_scope=kwargs["attempt_id"],
                network_name="qea-run-evolver-network",
                network_id="network-1",
                native_id="proxy-1",
                allowed_model="example/model",
                lifecycle_uri=lifecycle_uri,
                immutable_image_ref=handle.immutable_image_ref,
                spec_sha256=handle.spec_sha256,
                public_plan_sha256=public_plan_sha256,
                public_config_sha256=public_config_sha256,
                attempt_identity_sha256=(
                    self.tamper_attempt_identity or attempt_identity_sha256
                ),
            )
        finally:
            mark_finished(lifecycle_uri)
            mark_cleaned(
                lifecycle_uri,
                cleanup_method="exact-id",
                cleanup_result="killed",
            )
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


def _proposer(
    tmp_path,
    *,
    backend=None,
    events=None,
    image=None,
    model=None,
    lifecycle_root=None,
):
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
        lifecycle_root=lifecycle_root or tmp_path / "lifecycles",
        proxy_manager=proxy,
        resource_pool=pool,
        model_name=model or "example/model",
    )
    return proposer, backend, proxy, pool, events


def _propose(proposer, tmp_path, **overrides):
    candidate, evidence, evolver = _roots(tmp_path / "run/inputs")
    (tmp_path / "run").mkdir(exist_ok=True)
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
        "/qea/evolver_discovery.py",
        "/qea/remote_evolver.py",
        "/qea/runtime_bridge.py",
        "/qea/diagnosis.txt",
    }
    assert b"def task_python(" in backend.uploads["/qea/runtime_bridge.py"]
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
        ("proxy_image_ref", "sha256:" + "e" * 64),
        ("proxy_spec_sha256", "4" * 64),
        ("proxy_config_sha256", "5" * 64),
        ("backend", "other-backend"),
    ):
        changed = dict(original)
        changed[field] = bad_value
        result_path.write_text(json.dumps(changed, sort_keys=True) + "\n")
        with pytest.raises(Exception, match="identity mismatch"):
            _propose(proposer, tmp_path)
        result_path.write_text(json.dumps(original, sort_keys=True) + "\n")


def test_completed_resume_rejects_proxy_configuration_drift(tmp_path):
    proposer, backend, proxy, _, _ = _proposer(tmp_path)
    _propose(proposer, tmp_path)

    proxy.config.image_ref = "sha256:" + "d" * 64

    with pytest.raises(Exception, match="identity mismatch"):
        _propose(proposer, tmp_path)
    assert len(backend.specs) == 1
    assert proxy.opens == 1


def test_completed_resume_binds_executed_proxy_lifecycle_provenance(tmp_path):
    proposer, _, _, _, _ = _proposer(tmp_path)
    first = _propose(proposer, tmp_path)
    manifest_path = tmp_path / "run/evolutions/iteration-0001/result.json"
    manifest = json.loads(manifest_path.read_text())

    assert first.executed_proxy_image_ref == manifest[
        "executed_proxy_image_ref"
    ]
    assert first.executed_proxy_spec_sha256 == manifest[
        "executed_proxy_spec_sha256"
    ]
    assert first.executed_proxy_public_plan_sha256 == manifest[
        "executed_proxy_public_plan_sha256"
    ]
    assert first.executed_proxy_config_sha256 == manifest[
        "executed_proxy_config_sha256"
    ]
    assert first.executed_proxy_attempt_identity_sha256 == manifest[
        "executed_proxy_attempt_identity_sha256"
    ]
    proxy_lifecycle = json.loads(first.proxy_lifecycle_uri.read_text())
    assert proxy_lifecycle["cleaned_up"] is True
    assert proxy_lifecycle["native_id"] == first.proxy_sandbox_id
    assert proxy_lifecycle["attempt_identity_sha256"] == (
        first.executed_proxy_attempt_identity_sha256
    )

    proxy_lifecycle["attempt_identity_sha256"] = "f" * 64
    first.proxy_lifecycle_uri.write_text(
        json.dumps(proxy_lifecycle, sort_keys=True) + "\n"
    )
    with pytest.raises(Exception, match="proxy lifecycle identity mismatch"):
        _propose(proposer, tmp_path)


def test_completed_resume_ignores_later_monotonic_proxy_denylist_growth(tmp_path):
    proposer, backend, proxy, _, _ = _proposer(tmp_path)
    first = _propose(proposer, tmp_path)
    registry = tmp_path / "run/proxy-request-registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "request_identities_sha256": ["9" * 64],
            },
            sort_keys=True,
        )
        + "\n"
    )

    second = _propose(proposer, tmp_path)

    assert second == first
    assert len(backend.specs) == 1
    assert proxy.opens == 1


def test_fresh_result_rejects_tampered_proxy_session_identity(tmp_path):
    proposer, backend, proxy, _, _ = _proposer(tmp_path)
    proxy.tamper_attempt_identity = "e" * 64

    with pytest.raises(Exception, match="proxy session identity"):
        _propose(proposer, tmp_path)

    assert len(backend.specs) == 0
    assert not (tmp_path / "run/evolutions/iteration-0001/result.json").exists()


def test_diagnosis_credentials_are_structurally_scrubbed_from_all_artifacts(tmp_path):
    secret = "sk-or-v1-sensitive-real-bytes"
    url_password = "url-password-sensitive"
    events = []
    backend = FakeBackend(events, echo_secret=secret)
    proposer, backend, _, _, _ = _proposer(
        tmp_path, backend=backend, events=events
    )

    result = _propose(
        proposer,
        tmp_path,
        diagnosis={
            "OPENROUTER_API_KEY": secret,
            "nested": {
                "authorization": f"Bearer {secret}",
                "note": f"provider repeated {secret}",
            },
            "provider_assignment": f"OPENROUTER_API_KEY={secret}",
            "provider_url": (
                f"https://agent:{url_password}@provider.example.invalid/v1"
            ),
        },
    )

    diagnosis_upload = backend.uploads["/qea/diagnosis.txt"]
    assert b"[REDACTED]" in diagnosis_upload
    checked = list(backend.uploads.values())
    checked.extend(
        path.read_bytes()
        for path in (tmp_path / "run").rglob("*")
        if path.is_file()
    )
    checked.extend(
        path.read_bytes()
        for path in result.lifecycle_uri.parent.rglob("*")
        if path.is_file()
    )
    for payload in checked:
        assert secret.encode() not in payload
        assert url_password.encode() not in payload


def test_rejected_resume_drift_does_not_overwrite_committed_input_bundle(tmp_path):
    proposer, _, _, _, _ = _proposer(tmp_path)
    _propose(proposer, tmp_path)
    input_path = tmp_path / "run/evolutions/iteration-0001/input.tar"
    committed = input_path.read_bytes()
    candidate = tmp_path / "run/inputs/candidate"
    evidence = _evidence_record(tmp_path / "run/inputs/evidence")
    evolver = tmp_path / "run/inputs/evolve_agent"
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
    candidate = tmp_path / "run/inputs/candidate"
    (candidate / "systemprompt.md").write_text("Drifted input.\n")

    with pytest.raises(Exception, match="quarantined"):
        proposer.propose(
            candidate_dir=candidate,
            evidence_dir=_evidence_record(tmp_path / "run/inputs/evidence"),
            evolver_dir=tmp_path / "run/inputs/evolve_agent",
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
    candidate = tmp_path / "run/inputs/candidate"
    (candidate / "systemprompt.md").write_text("Drifted input.\n")

    with pytest.raises(Exception, match="ambiguous"):
        proposer.propose(
            candidate_dir=candidate,
            evidence_dir=_evidence_record(tmp_path / "run/inputs/evidence"),
            evolver_dir=tmp_path / "run/inputs/evolve_agent",
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


def test_evolver_requires_authorized_evidence_record_not_a_bare_path(tmp_path):
    proposer, backend, proxy, pool, _ = _proposer(tmp_path)
    candidate, evidence, evolver = _roots(tmp_path / "run/inputs")
    (tmp_path / "run").mkdir(exist_ok=True)

    with pytest.raises(Exception, match="EvidenceRecord"):
        proposer.propose(
            candidate_dir=candidate,
            evidence_dir=evidence.root,
            evolver_dir=evolver,
            diagnosis="Improve validation.",
            iteration=1,
            run_id="run-001",
            run_dir=tmp_path / "run",
            model_env={},
        )

    assert backend.specs == []
    assert proxy.opens == 0
    assert pool.requests == []


def test_evolver_requires_evidence_record_root_inside_run(tmp_path):
    proposer, backend, proxy, pool, _ = _proposer(tmp_path)
    candidate, evidence, evolver = _roots(tmp_path / "outside-inputs")
    (tmp_path / "run").mkdir()

    with pytest.raises(Exception, match="escapes its trusted root"):
        proposer.propose(
            candidate_dir=candidate,
            evidence_dir=evidence,
            evolver_dir=evolver,
            diagnosis="Improve validation.",
            iteration=1,
            run_id="run-001",
            run_dir=tmp_path / "run",
            model_env={},
        )

    assert backend.specs == []
    assert proxy.opens == 0
    assert pool.requests == []


def test_evolver_rejects_mutated_or_private_evidence_before_upload(tmp_path):
    proposer, backend, proxy, pool, _ = _proposer(tmp_path)
    candidate, evidence, evolver = _roots(tmp_path / "run/inputs")
    (tmp_path / "run").mkdir(exist_ok=True)
    (evidence.root / "contract.json").write_text('{"mode":"mutated"}\n')

    with pytest.raises(Exception, match="evidence.*digest"):
        proposer.propose(
            candidate_dir=candidate,
            evidence_dir=evidence,
            evolver_dir=evolver,
            diagnosis="Improve validation.",
            iteration=1,
            run_id="run-001",
            run_dir=tmp_path / "run",
            model_env={},
        )

    private = evidence.root / "tests"
    private.mkdir()
    (private / "hidden.json").write_text('{"answer":42}\n')
    with pytest.raises(Exception, match="private evaluator path"):
        proposer.propose(
            candidate_dir=candidate,
            evidence_dir=_evidence_record(evidence.root),
            evolver_dir=evolver,
            diagnosis="Improve validation.",
            iteration=1,
            run_id="run-001",
            run_dir=tmp_path / "run",
            model_env={},
        )

    assert backend.specs == []
    assert proxy.opens == 0
    assert pool.requests == []


@pytest.mark.parametrize("surface", ["run", "input", "result", "lifecycle", "evidence"])
def test_evolver_rejects_symlinked_trusted_surfaces(tmp_path, surface):
    lifecycle_root = tmp_path / "lifecycles"
    proposer, backend, proxy, pool, _ = _proposer(
        tmp_path, lifecycle_root=lifecycle_root
    )
    run_root = tmp_path / "run"
    run_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    if surface == "run":
        candidate, evidence, evolver = _roots(outside / "inputs")
        run_root.rmdir()
        run_root.symlink_to(outside, target_is_directory=True)
    else:
        candidate, evidence, evolver = _roots(run_root / "inputs")

    if surface == "input":
        evolution = run_root / "evolutions/iteration-0001"
        evolution.mkdir(parents=True)
        target = outside / "input.tar"
        target.write_text("sentinel")
        (evolution / "input.pending.tar").symlink_to(target)
    elif surface == "result":
        evolution = run_root / "evolutions/iteration-0001"
        evolution.mkdir(parents=True)
        target = outside / "result.json"
        target.write_text("{}\n")
        (evolution / "result.json").symlink_to(target)
    elif surface == "lifecycle":
        leaf = lifecycle_root / "run-001/evolver-iteration-1"
        leaf.mkdir(parents=True)
        target = outside / "lifecycle.json"
        target.write_text("{}\n")
        (leaf / "evolver-sandbox-lifecycle-v2.json").symlink_to(target)
    elif surface == "evidence":
        target = outside / "contract.json"
        target.write_text('{"mode":"rich"}\n')
        (evidence.root / "contract.json").unlink()
        (evidence.root / "contract.json").symlink_to(target)
        evidence = EvidenceRecord(
            root=evidence.root,
            sha256="0" * 64,
            members=("contract.json",),
        )

    with pytest.raises(Exception, match="symlink"):
        proposer.propose(
            candidate_dir=candidate,
            evidence_dir=evidence,
            evolver_dir=evolver,
            diagnosis="Improve validation.",
            iteration=1,
            run_id="run-001",
            run_dir=run_root,
            model_env={},
        )

    assert backend.specs == []
    assert proxy.opens == 0
    assert pool.requests == []
    if surface == "input":
        assert (outside / "input.tar").read_text() == "sentinel"


def test_evolver_downloads_are_bounded_without_backend_read_bytes(tmp_path):
    proposer, _, _, _, events = _proposer(tmp_path)

    _propose(proposer, tmp_path)

    assert not [event for event in events if str(event).startswith("read:")]
    bounded = [event for event in events if str(event).startswith("run:bounded:")]
    assert len(bounded) == 7


@pytest.mark.parametrize(
    "remote_path",
    [
        "/qea/result/candidate.tar",
        "/qea/result/raw_trace.jsonl",
    ],
)
def test_oversized_sandbox_download_is_rejected_before_transfer(tmp_path, remote_path):
    events = []
    backend = FakeBackend(events, oversized_path=remote_path)
    proposer, _, _, _, _ = _proposer(
        tmp_path, backend=backend, events=events
    )

    with pytest.raises(Exception, match="bounded read"):
        _propose(proposer, tmp_path)

    assert not [event for event in events if str(event).startswith("read:")]
    assert "kill:sandbox-evolver-1" in events
    assert not (tmp_path / "run/evolutions/iteration-0001/result.json").exists()


def test_cleanup_error_preserves_lifecycle_finish_error_and_primary_cause(
    tmp_path, monkeypatch
):
    import qea.executors.sandbox_runtime as runtime

    lifecycle = tmp_path / "lifecycle.json"
    lifecycle.write_text("{}\n")
    primary = ValueError("primary failure")

    def fail_finish(*args, **kwargs):
        raise RuntimeError("finish failed")

    class CleanupFailure:
        def kill(self, native_id):
            raise RuntimeError("cleanup failed")

    monkeypatch.setattr(runtime, "mark_finished", fail_finish)
    with pytest.raises(runtime.SandboxInfrastructureError, match="cleanup failed") as caught:
        runtime.finish_and_cleanup(
            backend=CleanupFailure(),
            handle=SimpleNamespace(native_id="sandbox-1"),
            lifecycle_path=lifecycle,
            clock=runtime.utc_now,
            role="evolver",
            primary_error=primary,
            finished=False,
        )

    assert caught.value.__cause__ is primary
    secondary = caught.value.secondary_failures
    assert len(secondary) == 1
    assert secondary[0].phase == "evolver.lifecycle"
    assert "finish failed" in str(secondary[0])


def test_evolver_rechecks_actual_bundled_evidence_against_record(
    tmp_path, monkeypatch
):
    import qea.executors.sandbox_evolver as module
    from qea.executors.bundles import build_evolver_input_bundle as real_build

    def substitute(*args, **kwargs):
        record = real_build(*args, **kwargs)
        files = {}
        with tarfile.open(record.path, mode="r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                handle = archive.extractfile(member)
                assert handle is not None
                files[member.name] = handle.read()
        files["evidence/contract.json"] = b'{"mode":"substituted"}\n'
        payload = _tar_bytes(files)
        record.path.write_bytes(payload)
        return replace(
            record,
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
        )

    monkeypatch.setattr(module, "build_evolver_input_bundle", substitute)
    proposer, backend, proxy, pool, _ = _proposer(tmp_path)

    with pytest.raises(Exception, match="bundled evidence differs"):
        _propose(proposer, tmp_path)

    assert backend.specs == []
    assert proxy.opens == 0
    assert pool.requests == []


@pytest.mark.parametrize("state", ["missing", "nonempty", "nested"])
def test_evolver_requires_one_empty_root_access_log(tmp_path, state):
    proposer, backend, proxy, pool, _ = _proposer(tmp_path)
    candidate, evidence, evolver = _roots(tmp_path / "run/inputs")
    if state == "missing":
        (evidence.root / "access_log.jsonl").unlink()
    elif state == "nonempty":
        (evidence.root / "access_log.jsonl").write_text('{"access":true}\n')
    else:
        nested = evidence.root / "nested"
        nested.mkdir()
        (nested / "access_log.jsonl").write_text("")

    with pytest.raises(Exception, match="access_log.jsonl"):
        proposer.propose(
            candidate_dir=candidate,
            evidence_dir=evidence,
            evolver_dir=evolver,
            diagnosis="Improve validation.",
            iteration=1,
            run_id="run-001",
            run_dir=tmp_path / "run",
            model_env={},
        )

    assert backend.specs == []
    assert proxy.opens == 0
    assert pool.requests == []


def test_evolver_rejects_substituted_access_log_in_actual_bundle(
    tmp_path, monkeypatch
):
    import qea.executors.sandbox_evolver as module
    from qea.executors.bundles import build_evolver_input_bundle as real_build

    def substitute(*args, **kwargs):
        record = real_build(*args, **kwargs)
        files = {}
        with tarfile.open(record.path, mode="r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                handle = archive.extractfile(member)
                assert handle is not None
                files[member.name] = handle.read()
        files["evidence/access_log.jsonl"] = b'{"substituted":true}\n'
        payload = _tar_bytes(files)
        record.path.write_bytes(payload)
        return replace(
            record,
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
        )

    monkeypatch.setattr(module, "build_evolver_input_bundle", substitute)
    proposer, backend, proxy, pool, _ = _proposer(tmp_path)

    with pytest.raises(Exception, match="access_log.jsonl"):
        _propose(proposer, tmp_path)

    assert backend.specs == []
    assert proxy.opens == 0
    assert pool.requests == []


def test_nonzero_command_error_redacts_known_diagnosis_secret_everywhere(tmp_path):
    secret = "sk-or-v1-command-error-secret"
    events = []
    backend = FakeBackend(events, command_error=secret)
    proposer, _, _, _, _ = _proposer(
        tmp_path, backend=backend, events=events
    )

    with pytest.raises(Exception, match="evolver command exited") as caught:
        _propose(
            proposer,
            tmp_path,
            diagnosis={"OPENROUTER_API_KEY": secret, "goal": "improve"},
        )

    current = caught.value
    while current is not None:
        assert secret not in str(current)
        current = current.__cause__
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert secret.encode() not in path.read_bytes()
    for payload in backend.uploads.values():
        assert secret.encode() not in payload


@pytest.mark.parametrize("parent_name", ["attempts", "lifecycles"])
def test_evolver_rejects_symlinked_proxy_state_parent_before_acquisition(
    tmp_path, parent_name
):
    proposer, backend, proxy, pool, _ = _proposer(tmp_path)
    candidate, evidence, evolver = _roots(tmp_path / "run/inputs")
    external = tmp_path / f"external-{parent_name}"
    external.mkdir()
    marker = external / "sentinel"
    marker.write_text("unchanged")
    (tmp_path / "run" / parent_name).symlink_to(
        external, target_is_directory=True
    )

    with pytest.raises(Exception, match="symlink"):
        proposer.propose(
            candidate_dir=candidate,
            evidence_dir=evidence,
            evolver_dir=evolver,
            diagnosis="Improve validation.",
            iteration=1,
            run_id="run-001",
            run_dir=tmp_path / "run",
            model_env={},
        )

    assert marker.read_text() == "unchanged"
    assert sorted(path.name for path in external.iterdir()) == ["sentinel"]
    assert backend.specs == []
    assert proxy.opens == 0
    assert pool.requests == []
