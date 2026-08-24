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


def test_quant_evolver_searches_the_full_workflow_without_forcing_prompt_prose():
    prompt = EVOLVER_PROMPT.read_text(encoding="utf-8")
    compact = " ".join(prompt.split())

    assert "inspect the complete six-state workflow" in compact
    assert "`stage_local`, `cross_stage`, or `workflow_global`" in compact
    assert "at least two distinct frozen-H0 tasks" in compact
    assert "`systemprompt`, `skills`, `middleware`, and `routing`" in compact
    assert "global scope neither requires generic prompt prose" in compact
    assert "subject to the public-only claim-provenance requirements" in compact
