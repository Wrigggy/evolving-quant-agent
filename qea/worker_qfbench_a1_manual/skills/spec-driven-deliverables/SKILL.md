---
name: spec-driven-deliverables
description: Load before implementing a quantitative task with dense public specifications, formulas, parameter files, precise output schemas, or unavailable optional packages. It provides a bounded spec-first workflow that avoids convention drift and dependency-search loops.
---

# Spec-driven quantitative deliverables

Use this workflow only when the public task actually has a dense numerical or
artifact contract. Keep simple tasks simple.

1. Inventory the public files once. Read the instruction plus every shipped
   formula, parameter, convention, schema, and template file that constrains the
   requested output. Treat those task-local public files as authoritative.
2. Before coding, make a compact contract ledger: required filenames and
   fields, row/key order, units, signs, date rules, methods, seeds, sample sizes,
   edge cases, and rounding. Do not silently replace a stated method with a
   textbook-equivalent convention.
3. Check an optional dependency at most once. Do not spend the run installing
   packages, probing the network, or searching for hidden solutions. If a
   dependency is absent, use available NumPy, pandas, or SciPy primitives and
   implement only the formulas supplied by the public task.
4. Write the smallest structurally valid deliverables early. Then fill in the
   computations with deterministic, vectorized code where appropriate. Bound
   numerical searches and simulation work to the task's stated requirements.
5. Re-open every final artifact. Check existence, parseability, exact schema,
   key and column order, shapes, finite values, identities or invariants stated
   by the task, and the task's exact rounding policy. Fix only discrepancies
   against the public contract; do not add unrequested outputs or re-derive a
   matching deliverable into a different convention.

Leave enough time to save and validate the final artifacts. Once the contract
checks pass, finish instead of starting another exploratory loop.
