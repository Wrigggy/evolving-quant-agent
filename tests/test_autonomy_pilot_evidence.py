from pathlib import Path

import pytest


def test_authorizes_public_text_evidence_tree(tmp_path):
    from qea.evolution_evidence import authorize_evidence_tree

    (tmp_path / "access_log.jsonl").write_text("")
    (tmp_path / "contract.json").write_text('{"stage":"A2"}\n')
    (tmp_path / "parents").mkdir()
    (tmp_path / "parents/source.md").write_text("public harness parent\n")

    record = authorize_evidence_tree(tmp_path)

    assert len(record.sha256) == 64
    assert record.members == ("contract.json", "parents/source.md")


@pytest.mark.parametrize("relative", ["tests/test.sh", ".env"])
def test_rejects_private_or_secret_like_evidence(tmp_path, relative):
    from qea.evolution_evidence import EvidenceContractError, authorize_evidence_tree

    (tmp_path / "access_log.jsonl").write_text("")
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("forbidden\n")

    with pytest.raises(EvidenceContractError):
        authorize_evidence_tree(tmp_path)


def test_rejects_symlinked_evidence_root(tmp_path):
    from qea.evolution_evidence import EvidenceContractError, authorize_evidence_tree

    actual = tmp_path / "actual"
    actual.mkdir()
    (actual / "access_log.jsonl").write_text("")
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)

    with pytest.raises(EvidenceContractError, match="must not be a symlink"):
        authorize_evidence_tree(alias)


def test_a3_selection_is_automatic_and_uses_flip_then_regression_order():
    from scripts.build_qfbench_autonomy_pilot_evidence import _automated_selection

    vectors = {
        "seed": {
            "overall": 0.4,
            "positive_flips": [],
            "negative_flips": [],
        },
        "iteration-01-candidate": {
            "overall": 0.35,
            "positive_flips": ["gain-a", "gain-b"],
            "negative_flips": ["loss-a"],
        },
        "iteration-02-candidate": {
            "overall": 0.45,
            "positive_flips": ["gain-c", "gain-d"],
            "negative_flips": ["loss-a", "loss-b"],
        },
    }

    selection = _automated_selection(vectors)

    assert selection["source_parent"] == "iteration-01-candidate"
    assert selection["backbone_parent"] == "iteration-02-candidate"
    assert selection["human_selected_parent"] is False
    assert selection["human_selected_tasks"] is False


def test_evolver_pilot_panel_comes_only_from_selected_flip_clusters():
    from scripts.run_qfbench_evolver_pilot import _selection_task_ids

    selection = {
        "positive_task_cluster": ["credit-migration-matrix", "evt-pot-var"],
        "negative_task_cluster": [
            "fomc-tone-event-study",
            "realized-vol-estimators",
        ],
    }

    assert _selection_task_ids(selection) == (
        "credit-migration-matrix",
        "evt-pot-var",
        "fomc-tone-event-study",
        "realized-vol-estimators",
    )
