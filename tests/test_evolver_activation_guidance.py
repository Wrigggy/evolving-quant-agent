from pathlib import Path


EVOLVER_PROMPT = (
    Path(__file__).resolve().parents[1]
    / "qea/evolve_agent_full/systemprompt.md"
)


def test_quant_evolver_treats_early_component_activation_as_part_of_candidate():
    prompt = EVOLVER_PROMPT.read_text(encoding="utf-8")
    compact = " ".join(prompt.split())

    assert "Treat activation as part of the intervention" in compact
    assert "before broad background research" in compact
    assert "one-shot middleware or routing checkpoint" in compact
    assert "must not manufacture task-specific arguments" in compact
