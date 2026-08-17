from scripts.run_quantcodeeval_breadth_candidate import _proposal_inputs


def _report(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    return {
        "proposal": {
            "decision": "ACT",
            "candidate_dir": str(candidate),
            "admission": {"admitted": True},
            "mutation_metrics": {
                "component_roles": ["middleware", "tools", "systemprompt"]
            },
            "summary": {
                "component_tests": [
                    {
                        "component": "middleware",
                        "status": "passed",
                        "candidate_digest": "1" * 64,
                    },
                    {
                        "component": "tools",
                        "status": "passed",
                        "candidate_digest": "1" * 64,
                    },
                ],
                "discovery_hypothesis": {
                    "hypothesis": {
                        "search_operator": "COMPOSE",
                        "primary_components": ["middleware", "tools"],
                    }
                },
            },
        }
    }


def test_reuses_all_evolver_primary_components_and_their_tests(tmp_path):
    candidate, mechanism, primary, declared, tests = _proposal_inputs(
        _report(tmp_path),
        reuse_component_tests=True,
    )

    assert candidate == (tmp_path / "candidate").resolve()
    assert mechanism == "COMPOSE"
    assert primary == ("middleware", "tools")
    assert declared == ["middleware", "tools", "systemprompt"]
    assert [row["component"] for row in tests] == ["middleware", "tools"]


def test_manual_mode_keeps_component_tests_for_the_caller(tmp_path):
    _, _, primary, _, tests = _proposal_inputs(
        _report(tmp_path),
        reuse_component_tests=False,
    )

    assert primary == ("middleware", "tools")
    assert tests == ()
