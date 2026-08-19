# ICLR 2027 paper workspace

This directory is the continuously updated LaTeX manuscript for the current
research route.

## Template status

This workspace vendors the unmodified official ICLR 2027 style and bibliography
files linked by the author guide. If the conference updates its package before
submission, replace the vendored files from the same official source and build
the manuscript again.

Current ICLR 2027 rules to track:

- abstract deadline: 2026-09-18 AOE;
- full paper deadline: 2026-09-25 AOE;
- initial main text: at most 9 pages, excluding references;
- double-blind submission;
- required AI-use statement;
- reproducibility and ethics statements are recommended.

Primary source: <https://iclr.cc/Conferences/2027/AuthorGuidelines>

Official style package:
<https://media.iclr.cc/Conferences/ICLR2027/iclr-2027-style-files.zip>

## Build

```bash
cd paper/iclr2027
make
```

This uses `latexmk` when available. `make clean` removes LaTeX build products.

## Update protocol after every experiment

1. Add the exact measured values to `experiment_data/experiment_values.tex`.
2. Update `tables/experiment_claim_ledger.tex` with one concise row.
3. Add or revise the relevant paragraph in `sections/05_results.tex`.
4. Update the corresponding interpretation in `sections/06_analysis.tex`.
5. Keep proposed, measured, negative, and superseded evidence distinct.
6. Do not turn invariant-level mechanism evidence into an official benchmark
   claim; report both when both exist.

Use these draft commands consistently:

- `\Measured{...}` for evidence already produced by an experiment;
- `\Proposed{...}` for a method or protocol not yet tested;
- `\Pending{...}` for an unfilled result cell;
- `\Boundary{...}` for a claim limitation that must remain visible.

The draft commands are intentionally visible in color. Remove draft labels only
when the corresponding text has been checked for submission.

## File map

- `main.tex`: title, anonymity, package setup, and section order.
- `sections/`: paper text in submission order.
- `experiment_data/experiment_values.tex`: reusable measured-value macros.
- `tables/experiment_claim_ledger.tex`: experiment-to-claim status table.
- `references.bib`: manuscript bibliography.
- `appendix.tex`: supplementary method and evidence details.
