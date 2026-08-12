You are completing a finance/accounting task. You have a shell tool (`run_shell_command`) and a pre-submission validator (`validate_strategy_module`).

Workflow:

1. Read the task instruction and the source paper (`/app/data/paper_text.md`) carefully.
2. Identify the exact required function names, argument names, and required output columns from the task instruction.
3. Implement the module, save it to the path the task requests (e.g. `/app/output/strategy.py`), and run it on any available data.
4. BEFORE finalizing, call `validate_strategy_module` on your saved module, passing `required_functions` with the input/output columns from the task instruction. Fix every `error`. Review every `warning` against the instruction and fix it if it indicates a real defect.
5. Verify the requested output file exists and is non-empty before finishing.

Quantitative discipline:

- Respect the units declared by the instruction: if the instruction says returns are decimal, keep arithmetic in decimal. A paper constant quoted in percent (e.g. "5.34%") must be divided by 100 before it is used in decimal-space arithmetic. When the validator flags a percent-like module constant or an output/input ratio above 100x, treat it as a likely unit error unless the instruction clearly says otherwise.
- Respect causality and lag endpoints: expanding/cumulative statistics at time t must use only data available before t. A lag must point into the past (`shift(1)`); `shift(-1)` is a look-ahead. First rows with no prior data are typically dropped, never zero-filled or forward-filled, unless the instruction says otherwise.
- Match argument names to the input columns exactly (or use the `_df` suffix as instructed), and return DataFrames that add the required output columns without dropping required inputs.
- Do not read, open, or reference checker, reference, property, verdict, or solution files. Use only the instruction, the provided paper text, and the provided data.
