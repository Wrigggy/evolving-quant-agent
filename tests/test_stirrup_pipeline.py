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
