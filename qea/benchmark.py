"""A Benchmark owns its tasks, its grader, its Evaluator, and its leakage
answer_corpus. The loop is benchmark-agnostic; `make_benchmark` selects the
(evaluator, debugger) per benchmark."""
from __future__ import annotations

from dataclasses import dataclass

from .evaluator import MultimodalEvaluator, RubricTextEvaluator
from .tasks import load_gdpval_finance, load_gdpval_a_pile, rubric_corpus
from .tasks_fab import load_fab_v2
from .verifier import SoftJudge, HardVerifier


@dataclass
class Benchmark:
    name: str
    tasks: list
    grader: object
    answer_corpus: list
    debugger_kind: str  # "b_pile" | "synthetic"
    evaluator: object = None  # benchmark-specific worker-run scorer (set by loaders)


def gdpval_benchmark(*, broad: bool = True, allow_download: bool = True, llm=None,
                     occupations: tuple = None) -> Benchmark:
    tasks = load_gdpval_finance(broad=broad, allow_download=allow_download,
                                occupations=occupations)
    name = "gdpval_all" if occupations == () else "gdpval_finance"
    return Benchmark(name, tasks, SoftJudge(llm), rubric_corpus(tasks),
                     "b_pile", evaluator=MultimodalEvaluator(llm))


def fab_benchmark(*, llm=None, k: int = 2) -> Benchmark:
    tasks = load_fab_v2()
    corpus = [c["criterion"] for t in tasks for c in (getattr(t, "rubric_items", None) or [])]
    return Benchmark("fab_v2", tasks, SoftJudge(llm), corpus,
                     "b_pile", evaluator=RubricTextEvaluator(llm, k=k))


def make_benchmark(name: str, *, llm=None, broad: bool = True, k: int = 2) -> Benchmark:
    """Route a benchmark name to its loader. Keeps the loop free of benchmark `if`s."""
    name = (name or "").lower()
    if name in ("fab", "fab_v2"):
        return fab_benchmark(llm=llm, k=k)
    if name in ("gdpval", "gdpval_finance"):
        return gdpval_benchmark(broad=broad, allow_download=True, llm=llm)
    if name == "gdpval_all":
        # Protocol-v2 pool: the full open gold subset (220 tasks, 44 occupations).
        return gdpval_benchmark(broad=broad, allow_download=True, llm=llm, occupations=())
    if name == "apex_ib":
        # APEX-Agents Investment Banking (160 tasks, 10 worlds): rubric LLM judge
        # (our shared scorer); worlds stage via in-VM HF download (vm_setup_cmd).
        from .bench_apex import APEXEvaluator, load_apex_ib
        tasks = load_apex_ib()
        corpus = [c["criterion"] for t in tasks for c in (t.rubric_items or [])]
        return Benchmark("apex_ib", tasks, SoftJudge(llm), corpus, "b_pile",
                         evaluator=APEXEvaluator(llm, k=k))
    if name == "dsbench":
        # DSBench data-analysis (466 ModelOff finance questions): deterministic
        # letter/numeric matching + official LLM judge fallback — near-zero judge noise.
        from .bench_dsbench import DSBenchEvaluator, load_dsbench
        tasks = load_dsbench()
        return Benchmark("dsbench_da", tasks, HardVerifier(), [], "b_pile",
                         evaluator=DSBenchEvaluator(llm))
    if name.startswith("ssb"):
        # SpreadsheetBench: deterministic official checker — zero judge noise.
        # "ssb" / "ssb_912" = evolution pool; "ssb_verified" = held-out reporting.
        from .bench_ssb import SSBEvaluator, load_ssb
        split = {"ssb": "912", "ssb_912": "912", "ssb_verified": "verified",
                 "ssb_sample": "sample"}[name]
        tasks = load_ssb(split=split)
        return Benchmark(f"ssb_{split}", tasks, HardVerifier(), [], "b_pile",
                         evaluator=SSBEvaluator())
    raise ValueError(f"unknown benchmark {name!r} (expected 'fab', 'gdpval', 'gdpval_all', or 'ssb*')")


def synthetic_fixture_benchmark() -> Benchmark:
    """Offline plumbing fixture only — NOT a real benchmark, makes no headroom claim."""
    tasks = load_gdpval_a_pile()
    refs = [str(t.reference(t.inputs)) for t in tasks]  # numeric answers as the corpus
    return Benchmark("synthetic_fixture", tasks, HardVerifier(), refs, "synthetic")
