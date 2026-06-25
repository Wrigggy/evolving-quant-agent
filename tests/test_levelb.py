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


def test_levelb_loop_keeps_improving_edit_offline(tmp_path, monkeypatch):
    import qea.loop_levelb as L
    from qea.worker_runtime import WorkerRun
    from qea.grading.multimodal_judge import GradeResult
    from qea.tasks import BTask

    tasks = [BTask(task_id="t1", subtype="Accountants and Auditors", prompt="p", rubric="",
                   rubric_items=[{"points": 1, "criterion": "c"}], gold="g")]

    class StubLLM:  # the firewalled debugger's critic + classify calls
        def complete(self, prompt, *, role="judge", **kw):
            return ('{"root_cause_tag":"WrongStructure","target_slot":"prompt"}'
                    if "Classify" in prompt else "omits the required structure")

    # worker: returns a fixed deliverable + trace; score depends on whether the
    # incumbent worker prompt has been improved (the evolve agent appends a marker).
    def fake_run_worker(task, worker_dir, run_dir):
        improved = "IMPROVED" in (worker_dir / "systemprompt.md").read_text()
        return WorkerRun(f"deliverable improved={improved}", [], {"files": 1, "turns": 5, "tool_errors": 0})
    monkeypatch.setattr(L, "run_worker", fake_run_worker)

    # judge: 0.50 for the seed, 0.90 once the worker prompt is improved
    class FakeJudge:
        def __init__(self, *a, **k): pass
        def grade(self, task, rendered):
            score = 0.90 if "improved=True" in rendered.text else 0.50
            return GradeResult(task.task_id, score, score, {"1": score > 0.6}, 0.0, False)
    monkeypatch.setattr(L, "MultimodalJudge", FakeJudge)

    # render: trivial passthrough exposing .text / .extracted_text / .images / .degraded
    def fake_render(text, produced, out_dir):
        from types import SimpleNamespace
        return SimpleNamespace(text=text, extracted_text=text, images=[], degraded=False)
    monkeypatch.setattr(L, "render", fake_render)

    # evolve agent: appends the IMPROVED marker to the snapshot's systemprompt.md
    def fake_run_evolve(snapshot_dir_path, diag, run_dir):
        sp = snapshot_dir_path / "systemprompt.md"
        sp.write_text(sp.read_text() + "\nIMPROVED: verify the file before finishing.\n")
        return {"final_text": "added verify guidance", "trace": {"turns": 2}}
    monkeypatch.setattr(L, "run_evolve_agent", fake_run_evolve)

    seed = tmp_path / "seed"; (seed / "tool_descriptions").mkdir(parents=True)
    (seed / "agent.yaml").write_text("name: w\n")
    (seed / "systemprompt.md").write_text("do the task\n")
    cfg = L.LevelBConfig(n_iters=1, k=1, n_tasks=1, results_dir=str(tmp_path / "res"),
                         seed_worker_dir=str(seed))

    res = L.run_gdpval_levelb(cfg, _tasks=tasks, _llm=StubLLM())
    assert res.n_kept == 1                                   # the +0.40 edit beats the noise floor
    assert res.mean_score_trajectory[-1] > res.mean_score_trajectory[0]
    assert "IMPROVED" in (Path(res.final_worker_dir) / "systemprompt.md").read_text()


def test_levelb_loop_rolls_back_non_improving_edit(tmp_path, monkeypatch):
    import qea.loop_levelb as L
    from qea.worker_runtime import WorkerRun
    from qea.grading.multimodal_judge import GradeResult
    from qea.tasks import BTask
    from types import SimpleNamespace

    tasks = [BTask(task_id="t1", subtype="x", prompt="p", rubric="",
                   rubric_items=[{"points": 1, "criterion": "c"}], gold="g")]

    class StubLLM:
        def complete(self, prompt, *, role="judge", **kw):
            return ('{"root_cause_tag":"WrongStructure","target_slot":"prompt"}'
                    if "Classify" in prompt else "omits the required structure")

    monkeypatch.setattr(L, "run_worker",
                        lambda task, wd, rd: WorkerRun("same", [], {"files": 1, "turns": 5, "tool_errors": 0}))

    class FlatJudge:
        def __init__(self, *a, **k): pass
        def grade(self, task, rendered):
            return GradeResult(task.task_id, 0.50, 0.50, {"1": False}, 0.0, False)  # never improves
    monkeypatch.setattr(L, "MultimodalJudge", FlatJudge)
    monkeypatch.setattr(L, "render",
                        lambda t, p, o: SimpleNamespace(text=t, extracted_text=t, images=[], degraded=False))
    # evolve makes a real (but useless) change so the diff is non-empty
    def ev(snap, diag, rd):
        sp = snap / "systemprompt.md"; sp.write_text(sp.read_text() + "\nnoise edit\n")
        return {"final_text": "x", "trace": {}}
    monkeypatch.setattr(L, "run_evolve_agent", ev)

    seed = tmp_path / "seed"; (seed / "tool_descriptions").mkdir(parents=True)
    (seed / "agent.yaml").write_text("name: w\n"); (seed / "systemprompt.md").write_text("do it\n")
    cfg = L.LevelBConfig(n_iters=1, k=1, n_tasks=1, results_dir=str(tmp_path / "res"),
                         seed_worker_dir=str(seed))
    res = L.run_gdpval_levelb(cfg, _tasks=tasks, _llm=StubLLM())
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


@pytest.mark.skipif(os.environ.get("QEA_LEVELB_SMOKE") != "1",
                    reason="set QEA_LEVELB_SMOKE=1 to run the real-API NexAU Level-B smoke test")
def test_levelb_smoke_one_task_one_iter(tmp_path):
    # End-to-end on ONE real GDPval task, ONE iteration, against the real NexAU
    # weak worker + evolve agent. Proves the wiring runs; makes no headroom claim.
    import run as runmod
    runmod._load_dotenv()
    from qea.loop_levelb import LevelBConfig, run_gdpval_levelb
    cfg = LevelBConfig(n_iters=1, k=1, n_tasks=1, results_dir=str(tmp_path / "res"))
    res = run_gdpval_levelb(cfg)
    assert res.n_tasks == 1
    assert len(res.mean_score_trajectory) >= 1
    assert Path(res.final_worker_dir).exists()
    assert (Path(cfg.results_dir) / "iter_001" / "manifest.json").exists()
