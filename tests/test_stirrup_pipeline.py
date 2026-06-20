"""Offline pipeline tests for the Stirrup-on-E2B base-harness feature.

No network, no E2B, no LibreOffice required: the render test exercises the
degraded path, the judge/worker tests use fakes/stubs.
"""
from dataclasses import dataclass, field

from qea.llm import MockLLM, _encode_image


# --------------------------------------------------------------------------- #
# Task 2: multimodal LLM support                                              #
# --------------------------------------------------------------------------- #
def test_mock_llm_accepts_and_ignores_images(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 16)  # minimal png-ish bytes
    out = MockLLM().complete("grade this", role="judge", images=[img])
    assert out == ""


def test_encode_image_returns_base64_data_url(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 16)
    url = _encode_image(img)
    assert url.startswith("data:image/png;base64,")
    assert len(url) > 30


# --------------------------------------------------------------------------- #
# Shared fixtures (used by Task 3+)                                           #
# --------------------------------------------------------------------------- #
@dataclass
class _FakeTask:
    task_id: str = "T1"
    subtype: str = "valuation"
    prompt: str = "Write a memo."
    rubric_items: list = field(default_factory=lambda: [
        {"points": 2, "criterion": "States the discount rate."},
        {"points": 1, "criterion": "Gives a recommendation."},
    ])


class _FixedLLM:
    def __init__(self, text): self.text = text
    def complete(self, prompt, *, role="agent", images=None): return self.text


def _make_xlsx(path):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws["A1"] = "DISCOUNT_RATE_9PCT"; wb.save(path)


# --------------------------------------------------------------------------- #
# Task 3: shared rubric scorer                                                #
# --------------------------------------------------------------------------- #
from qea.verifier import build_rubric_prompt, score_rubric, SoftJudge  # noqa: E402


def test_score_rubric_points_weighted_fraction():
    items = _FakeTask().rubric_items
    frac, verdicts = score_rubric('{"1": true, "2": false}', items)
    assert abs(frac - (2 / 3)) < 1e-9
    assert verdicts == {"1": True, "2": False}


def test_build_rubric_prompt_contains_task_rubric_deliverable():
    t = _FakeTask()
    p = build_rubric_prompt(t, "MY DELIVERABLE", t.rubric_items)
    assert "Write a memo." in p and "States the discount rate." in p
    assert "MY DELIVERABLE" in p and p.rstrip().endswith("JSON:")


def test_softjudge_real_sample_uses_shared_scorer():
    t = _FakeTask()
    j = SoftJudge(_FixedLLM('{"1": true, "2": true}'))
    frac, verdicts = j._real_sample(t, "deliverable text")
    assert abs(frac - 1.0) < 1e-9


# --------------------------------------------------------------------------- #
# Task 4: render step (force degraded path for a fast, offline test)          #
# --------------------------------------------------------------------------- #
def test_render_extracts_text_and_degrades_without_render(tmp_path, monkeypatch):
    import qea.grading.render as r
    monkeypatch.setattr(r, "_soffice", lambda: None)  # force degraded path: fast + offline
    xlsx = tmp_path / "deliverable.xlsx"; _make_xlsx(xlsx)
    out = r.render("final text", [xlsx], tmp_path / "render")
    assert isinstance(out, r.RenderedDeliverable)
    assert out.text == "final text"
    assert "DISCOUNT_RATE_9PCT" in out.extracted_text
    assert out.images == [] and out.degraded  # no soffice -> no images, degrade note


# --------------------------------------------------------------------------- #
# Task 5: multimodal judge                                                    #
# --------------------------------------------------------------------------- #
from qea.grading.multimodal_judge import MultimodalJudge, GradeResult  # noqa: E402
from qea.grading.render import RenderedDeliverable  # noqa: E402


class _CountingLLM:
    """Returns a fixed verdict JSON; records whether images were passed each call."""
    def __init__(self): self.image_calls = 0; self.text_calls = 0
    def complete(self, prompt, *, role="agent", images=None):
        if images:
            self.image_calls += 1
        else:
            self.text_calls += 1
        return '{"1": true, "2": false}'


def test_multimodal_judge_grades_both_paths():
    t = _FakeTask()
    rendered = RenderedDeliverable("final", "extracted DISCOUNT_RATE", images=["/tmp/p1.png"], degraded=[])
    llm = _CountingLLM()
    judge = MultimodalJudge(llm, k=2)
    res = judge.grade(t, rendered)
    assert isinstance(res, GradeResult)
    assert abs(res.multimodal_fraction - (2 / 3)) < 1e-9
    assert abs(res.text_fraction - (2 / 3)) < 1e-9
    assert llm.image_calls == 2 and llm.text_calls == 2   # k=2 each path
    assert res.degraded is False                            # had images, no degrade notes


# --------------------------------------------------------------------------- #
# Task 6: Stirrup worker (stub — no E2B/API)                                  #
# --------------------------------------------------------------------------- #
from qea.workers.stirrup_worker import Deliverable, StubWorker  # noqa: E402


def test_stub_worker_returns_deliverable(tmp_path):
    f = tmp_path / "out.xlsx"; _make_xlsx(f)
    w = StubWorker(final_text="done", files=[f])
    d = w.run_task(_FakeTask())
    assert isinstance(d, Deliverable)
    assert d.task_id == "T1" and d.final_text == "done" and d.files == [f]
