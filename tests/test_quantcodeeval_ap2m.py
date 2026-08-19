from qea.quantcodeeval_ap2m import AP2MExperimentSpec


def test_ap2m_experiment_spec_accepts_evolver_authored_repair():
    spec = AP2MExperimentSpec.from_decision(
        {
            "experiment_spec": {
                "mode": "repair",
                "seed_experience": "t26_h0",
                "worker_instruction": "Reproduce the public failure and repair it.",
                "max_iterations": 8,
                "prediction": "The repaired artifact should complete more properties.",
                "decision_changing_observation": (
                    "If the same failures remain, roll back the component."
                ),
            }
        }
    )

    assert spec.mode == "repair"
    assert spec.seed_experience == "t26_h0"
    assert spec.max_iterations == 8


def test_ap2m_experiment_spec_accepts_from_scratch_without_seed():
    spec = AP2MExperimentSpec.from_decision(
        {
            "experiment_spec": {
                "mode": "from_scratch",
                "seed_experience": None,
                "worker_instruction": "Solve the public task and test the artifact.",
                "max_iterations": 10,
                "prediction": "The component should activate before implementation.",
                "decision_changing_observation": "If unused, revise the binding.",
            }
        }
    )

    assert spec.mode == "from_scratch"
    assert spec.seed_experience is None
