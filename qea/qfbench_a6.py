"""Deterministic validation for an expanded A6 train-only discovery panel."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence


_SHA256_FIELDS = (
    "protocol_manifest_sha256",
    "rootless_config_sha256",
    "image_set_manifest_sha256",
    "public_task_role_manifest_sha256",
    "trusted_task_role_manifest_sha256",
    "scheduler_identity_sha256",
    "provider_route_identity_sha256",
    "a6_source_release_sha256",
)
_LAUNCH_IDENTITY_FIELD = "materialized_launch_identity_sha256"
_PRELAUNCH_FIELDS = (
    "protocol_manifest_sha256",
    "rootless_config_sha256",
    "image_set_manifest_sha256",
    "public_task_role_manifest_sha256",
    "trusted_task_role_manifest_sha256",
    "scheduler_epoch",
    "scheduler_identity_sha256",
    "provider_route_identity_sha256",
    "a6_source_release_sha256",
    _LAUNCH_IDENTITY_FIELD,
)
_EFFECTIVE_IDENTITY_FIELDS = tuple(
    field
    for field in _PRELAUNCH_FIELDS
    if field not in {"protocol_manifest_sha256", _LAUNCH_IDENTITY_FIELD}
)


class A6PanelError(ValueError):
    """The frozen A6 panel is inconsistent with its pinned baseline facts."""


def materialized_a6_launch_identity_digest(
    record: Mapping[str, object],
) -> str:
    """Hash the canonical materialized launch fields, excluding its own digest."""

    payload = {
        "schema_version": 1,
        "stage": "A6",
        **{field: record.get(field) for field in _SHA256_FIELDS},
        "scheduler_epoch": record.get("scheduler_epoch"),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_a6_prelaunch_identity(
    *,
    frozen: Mapping[str, object],
    freeze_record: Mapping[str, object] | None,
    protocol_manifest_path: str | Path,
    effective_identity: Mapping[str, object] | None,
) -> dict[str, object]:
    """Fail closed until every effective A6 launch identity is materialized.

    The protocol-manifest digest is intentionally stored in a separate record;
    embedding it in the protocol manifest would create a self-referential hash.
    The materialized launch digest binds that protocol hash to the effective
    runtime, image/role manifests, scheduler, provider route, and source release.
    """

    if frozen.get("stage") != "A6":
        raise A6PanelError("A6 protocol manifest has the wrong stage")
    spec = frozen.get("prelaunch_identity_freeze")
    if not isinstance(spec, Mapping) or spec.get("schema_version") != 1:
        raise A6PanelError("A6 prelaunch identity freeze schema is unavailable")
    if spec.get("required_before_any_a6_model_call") is not True:
        raise A6PanelError("A6 prelaunch identity freeze is not fail-closed")
    declared_fields = spec.get("required_record_fields")
    if not isinstance(declared_fields, list) or tuple(declared_fields) != _PRELAUNCH_FIELDS:
        raise A6PanelError("A6 prelaunch required fields differ from the schema")
    if freeze_record is None:
        raise A6PanelError("A6 prelaunch identity record is not materialized")
    record = dict(freeze_record)
    if record.get("schema_version") != 1 or record.get("stage") != "A6":
        raise A6PanelError("A6 prelaunch identity record schema is invalid")
    if record.get("status") != "materialized":
        raise A6PanelError("A6 prelaunch identity record is not materialized")
    missing = [field for field in _PRELAUNCH_FIELDS if field not in record]
    if missing:
        raise A6PanelError(
            "A6 prelaunch identity record is missing fields: " + ", ".join(missing)
        )
    for field in (*_SHA256_FIELDS, _LAUNCH_IDENTITY_FIELD):
        value = record.get(field)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise A6PanelError(f"A6 prelaunch field {field} is not lowercase SHA-256")
    scheduler_epoch = record.get("scheduler_epoch")
    if not isinstance(scheduler_epoch, str) or not scheduler_epoch.strip():
        raise A6PanelError("A6 prelaunch scheduler_epoch is invalid")
    manifest_path = Path(protocol_manifest_path)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise A6PanelError("A6 protocol manifest path is unavailable")
    observed_protocol_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if record["protocol_manifest_sha256"] != observed_protocol_digest:
        raise A6PanelError("A6 protocol manifest digest differs from the freeze record")
    if not isinstance(effective_identity, Mapping):
        raise A6PanelError("A6 effective launch identity is unavailable")
    missing_effective = [
        field
        for field in _EFFECTIVE_IDENTITY_FIELDS
        if field not in effective_identity
    ]
    if missing_effective:
        raise A6PanelError(
            "A6 effective launch identity is missing fields: "
            + ", ".join(missing_effective)
        )
    drifted = [
        field
        for field in _EFFECTIVE_IDENTITY_FIELDS
        if effective_identity.get(field) != record.get(field)
    ]
    if drifted:
        raise A6PanelError(
            "A6 effective launch identity differs from the freeze record: "
            + ", ".join(drifted)
        )
    expected_launch_digest = materialized_a6_launch_identity_digest(record)
    if record[_LAUNCH_IDENTITY_FIELD] != expected_launch_digest:
        raise A6PanelError("A6 materialized launch identity digest is inconsistent")
    return record


def validate_a6_evidence_contract(
    *,
    frozen: Mapping[str, object],
    contract: Mapping[str, object],
    arm: str,
    prelaunch_identity: Mapping[str, object],
    identity_record_sha256: str,
    public_contract_source: Mapping[str, object],
) -> dict[str, object]:
    """Bind the model-visible A6 evidence contract to the frozen protocol."""

    if frozen.get("stage") != "A6":
        raise A6PanelError("A6 protocol manifest has the wrong stage")
    normalized_arm = arm.strip().upper().replace("_", "-")
    if normalized_arm not in {"A6-R", "A6-E", "A6-EC"}:
        raise A6PanelError("A6 evidence arm is invalid")
    design = frozen.get("discovery_design")
    if not isinstance(design, Mapping):
        raise A6PanelError("A6 discovery design is unavailable")
    raw_arms = design.get("arms")
    if not isinstance(raw_arms, Mapping):
        raise A6PanelError("A6 discovery arm contracts are unavailable")
    arm_spec = raw_arms.get(normalized_arm)
    if not isinstance(arm_spec, Mapping):
        raise A6PanelError(f"A6 discovery arm {normalized_arm} is unavailable")
    panel = frozen.get("panel")
    if not isinstance(panel, Mapping):
        raise A6PanelError("A6 panel is unavailable")

    def role_ids(key: str) -> list[str]:
        raw = panel.get(key)
        if not isinstance(raw, list):
            raise A6PanelError(f"A6 panel {key} is invalid")
        values: list[str] = []
        for item in raw:
            task_id = item.get("task_id") if isinstance(item, Mapping) else None
            if not isinstance(task_id, str) or not task_id:
                raise A6PanelError(f"A6 panel {key} has an invalid task")
            values.append(task_id)
        return values

    targets = role_ids("targets")
    protections = role_ids("protections")
    sentinel_key = (
        "coverage_sentinels"
        if "coverage_sentinels" in panel
        else "sentinels"
    )
    sentinels = role_ids(sentinel_key)
    task_ids = panel.get("task_ids")
    if task_ids != targets + protections + sentinels:
        raise A6PanelError("A6 panel task_ids differ from ordered roles")
    if (
        prelaunch_identity.get("schema_version") != 1
        or prelaunch_identity.get("stage") != "A6"
        or prelaunch_identity.get("status") != "materialized"
    ):
        raise A6PanelError("A6 evidence contract has no materialized seed identity")
    seed_launch_identity = prelaunch_identity.get(
        "materialized_launch_identity_sha256"
    )
    for label, value in (
        ("seed launch identity", seed_launch_identity),
        ("seed identity record", identity_record_sha256),
    ):
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise A6PanelError(f"A6 {label} is not lowercase SHA-256")
    exposes_contracts = arm_spec.get("public_contract_index")
    if not isinstance(exposes_contracts, bool):
        raise A6PanelError("A6 arm public-contract exposure is invalid")
    expected_public_source_keys = {
        "benchmark_commit",
        "instruction_member_count",
        "instruction_members_sha256",
        "members",
        "protocol",
        "public_task_role_manifest_sha256",
        "schema_version",
        "task_ids",
    }
    if (
        set(public_contract_source) != expected_public_source_keys
        or public_contract_source.get("schema_version") != 1
        or public_contract_source.get("protocol")
        != "pinned_public_role_instructions_v1"
        or public_contract_source.get("benchmark_commit")
        != frozen.get("benchmark_commit")
        or public_contract_source.get("task_ids") != task_ids
    ):
        raise A6PanelError(
            "A6 public-contract source identity differs from the frozen panel"
        )
    source_members = public_contract_source.get("members")
    if (
        public_contract_source.get("instruction_member_count") != len(task_ids)
        or not isinstance(source_members, list)
        or len(source_members) != len(task_ids)
    ):
        raise A6PanelError("A6 public-contract source members are incomplete")
    for task_id, member in zip(task_ids, source_members):
        expected_source_path = f"tasks/{task_id}/instruction.md"
        if (
            not isinstance(member, Mapping)
            or set(member) != {"sha256", "size_bytes", "source_path", "task_id"}
            or member.get("task_id") != task_id
            or member.get("source_path") != expected_source_path
            or not isinstance(member.get("size_bytes"), int)
            or isinstance(member.get("size_bytes"), bool)
            or member.get("size_bytes") < 0
        ):
            raise A6PanelError(
                f"A6 public-contract source member differs: {task_id!r}"
            )
        member_sha256 = member.get("sha256")
        if (
            not isinstance(member_sha256, str)
            or len(member_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in member_sha256
            )
        ):
            raise A6PanelError(
                f"A6 public-contract source member digest is invalid: {task_id!r}"
            )
    public_role_manifest_sha256 = public_contract_source.get(
        "public_task_role_manifest_sha256"
    )
    public_source_members_sha256 = public_contract_source.get(
        "instruction_members_sha256"
    )
    for label, value in (
        ("public task role manifest", public_role_manifest_sha256),
        ("public contract source members", public_source_members_sha256),
    ):
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise A6PanelError(f"A6 {label} identity is not lowercase SHA-256")
    expected = {
        "schema_version": 1,
        "stage": "A6",
        "purpose": "failure-type induction, probe, and decision canary",
        "mode": "indexed_full_trace",
        "train_task_ids": task_ids,
        "target_task_ids": targets,
        "protection_task_ids": protections,
        "sentinel_task_ids": sentinels,
        "held_out_feedback": False,
        "private_evaluator_feedback": False,
        "official_solution": False,
        "component_hint": None,
        "root_cause_hint": None,
        "evolver_instruction": design.get("evolver_instruction"),
        "contract_arm": normalized_arm,
        "decision_protocol": arm_spec.get("decision_protocol"),
        "success_counterfactual": arm_spec.get("success_counterfactual"),
        "probe_policy": arm_spec.get("probe_policy"),
        "max_components": design.get("max_components"),
        "public_contract_evidence": exposes_contracts,
        "public_contract_index": (
            "contracts/index.json" if exposes_contracts else None
        ),
        "public_task_role_manifest_sha256": (
            public_role_manifest_sha256 if exposes_contracts else None
        ),
        "public_contract_source_members_sha256": (
            public_source_members_sha256 if exposes_contracts else None
        ),
        "semantic_comparison": arm_spec.get("semantic_comparison"),
        "evaluator_feedback_tier": design.get("evaluator_feedback_tier"),
        "feedback_manifest_digest": design.get("feedback_manifest_digest"),
        "seed_launch_identity_sha256": seed_launch_identity,
        "seed_identity_record_sha256": identity_record_sha256,
    }
    missing_manifest_values = sorted(
        key
        for key in (
            "evolver_instruction",
            "decision_protocol",
            "success_counterfactual",
            "probe_policy",
            "max_components",
            "semantic_comparison",
            "evaluator_feedback_tier",
        )
        if expected[key] is None
    )
    if missing_manifest_values:
        raise A6PanelError(
            "A6 evidence contract fields are not frozen: "
            + ", ".join(missing_manifest_values)
        )
    drifted = sorted(
        key
        for key, value in expected.items()
        if key not in contract or contract.get(key) != value
    )
    unexpected = sorted(set(contract) - set(expected))
    if drifted or unexpected:
        details = []
        if drifted:
            details.append("drifted=" + ",".join(drifted))
        if unexpected:
            details.append("unexpected=" + ",".join(unexpected))
        raise A6PanelError(
            "A6 model-visible evidence contract differs from the frozen protocol: "
            + "; ".join(details)
        )
    return dict(contract)


@dataclass(frozen=True)
class A6TaskStats:
    """Five-repeat answer-free facts for one explicitly frozen A6 task."""

    task_id: str
    domain: str
    role: str
    rewards: tuple[float, ...]
    tests_passed: tuple[int, ...]
    tests_failed: tuple[int, ...]
    verifier_exit_codes: tuple[int, ...]
    min_pass_fraction: float
    mean_pass_fraction: float
    min_test_count: int

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for name in (
            "rewards",
            "tests_passed",
            "tests_failed",
            "verifier_exit_codes",
        ):
            payload[name] = list(payload[name])
        return payload


@dataclass(frozen=True)
class A6Panel:
    """A6 failure targets, strict protections, and volatile sentinels."""

    targets: tuple[A6TaskStats, ...]
    protections: tuple[A6TaskStats, ...]
    sentinels: tuple[A6TaskStats, ...]

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(
            item.task_id
            for item in self.targets + self.protections + self.sentinels
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "targets": [item.as_dict() for item in self.targets],
            "protections": [item.as_dict() for item in self.protections],
            "sentinels": [item.as_dict() for item in self.sentinels],
            "task_ids": list(self.task_ids),
        }


def _object(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise A6PanelError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise A6PanelError(f"{label} must be an array")
    return value


def _train_tasks(evolution_manifest: Mapping[str, object]) -> dict[str, str]:
    evolution = _object(evolution_manifest.get("evolution"), label="evolution")
    train = _sequence(evolution.get("train"), label="evolution.train")
    tasks: dict[str, str] = {}
    for index, raw in enumerate(train):
        item = _object(raw, label=f"evolution.train[{index}]")
        task_id = item.get("task_id")
        domain = item.get("domain")
        if not isinstance(task_id, str) or not task_id:
            raise A6PanelError("train task has no task_id")
        if not isinstance(domain, str) or not domain:
            raise A6PanelError(f"train task {task_id!r} has no domain")
        if task_id in tasks:
            raise A6PanelError(f"duplicate train task: {task_id}")
        tasks[task_id] = domain
    if not tasks:
        raise A6PanelError("train split is empty")
    return tasks


def _baseline_rows(
    baseline_result: Mapping[str, object],
    selected_ids: set[str],
) -> dict[str, list[Mapping[str, object]]]:
    if baseline_result.get("complete") is not True:
        raise A6PanelError("baseline result is not complete")
    repetitions = _sequence(
        baseline_result.get("repetitions"), label="baseline repetitions"
    )
    if len(repetitions) != 5:
        raise A6PanelError("A6 requires the completed five-repetition baseline")
    rows = {task_id: [] for task_id in selected_ids}
    for repetition_index, raw in enumerate(repetitions, start=1):
        repetition = _object(raw, label=f"repetition {repetition_index}")
        primary = _object(
            repetition.get("primary"), label=f"repetition {repetition_index} primary"
        )
        scores = _sequence(
            primary.get("scores"), label=f"repetition {repetition_index} scores"
        )
        seen: set[str] = set()
        for score_index, score_raw in enumerate(scores):
            score = _object(
                score_raw,
                label=f"repetition {repetition_index} score {score_index}",
            )
            task_id = score.get("task_id")
            if task_id not in selected_ids:
                continue
            task_id = str(task_id)
            if task_id in seen:
                raise A6PanelError(
                    f"duplicate primary score for {task_id} in repetition "
                    f"{repetition_index}"
                )
            seen.add(task_id)
            rows[task_id].append(score)
        missing = sorted(selected_ids - seen)
        if missing:
            raise A6PanelError(
                f"repetition {repetition_index} is missing A6 scores: {missing}"
            )
    return rows


def _stats(
    *,
    task_id: str,
    domain: str,
    role: str,
    rows: Sequence[Mapping[str, object]],
) -> A6TaskStats:
    rewards: list[float] = []
    passed: list[int] = []
    failed: list[int] = []
    exits: list[int] = []
    for row in rows:
        reward = row.get("reward")
        good = row.get("tests_passed")
        bad = row.get("tests_failed")
        exit_code = row.get("verifier_exit_code")
        if (
            isinstance(reward, bool)
            or not isinstance(reward, (int, float))
            or isinstance(good, bool)
            or not isinstance(good, int)
            or isinstance(bad, bool)
            or not isinstance(bad, int)
            or good < 0
            or bad < 0
            or good + bad <= 0
            or isinstance(exit_code, bool)
            or not isinstance(exit_code, int)
        ):
            raise A6PanelError(f"task {task_id!r} has invalid baseline evidence")
        rewards.append(float(reward))
        passed.append(good)
        failed.append(bad)
        exits.append(exit_code)
    fractions = [good / (good + bad) for good, bad in zip(passed, failed)]
    return A6TaskStats(
        task_id=task_id,
        domain=domain,
        role=role,
        rewards=tuple(rewards),
        tests_passed=tuple(passed),
        tests_failed=tuple(failed),
        verifier_exit_codes=tuple(exits),
        min_pass_fraction=min(fractions),
        mean_pass_fraction=statistics.fmean(fractions),
        min_test_count=min(good + bad for good, bad in zip(passed, failed)),
    )


def _frozen_ids(
    panel: Mapping[str, object], role_plural: str
) -> tuple[tuple[str, Mapping[str, object]], ...]:
    manifest_key = (
        "coverage_sentinels"
        if role_plural == "sentinels" and "coverage_sentinels" in panel
        else role_plural
    )
    raw_items = _sequence(
        panel.get(manifest_key, []), label=f"panel.{manifest_key}"
    )
    items: list[tuple[str, Mapping[str, object]]] = []
    for index, raw in enumerate(raw_items):
        item = _object(raw, label=f"panel.{manifest_key}[{index}]")
        task_id = item.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise A6PanelError(f"panel.{manifest_key}[{index}] has no task_id")
        items.append((task_id, item))
    return tuple(items)


def validate_frozen_a6_panel(
    *,
    frozen: Mapping[str, object],
    baseline_result: Mapping[str, object],
    evolution_manifest: Mapping[str, object],
) -> A6Panel:
    """Validate all A6 roles against the same complete train-only baseline.

    Sentinels are deliberately distinct from protections: they must be volatile
    across the five repeats and never enter the strict protection gate.
    """

    train = _train_tasks(evolution_manifest)
    role_specs = (
        ("targets", "target"),
        ("protections", "protection"),
        ("sentinels", "sentinel"),
    )
    frozen_by_role = {
        plural: _frozen_ids(frozen, plural) for plural, _ in role_specs
    }
    expected_role_counts = {
        "repeat_failure_target": len(frozen_by_role["targets"]),
        "strict_protection": len(frozen_by_role["protections"]),
        "volatile_coverage_sentinel": len(frozen_by_role["sentinels"]),
    }
    all_ids = [
        task_id
        for plural, _ in role_specs
        for task_id, _ in frozen_by_role[plural]
    ]
    if not all_ids or len(all_ids) != len(set(all_ids)):
        raise A6PanelError("A6 task roles must be non-empty and disjoint")
    declared_task_count = frozen.get("task_count")
    if declared_task_count is not None and declared_task_count != len(all_ids):
        raise A6PanelError("A6 panel task_count differs from its role members")
    declared_role_counts = frozen.get("role_counts")
    if (
        declared_role_counts is not None
        and declared_role_counts != expected_role_counts
    ):
        raise A6PanelError("A6 panel role_counts differ from its role members")
    if not set(all_ids) <= set(train):
        raise A6PanelError("A6 panel contains a non-train task")
    frozen_task_ids = _sequence(frozen.get("task_ids"), label="panel.task_ids")
    if list(frozen_task_ids) != all_ids:
        raise A6PanelError(
            "A6 panel task_ids must preserve target/protection/sentinel order"
        )

    rows = _baseline_rows(baseline_result, set(all_ids))
    derived: dict[str, tuple[A6TaskStats, ...]] = {}
    role_aliases = {
        "target": {"target", "repeat_failure_target"},
        "protection": {"protection", "strict_protection"},
        "sentinel": {"sentinel", "volatile_coverage_sentinel"},
    }
    measured_fields = {
        "task_id",
        "domain",
        "rewards",
        "tests_passed",
        "tests_failed",
        "verifier_exit_codes",
        "min_pass_fraction",
        "mean_pass_fraction",
        "min_test_count",
    }
    metadata_fields = {"role", "reward_kind", "selection_reason", "strict_protection"}
    fully_frozen = any(
        key in frozen for key in ("task_count", "role_counts", "domain_counts")
    )
    for plural, role in role_specs:
        values: list[A6TaskStats] = []
        for task_id, frozen_item in frozen_by_role[plural]:
            item = _stats(
                task_id=task_id,
                domain=train[task_id],
                role=role,
                rows=rows[task_id],
            )
            if any(code != 0 for code in item.verifier_exit_codes):
                raise A6PanelError(f"A6 {role} {task_id!r} has verifier failures")
            if role == "target" and any(reward != 0.0 for reward in item.rewards):
                raise A6PanelError(f"A6 target {task_id!r} is not a clean 0/5 failure")
            if role == "protection" and any(
                reward != 1.0 for reward in item.rewards
            ):
                raise A6PanelError(
                    f"A6 protection {task_id!r} is not a strict 5/5 success"
                )
            if role == "sentinel" and not (
                any(reward == 0.0 for reward in item.rewards)
                and any(reward == 1.0 for reward in item.rewards)
            ):
                raise A6PanelError(
                    f"A6 sentinel {task_id!r} is not volatile across repetitions"
                )
            observed = item.as_dict()
            if fully_frozen:
                missing_fields = measured_fields - set(frozen_item)
                if missing_fields:
                    raise A6PanelError(
                        f"frozen A6 facts are incomplete for {task_id!r}: "
                        + ", ".join(sorted(missing_fields))
                    )
            for key, value in frozen_item.items():
                if key == "role":
                    if value not in role_aliases[role]:
                        raise A6PanelError(
                            f"frozen A6 role differs for {task_id!r}"
                        )
                    continue
                if key == "strict_protection":
                    if role != "sentinel" or value is not False:
                        raise A6PanelError(
                            f"frozen A6 strict_protection flag differs for {task_id!r}"
                        )
                    continue
                if key in metadata_fields:
                    continue
                if key not in measured_fields:
                    raise A6PanelError(
                        f"unknown frozen A6 field for {task_id!r}: {key!r}"
                    )
                differs = observed[key] != value
                if isinstance(observed[key], float) and isinstance(value, float):
                    differs = not math.isclose(
                        observed[key], value, rel_tol=0.0, abs_tol=1e-12
                    )
                if differs:
                    raise A6PanelError(
                        f"frozen A6 facts differ for {task_id!r} field {key!r}"
                    )
            values.append(item)
        derived[plural] = tuple(values)
    declared_domain_counts = frozen.get("domain_counts")
    observed_domain_counts = {
        domain: sum(train[task_id] == domain for task_id in all_ids)
        for domain in sorted({train[task_id] for task_id in all_ids})
    }
    if (
        declared_domain_counts is not None
        and declared_domain_counts != observed_domain_counts
    ):
        raise A6PanelError("A6 panel domain_counts differ from its task domains")
    return A6Panel(
        targets=derived["targets"],
        protections=derived["protections"],
        sentinels=derived["sentinels"],
    )


__all__ = [
    "A6Panel",
    "A6PanelError",
    "A6TaskStats",
    "materialized_a6_launch_identity_digest",
    "validate_a6_evidence_contract",
    "validate_a6_prelaunch_identity",
    "validate_frozen_a6_panel",
]
