"""A Benchmark owns its tasks, its grader, and its leakage answer_corpus. The loop
is benchmark-agnostic; the router selects the (grader, debugger) per benchmark."""
from __future__ import annotations

from dataclasses import dataclass

from .tasks import load_gdpval_finance, load_gdpval_a_pile, rubric_corpus
from .verifier import SoftJudge, HardVerifier


@dataclass
class Benchmark:
    name: str
    tasks: list
    grader: object
    answer_corpus: list
    debugger_kind: str  # "b_pile" | "synthetic"


def gdpval_benchmark(*, broad: bool = True, allow_download: bool = True, llm=None) -> Benchmark:
    tasks = load_gdpval_finance(broad=broad, allow_download=allow_download)
    return Benchmark("gdpval_finance", tasks, SoftJudge(llm), rubric_corpus(tasks), "b_pile")


def synthetic_fixture_benchmark() -> Benchmark:
    """Offline plumbing fixture only — NOT a real benchmark, makes no headroom claim."""
    tasks = load_gdpval_a_pile()
    refs = [str(t.reference(t.inputs)) for t in tasks]  # numeric answers as the corpus
    return Benchmark("synthetic_fixture", tasks, HardVerifier(), refs, "synthetic")
