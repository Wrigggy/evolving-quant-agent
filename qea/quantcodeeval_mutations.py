"""Deterministic, single-component mutations for QuantCodeEval harnesses.

The operators in this module are intentionally task-agnostic.  They translate
one coarse, answer-free failure class into one bounded system-prompt guard.
They never inspect checker details, task IDs, reference implementations, or
benchmark answers.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping

from .worker_identity import WorkerIdentityError, hash_worker_directory


_OPERATOR_VERSION = "quantcodeeval-systemprompt-v5"
_SYSTEM_PROMPT = "systemprompt.md"
_AGENT_CONFIG = "agent.yaml"


class QuantCodeEvalMutationError(ValueError):
    """A requested mutation cannot produce a safe deterministic snapshot."""


class QuantCodeEvalFailureClass(str, Enum):
    """Answer-free failure classes accepted by the deterministic router."""

    ARTIFACT_INTERFACE = "artifact_interface"
    DATA_TEMPORAL_INTEGRITY = "data_temporal_integrity"
    QUANT_DEFINITION_ESTIMATION = "quant_definition_estimation"
    PORTFOLIO_EXECUTION = "portfolio_execution"
    RESOURCE_TERMINATION = "resource_termination"
    ISOLATED_TASK_SPECIFIC = "isolated_task_specific"
    UNKNOWN = "unknown"


class MutationDecision(str, Enum):
    ACT = "ACT"
    ABSTAIN = "ABSTAIN"


_PROMPT_GUIDANCE: Mapping[QuantCodeEvalFailureClass, tuple[str, ...]] = {
    QuantCodeEvalFailureClass.ARTIFACT_INTERFACE: (
        "Treat the public task's file and function interface as an executable contract before solving it.",
        "The only artifact you submit is `strategy.py`; task-provided inputs are not submission artifacts.",
        "Perform import, interface, and smoke validation in a fresh temporary directory rather than in the submission directory.",
        "Before finishing, remove only scratch files, generated reports, caches, logs, and other by-products you created; never delete or rewrite task-provided inputs.",
        "Finish only after confirming that `strategy.py` is a regular, importable file and that every publicly required top-level function is present.",
    ),
    QuantCodeEvalFailureClass.DATA_TEMPORAL_INTEGRITY: (
        "Write down the observation time, formation time, and realization time for every signal, weight, and return before coding.",
        "Sort and validate dates, make lag and window endpoints explicit, and ensure each decision uses only information available at its formation time.",
        "Test temporal causality with small synthetic data, a truncated-history rerun, and a future-data perturbation that must not change earlier outputs.",
        "Handle duplicates, missing values, and boundary rows deliberately instead of silently backfilling or leaking future observations.",
    ),
    QuantCodeEvalFailureClass.QUANT_DEFINITION_ESTIMATION: (
        "For arithmetic with decimal-valued returns, convert a paper constant written as `x%` to `x / 100`; preserve any separately requested reporting unit and every other task-specific rule.",
    ),
    QuantCodeEvalFailureClass.PORTFOLIO_EXECUTION: (
        "Specify the full timeline from observed signal to formed position to realized return before implementing the portfolio.",
        "Audit sign, lag, rebalance timing, normalization, funding convention, exposure, and any public constraints as separate decisions.",
        "Use a tiny deterministic price/return sequence to verify that weights apply to the intended future period and that accounting identities hold.",
        "Keep signal construction, portfolio weights, and realized returns separately inspectable rather than collapsing them into one opaque expression.",
    ),
    QuantCodeEvalFailureClass.RESOURCE_TERMINATION: (
        "Create a valid, importable `strategy.py` checkpoint within the first two tool calls; improve that file in place instead of postponing the deliverable.",
        "For arithmetic with decimal-valued returns, convert a paper constant written as `x%` to `x / 100`; preserve every separately requested reporting, timing, and interface rule.",
        "Retain the best valid checkpoint before further investigation and stop before the iteration limit with `/app/output/strategy.py` still importable.",
    ),
}

_ABSTAIN_REASONS: Mapping[QuantCodeEvalFailureClass, str] = {
    QuantCodeEvalFailureClass.ISOLATED_TASK_SPECIFIC: (
        "An isolated task-specific failure does not justify a reusable global harness mutation."
    ),
    QuantCodeEvalFailureClass.UNKNOWN: (
        "No supported failure mechanism was identified, so a deterministic mutation would be ungrounded."
    ),
}


@dataclass(frozen=True)
class QuantCodeEvalMutationRecord:
    """Content-addressed provenance for one ACT or ABSTAIN decision."""

    mutation_id: str
    decision: MutationDecision
    failure_class: QuantCodeEvalFailureClass
    iteration: int
    operator_version: str
    component: str | None
    parent_digest: str
    candidate_digest: str | None
    changed_paths: tuple[str, ...]
    prompt_block_sha256: str | None
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "mutation_id": self.mutation_id,
            "decision": self.decision.value,
            "failure_class": self.failure_class.value,
            "iteration": self.iteration,
            "operator_version": self.operator_version,
            "component": self.component,
            "parent_digest": self.parent_digest,
            "candidate_digest": self.candidate_digest,
            "changed_paths": list(self.changed_paths),
            "prompt_block_sha256": self.prompt_block_sha256,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class QuantCodeEvalMutationResult:
    """Materialized candidate, if any, and its immutable mutation record."""

    candidate_dir: Path | None
    record_path: Path
    record: QuantCodeEvalMutationRecord


def _normalize_failure_class(value: object) -> QuantCodeEvalFailureClass:
    raw = value.value if isinstance(value, Enum) else value
    if not isinstance(raw, str):
        raise QuantCodeEvalMutationError("failure_class must be text or an enum")
    try:
        return QuantCodeEvalFailureClass(raw.strip().casefold())
    except ValueError as exc:
        raise QuantCodeEvalMutationError(
            f"unsupported QuantCodeEval failure class: {raw!r}"
        ) from exc


def _validate_iteration(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise QuantCodeEvalMutationError("iteration must be a positive integer")
    return value


def _validate_worker_tree(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise QuantCodeEvalMutationError(
            f"parent worker must be one regular directory: {root}"
        )
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".git" in relative.parts or "__pycache__" in relative.parts:
            raise QuantCodeEvalMutationError(
                f"parent worker contains a non-source cache path: {relative}"
            )
        if path.is_symlink():
            raise QuantCodeEvalMutationError(
                f"parent worker contains a forbidden symlink: {relative}"
            )
        mode = path.stat().st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise QuantCodeEvalMutationError(
                f"parent worker contains a special filesystem entry: {relative}"
            )
    for required in (_AGENT_CONFIG, _SYSTEM_PROMPT):
        path = root / required
        if not path.is_file() or path.is_symlink():
            raise QuantCodeEvalMutationError(
                f"parent worker is missing regular {required}"
            )


def _tree_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file()
    }


def _changed_paths(before: Path, after: Path) -> tuple[str, ...]:
    left = _tree_files(before)
    right = _tree_files(after)
    return tuple(
        sorted(
            path
            for path in set(left) | set(right)
            if left.get(path) != right.get(path)
        )
    )


def _prompt_block(
    failure_class: QuantCodeEvalFailureClass,
    iteration: int,
) -> str:
    lines = [
        f"## QuantCodeEval harness guard ({failure_class.value}, iteration {iteration})",
        "",
    ]
    lines.extend(f"- {line}" for line in _PROMPT_GUIDANCE[failure_class])
    return "\n".join(lines) + "\n"


def _canonical_json(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _record_core(
    *,
    decision: MutationDecision,
    failure_class: QuantCodeEvalFailureClass,
    iteration: int,
    component: str | None,
    parent_digest: str,
    candidate_digest: str | None,
    changed_paths: tuple[str, ...],
    prompt_block_sha256: str | None,
    reason: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "decision": decision.value,
        "failure_class": failure_class.value,
        "iteration": iteration,
        "operator_version": _OPERATOR_VERSION,
        "component": component,
        "parent_digest": parent_digest,
        "candidate_digest": candidate_digest,
        "changed_paths": list(changed_paths),
        "prompt_block_sha256": prompt_block_sha256,
        "reason": reason,
    }


def _make_record(**core: object) -> QuantCodeEvalMutationRecord:
    mutation_id = hashlib.sha256(_canonical_json(core)).hexdigest()
    return QuantCodeEvalMutationRecord(
        mutation_id=mutation_id,
        decision=MutationDecision(str(core["decision"])),
        failure_class=QuantCodeEvalFailureClass(str(core["failure_class"])),
        iteration=int(core["iteration"]),
        operator_version=str(core["operator_version"]),
        component=core["component"] if isinstance(core["component"], str) else None,
        parent_digest=str(core["parent_digest"]),
        candidate_digest=(
            str(core["candidate_digest"])
            if isinstance(core["candidate_digest"], str)
            else None
        ),
        changed_paths=tuple(str(item) for item in core["changed_paths"]),
        prompt_block_sha256=(
            str(core["prompt_block_sha256"])
            if isinstance(core["prompt_block_sha256"], str)
            else None
        ),
        reason=str(core["reason"]),
    )


def _ensure_output_directory(path: Path) -> None:
    if path.is_symlink():
        raise QuantCodeEvalMutationError(
            f"mutation output directory must not be a symlink: {path}"
        )
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise QuantCodeEvalMutationError(
            f"mutation output path is not a regular directory: {path}"
        )


def _record_matches(destination: Path, payload: bytes) -> bool:
    return (
        not destination.is_symlink()
        and destination.is_file()
        and destination.read_bytes() == payload
    )


def _publish_record(record: QuantCodeEvalMutationRecord, records: Path) -> Path:
    _ensure_output_directory(records)
    destination = records / f"{record.mutation_id}.json"
    payload = _canonical_json(record.to_dict())
    if destination.exists() or destination.is_symlink():
        if not _record_matches(destination, payload):
            raise QuantCodeEvalMutationError(
                f"existing mutation record is not immutable: {destination}"
            )
        return destination
    descriptor, temporary_name = tempfile.mkstemp(
        dir=records,
        prefix=f".{record.mutation_id}.",
        suffix=".partial",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if not _record_matches(destination, payload):
                raise QuantCodeEvalMutationError(
                    f"concurrent mutation record differs: {destination}"
                )
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _resolve_output_root(parent: Path, output_root: str | Path | None) -> Path:
    if output_root is None:
        selected = parent.parent / f".{parent.name}.quantcodeeval-mutations"
    else:
        selected = Path(output_root).expanduser()
    resolved = selected.resolve()
    try:
        resolved.relative_to(parent)
    except ValueError:
        return resolved
    raise QuantCodeEvalMutationError("output_root must not be inside the parent worker")


def materialize_quantcodeeval_mutation(
    parent_worker_dir: str | Path,
    failure_class: object,
    iteration: int,
    *,
    output_root: str | Path | None = None,
) -> QuantCodeEvalMutationResult:
    """Materialize one deterministic system-prompt mutation or ABSTAIN.

    Repeating the same call is idempotent: it returns the same content-addressed
    candidate directory and byte-identical JSON record.  The candidate contains
    no provenance sidecar, so exactly one harness component changes.
    """

    parent = Path(parent_worker_dir).expanduser().resolve()
    normalized_failure = _normalize_failure_class(failure_class)
    normalized_iteration = _validate_iteration(iteration)
    _validate_worker_tree(parent)
    try:
        parent_digest = hash_worker_directory(parent)
    except WorkerIdentityError as exc:
        raise QuantCodeEvalMutationError(str(exc)) from exc
    destination_root = _resolve_output_root(parent, output_root)
    records_root = destination_root / "records"

    if normalized_failure in _ABSTAIN_REASONS:
        core = _record_core(
            decision=MutationDecision.ABSTAIN,
            failure_class=normalized_failure,
            iteration=normalized_iteration,
            component=None,
            parent_digest=parent_digest,
            candidate_digest=None,
            changed_paths=(),
            prompt_block_sha256=None,
            reason=_ABSTAIN_REASONS[normalized_failure],
        )
        record = _make_record(**core)
        return QuantCodeEvalMutationResult(
            candidate_dir=None,
            record_path=_publish_record(record, records_root),
            record=record,
        )

    block = _prompt_block(normalized_failure, normalized_iteration)
    block_digest = hashlib.sha256(block.encode("utf-8")).hexdigest()
    candidates_root = destination_root / "candidates"
    _ensure_output_directory(candidates_root)
    temporary_root = Path(
        tempfile.mkdtemp(dir=candidates_root, prefix=".candidate.partial-")
    )
    temporary_candidate = temporary_root / "snapshot"
    try:
        shutil.copytree(parent, temporary_candidate, copy_function=shutil.copy2)
        if hash_worker_directory(temporary_candidate) != parent_digest:
            raise QuantCodeEvalMutationError(
                "parent worker changed while the candidate was being copied"
            )
        prompt_path = temporary_candidate / _SYSTEM_PROMPT
        try:
            existing_prompt = prompt_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise QuantCodeEvalMutationError(
                "systemprompt.md must be UTF-8 text"
            ) from exc
        original_mode = stat.S_IMODE(prompt_path.stat().st_mode)
        os.chmod(prompt_path, original_mode | stat.S_IWUSR)
        prompt_path.write_text(
            existing_prompt.rstrip() + "\n\n" + block,
            encoding="utf-8",
        )
        os.chmod(prompt_path, original_mode)
        changed = _changed_paths(parent, temporary_candidate)
        if changed != (_SYSTEM_PROMPT,):
            raise QuantCodeEvalMutationError(
                f"operator escaped the single-component envelope: {changed}"
            )
        if (temporary_candidate / _AGENT_CONFIG).read_bytes() != (
            parent / _AGENT_CONFIG
        ).read_bytes():
            raise QuantCodeEvalMutationError("agent.yaml changed during mutation")
        candidate_digest = hash_worker_directory(temporary_candidate)
        candidate_dir = candidates_root / candidate_digest
        if candidate_dir.is_symlink():
            raise QuantCodeEvalMutationError(
                f"content-addressed candidate must not be a symlink: {candidate_dir}"
            )
        if candidate_dir.exists():
            if not candidate_dir.is_dir():
                raise QuantCodeEvalMutationError(
                    f"content-addressed candidate is not a directory: {candidate_dir}"
                )
            if hash_worker_directory(candidate_dir) != candidate_digest:
                raise QuantCodeEvalMutationError(
                    f"content-addressed candidate was modified: {candidate_dir}"
                )
            if _changed_paths(parent, candidate_dir) != (_SYSTEM_PROMPT,):
                raise QuantCodeEvalMutationError(
                    "existing candidate differs outside systemprompt.md"
                )
        else:
            try:
                os.replace(temporary_candidate, candidate_dir)
            except OSError as exc:
                if candidate_dir.is_symlink():
                    raise QuantCodeEvalMutationError(
                        "concurrent candidate publication created a symlink"
                    ) from exc
                if not candidate_dir.is_dir():
                    raise QuantCodeEvalMutationError(
                        f"cannot publish candidate snapshot: {exc}"
                    ) from exc
                if hash_worker_directory(candidate_dir) != candidate_digest:
                    raise QuantCodeEvalMutationError(
                        "concurrent candidate publication differs"
                    ) from exc
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)

    reason = (
        f"Applied the deterministic {normalized_failure.value} guard to the "
        "system prompt only."
    )
    core = _record_core(
        decision=MutationDecision.ACT,
        failure_class=normalized_failure,
        iteration=normalized_iteration,
        component="systemprompt",
        parent_digest=parent_digest,
        candidate_digest=candidate_digest,
        changed_paths=(_SYSTEM_PROMPT,),
        prompt_block_sha256=block_digest,
        reason=reason,
    )
    record = _make_record(**core)
    return QuantCodeEvalMutationResult(
        candidate_dir=candidate_dir,
        record_path=_publish_record(record, records_root),
        record=record,
    )


__all__ = [
    "MutationDecision",
    "QuantCodeEvalFailureClass",
    "QuantCodeEvalMutationError",
    "QuantCodeEvalMutationRecord",
    "QuantCodeEvalMutationResult",
    "materialize_quantcodeeval_mutation",
]
