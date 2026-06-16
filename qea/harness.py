"""The seven-slot harness, its minimal seed, and edit/clone/rollback.

Seven slots (NexAU-style, quant semantics): five inherited from AHE
(tool / middleware / skill / prompt / memory) plus two quant-native
(validator, router). The seed fills ONLY ``tool`` (one code-execution sandbox)
and leaves the other six empty, so every component the evolve-agent adds must
earn its place via measured OOS delta (attribution purity).

A ``Component`` carries real ``content`` (used to assemble the quant_agent's
context in real mode) and a mock ``effect`` tag (used by the deterministic mock
world model). An ``Edit`` is one add/update/delete on one slot, carrying the
falsifiable change-manifest fields (failure_evidence -> root_cause ->
targeted_fix -> predicted_fixes/risk_tasks).
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field

SLOTS = ("tool", "middleware", "skill", "prompt", "validator", "memory", "router")


@dataclass
class Component:
    name: str
    slot: str
    content: str = ""          # real-mode: injected into agent context / verifier
    effect: str = ""           # mock-mode: world-model tag (e.g. exec_ok, probe_enforce)
    origin: str = "evolved"    # "seed" | "evolved"


@dataclass
class Edit:
    """One harness edit + its falsifiable change manifest."""

    op: str                    # "add" | "update" | "delete"
    slot: str
    component_name: str
    content: str = ""
    effect: str = ""
    # change-manifest (HARNESS.md v1.0 fields)
    summary: str = ""
    failure_evidence: str = ""
    root_cause: str = ""
    targeted_fix: str = ""
    predicted_fixes: list[str] = field(default_factory=list)
    risk_tasks: list[str] = field(default_factory=list)
    rationale: str = ""

    def signature(self) -> str:
        """Normalized identity for the rejected-edit buffer (no semantic dedup;
        SkillOpt-style: exact match only). Hashes the FULL normalized content so
        two edits differing only past char 120 do not collide."""
        content_hash = hashlib.md5(self.content.strip().lower().encode()).hexdigest()[:12]
        return f"{self.op}:{self.slot}:{self.component_name}:{self.effect}:{content_hash}".lower()


class Harness:
    def __init__(self) -> None:
        self.slots: dict[str, dict[str, Component]] = {s: {} for s in SLOTS}

    # -- inspection --------------------------------------------------------- #
    def components(self, slot: str) -> dict[str, Component]:
        return self.slots[slot]

    def has(self, slot: str, name: str) -> bool:
        return name in self.slots[slot]

    def get(self, slot: str, name: str) -> Component | None:
        return self.slots[slot].get(name)

    def all_components(self) -> list[Component]:
        return [c for slot in SLOTS for c in self.slots[slot].values()]

    # -- mutation ----------------------------------------------------------- #
    def clone(self) -> "Harness":
        return copy.deepcopy(self)

    def apply(self, edit: Edit) -> None:
        if edit.slot not in SLOTS:
            raise ValueError(f"unknown slot {edit.slot!r}")
        bucket = self.slots[edit.slot]
        if edit.op == "delete":
            bucket.pop(edit.component_name, None)
        elif edit.op in ("add", "update"):
            bucket[edit.component_name] = Component(
                name=edit.component_name,
                slot=edit.slot,
                content=edit.content,
                effect=edit.effect,
            )
        else:
            raise ValueError(f"unknown op {edit.op!r}")

    # -- real-mode context assembly ---------------------------------------- #
    def assemble_system_prompt(self) -> str:
        """Concatenate prompt + skill + memory + validator instructions for the
        real quant_agent. (Tools/middleware are wired by the runner.)"""
        parts: list[str] = []
        for slot in ("prompt", "skill", "memory", "validator"):
            for c in self.slots[slot].values():
                if c.content:
                    parts.append(f"[{slot}:{c.name}]\n{c.content}")
        return "\n\n".join(parts)

    def tool_names(self) -> list[str]:
        return list(self.slots["tool"].keys())

    # -- summary ------------------------------------------------------------ #
    def summary(self) -> dict[str, list[str]]:
        return {s: list(self.slots[s].keys()) for s in SLOTS if self.slots[s]}

    def signature(self) -> str:
        """Content hash of the whole harness (for the deliverable cache). Stable
        within a run: every candidate is `clone() + one edit`, so component
        insertion order is deterministic (the hash is insertion-order-sensitive)."""
        return hashlib.md5(json.dumps(self.to_state(), sort_keys=True).encode()).hexdigest()

    # -- (de)serialization for checkpoint/resume --------------------------- #
    def to_state(self) -> dict:
        return {s: [{"name": c.name, "content": c.content, "effect": c.effect, "origin": c.origin}
                    for c in self.slots[s].values()] for s in SLOTS}

    @staticmethod
    def from_state(state: dict) -> "Harness":
        h = Harness()
        for slot, comps in state.items():
            for c in comps:
                h.slots[slot][c["name"]] = Component(
                    name=c["name"], slot=slot, content=c.get("content", ""),
                    effect=c.get("effect", ""), origin=c.get("origin", "evolved"))
        return h


def seed_harness() -> Harness:
    """Minimal seed: one tool (deterministic code-execution sandbox), six empty slots."""
    h = Harness()
    h.slots["tool"]["code_exec"] = Component(
        name="code_exec",
        slot="tool",
        content=(
            "code_exec: run the candidate `solve(inputs)` function and return its output. "
            "Deterministic, sandboxed, with a wall-clock timeout."
        ),
        effect="exec_ok",
        origin="seed",
    )
    h.slots["tool"]["xlsx_writer"] = Component(
        name="xlsx_writer",
        slot="tool",
        content=(
            "xlsx_writer: produce an .xlsx workbook deliverable by emitting a Python "
            "code block using openpyxl that builds and saves the file; it is run in a "
            "sandbox and the produced workbook is captured and graded."
        ),
        effect="artifact_ok",
        origin="seed",
    )
    return h
