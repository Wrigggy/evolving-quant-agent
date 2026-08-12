"""Two-container QuantCodeEval verifier with an oracle-free strategy process."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..evaluation import OfficialTaskScore, TaskAttempt
from ..benchmarks.quantcodeeval import verify_quantcodeeval_role_root
from ..executors.execution_record import WorkerExecution
from ..executors.sandbox_nexau import SandboxQFBenchVerifier
from ..executors.sandbox_runtime import (
    SandboxInfrastructureError,
    SandboxResourceContract,
    backend_call,
    finish_and_cleanup,
    run_required,
    utc_now,
)
from ..sandbox_backend import SandboxBackend, SandboxNetworkHandle, SandboxSpec
from ..sandbox_lifecycle import create_lifecycle, mark_finished, mark_started
from .quantcodeeval import (
    parse_official_quantcodeeval_score,
    quantcodeeval_answer_free_summary,
)


class IsolatedQuantCodeEvalVerifier:
    """Execute candidate functions outside the checker/oracle container.

    The candidate container receives only ``strategy.py`` and an attempt-local
    internal network.  The checker container receives the trusted bundle and a
    bounded JSON-RPC endpoint.  Neither container has Internet egress.
    """

    def __init__(
        self,
        *,
        backend: SandboxBackend,
        lifecycle_root: str | Path,
        verifier_image_ref: str,
        public_task_root: str | Path,
        trusted_task_root: str | Path,
        resource_contract: SandboxResourceContract,
        max_strategy_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        if type(max_strategy_bytes) is not int or max_strategy_bytes <= 0:
            raise SandboxInfrastructureError(
                "quantcodeeval.config", "max strategy bytes must be positive"
            )
        self.backend = backend
        self.lifecycle_root = Path(lifecycle_root).expanduser().resolve()
        self.verifier_image_ref = verifier_image_ref
        self.public_task_root = Path(public_task_root).expanduser().resolve()
        self.trusted_task_root = Path(trusted_task_root).expanduser().resolve()
        self.resource_contract = resource_contract
        self.max_strategy_bytes = max_strategy_bytes
        public = verify_quantcodeeval_role_root(self.public_task_root, "public")
        trusted = verify_quantcodeeval_role_root(
            self.trusted_task_root, "trusted-verifier"
        )
        if public.commit != trusted.commit or public.task_ids != trusted.task_ids:
            raise SandboxInfrastructureError(
                "quantcodeeval.config", "public/trusted role identities differ"
            )

    def _strategy_path(self, execution: WorkerExecution) -> Path:
        records = tuple(sorted(execution.artifacts, key=lambda item: item.path))
        if tuple(record.path for record in records) != ("strategy.py",):
            raise SandboxInfrastructureError(
                "quantcodeeval.artifacts",
                "QuantCodeEval requires exactly one strategy.py artifact",
            )
        if records[0].size_bytes > self.max_strategy_bytes:
            raise SandboxInfrastructureError(
                "quantcodeeval.artifacts", "strategy.py exceeds the byte limit"
            )
        path = Path(execution.artifact_dir).resolve() / "strategy.py"
        if path.is_symlink() or not path.is_file():
            raise SandboxInfrastructureError(
                "quantcodeeval.artifacts", "strategy.py is not a regular file"
            )
        payload = path.read_bytes()
        if (
            len(payload) != records[0].size_bytes
            or hashlib.sha256(payload).hexdigest() != records[0].sha256
        ):
            raise SandboxInfrastructureError(
                "quantcodeeval.artifacts", "strategy.py identity changed"
            )
        return path

    def verify(
        self,
        *,
        attempt: TaskAttempt,
        task,
        execution: WorkerExecution,
        run_dir: str | Path,
    ) -> OfficialTaskScore:
        strategy = self._strategy_path(execution)
        create_network = getattr(self.backend, "create_internal_network", None)
        remove_network = getattr(self.backend, "remove_internal_network", None)
        if not callable(create_network) or not callable(remove_network):
            raise SandboxInfrastructureError(
                "quantcodeeval.network", "backend has no scoped internal network"
            )
        scope = f"qcev-{attempt.attempt_id[:96]}"
        network = backend_call(
            "quantcodeeval.network",
            lambda: create_network(attempt.run_id, network_scope=scope),
        )
        if not isinstance(network, SandboxNetworkHandle):
            raise SandboxInfrastructureError(
                "quantcodeeval.network", "backend returned no scoped network handle"
            )
        candidate_attempt_id = f"{attempt.attempt_id[:110]}-strategy"
        candidate_spec = SandboxSpec(
            role="worker",
            run_id=attempt.run_id,
            attempt_id=candidate_attempt_id,
            task_id=task.task_id,
            image_ref=self.verifier_image_ref,
            cpu_count=self.resource_contract.cpu_count,
            memory_mb=self.resource_contract.memory_mb,
            pids_limit=self.resource_contract.pids_limit,
            timeout_seconds=self.resource_contract.timeout_seconds,
            network_policy="worker-proxy-only",
            environment={},
            writable_tmpfs_mb={"/tmp": 64, "/candidate": 16},
            network_scope=scope,
        )
        candidate_identity = hashlib.sha256(
            (candidate_spec.spec_sha256 + execution.artifacts[0].sha256).encode()
        ).hexdigest()
        lifecycle_path = (
            self.lifecycle_root / attempt.run_id / candidate_attempt_id
            / "strategy-sandbox-lifecycle-v2.json"
        )
        candidate_handle = None
        primary_error: BaseException | None = None
        finished = False
        score: OfficialTaskScore | None = None
        try:
            candidate_handle = backend_call(
                "quantcodeeval.strategy.create",
                lambda: self.backend.create(candidate_spec),
            )
            create_lifecycle(
                lifecycle_path,
                handle=candidate_handle,
                spec=candidate_spec,
                attempt_identity_sha256=candidate_identity,
                at=utc_now(),
            )
            backend_call(
                "quantcodeeval.strategy.start",
                lambda: self.backend.start(candidate_handle),
            )
            mark_started(lifecycle_path, at=utc_now())
            backend_call(
                "quantcodeeval.strategy.upload",
                lambda: self.backend.put_bytes(
                    candidate_handle, "/candidate/strategy.py", strategy.read_bytes()
                ),
            )
            public_data = (
                self.public_task_root / "tasks" / task.task_id
                / "environment" / "data"
            )
            if public_data.is_symlink() or not public_data.is_dir():
                raise SandboxInfrastructureError(
                    "quantcodeeval.strategy.data", "public task data is missing"
                )
            run_required(
                self.backend,
                candidate_handle,
                ("mkdir", "-p", "/candidate/data"),
                environment={},
                timeout_seconds=30,
                phase="quantcodeeval.strategy.data",
            )
            for path in sorted(public_data.rglob("*")):
                if path.is_symlink() or (not path.is_file() and not path.is_dir()):
                    raise SandboxInfrastructureError(
                        "quantcodeeval.strategy.data", "unsafe public data entry"
                    )
                if not path.is_file():
                    continue
                relative = path.relative_to(public_data).as_posix()
                parent = str(Path("/candidate/data") / Path(relative).parent)
                run_required(
                    self.backend,
                    candidate_handle,
                    ("mkdir", "-p", parent),
                    environment={},
                    timeout_seconds=30,
                    phase="quantcodeeval.strategy.data",
                )
                backend_call(
                    "quantcodeeval.strategy.data",
                    lambda path=path, relative=relative: self.backend.put_bytes(
                        candidate_handle,
                        f"/candidate/data/{relative}",
                        path.read_bytes(),
                    ),
                )
            run_required(
                self.backend,
                candidate_handle,
                (
                    "sh", "-c",
                    "PYTHONPATH=/opt/qea-qce /usr/local/bin/python3 "
                    "-m qea.verifiers.quantcodeeval_rpc_server "
                    "--strategy /candidate/strategy.py --port 8765 "
                    ">/tmp/strategy-rpc.log 2>&1 &",
                ),
                environment={},
                timeout_seconds=30,
                phase="quantcodeeval.strategy.service",
            )
            checker = SandboxQFBenchVerifier(
                backend=self.backend,
                lifecycle_root=self.lifecycle_root,
                verifier_image_ref=self.verifier_image_ref,
                trusted_task_root=self.trusted_task_root,
                resource_contract=self.resource_contract,
                score_parser=parse_official_quantcodeeval_score,
                answer_free_evidence_builder=quantcodeeval_answer_free_summary,
                sandbox_role="canary",
                network_policy="worker-proxy-only",
                network_scope=scope,
                verifier_environment={
                    "QEA_STRATEGY_RPC_URL": (
                        f"http://{candidate_handle.native_id[:12]}:8765/rpc"
                    ),
                },
            )
            score = checker.verify(
                attempt=attempt,
                task=task,
                execution=execution,
                run_dir=run_dir,
            )
            try:
                probe_raw = self.backend.read_bytes(
                    candidate_handle, "/candidate/qea-isolation-probe.json"
                )
            except Exception:  # no probe is the normal production case.
                probe_raw = None
            if probe_raw is not None:
                if len(probe_raw) > 4096:
                    raise SandboxInfrastructureError(
                        "quantcodeeval.strategy.probe", "probe exceeds byte limit"
                    )
                try:
                    probe = json.loads(probe_raw)
                except json.JSONDecodeError as exc:
                    raise SandboxInfrastructureError(
                        "quantcodeeval.strategy.probe", "probe is not JSON"
                    ) from exc
                expected_keys = {"tests_exists", "golden_exists", "expected_exists"}
                if (
                    not isinstance(probe, dict)
                    or set(probe) != expected_keys
                    or not all(type(value) is bool for value in probe.values())
                ):
                    raise SandboxInfrastructureError(
                        "quantcodeeval.strategy.probe", "probe schema is invalid"
                    )
                probe_path = (
                    Path(run_dir).resolve() / "attempts" / attempt.attempt_id
                    / "verifier" / "strategy-isolation-probe.json"
                )
                probe_path.write_text(
                    json.dumps(probe, sort_keys=True, indent=2) + "\n"
                )
            mark_finished(lifecycle_path, at=utc_now())
            finished = True
        except BaseException as exc:  # cleanup must cover every candidate failure.
            primary_error = exc
        finally:
            if candidate_handle is not None:
                finish_and_cleanup(
                    backend=self.backend,
                    handle=candidate_handle,
                    lifecycle_path=lifecycle_path,
                    clock=utc_now,
                    role="strategy",
                    primary_error=primary_error,
                    finished=finished,
                )
            try:
                remove_network(network)
            except Exception as exc:  # noqa: BLE001 - normalize cleanup failure.
                if primary_error is None:
                    primary_error = SandboxInfrastructureError(
                        "quantcodeeval.network.cleanup", str(exc)
                    )
        if primary_error is not None:
            raise primary_error
        assert score is not None
        return score
