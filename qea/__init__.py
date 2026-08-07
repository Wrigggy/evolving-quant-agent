"""QEA — Evolving Quant Agent.

A task-family-aware discovery, evolution, and verification harness for
quantitative-finance agents. The original v0 includes an explicitly attributed
AHE-derived falsification baseline; newer QFBench discovery mechanisms are kept
methodologically separate from that provenance.

See ``docs/PROJECT_MEMORY.md`` for the current architecture and decision record.
"""

__version__ = "0.0.1"

from .repair_supervisor import (  # noqa: E402
    Classification,
    ExpectedIdentity,
    Incident,
    IncidentState,
    IncidentStore,
)

__all__ = [
    "Classification",
    "ExpectedIdentity",
    "Incident",
    "IncidentState",
    "IncidentStore",
    "__version__",
]
