"""Phase-4 Level-B loop: unit tests for the pure logic + a gated NexAU smoke test.

The NexAU-real pieces (run_worker / run_evolve_agent / the full loop) require an
API key + proxy and are gated behind QEA_LEVELB_SMOKE=1; everything else is
offline and deterministic.
"""
import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _dummy_llm_env(monkeypatch):
    """AgentConfig.from_yaml eagerly resolves ${env.LLM_*}; offline tests only need
    the config to PARSE, so provide harmless dummies (no network is made)."""
    monkeypatch.setenv("LLM_MODEL", "deepseek/deepseek-v4-pro")
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")


class _FakeMsg:
    def __init__(self, role, text):
        self.role = role
        self._text = text
    def get_text_content(self):
        return self._text


class _FakeAgent:
    def __init__(self, msgs):
        self.full_trace = msgs


def test_summarize_trace_counts_roles_and_errors():
    from qea.worker_runtime import summarize_trace
    agent = _FakeAgent([
        _FakeMsg("assistant", "let me build it"),
        _FakeMsg("tool", "ok, file written"),
        _FakeMsg("assistant", "now verify"),
        _FakeMsg("tool", "Traceback (most recent call last): Error: boom"),
        _FakeMsg("user", "the task prompt"),
    ])
    mon = summarize_trace(agent)
    assert mon["turns"] == 2          # two assistant messages
    assert mon["tool_calls"] == 2     # two non-user tool/result messages
    assert mon["tool_errors"] == 1    # one carried an error marker


WEAK_DIR = Path(__file__).resolve().parent.parent / "qea" / "worker_gdpval_weak"
FULL_PROMPT = (Path(__file__).resolve().parent.parent
               / "qea" / "worker_gdpval" / "systemprompt.md").read_text()


def test_weak_seed_is_process_limited_not_capability_walled():
    # The weak seed must still load as a NexAU config and keep the shell tool
    # (so evolution CAN recover capability), but its prompt must be stripped of the
    # high-level finish-guidance / per-extension hints the full worker ships.
    from nexau import AgentConfig
    cfg = AgentConfig.from_yaml(config_path=WEAK_DIR / "agent.yaml")
    assert cfg is not None
    weak_prompt = (WEAK_DIR / "systemprompt.md").read_text()
    # headroom markers present in the FULL worker prompt, removed from the weak seed:
    assert "ls -la" not in weak_prompt              # finish/verify guidance removed
    assert "openpyxl" not in weak_prompt            # per-extension tool hints removed
    assert "Verify the file was written" not in weak_prompt
    assert len(weak_prompt) < len(FULL_PROMPT)      # strictly leaner
    # but the shell tool is still available (capability is recoverable by editing)
    tool_yaml = (WEAK_DIR / "tool_descriptions" / "run_shell_command.tool.yaml").read_text()
    assert "run_shell_command" in tool_yaml


def test_process_note_is_answer_free_and_flags_no_deliverable():
    from qea.debugger import process_note
    # produced no file, burned few turns -> the headroom signal
    n = process_note({"files": 0, "turns": 4, "tool_calls": 2, "tool_errors": 1, "secs": 30.0})
    assert "no deliverable file" in n.lower()
    assert "4 turn" in n
    assert "1 tool error" in n
    # a healthy run produces a benign note
    ok = process_note({"files": 1, "turns": 11, "tool_calls": 6, "tool_errors": 0, "secs": 200.0})
    assert "produced" in ok.lower() and "no deliverable file" not in ok.lower()
    # process notes carry only counts — never any answer/number-from-the-task content
    assert "$" not in n and "going-concern" not in n


def test_trace_fold_preserves_firewall():
    from qea.tasks import BTask
    from qea.verifier import TaskResult
    from qea.falsify import EvalSummary
    from qea.debugger import diagnose_b_pile

    class CriticLLM:
        def complete(self, prompt, *, role="judge"):
            if "Classify" in prompt:
                return '{"root_cause_tag": "WrongStructure", "target_slot": "prompt"}'
            return "The deliverable omits the required reconciliation section."

    res = {"t1": TaskResult("t1", "Accountants and Auditors", "B", False, False, False, 0.3, 0.0,
                            None, criterion_verdicts={"1": False})}
    tasks = [BTask(task_id="t1", subtype="Accountants and Auditors", prompt="reconcile the ledger",
                   rubric="", rubric_items=[{"points": 1, "criterion": "reconciles to control total"}],
                   gold="SECRET-CONTROL-TOTAL-98765")]
    diag = diagnose_b_pile(EvalSummary(res, {"t1": "weak memo"}), tasks, llm=CriticLLM(),
                           traces={"t1": {"files": 0, "turns": 3, "tool_errors": 1}})
    payload = repr(diag.proposer_payload())
    assert "SECRET-CONTROL-TOTAL-98765" not in payload   # firewall holds with traces folded in
    assert "t1" in diag.predicted_fix_task_ids


def test_snapshot_and_diff_and_signature(tmp_path):
    from qea.evolve_runtime import snapshot_dir, dir_unified_diff, diff_signature, DirEdit
    src = tmp_path / "incumbent"
    (src / "tool_descriptions").mkdir(parents=True)
    (src / "systemprompt.md").write_text("original line\n")
    (src / "agent.yaml").write_text("name: w\n")

    snap = tmp_path / "snap"
    snapshot_dir(src, snap)
    assert (snap / "systemprompt.md").read_text() == "original line\n"

    # no edit yet -> empty diff, and a DirEdit over an empty diff has empty content
    assert dir_unified_diff(src, snap) == ""
    # edit the snapshot
    (snap / "systemprompt.md").write_text("original line\nADDED guidance\n")
    diff = dir_unified_diff(src, snap)
    assert "ADDED guidance" in diff and "systemprompt.md" in diff

    sig = diff_signature(diff)
    assert isinstance(sig, str) and len(sig) == 64           # sha256 hex
    # identical diff -> identical signature; different diff -> different
    assert diff_signature(diff) == sig
    assert diff_signature(diff + "x") != sig

    # DirEdit is the Edit-like shim the buffer + leakage guard consume
    de = DirEdit(diff)
    assert de.signature() == sig
    assert "ADDED guidance" in de.content            # leakage guard inspects .content
    assert de.summary                                 # non-empty human summary


def test_leakage_guard_blocks_dir_edit_that_pastes_answer():
    from qea.verifier import LeakageGuard
    from qea.evolve_runtime import DirEdit
    corpus = ["flags any going-concern triggers in the liquidity position"]
    guard = LeakageGuard(corpus, threshold=0.6)
    leaked_diff = ("--- a/systemprompt.md\n+++ b/systemprompt.md\n"
                   "+Always flags any going-concern triggers in the liquidity position.\n")
    assert guard.is_leak(DirEdit(leaked_diff)) is True
    ok_diff = ("--- a/systemprompt.md\n+++ b/systemprompt.md\n"
               "+After producing the file, list the directory to verify it was written.\n")
    assert guard.is_leak(DirEdit(ok_diff)) is False


def test_evolve_agent_config_loads():
    from nexau import AgentConfig
    from qea.evolve_runtime import EVOLVE_DIR
    cfg = AgentConfig.from_yaml(config_path=EVOLVE_DIR / "agent.yaml")
    assert cfg is not None


class _FakeEval:
    """Benchmark-agnostic fake Evaluator: score depends on whether the worker prompt
    was improved (the evolve agent appends a marker the fake worker echoes)."""
    def __init__(self, base=0.50, improved=0.90):
        self.base, self.improved = base, improved
    def evaluate(self, task, worker_run, out_dir=None):
        from qea.evaluator import TaskEval
        s = self.improved if "improved=True" in worker_run.deliverable_text else self.base
        return TaskEval(s, s, True, worker_run.deliverable_text, {"1": s > 0.6}, 0.0)


def test_levelb_loop_keeps_improving_edit_offline(tmp_path, monkeypatch):
    import qea.loop_levelb as L
    from qea.worker_runtime import WorkerRun
    from qea.tasks import BTask

    tasks = [BTask(task_id="t1", subtype="Accountants and Auditors", prompt="p", rubric="",
                   rubric_items=[{"points": 1, "criterion": "c"}], gold="g")]

    class StubLLM:  # the firewalled debugger's critic + classify calls
        def complete(self, prompt, *, role="judge", **kw):
            return ('{"root_cause_tag":"WrongStructure","target_slot":"prompt"}'
                    if "Classify" in prompt else "omits the required structure")

    # worker: returns a fixed deliverable; "improved=True" once the prompt is edited.
    def fake_run_worker(task, worker_dir, run_dir):
        improved = "IMPROVED" in (worker_dir / "systemprompt.md").read_text()
        return WorkerRun(f"deliverable improved={improved}", [], {"files": 1, "turns": 5, "tool_errors": 0})
    monkeypatch.setattr(L, "run_worker", fake_run_worker)

    # evolve agent: appends the IMPROVED marker + predicts it fixes t1
    def fake_run_evolve(snapshot_dir_path, diag, run_dir, *, edit_history=""):
        sp = snapshot_dir_path / "systemprompt.md"
        sp.write_text(sp.read_text() + "\nIMPROVED: verify the file before finishing.\n")
        return {"final_text": "added verify guidance", "trace": {"turns": 2},
                "prediction": {"predicted_fixes": ["t1"], "risk_tasks": []}}
    monkeypatch.setattr(L, "run_evolve_agent", fake_run_evolve)

    seed = tmp_path / "seed"; (seed / "tool_descriptions").mkdir(parents=True)
    (seed / "agent.yaml").write_text("name: w\n")
    (seed / "systemprompt.md").write_text("do the task\n")
    cfg = L.LevelBConfig(n_iters=1, k=1, n_tasks=1, results_dir=str(tmp_path / "res"),
                         seed_worker_dir=str(seed))

    res = L.run_levelb(cfg, _tasks=tasks, _evaluator=_FakeEval(), _llm=StubLLM())
    assert res.n_kept == 1                                   # the +0.40 edit beats the noise floor
    assert res.records[0].verdict == "EFFECTIVE"            # predicted t1 fixed, t1 flipped
    assert res.records[0].improved == ["t1"]
    assert res.mean_score_trajectory[-1] > res.mean_score_trajectory[0]
    assert "IMPROVED" in (Path(res.final_worker_dir) / "systemprompt.md").read_text()


def test_levelb_loop_rolls_back_non_improving_edit(tmp_path, monkeypatch):
    import qea.loop_levelb as L
    from qea.worker_runtime import WorkerRun
    from qea.tasks import BTask

    tasks = [BTask(task_id="t1", subtype="x", prompt="p", rubric="",
                   rubric_items=[{"points": 1, "criterion": "c"}], gold="g")]

    class StubLLM:
        def complete(self, prompt, *, role="judge", **kw):
            return ('{"root_cause_tag":"WrongStructure","target_slot":"prompt"}'
                    if "Classify" in prompt else "omits the required structure")

    monkeypatch.setattr(L, "run_worker",
                        lambda task, wd, rd: WorkerRun("same", [], {"files": 1, "turns": 5, "tool_errors": 0}))

    # evolve makes a real (but useless) change so the diff is non-empty; predicts t1
    def ev(snap, diag, rd, *, edit_history=""):
        sp = snap / "systemprompt.md"; sp.write_text(sp.read_text() + "\nnoise edit\n")
        return {"final_text": "x", "trace": {}, "prediction": {"predicted_fixes": ["t1"], "risk_tasks": []}}
    monkeypatch.setattr(L, "run_evolve_agent", ev)

    seed = tmp_path / "seed"; (seed / "tool_descriptions").mkdir(parents=True)
    (seed / "agent.yaml").write_text("name: w\n"); (seed / "systemprompt.md").write_text("do it\n")
    cfg = L.LevelBConfig(n_iters=1, k=1, n_tasks=1, results_dir=str(tmp_path / "res"),
                         seed_worker_dir=str(seed))
    # a flat evaluator: score never moves -> nothing flips -> INEFFECTIVE -> rolled back
    res = L.run_levelb(cfg, _tasks=tasks, _evaluator=_FakeEval(base=0.50, improved=0.50),
                       _llm=StubLLM())
    assert res.n_kept == 0 and res.n_rolled_back == 1        # flat score -> rolled back
    assert res.records[0].verdict == "INEFFECTIVE"


def test_format_gate_keyed_to_gold_extension():
    from qea.grading.format_gate import format_ok, apply_gate
    from qea.tasks import BTask

    # text-gold task (no required ext) -> always ok, even with no files
    txt = BTask(task_id="t", subtype="x", prompt="p", rubric="", deliverable_exts=[])
    assert format_ok(txt, []) is True
    assert apply_gate(0.8, txt, []) == (0.8, True)

    # xlsx-gold task: must produce an .xlsx
    xls = BTask(task_id="t", subtype="x", prompt="p", rubric="", deliverable_exts=[".xlsx"])
    assert format_ok(xls, ["/tmp/report.xlsx"]) is True
    assert apply_gate(0.83, xls, ["/tmp/report.xlsx"]) == (0.83, True)
    # wrong container (asked xlsx, produced pdf) -> gated to 0
    assert format_ok(xls, ["/tmp/report.pdf"]) is False
    assert apply_gate(0.83, xls, ["/tmp/report.pdf"]) == (0.0, False)
    # no file at all (text answer) -> gated to 0
    assert apply_gate(0.83, xls, []) == (0.0, False)

    # multi-ext gold: any one matching extension satisfies it
    both = BTask(task_id="t", subtype="x", prompt="p", rubric="", deliverable_exts=[".pdf", ".xlsx"])
    assert format_ok(both, ["/tmp/a.xlsx"]) is True


def test_gdpval_loader_populates_deliverable_exts():
    # The GDPval loader must attach the gold deliverable extension(s) to each task.
    from qea.tasks import _gold_deliverable_exts
    assert _gold_deliverable_exts(["deliverable_files/abc/Fall Music Tour Output.xlsx"]) == [".xlsx"]
    assert _gold_deliverable_exts(None) == []          # text deliverable -> no required ext
    assert _gold_deliverable_exts(["a/x.pdf", "b/y.pptx"]) == [".pdf", ".pptx"]


def test_rubric_text_evaluator_scores_and_no_op_gate():
    from qea.evaluator import RubricTextEvaluator
    from qea.worker_runtime import WorkerRun
    from qea.tasks import BTask

    class JudgeLLM:
        def complete(self, prompt, *, role="judge", **kw):
            return "1: yes\n2: no"            # 1 of 2 criteria satisfied -> 0.5
    task = BTask(task_id="f0", subtype="x", prompt="p", rubric="",
                 rubric_items=[{"points": 1, "criterion": "a"}, {"points": 1, "criterion": "b"}])
    te = RubricTextEvaluator(JudgeLLM(), k=1).evaluate(task, WorkerRun("my answer", [], {}), None)
    assert 0.0 <= te.content_score <= 1.0
    assert te.format_ok is True and te.gated_score == te.content_score   # text-gold -> gate no-op
    assert te.deliverable_text == "my answer"


def test_multimodal_evaluator_applies_format_gate():
    from qea.evaluator import MultimodalEvaluator
    from qea.worker_runtime import WorkerRun
    from qea.grading.multimodal_judge import GradeResult
    from qea.tasks import BTask
    from types import SimpleNamespace

    ev = MultimodalEvaluator(llm=None)
    ev.judge = SimpleNamespace(grade=lambda task, rendered: GradeResult(task.task_id, 0.8, 0.8, {"1": True}, 0.0, False))
    # stub render so no LibreOffice/PyMuPDF is needed (evaluate imports it at call time)
    monkey = SimpleNamespace(text="t", extracted_text="t", images=[], degraded=[])
    import qea.grading.render as R
    orig = R.render
    R.render = lambda text, files, out_dir: monkey
    try:
        xls = BTask(task_id="g0", subtype="x", prompt="p", rubric="", deliverable_exts=[".xlsx"])
        ok = ev.evaluate(xls, WorkerRun("t", ["/tmp/report.xlsx"], {}), "/tmp/out")
        assert ok.gated_score == 0.8 and ok.format_ok is True
        miss = ev.evaluate(xls, WorkerRun("t", ["/tmp/report.pdf"], {}), "/tmp/out")
        assert miss.content_score == 0.8 and miss.gated_score == 0.0 and miss.format_ok is False
    finally:
        R.render = orig


def test_prediction_parsing_handles_present_absent_malformed():
    from qea.evolve_runtime import _parse_prediction
    good = _parse_prediction('done.\n{"predicted_fixes": ["t1", "t2"], "risk_tasks": ["t3"]}')
    assert good == {"predicted_fixes": ["t1", "t2"], "risk_tasks": ["t3"]}
    absent = _parse_prediction("I changed the prompt, no JSON here.")
    assert absent == {"predicted_fixes": [], "risk_tasks": []}
    malformed = _parse_prediction('{"predicted_fixes": [oops')
    assert malformed == {"predicted_fixes": [], "risk_tasks": []}


def test_classify_verdict_table():
    from qea.loop_levelb import _classify
    from qea.evolve_runtime import DirEdit
    from qea.evaluator import TaskEval

    def evals(scores):  # tid -> gated score
        return {t: TaskEval(s, s, True, "", {}, 0.0) for t, s in scores.items()}

    inc = evals({"a": 0.2, "b": 0.5, "c": 0.5})
    # EFFECTIVE: predicted a fixed, a flips, nothing regresses
    e = DirEdit("d", predicted_fixes=["a"], risk_tasks=[])
    assert _classify(e, inc, evals({"a": 0.9, "b": 0.5, "c": 0.5}), 0.05)["verdict"] == "EFFECTIVE"
    # HARMFUL: nothing predicted-fixed flipped, an unattributed task regressed
    e2 = DirEdit("d", predicted_fixes=["a"], risk_tasks=[])
    assert _classify(e2, inc, evals({"a": 0.2, "b": 0.1, "c": 0.5}), 0.05)["verdict"] == "HARMFUL"
    # MIXED: a predicted fix flips AND an unattributed task regresses
    e3 = DirEdit("d", predicted_fixes=["a"], risk_tasks=[])
    assert _classify(e3, inc, evals({"a": 0.9, "b": 0.1, "c": 0.5}), 0.05)["verdict"] == "MIXED"
    # INEFFECTIVE: nothing moves
    e4 = DirEdit("d", predicted_fixes=["a"], risk_tasks=[])
    assert _classify(e4, inc, evals({"a": 0.2, "b": 0.5, "c": 0.5}), 0.05)["verdict"] == "INEFFECTIVE"


def test_make_benchmark_routes_to_the_right_evaluator():
    from qea.benchmark import make_benchmark
    from qea.evaluator import RubricTextEvaluator
    fab = make_benchmark("fab", llm=None, k=2)
    assert fab.name == "fab_v2" and isinstance(fab.evaluator, RubricTextEvaluator)
    assert fab.answer_corpus and all(isinstance(c, str) for c in fab.answer_corpus)
    with pytest.raises(ValueError):
        make_benchmark("nonsense")


def test_evaluate_dir_tolerates_worker_failure(tmp_path, monkeypatch):
    # A crashing worker (e.g. NexAU empty-response after retries) must not kill the
    # run: the task scores 0, the error is recorded in the trace, the loop continues.
    import qea.loop_levelb as L
    from qea.tasks import BTask

    tasks = [BTask(task_id="t1", subtype="x", prompt="p", rubric="",
                   rubric_items=[{"points": 1, "criterion": "c"}]),
             BTask(task_id="t2", subtype="x", prompt="p", rubric="",
                   rubric_items=[{"points": 1, "criterion": "c"}])]

    def boom(task, wd, rd):
        if task.task_id == "t1":
            raise RuntimeError("Error in agent execution: No response content or tool calls")
        from qea.worker_runtime import WorkerRun
        return WorkerRun("ok answer", [], {"files": 0, "turns": 3, "tool_errors": 0})
    monkeypatch.setattr(L, "run_worker", boom)

    evals, traces, deliverables, mean = L.evaluate_dir(
        tmp_path / "w", tasks, _FakeEval(base=0.7, improved=0.7), tmp_path / "r")
    assert evals["t1"].gated_score == 0.0 and evals["t1"].format_ok is False
    assert "RuntimeError" in traces["t1"]["error"]
    assert evals["t2"].gated_score == 0.7                 # the healthy task still scored
    assert mean == 0.35                                    # (0.0 + 0.7) / 2


@pytest.mark.skipif(os.environ.get("QEA_LEVELB_SMOKE") != "1",
                    reason="set QEA_LEVELB_SMOKE=1 to run the real-API NexAU Level-B smoke test")
def test_levelb_smoke_one_task_one_iter(tmp_path):
    # End-to-end on ONE real FAB task, ONE iteration, against the real NexAU weak
    # worker + evolve agent. Proves the wiring runs; makes no headroom claim.
    import run as runmod
    runmod._load_dotenv()
    from qea.loop_levelb import LevelBConfig, run_levelb
    cfg = LevelBConfig(n_iters=1, k=1, n_tasks=1, benchmark="fab",
                       seed_worker_dir="qea/worker_fab_weak", results_dir=str(tmp_path / "res"))
    res = run_levelb(cfg)
    assert res.n_tasks == 1
    assert len(res.mean_score_trajectory) >= 1
    assert Path(res.final_worker_dir).exists()
    assert (Path(cfg.results_dir) / "iter_001" / "manifest.json").exists()
