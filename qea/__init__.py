"""QEA v0 — Evolving Quant Agent.

A task-family-aware evolutionary harness that reuses the AHE
evolve -> falsify -> rollback loop with quant semantics. v0 targets one task
family: the GDPval finance/accounting numeric (A-pile) tasks, with a soft-judged
B-pile used only for transfer evaluation.

See PLAN.md for the design and the four iron laws.
"""

__version__ = "0.0.1"
