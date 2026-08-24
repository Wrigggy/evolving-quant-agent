"""Passive structured telemetry for the six-state quant workflow."""

from __future__ import annotations


_STAGES = {f"S{index}" for index in range(1, 7)}
_ACTIONS = {"ENTER", "COMPLETE", "NOT_APPLICABLE", "REVISIT"}
_REVISIT_TARGETS = {"S2", "S3", "S4"}


def record_quant_state(
    stage: str,
    action: str,
    public_summary: str,
) -> dict[str, str]:
    """Acknowledge one schema-valid public state event without side effects."""

    if stage not in _STAGES:
        return {"status": "rejected", "error": "invalid stage"}
    if action not in _ACTIONS:
        return {"status": "rejected", "error": "invalid action"}
    if not isinstance(public_summary, str) or not public_summary.strip():
        return {"status": "rejected", "error": "public_summary is required"}
    if len(public_summary) > 512:
        return {"status": "rejected", "error": "public_summary is too long"}
    if action == "REVISIT" and stage not in _REVISIT_TARGETS:
        return {"status": "rejected", "error": "invalid revisit target"}
    if action == "NOT_APPLICABLE" and stage == "S6":
        return {"status": "rejected", "error": "S6 must be completed"}
    return {"status": "recorded"}


__all__ = ["record_quant_state"]
