This is a bounded component-activation experiment, not a from-scratch task.
A strategy produced earlier in the same AP-3 run is already staged at
`/app/output/strategy.py`, with a read-only copy at
`/app/data/probe_seed_strategy.py`.

Read the complete public T26 contract above and inspect the staged strategy.
Invoke `check_strategy_artifact` early with the seven required functions and
the contract's datetime and determinism conventions.  Reconcile its diagnostics
against the public contract, make only grounded repairs, invoke the component
again after editing, and leave the best runnable strategy at
`/app/output/strategy.py`.

Do not inspect checker code, reference solutions, expected values, property
verdict files, or credentials.
