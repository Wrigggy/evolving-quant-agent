"""Fail-closed incident policy and durable state for QFBench repair automation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping


_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
_CATEGORY = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_PROVIDER = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
_FORBIDDEN_EXCERPT = (
    ".env",
    "api_key",
    "api-key",
    "authorization: bearer",
    "openrouter_api_key",
    "official tests",
    "reference data",
    "raw verifier",
    "solution/",
)
_HARD_STOP_CATEGORIES = frozenset(
    {
        "verifier_firewall_drift",
        "credential_exposure",
        "official_data_exposure",
        "identity_drift",
        "historical_hash_drift",
        "ambiguous_upstream",
        "unsupported_cost_omission",
        "cleanup_failure",
        "supervisor_orphan",
    }
)
_REPAIRABLE_CATEGORIES = frozenset({"artifact_integrity", "harness_bug"})
_RESUMABLE_CATEGORIES = frozenset({"replay_safe_interruption"})


class SupervisorPolicyError(RuntimeError):
    """Supervisor input or state violates the approved repair policy."""


class RepairBudgetError(SupervisorPolicyError):
    """The bounded autonomous code-repair budget has been exhausted."""


class IncidentState(str, Enum):
    OBSERVED = "observed"
    FROZEN = "frozen"
    CLASSIFIED = "classified"
    REPAIRING = "repairing"
    TESTED = "tested"
    DEPLOYED = "deployed"
    CANARY_PASSED = "canary_passed"
    RESUMED = "resumed"
    RESOLVED = "resolved"
    HARD_STOP = "hard_stop"
    REPAIR_BUDGET_EXHAUSTED = "repair_budget_exhausted"


_TERMINAL_STATES = frozenset(
    {
        IncidentState.RESOLVED,
        IncidentState.HARD_STOP,
        IncidentState.REPAIR_BUDGET_EXHAUSTED,
    }
)
_ALLOWED_TRANSITIONS = {
    IncidentState.OBSERVED: frozenset({IncidentState.FROZEN}),
    IncidentState.FROZEN: frozenset({IncidentState.CLASSIFIED}),
    IncidentState.CLASSIFIED: frozenset(
        {IncidentState.REPAIRING, IncidentState.CANARY_PASSED}
    ),
    IncidentState.REPAIRING: frozenset({IncidentState.TESTED}),
    IncidentState.TESTED: frozenset(
        {IncidentState.REPAIRING, IncidentState.DEPLOYED}
    ),
    IncidentState.DEPLOYED: frozenset(
        {IncidentState.REPAIRING, IncidentState.CANARY_PASSED}
    ),
    IncidentState.CANARY_PASSED: frozenset(
        {IncidentState.REPAIRING, IncidentState.RESUMED}
    ),
    IncidentState.RESUMED: frozenset({IncidentState.RESOLVED}),
}


def _bounded_text(value: object, label: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise SupervisorPolicyError(f"{label} must be a non-empty bounded string")
    if any(ord(character) < 0x20 and character not in "\n\t" for character in value):
        raise SupervisorPolicyError(f"{label} contains control characters")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise SupervisorPolicyError(f"{label} must be a lowercase SHA-256")
    return value


def _exact_keys(payload: object, expected: set[str], label: str) -> dict:
    if not isinstance(payload, dict) or set(payload) != expected:
        raise SupervisorPolicyError(f"{label} schema is invalid")
    return payload


def incident_id(
    run_id: str,
    source_commit: str,
    exit_evidence_sha256: str,
    failure_signature: str,
) -> str:
    """Return the stable content address for one normalized run failure."""

    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise SupervisorPolicyError("run_id is invalid")
    if not isinstance(source_commit, str) or not _GIT_SHA.fullmatch(source_commit):
        raise SupervisorPolicyError("source_commit must be a full lowercase Git SHA")
    _digest(exit_evidence_sha256, "exit_evidence_sha256")
    signature = _bounded_text(failure_signature, "failure_signature", maximum=512)
    payload = "\n".join(
        (run_id, source_commit, exit_evidence_sha256, signature)
    ).encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ExpectedIdentity:
    benchmark_commit: str
    model: str
    required_provider: str
    allow_fallbacks: bool
    image_set_sha256: str
    runtime_sha256: str
    scheduler_sha256: str
    config_sha256: str
    checkpoint_sha256: str

    def __post_init__(self) -> None:
        if not _GIT_SHA.fullmatch(self.benchmark_commit):
            raise SupervisorPolicyError("benchmark_commit must be a full Git SHA")
        _bounded_text(self.model, "model", maximum=128)
        if not _PROVIDER.fullmatch(self.required_provider):
            raise SupervisorPolicyError("required_provider is invalid")
        if self.allow_fallbacks is not False:
            raise SupervisorPolicyError("provider fallbacks must remain disabled")
        for field_name in (
            "image_set_sha256",
            "runtime_sha256",
            "scheduler_sha256",
            "config_sha256",
            "checkpoint_sha256",
        ):
            _digest(getattr(self, field_name), field_name)

    def to_dict(self) -> dict[str, object]:
        return {
            "benchmark_commit": self.benchmark_commit,
            "model": self.model,
            "required_provider": self.required_provider,
            "allow_fallbacks": self.allow_fallbacks,
            "image_set_sha256": self.image_set_sha256,
            "runtime_sha256": self.runtime_sha256,
            "scheduler_sha256": self.scheduler_sha256,
            "config_sha256": self.config_sha256,
            "checkpoint_sha256": self.checkpoint_sha256,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "ExpectedIdentity":
        parsed = _exact_keys(
            payload,
            {
                "benchmark_commit",
                "model",
                "required_provider",
                "allow_fallbacks",
                "image_set_sha256",
                "runtime_sha256",
                "scheduler_sha256",
                "config_sha256",
                "checkpoint_sha256",
            },
            "expected identity",
        )
        return cls(**parsed)


@dataclass(frozen=True)
class Incident:
    schema_version: int
    incident_id: str
    run_id: str
    source_commit: str
    exit_code: int
    exit_evidence_sha256: str
    failure_signature: str
    category: str
    excerpt: str
    expected_identity: ExpectedIdentity
    evidence_hashes: tuple[tuple[str, str], ...]

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        source_commit: str,
        exit_code: int,
        exit_evidence_sha256: str,
        failure_signature: str,
        category: str,
        excerpt: str,
        expected_identity: ExpectedIdentity,
        evidence_hashes: Mapping[str, str],
    ) -> "Incident":
        identity = incident_id(
            run_id, source_commit, exit_evidence_sha256, failure_signature
        )
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            raise SupervisorPolicyError("exit_code must be an integer")
        if not isinstance(category, str) or not _CATEGORY.fullmatch(category):
            raise SupervisorPolicyError("incident category is invalid")
        safe_excerpt = _bounded_text(excerpt, "excerpt", maximum=2048)
        lowered = safe_excerpt.lower()
        if any(forbidden in lowered for forbidden in _FORBIDDEN_EXCERPT):
            raise SupervisorPolicyError("excerpt contains forbidden material")
        normalized_hashes: list[tuple[str, str]] = []
        for name, digest in sorted(evidence_hashes.items()):
            if not isinstance(name, str) or not _CATEGORY.fullmatch(name):
                raise SupervisorPolicyError("evidence hash name is invalid")
            normalized_hashes.append((name, _digest(digest, f"evidence hash {name}")))
        return cls(
            schema_version=1,
            incident_id=identity,
            run_id=run_id,
            source_commit=source_commit,
            exit_code=exit_code,
            exit_evidence_sha256=exit_evidence_sha256,
            failure_signature=failure_signature,
            category=category,
            excerpt=safe_excerpt,
            expected_identity=expected_identity,
            evidence_hashes=tuple(normalized_hashes),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "incident_id": self.incident_id,
            "run_id": self.run_id,
            "source_commit": self.source_commit,
            "exit_code": self.exit_code,
            "exit_evidence_sha256": self.exit_evidence_sha256,
            "failure_signature": self.failure_signature,
            "category": self.category,
            "excerpt": self.excerpt,
            "expected_identity": self.expected_identity.to_dict(),
            "evidence_hashes": dict(self.evidence_hashes),
        }

    @classmethod
    def from_dict(cls, payload: object) -> "Incident":
        parsed = _exact_keys(
            payload,
            {
                "schema_version",
                "incident_id",
                "run_id",
                "source_commit",
                "exit_code",
                "exit_evidence_sha256",
                "failure_signature",
                "category",
                "excerpt",
                "expected_identity",
                "evidence_hashes",
            },
            "incident",
        )
        if parsed["schema_version"] != 1:
            raise SupervisorPolicyError("incident schema version is unsupported")
        expected_identity = ExpectedIdentity.from_dict(parsed["expected_identity"])
        evidence_hashes = parsed["evidence_hashes"]
        if not isinstance(evidence_hashes, dict):
            raise SupervisorPolicyError("incident evidence hash schema is invalid")
        incident = cls.create(
            run_id=parsed["run_id"],
            source_commit=parsed["source_commit"],
            exit_code=parsed["exit_code"],
            exit_evidence_sha256=parsed["exit_evidence_sha256"],
            failure_signature=parsed["failure_signature"],
            category=parsed["category"],
            excerpt=parsed["excerpt"],
            expected_identity=expected_identity,
            evidence_hashes=evidence_hashes,
        )
        if parsed["incident_id"] != incident.incident_id:
            raise SupervisorPolicyError("incident content address is invalid")
        return incident


@dataclass(frozen=True)
class Classification:
    action: str
    reason: str


def classify_incident(incident: Incident) -> Classification:
    """Classify only explicitly allowlisted safe recovery categories."""

    if incident.category in _HARD_STOP_CATEGORIES:
        return Classification("hard_stop", f"fail-closed category: {incident.category}")
    if incident.category in _REPAIRABLE_CATEGORIES:
        return Classification("repairable", f"bounded infrastructure repair: {incident.category}")
    if incident.category in _RESUMABLE_CATEGORIES:
        return Classification("resume", "known replay-safe interruption")
    return Classification("hard_stop", f"unrecognized incident category: {incident.category}")


@dataclass(frozen=True)
class IncidentSnapshot:
    incident_id: str
    state: IncidentState
    repair_count: int
    history: tuple[str, ...]


def _canonical_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    content = _canonical_bytes(payload)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        os.chmod(temporary, 0o600)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)
    os.chmod(path, 0o600)


class IncidentStore:
    """Owner-only atomic store for one active content-addressed incident."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.incidents = self.root / "incidents"
        self.incidents.mkdir(exist_ok=True, mode=0o700)
        os.chmod(self.incidents, 0o700)
        if not self._active_path.is_file():
            _atomic_json(self._active_path, {"schema_version": 1, "incident_id": ""})

    @property
    def _active_path(self) -> Path:
        return self.root / "active.json"

    def _incident_dir(self, value: str) -> Path:
        if not _SHA256.fullmatch(value):
            raise SupervisorPolicyError("incident id is invalid")
        return self.incidents / value

    def _active_id(self) -> str:
        payload = _exact_keys(
            json.loads(self._active_path.read_text()),
            {"schema_version", "incident_id"},
            "active incident",
        )
        if payload["schema_version"] != 1:
            raise SupervisorPolicyError("active incident schema version is unsupported")
        value = payload["incident_id"]
        if value and (not isinstance(value, str) or not _SHA256.fullmatch(value)):
            raise SupervisorPolicyError("active incident id is invalid")
        return value

    def create(self, incident: Incident) -> IncidentSnapshot:
        incident_dir = self._incident_dir(incident.incident_id)
        incident_path = incident_dir / "incident.json"
        if incident_path.is_file():
            existing = Incident.from_dict(json.loads(incident_path.read_text()))
            if existing != incident:
                raise SupervisorPolicyError("persisted incident content drifted")
            return self.load(incident.incident_id)
        active = self._active_id()
        if active and active != incident.incident_id:
            raise SupervisorPolicyError(f"active incident already exists: {active}")
        incident_dir.mkdir(parents=True, mode=0o700)
        os.chmod(incident_dir, 0o700)
        _atomic_json(incident_path, incident.to_dict())
        snapshot = IncidentSnapshot(
            incident_id=incident.incident_id,
            state=IncidentState.OBSERVED,
            repair_count=0,
            history=(IncidentState.OBSERVED.value,),
        )
        self._write_snapshot(snapshot)
        _atomic_json(
            self._active_path,
            {"schema_version": 1, "incident_id": incident.incident_id},
        )
        return snapshot

    def _write_snapshot(self, snapshot: IncidentSnapshot) -> None:
        _atomic_json(
            self._incident_dir(snapshot.incident_id) / "state.json",
            {
                "schema_version": 1,
                "incident_id": snapshot.incident_id,
                "state": snapshot.state.value,
                "repair_count": snapshot.repair_count,
                "history": list(snapshot.history),
            },
        )

    def load_incident(self, value: str) -> Incident:
        path = self._incident_dir(value) / "incident.json"
        try:
            return Incident.from_dict(json.loads(path.read_text()))
        except (OSError, json.JSONDecodeError) as exc:
            raise SupervisorPolicyError(f"incident is unreadable: {exc}") from exc

    def load(self, value: str) -> IncidentSnapshot:
        path = self._incident_dir(value) / "state.json"
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise SupervisorPolicyError(f"incident state is unreadable: {exc}") from exc
        parsed = _exact_keys(
            payload,
            {"schema_version", "incident_id", "state", "repair_count", "history"},
            "incident state",
        )
        if parsed["schema_version"] != 1 or parsed["incident_id"] != value:
            raise SupervisorPolicyError("incident state identity is invalid")
        try:
            state = IncidentState(parsed["state"])
        except (TypeError, ValueError) as exc:
            raise SupervisorPolicyError("incident state value is invalid") from exc
        repair_count = parsed["repair_count"]
        history = parsed["history"]
        if (
            isinstance(repair_count, bool)
            or not isinstance(repair_count, int)
            or not 0 <= repair_count <= 3
            or not isinstance(history, list)
            or not history
            or any(not isinstance(item, str) for item in history)
            or history[-1] != state.value
        ):
            raise SupervisorPolicyError("incident state schema is invalid")
        return IncidentSnapshot(value, state, repair_count, tuple(history))

    def transition(self, value: str, target: IncidentState) -> IncidentSnapshot:
        if not isinstance(target, IncidentState):
            raise SupervisorPolicyError("transition target is invalid")
        current = self.load(value)
        if current.state is target:
            return current
        allowed = _ALLOWED_TRANSITIONS.get(current.state, frozenset())
        if target not in allowed and target is not IncidentState.HARD_STOP:
            raise SupervisorPolicyError(
                f"invalid incident transition: {current.state.value} -> {target.value}"
            )
        updated = IncidentSnapshot(
            value,
            target,
            current.repair_count,
            (*current.history, target.value),
        )
        self._write_snapshot(updated)
        if target in _TERMINAL_STATES:
            _atomic_json(self._active_path, {"schema_version": 1, "incident_id": ""})
        return updated

    def record_repair(self, value: str) -> IncidentSnapshot:
        current = self.load(value)
        if current.state in _TERMINAL_STATES:
            raise RepairBudgetError("repair budget is unavailable for a terminal incident")
        if current.repair_count >= 3:
            exhausted = IncidentSnapshot(
                value,
                IncidentState.REPAIR_BUDGET_EXHAUSTED,
                current.repair_count,
                (*current.history, IncidentState.REPAIR_BUDGET_EXHAUSTED.value),
            )
            self._write_snapshot(exhausted)
            _atomic_json(self._active_path, {"schema_version": 1, "incident_id": ""})
            raise RepairBudgetError("autonomous repair budget exhausted")
        if current.state not in {
            IncidentState.CLASSIFIED,
            IncidentState.REPAIRING,
            IncidentState.TESTED,
            IncidentState.DEPLOYED,
            IncidentState.CANARY_PASSED,
        }:
            raise SupervisorPolicyError(
                f"cannot record repair from state {current.state.value}"
            )
        history = current.history
        if current.state is not IncidentState.REPAIRING:
            history = (*history, IncidentState.REPAIRING.value)
        updated = IncidentSnapshot(
            value,
            IncidentState.REPAIRING,
            current.repair_count + 1,
            history,
        )
        self._write_snapshot(updated)
        return updated
