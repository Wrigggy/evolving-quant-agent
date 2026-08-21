# Point-in-time lineage refinement result

**Date:** 2026-08-21

**Status:** Complete with rollback

## Outcome

The retained point-in-time parent remains the earlier
`effective-state-reconciliation` candidate at 50/51 on
`13f-amendment-aware-crowding`. A valid second-lineage Evolver run eventually
selected `REFINE`, changed only the skill's canonical-label section, passed
admission and skill smoke, and activated in both a short probe and a normal-
budget Worker. The normal Worker completed all eight artifacts but scored
49/51, below the parent. The candidate was rolled back; no repeat or protection
was dispatched.

The refinement did not fully realize its own predicted transition. For one
CUSIP the delivered effective holdings still mixed `MICROSOFT CORP` and
`MICROSOFT CORP COM`. Two official failures also exposed a sign mismatch in
`summarypage_value_diff`. This is not a clean mechanism repair hidden by an
unrelated verifier ordering effect.

## What had to be repaired before the valid run

The first feedback attempt returned calibrated `ABSTAIN`: it could see the
50/51 score and Worker trace but not the exact parent skill as a direct
lineage-evidence file. The feedback builder now archives the tested parent
candidate next to its diff, prediction, and scored observation.

The next attempt exposed a second protocol bug. It still inherited
`COORDINATED_BREADTH`, forcing a second cross-task shared-mechanism discovery
during what should have been a within-lineage refinement. Its terminal decision
failed schema validation, and bounded systemd restarts then hit an ambiguous
cleaned lifecycle. The run is retained as setup-invalid. Feedback rounds now
use `LINEAGE_REFINEMENT`; they still require a target, bounded experiment spec,
history access, admission, and a structured decision, but do not repeat the
first-round novelty gate.

## Valid r4 chain

- Evolver decision: admitted `ACT`, operator `REFINE`.
- Candidate change: one skill file; no task ID, issuer, CUSIP, or expected
  answer embedded.
- Short probe: skill loaded, 7 turns, 12 tool calls, zero artifacts and 0/11.
  This is activation/completion-distance evidence only.
- Normal target: skill activated, 32 turns, 38 tool calls, eight artifacts,
  49/51 and reward 0.
- Selection: rollback to the 50/51 parent; no repeat and no protection.

The valid r4 Evolver-plus-target chain used 59 completed requests, 3,551,292
tokens, and $0.249454672. Including the two setup-localization attempts, the
full path used 81 completed requests, 4,646,332 tokens, and $0.52965072.

## Scale implications

This experiment validates a complete negative promotion path: runtime feedback
can produce a narrower next candidate, a short probe can establish component
reach, a normal target can reject it, and the parent remains unchanged. It also
identifies three concrete requirements for Main-0:

1. every feedback record carries the exact tested parent component source;
2. discovery and refinement use distinct decision stages; and
3. trace retrieval returns local excerpts instead of whole oversized JSONL
   lines.

Short probes remain diagnostics, not final-score gates. Conversely, a plausible
mechanism prediction is not enough to earn a repeat: the observed Worker must
realize the predicted transition or improve the target. If it does neither, the
controller rolls back without spending protection calls.

Compact evidence is in
[`data/breadth/MT_POINT_LINEAGE_REFINEMENT_RESULT.json`](../../data/breadth/MT_POINT_LINEAGE_REFINEMENT_RESULT.json).
Sanitized mirrors use the four run IDs recorded there.
