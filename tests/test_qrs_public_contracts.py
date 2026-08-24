from __future__ import annotations

import json
from pathlib import Path

import pytest

from qea.qrs_public_contracts import (
    QRSPublicContractsError,
    materialize_qrs_public_contracts,
)
from scripts.build_qrs_public_contracts import main


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _method(tmp_path: Path) -> Path:
    path = tmp_path / "method.json"
    _write_json(
        path,
        {
            "development_panels": [
                {
                    "panel_index": 1,
                    "family": "alpha",
                    "task_ids": ["alpha-one", "alpha-two"],
                },
                {
                    "panel_index": 2,
                    "family": "beta",
                    "task_ids": ["beta-one"],
                },
            ],
            "sealed_main_tasks": [
                {"task_id": "sealed-one", "group": "a"},
                {"task_id": "sealed-two", "group": "b"},
            ],
        },
    )
    return path


def _source(tmp_path: Path) -> Path:
    root = tmp_path / "qfbench-public"
    instructions = {
        "alpha-one": "# Alpha one\n\nProduce café.csv.\n",
        "alpha-two": "# Alpha two\n\n- Read the public input.\n- Write output.json.\n",
        "beta-one": "# Beta one\n\n```text\npublic example\n```\n",
        "sealed-one": "Sealed public instruction one.\n",
        "sealed-two": "Sealed public instruction two.\n",
    }
    for task_id, instruction in instructions.items():
        task = root / "tasks" / task_id
        task.mkdir(parents=True)
        (task / "instruction.md").write_text(instruction, encoding="utf-8")
    return root


def _materialize(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    destination = tmp_path / "contracts"
    report = materialize_qrs_public_contracts(
        qfbench_public_source_root=_source(tmp_path),
        method_plan_path=_method(tmp_path),
        destination=destination,
    )
    return destination, report


def test_materializes_direct_development_contract_layout_only(tmp_path: Path) -> None:
    destination, report = _materialize(tmp_path)

    assert report["development_task_count"] == 3
    assert report["sealed_task_count"] == 2
    assert report["resumed_identical"] is False
    expected_tasks = {"alpha-one", "alpha-two", "beta-one"}
    observed_tasks = {path.name for path in destination.iterdir() if path.is_dir()}
    assert observed_tasks == expected_tasks
    assert not (destination / "sealed-one").exists()
    assert not (destination / "sealed-two").exists()
    for task_id in expected_tasks:
        task = destination / task_id
        assert {path.name for path in task.iterdir()} == {
            "instruction.md",
            "clauses.json",
        }
        clauses = json.loads((task / "clauses.json").read_text(encoding="utf-8"))
        assert clauses["task_id"] == task_id
        assert clauses["clause_count"] == len(clauses["clauses"])
        assert clauses["clauses"]
        assert set(clauses) == {
            "schema_version",
            "record_kind",
            "task_id",
            "source",
            "clause_count",
            "clauses",
        }
        assert set(clauses["clauses"][0]) == {
            "clause_id",
            "ordinal",
            "kind",
            "heading_path",
            "start_line",
            "end_line",
            "text",
        }
    assert (destination / "alpha-one/instruction.md").read_text(
        encoding="utf-8"
    ) == "# Alpha one\n\nProduce café.csv.\n"
    manifest = json.loads(
        (destination / "QRS-PUBLIC-CONTRACTS.json").read_text(encoding="utf-8")
    )
    assert manifest["development_only"] is True
    assert manifest["sealed_materialized"] is False
    assert "sealed_task_ids" not in manifest


def test_identical_destination_resumes_and_different_destination_refuses(
    tmp_path: Path,
) -> None:
    destination, _ = _materialize(tmp_path)
    resumed = materialize_qrs_public_contracts(
        qfbench_public_source_root=tmp_path / "qfbench-public",
        method_plan_path=tmp_path / "method.json",
        destination=destination,
    )
    assert resumed["resumed_identical"] is True

    (destination / "alpha-one/instruction.md").write_text(
        "changed\n", encoding="utf-8"
    )
    with pytest.raises(QRSPublicContractsError, match="differs"):
        materialize_qrs_public_contracts(
            qfbench_public_source_root=tmp_path / "qfbench-public",
            method_plan_path=tmp_path / "method.json",
            destination=destination,
        )


def test_extra_existing_member_is_not_an_identical_resume(tmp_path: Path) -> None:
    destination, _ = _materialize(tmp_path)
    (destination / "extra.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(QRSPublicContractsError, match="differs"):
        materialize_qrs_public_contracts(
            qfbench_public_source_root=tmp_path / "qfbench-public",
            method_plan_path=tmp_path / "method.json",
            destination=destination,
        )

    (destination / "extra.json").unlink()
    (destination / "extra-empty-directory").mkdir()
    with pytest.raises(QRSPublicContractsError, match="differs"):
        materialize_qrs_public_contracts(
            qfbench_public_source_root=tmp_path / "qfbench-public",
            method_plan_path=tmp_path / "method.json",
            destination=destination,
        )


def test_rejects_development_sealed_overlap(tmp_path: Path) -> None:
    method = _method(tmp_path)
    value = json.loads(method.read_text(encoding="utf-8"))
    value["sealed_main_tasks"].append({"task_id": "alpha-one", "group": "a"})
    _write_json(method, value)

    with pytest.raises(QRSPublicContractsError, match="overlap"):
        materialize_qrs_public_contracts(
            qfbench_public_source_root=_source(tmp_path),
            method_plan_path=method,
            destination=tmp_path / "contracts",
        )


def test_rejects_non_utf8_or_symbolic_instruction(tmp_path: Path) -> None:
    source = _source(tmp_path)
    method = _method(tmp_path)
    instruction = source / "tasks/alpha-one/instruction.md"
    instruction.write_bytes(b"\xff\xfe")

    with pytest.raises(QRSPublicContractsError, match="UTF-8"):
        materialize_qrs_public_contracts(
            qfbench_public_source_root=source,
            method_plan_path=method,
            destination=tmp_path / "contracts-a",
        )

    instruction.unlink()
    external = tmp_path / "external.md"
    external.write_text("public\n", encoding="utf-8")
    instruction.symlink_to(external)
    with pytest.raises(QRSPublicContractsError, match="regular file"):
        materialize_qrs_public_contracts(
            qfbench_public_source_root=source,
            method_plan_path=method,
            destination=tmp_path / "contracts-b",
        )


def test_rejects_ambiguous_or_inexact_task_roots(tmp_path: Path) -> None:
    source = _source(tmp_path)
    method = _method(tmp_path)
    for task_id in ("alpha-one", "alpha-two", "beta-one"):
        direct = source / task_id
        direct.mkdir()
        (direct / "instruction.md").write_text("public\n", encoding="utf-8")

    with pytest.raises(QRSPublicContractsError, match="exactly one"):
        materialize_qrs_public_contracts(
            qfbench_public_source_root=source,
            method_plan_path=method,
            destination=tmp_path / "contracts",
        )


def test_cli_materializes_without_external_execution(tmp_path: Path, capsys) -> None:
    source = _source(tmp_path)
    method = _method(tmp_path)
    destination = tmp_path / "contracts"

    code = main(
        [
            "--qfbench-public-source-root",
            str(source),
            "--method-plan",
            str(method),
            "--destination",
            str(destination),
        ]
    )

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "complete"
    assert report["destination"] == str(destination.resolve())
