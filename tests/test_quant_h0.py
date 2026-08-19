from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
QUANT_H0 = ROOT / "qea" / "worker_quant_h0"


def test_quant_h0_is_shell_only_with_six_research_states():
    prompt = (QUANT_H0 / "systemprompt.md").read_text(encoding="utf-8")
    config = yaml.safe_load((QUANT_H0 / "agent.yaml").read_text(encoding="utf-8"))

    assert "Quant Research Worker Agent" in prompt
    assert prompt.count("Research State") >= 1
    assert [tool["name"] for tool in config["tools"]] == ["run_shell_command"]
    assert config["name"] == "qea_quant_h0_worker"

    for name in (
        "Research Mandate & Contract",
        "Research Evidence & Data",
        "Quantitative Representation",
        "Research Operation",
        "Evaluation & Reconciliation",
        "Research Artifact & Completion",
    ):
        assert name in prompt


def test_quant_h0_does_not_include_evolved_search_or_task_answers():
    prompt = (QUANT_H0 / "systemprompt.md").read_text(encoding="utf-8").casefold()

    for excluded in (
        "failure class",
        "earliest divergence",
        "component library",
        "checker answer",
        "expected value",
        "candidate history",
    ):
        assert excluded not in prompt
