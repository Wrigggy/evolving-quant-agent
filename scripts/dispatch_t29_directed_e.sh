#!/usr/bin/env bash
# T29 temporal_causality directed Evolver round.
# Run on bc-server (julius@...) after confirming SSH connectivity.
# All paths are bc-server paths derived from qr-family-own-pair-refinement inputs.
#
# CONSTRAINT: failure_class=temporal_causality → requires executable component.
# Evolver systemprompt now enforces this (Oct 6 2026 prompt-skepticism update).
# A prompt-only ACT for temporal_causality is not acceptable.
#
# Usage:
#   ssh julius@<bc-server> 'bash -s' < scripts/dispatch_t29_directed_e.sh
#   OR copy to server and run directly.

set -euo pipefail

# ── Config paths (from qr-family-own-pair-refinement inputs) ────────────────
CONFIG_PATH="/data/qea-julius-storage/deploy/qr-evolver-pro-r2-20261005-r1/configs/quantcodeeval_deepseek_v4_flash_relation_policy_v6.json"
EVOLVER_CONFIG_PATH="/data/qea-julius-storage/deploy/qr-evolver-pro-r2-20261005-r1/configs/evolver-pro.json"
EVOLVER_IMAGE="sha256:adb2a68688488fe94e0fffbe1ffecf8c5416a4c3d2325cee6379e854521b29d2"
PROXY_IMAGE="sha256:9eae2354ea4882aa0249d17bf1467d57b2bba29d99dca5e75512f9da6c2b9b67"
EVOLVER_PROFILE="early_intervention_full_harness_v1"

# ── T29 parent worker dir (from qr-family-failure-research) ─────────────────
PARENT_WORKER_DIR="/data/qea-julius-storage/runs/qr-family-failure-research-20261005-r1/revisions/qr-family-failure-revision-20261005-r1/evolutions/iteration-0001/candidate"

# ── QCE release / panel ──────────────────────────────────────────────────────
RELEASE_PATH="/data/qea-julius-storage/deploy/qr-capability-family-screen-20261005-r1"
PANEL_PATH="${RELEASE_PATH}/data/PANEL.json"

# ── T29 replay routes (from qr-family-own-pair-refinement inputs) ────────────
T29_PUBLIC_ROOT="/data/qea-julius-storage/runtime/quantcodeeval-breadth-20260816/public"
T29_TASK_PANEL_PATH="${RELEASE_PATH}/data/quantcodeeval/PANEL_PUBLIC_CANARY_20260928.json"
T29_TRUSTED_ROOT="/data/qea-julius-storage/runtime/quantcodeeval-breadth-20260816/trusted"

# ── Run dirs ─────────────────────────────────────────────────────────────────
PYTHON="/home/julius/qea/runtime/venvs/rootless/bin/python"
QEA_SRC="/home/julius/qea/src"
RUN_DIR="/data/qea-julius-storage/runs/qr-t29-temporal-causality-directed-e-20261006-r1"

# ── Research memory: use the latest family own-pair refinement R ─────────────
RESEARCH_MEMORY_PATH="/data/qea-julius-storage/runs/qr-family-own-pair-refinement-20261005-r1/revisions/qr-family-own-pair-refinement-revision-20261005-r1/evolutions/iteration-0001/${MEMORY_RESULT:-research-operation-memory.json}"

echo "=== T29 temporal_causality directed Evolver round ==="
echo "Run dir : $RUN_DIR"
echo "Parent H: $PARENT_WORKER_DIR"
echo "Profile : $EVOLVER_PROFILE"
echo ""
echo "NOTE: temporal_causality failure class."
echo "Evolver must produce tools/ or validator/ component (prompt-only NOT accepted)."
echo ""

mkdir -p "$RUN_DIR"

# ── Dispatch ──────────────────────────────────────────────────────────────────
cd "$QEA_SRC"

"$PYTHON" scripts/run_quantcodeeval_v2_activation.py \
  --config          "$CONFIG_PATH" \
  --release         "$RELEASE_PATH" \
  --run-dir         "$RUN_DIR" \
  --evolver-image   "$EVOLVER_IMAGE" \
  --proxy-image     "$PROXY_IMAGE" \
  --evolver-profile "$EVOLVER_PROFILE" \
  --prior-scored-candidate-run \
    "/data/qea-julius-storage/runs/qr-family-own-pair-refinement-parent-qce-20261005-r1/episodes/qr-family-own-pair-refinement-pair-20261005-r1-parent-qce" \
  2>&1 | tee "$RUN_DIR/dispatch.log"

echo ""
echo "=== Dispatch complete ==="
echo "Check $RUN_DIR for ACTIVATION-RESULT.json"
