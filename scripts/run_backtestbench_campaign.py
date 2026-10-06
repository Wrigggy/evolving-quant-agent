#!/usr/bin/env python3
"""Run or resume a BacktestBench automated evolution campaign.

Uses research_campaign.advance_campaign() to advance one stage at a time,
looping until the campaign is complete or stopped. Each call to
advance_campaign() is durable: state is checkpointed before returning.

Usage:
    python scripts/run_backtestbench_campaign.py \
        --plan data/backtestbench/CAMPAIGN_PLAN_R1.json \
        --state-dir /data/qea-julius-storage/runs/bc-campaign-r1 \
        --config configs/rootless_backtestbench.json \
        --evolver-config configs/evolver-pro.json \
        --public-root /data/backtestbench/public \
        --trusted-root /data/backtestbench/trusted \
        --worker /path/to/initial_harness \
        --worker-image sha256:... \
        --evolver-image sha256:... \
        --proxy-image sha256:...

The --state-dir must be stable across runs. The campaign is initialized on
the first run and resumed on subsequent runs automatically.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.backtestbench_campaign_backend import BacktestBenchBackend
from qea.research_campaign import (
    ResearchCampaignError,
    advance_campaign,
    initialize_campaign,
    validate_campaign_plan,
)
from qea.worker_identity import hash_worker_directory


_TERMINAL_STATUSES = {"complete", "stopped", "failed"}


def _print_phase(state: dict) -> None:
    phase = state.get("phase", "?")
    status = state.get("status", "?")
    round_idx = state.get("round_index", "?")
    n_rounds = len(state.get("plan", {}).get("rounds", []))
    completed = len(state.get("completed_rounds", []))
    print(
        f"  phase={phase} status={status} "
        f"round={round_idx}/{n_rounds} completed_rounds={completed}",
        flush=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True,
                        help="Path to the campaign plan JSON")
    parser.add_argument("--state-dir", type=Path, required=True,
                        help="Directory for campaign state and stage artefacts")
    parser.add_argument("--config", type=Path, required=True,
                        help="Rootless infrastructure config for Worker sandbox")
    parser.add_argument("--evolver-config", type=Path, required=True,
                        help="Evolver model config")
    parser.add_argument("--public-root", type=Path, required=True,
                        help="BacktestBench public task data root")
    parser.add_argument("--trusted-root", type=Path, required=True,
                        help="BacktestBench trusted answer root (never sent to Workers)")
    parser.add_argument("--worker", type=Path, required=True,
                        help="Initial harness Worker directory")
    parser.add_argument("--worker-image", required=True,
                        help="Worker sandbox container image ref")
    parser.add_argument("--evolver-image", required=True,
                        help="Evolver sandbox container image ref")
    parser.add_argument("--proxy-image", required=True,
                        help="Credential proxy container image ref")
    parser.add_argument("--concurrency", type=int, default=4,
                        help="Worker concurrency per episode (default 4)")
    parser.add_argument("--scoring-mode", default="official",
                        help="BacktestBench scoring mode (default: official)")
    parser.add_argument("--condition-id", default="",
                        help="Campaign condition ID (defaults to state-dir name)")
    parser.add_argument("--max-stages", type=int, default=0,
                        help="Stop after this many stages; 0 means run to completion")
    parser.add_argument("--dry-run", action="store_true",
                        help="Initialize and validate plan without running any stages")
    args = parser.parse_args(argv)

    # Load and validate plan.
    plan_path = args.plan.expanduser().resolve()
    if not plan_path.is_file():
        print(f"ERROR: plan not found: {plan_path}", file=sys.stderr)
        return 1
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    try:
        validated_plan = validate_campaign_plan(plan)
    except ResearchCampaignError as exc:
        print(f"ERROR: campaign plan is invalid: {exc}", file=sys.stderr)
        return 1
    print(f"Plan: {validated_plan['campaign_id']}")
    print(f"  {len(validated_plan.get('rounds', []))} rounds, "
          f"net_gains_required={validated_plan['rounds'][0]['revision_options'].get('promotion_net_gains_required', 'none') if validated_plan.get('rounds') else 'n/a'}")

    # Verify initial worker dir.
    worker_dir = args.worker.expanduser().resolve()
    if not worker_dir.is_dir():
        print(f"ERROR: worker directory not found: {worker_dir}", file=sys.stderr)
        return 1
    harness_id = hash_worker_directory(worker_dir)
    print(f"Initial H: {harness_id[:12]}... at {worker_dir}")

    # Verify initial H matches plan.
    plan_h = validated_plan.get("initial_research_parent", {}).get("harness_id", "")
    if plan_h and plan_h != harness_id:
        print(
            f"WARNING: worker dir hash {harness_id[:12]} differs from "
            f"plan initial_research_parent {plan_h[:12]}",
            file=sys.stderr,
        )

    # Set up state directory and state path.
    state_dir = args.state_dir.expanduser().resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "CAMPAIGN-STATE.json"

    # Initialize campaign (idempotent if already exists).
    try:
        state = initialize_campaign(plan=validated_plan, state_path=state_path)
    except ResearchCampaignError as exc:
        print(f"ERROR: campaign initialization failed: {exc}", file=sys.stderr)
        return 1
    print(f"Campaign state: {state_path}")
    _print_phase(state)

    if args.dry_run:
        print("Dry run complete — no stages executed.")
        return 0

    # Build backend.
    condition_id = args.condition_id or state_dir.name
    backend_config = {
        "config_path": str(args.config.expanduser().resolve()),
        "evolver_config_path": str(args.evolver_config.expanduser().resolve()),
        "public_root": str(args.public_root.expanduser().resolve()),
        "trusted_root": str(args.trusted_root.expanduser().resolve()),
        "worker_image_ref": args.worker_image,
        "evolver_image_ref": args.evolver_image,
        "proxy_image_ref": args.proxy_image,
        "concurrency": args.concurrency,
        "scoring_mode": args.scoring_mode,
    }
    backend = BacktestBenchBackend(
        config=backend_config,
        run_root=state_dir / "stages",
        condition_id=condition_id,
    )
    backends = {backend.backend_id: backend}

    # Run campaign loop.
    stages_run = 0
    while True:
        # Reload state from disk to get latest.
        state = json.loads(state_path.read_text(encoding="utf-8"))
        status = state.get("status", "")
        if status in _TERMINAL_STATUSES:
            break
        if args.max_stages > 0 and stages_run >= args.max_stages:
            print(f"Reached max-stages={args.max_stages}, stopping.")
            break

        print(f"\n[stage {stages_run + 1}]")
        _print_phase(state)

        try:
            state = advance_campaign(state_path=state_path, backends=backends)
        except ResearchCampaignError as exc:
            print(f"ERROR: campaign advance failed: {exc}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("\nInterrupted. State is checkpointed; re-run to resume.")
            return 130

        stages_run += 1
        _print_phase(state)

        # Brief pause between stages to avoid hammering the scheduler.
        if state.get("status") not in _TERMINAL_STATUSES:
            time.sleep(0.5)

    # Final report.
    status = state.get("status", "?")
    print(f"\nCampaign finished: status={status} stages_run={stages_run}")

    terminal = state.get("terminal_comparison")
    if isinstance(terminal, dict):
        selected = terminal.get("selected", "?")
        win_claim = terminal.get("full_panel_win_claim")
        print(f"Terminal comparison: selected={selected} win_claim={win_claim}")
        for backend_id, comp in terminal.get("comparisons", {}).items():
            net = comp.get("net_task_gains")
            ngr = comp.get("net_task_regressions")
            print(f"  {backend_id}: selected={comp.get('selected')} "
                  f"net_gains={net} net_regressions={ngr}")

    accounting = state.get("accounting", {})
    cost = accounting.get("provider_cost_usd")
    requests = accounting.get("provider_requests")
    print(f"Total cost: {'${:.4f}'.format(cost) if cost is not None else 'unknown'} "
          f"requests: {requests}")

    return 0 if status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
