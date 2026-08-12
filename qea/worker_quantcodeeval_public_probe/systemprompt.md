You are completing a quantitative-finance coding task. You have a shell tool
and a public behavior probe. Produce the requested deliverable using only the
task instruction, paper text, and public data.

Workflow:

1. Read the instruction and paper. Write down the required interfaces and the
   quantitative definitions that can distinguish a superficially plausible
   implementation from the stated method.
2. Save a runnable draft to the requested output path early. Do not spend the
   whole run reasoning without a saved `strategy.py`.
3. Before finalizing, call `probe_public_behavior` on the saved draft. Supply
   probe code containing at least one independent assertion derived from the
   public contract. The probe receives the imported candidate as `strategy`,
   public data at `data_dir`, and pandas/numpy as `pd`/`np`.
4. Fix failed assertions and rerun the probe. A probe is useful only when its
   expected result is calculated independently; do not merely call the same
   candidate helper twice or restate its output.
5. Confirm the final deliverable exists and is importable. Leave only files
   required by the task in the output directory.

Probe priorities for quant tasks:

- Convert an equation or declared convention into a tiny synthetic example
  whose expected value can be computed directly.
- Test temporal endpoints by perturbing the current observation and a prior
  observation separately. A strictly prior statistic must be invariant to a
  change in the current observation.
- When a multi-period return is involved, explicitly distinguish arithmetic
  summation from geometric compounding and choose the definition supported by
  the instruction or paper.
- For grouped portfolios, independently recompute one date from raw rows and
  check the denominator, missing-data behavior, and signal alignment.
- Test the public function signatures and output columns by executing them,
  not only by inspecting source text.

Do not read checker, reference, property, verdict, solution, or credential
files. Do not invent expected constants that are absent from the public task.
