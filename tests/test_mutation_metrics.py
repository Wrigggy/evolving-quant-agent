from qea.mutation_metrics import measure_mutation


def test_mutation_metrics_measure_size_roles_surfaces_and_ast_symbols(tmp_path):
    before = tmp_path / "before"
    after = tmp_path / "after"
    for root in (before, after):
        (root / "tools").mkdir(parents=True)
        (root / "tool_descriptions").mkdir()
    (before / "systemprompt.md").write_text("Solve.\n")
    (after / "systemprompt.md").write_text("Solve and validate.\n")
    (before / "tools/check.py").write_text(
        "CONST = 1\n\ndef check(value):\n    return value\n"
    )
    (after / "tools/check.py").write_text(
        "CONST = 2\n\n"
        "def check(value):\n    return bool(value)\n\n"
        "def inspect(value):\n    return value\n"
    )
    (after / "tool_descriptions/check.tool.yaml").write_text(
        "type: tool\nname: check\n"
    )

    measured = measure_mutation(
        before_root=before,
        after_root=after,
        declared_roles=("systemprompt", "tool_descriptions", "tools"),
    )

    assert measured["measurement_only"] is True
    assert measured["mutation_envelope_changed"] is False
    assert measured["changed_file_count"] == 3
    assert measured["added_file_count"] == 1
    assert measured["modified_file_count"] == 2
    assert measured["component_roles"] == [
        "systemprompt",
        "tool_descriptions",
        "tools",
    ]
    assert measured["surface_file_counts"] == {
        "configuration": 0,
        "executable_code": 1,
        "other": 0,
        "prompt_or_description": 2,
    }
    assert measured["touches_executable_code"] is True
    assert measured["declared_roles_match_actual"] is True
    python = measured["python_top_level_symbols"][0]
    assert python["added_symbols"] == ["inspect"]
    assert python["changed_symbols"] == ["CONST", "check"]
    assert measured["added_lines"] > 0
    assert measured["deleted_lines"] > 0
    assert measured["added_bytes"] > measured["deleted_bytes"]


def test_mutation_metrics_exposes_declared_role_mismatch_without_enforcement(
    tmp_path,
):
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (before / "systemprompt.md").write_text("before\n")
    (after / "systemprompt.md").write_text("after\n")

    measured = measure_mutation(
        before_root=before,
        after_root=after,
        declared_roles=("tools",),
    )

    assert measured["declared_roles_match_actual"] is False
    assert measured["component_roles"] == ["systemprompt"]
    assert measured["mutation_envelope_changed"] is False


def test_mutation_metrics_counts_python_inside_skill_as_executable(tmp_path):
    before = tmp_path / "before"
    after = tmp_path / "after"
    (before / "skills/example").mkdir(parents=True)
    (after / "skills/example").mkdir(parents=True)
    (before / "skills/example/helper.py").write_text("VALUE = 1\n")
    (after / "skills/example/helper.py").write_text("VALUE = 2\n")

    measured = measure_mutation(
        before_root=before,
        after_root=after,
        declared_roles=("skills",),
    )

    assert measured["touches_executable_code"] is True
    assert measured["surface_file_counts"]["executable_code"] == 1
