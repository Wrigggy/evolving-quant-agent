"""The two agents + the ADB-lite diagnosis.

quant_agent  : the worker. Produces a solution (A: a `solve(inputs)` function;
               B: a deliverable). Renamed from "code_agent" because finance work
               differs from coding.
evolve_agent : the meta. Reads eval results + diagnosis + the rejected-edit
               buffer and proposes exactly ONE edit (edit budget L_t = 1).
diagnose     : ADB-lite. Distills the eval into a root-cause tag the evolve_agent
               can act on (the EVAL -> DIAGNOSE link in the causal chain).

Mock mode is fully scripted and deterministic; it exercises every path:
iter1 EFFECTIVE (add integrity_guard) -> iter2 HARMFUL (break code_exec, rolled
back) -> iter3 overfit (memorizes base, killed by the perturbation probe) ->
iter4 re-proposes the iter2 edit (blocked by the rejected-edit buffer).
"""

from __future__ import annotations

import json

from .harness import SLOTS, Edit


# --------------------------------------------------------------------------- #
# quant_agent.                                                                 #
# --------------------------------------------------------------------------- #
def quant_agent_solve(task, harness, *, mock: bool, llm):
    if mock:
        return _quant_solve_mock(task, harness)
    return _quant_solve_real(task, harness, llm)


def _quant_solve_mock(task, harness):
    if task.pile == "B":
        return ""  # mock soft judge keys off the harness, not the text
    code_exec = harness.get("tool", "code_exec")
    runnable = code_exec is not None and code_exec.effect != "exec_broken"
    parameterized = harness.has("validator", "integrity_guard")
    memorized = harness.has("validator", "overfit_cache")
    return {"runnable": runnable, "parameterized": parameterized, "memorized": memorized}


def _quant_solve_real(task, harness, llm):
    sys = harness.assemble_system_prompt()
    if task.pile == "A":
        prompt = (
            f"{sys}\n\nTASK: {task.prompt}\n\n"
            "Return ONLY a Python code block defining `def solve(inputs):` that "
            "returns a dict of {metric: value}. Use only the `math` module."
        )
        txt = llm.complete(prompt, role="quant_agent")
        return _extract_code(txt)
    prompt = f"{sys}\n\nTASK: {task.prompt}\n\nWrite the deliverable."
    return llm.complete(prompt, role="quant_agent")


def _extract_code(txt: str) -> str:
    if "```" in txt:
        parts = txt.split("```")
        for i in range(1, len(parts), 2):
            block = parts[i]
            if block.startswith("python"):
                block = block[len("python"):]
            if "def solve" in block:
                return block.strip()
    return txt.strip()


# --------------------------------------------------------------------------- #
# diagnose (ADB-lite).                                                         #
# --------------------------------------------------------------------------- #
def diagnose(eval_summary, *, mock: bool, llm):
    if mock:
        return _diagnose_mock(eval_summary)
    return _diagnose_real(eval_summary, llm)


def _diagnose_mock(eval_summary) -> dict:
    results = eval_summary.results
    any_broken = any((r.error or "").startswith("code_exec") for r in results.values())
    hardcoded = [tid for tid, r in results.items() if r.pile == "A" and r.base_pass and not r.probe_pass]
    walls = [tid for tid, r in results.items() if "wall" in tid and not r.base_pass]
    if any_broken:
        tag = "ToolBroken"
        overview = "code_exec is broken: A-tasks error on the base inputs."
    elif hardcoded:
        tag = "Hardcoding"
        overview = (
            f"{len(hardcoded)} A-task(s) pass the base inputs but FAIL the perturbation "
            "probe -> hardcoded constants, no general solution (no integrity guard)."
        )
    elif walls:
        tag = "InsufficientCapability"
        overview = f"{len(walls)} task(s) fail even the base inputs -> base-capability gap, not harness-fixable."
    else:
        tag = "None"
        overview = "No dominant failure pattern."
    return {"root_cause_tag": tag, "overview": overview, "hardcoded": hardcoded, "walls": walls}


def _diagnose_real(eval_summary, llm) -> dict:
    fails = [
        f"- {r.task_id} [{r.subtype}]: base={r.base_pass} probe={r.probe_pass} err={r.error}"
        for r in eval_summary.results.values()
        if not r.oos_pass
    ]
    prompt = (
        "You are an Agent Debugger for a quant harness. Classify the dominant "
        "failure into ONE tag from {Hardcoding, WrongFormula, MissingEdgeCase, "
        "BadFormat, ToolBroken, InsufficientCapability} and give a one-line "
        "overview. Return JSON {\"root_cause_tag\":..., \"overview\":...}.\n\n"
        "FAILURES:\n" + "\n".join(fails)
    )
    txt = llm.complete(prompt, role="evolve_agent")
    d = _parse_first_json(txt)
    if not isinstance(d, dict):
        return {"root_cause_tag": "Unknown", "overview": txt[:200], "hardcoded": [], "walls": []}
    d.setdefault("hardcoded", [])
    d.setdefault("walls", [])
    return d


# --------------------------------------------------------------------------- #
# evolve_agent.                                                                #
# --------------------------------------------------------------------------- #
def evolve_agent_propose(iteration, eval_summary, diagnosis, harness, buffer, *, mock: bool, llm):
    if mock:
        return _propose_mock(iteration, eval_summary)
    return _propose_real(iteration, eval_summary, diagnosis, harness, buffer, llm)


def _propose_mock(iteration: int, eval_summary):
    results = eval_summary.results
    nonwall_failing = [
        tid for tid, r in results.items()
        if r.pile == "A" and "wall" not in tid and not r.oos_pass
    ]
    walls = [tid for tid, r in results.items() if "wall" in tid]

    broken_edit = Edit(
        op="update", slot="tool", component_name="code_exec", effect="exec_broken",
        content="micro-optimized exec hot path (drops the inputs dict)",
        summary="Optimize code_exec for speed",
        failure_evidence="code_exec latency on long amortization schedules.",
        root_cause="(hypothesis) exec overhead; a faster path may also crack the hard amortization case.",
        targeted_fix="Rewrite the code_exec hot path.",
        predicted_fixes=list(walls), risk_tasks=[],
        rationale="Faster exec; expected to also fix the hard amortization wall.",
    )

    if iteration == 1:
        return Edit(
            op="add", slot="validator", component_name="integrity_guard", effect="probe_enforce",
            content=(
                "Produce a GENERAL, parameterized solve(inputs); it will be re-run on "
                "perturbed inputs. Never hardcode a constant fitted to one instance."
            ),
            summary="Add integrity_guard: force parameterized, probe-robust solutions",
            failure_evidence="6 A-tasks pass base inputs but fail the perturbation probe (hardcoded).",
            root_cause="Hardcoding: no validator forces a general solution.",
            targeted_fix="Add validator-slot integrity_guard enforcing parameterized solutions + the probe.",
            predicted_fixes=nonwall_failing, risk_tasks=[],
            rationale="Probe-robustness is the OOS signal; parameterization should flip all hardcoded-but-runnable tasks.",
        )
    if iteration == 2:
        return broken_edit
    if iteration == 3:
        return Edit(
            op="add", slot="validator", component_name="overfit_cache", effect="overfit",
            content="Cache the known answer for seen base inputs to pass the hard case.",
            summary="Memorize answers for the hard amortization case",
            failure_evidence="A_amort_wall still fails after integrity_guard.",
            root_cause="(hypothesis) the hard case needs a lookup table.",
            targeted_fix="Add overfit_cache validator memorizing base answers.",
            predicted_fixes=list(walls), risk_tasks=[],
            rationale="Memorized answers should make the hard case pass.",
        )
    # iter 4: re-propose the falsified iter-2 edit -> must be blocked by the buffer.
    return broken_edit


def _propose_real(iteration, eval_summary, diagnosis, harness, buffer, llm):
    fails = [
        f"- {r.task_id} [{r.subtype}] base={r.base_pass} probe={r.probe_pass} err={r.error}"
        for r in eval_summary.results.values() if not r.oos_pass
    ]
    prompt = (
        "You evolve a quant agent harness with 7 slots "
        "(tool/middleware/skill/prompt/validator/memory/router). The seed has only "
        "the code_exec tool. Propose EXACTLY ONE edit, justified by evidence.\n\n"
        f"CURRENT HARNESS: {json.dumps(harness.summary())}\n\n"
        f"DIAGNOSIS: {diagnosis.get('root_cause_tag')} — {diagnosis.get('overview')}\n\n"
        f"FAILING TASKS:\n" + "\n".join(fails) + "\n\n"
        f"REJECTED-EDIT BUFFER:\n{buffer.render()}\n\n"
        "Return ONLY JSON: {op, slot, component_name, content, summary, "
        "failure_evidence, root_cause, targeted_fix, predicted_fixes (task ids), "
        "risk_tasks (task ids), rationale}."
    )
    txt = llm.complete(prompt, role="evolve_agent")
    d = _parse_first_json(txt)
    # Edit-budget L_t=1 + fail-safe: a malformed / multi-edit / key-missing
    # response yields no edit this iteration (the loop treats None as a no-op)
    # rather than crashing the run.
    if not isinstance(d, dict) or not d.get("slot") or not d.get("component_name"):
        print("[evolve_agent] no valid single edit parsed from response; skipping iteration")
        return None
    if d.get("slot") not in SLOTS or d.get("op", "add") not in ("add", "update", "delete"):
        print(f"[evolve_agent] invalid slot/op ({d.get('slot')}/{d.get('op')}); skipping iteration")
        return None
    return Edit(
        op=d.get("op", "add"), slot=d["slot"], component_name=str(d["component_name"]),
        content=str(d.get("content", "")), effect=str(d.get("effect", "")),
        summary=str(d.get("summary", "")), failure_evidence=str(d.get("failure_evidence", "")),
        root_cause=str(d.get("root_cause", "")), targeted_fix=str(d.get("targeted_fix", "")),
        predicted_fixes=list(d.get("predicted_fixes", []) or []), risk_tasks=list(d.get("risk_tasks", []) or []),
        rationale=str(d.get("rationale", "")),
    )


def _parse_first_json(txt: str) -> dict | None:
    """Return the first balanced JSON object in txt (handles prose + fences +
    trailing extra objects), or None if none decodes."""
    dec = json.JSONDecoder()
    i = txt.find("{")
    while i >= 0:
        try:
            obj, _ = dec.raw_decode(txt[i:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        i = txt.find("{", i + 1)
    return None
