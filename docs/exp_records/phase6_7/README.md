# Phase 6-7 GDPval Level-B evolution — archived artifacts

Small durable copies of the key experiment outputs (the full `results/` tree is
gitignored; per-task caches and worker snapshots stay local-only).

- `phase6_gdpval_qwenflash_evolve_r{1,2,3_archive}/iter_*_manifest.json` — every
  evolution iteration's verdict/kept/edit/diagnosis + per-task candidate scores.
  Train trajectory across the three legs: 0.536 -> 0.588 -> 0.599 -> 0.695.
- `phase6_gdpval_heldout_stats.json` — first pooled held-out treatment (22 tasks,
  r2-final): +0.043, CI includes 0.
- `phase6_gdpval_heldout_stats_final.json` — repeat-averaged version (+0.043,
  CI [-0.046, +0.135], sign test p=1.0).
- `ph6_r3final_heldout_stats.json` — r3-final worker, 2x22 repeat-averaged:
  pooled +0.010 (0.1 sigma) — the train gain does not measurably transfer at
  this scale; motivated protocol v2 (n_samples / paired gate / confirm gate).
- `ph7_hard40_probe_summary.json` — seed on the 40 hardest/multimodal tasks of
  the 205-task all-occupation pool (mean 0.694; xlsx-deliverable mean 0.445 =
  the systematic weak spot; pptx 0.762 = not hard for the judge).
- `pool_difficulty.csv` — metadata difficulty/multimodal scoring of the pool.
- `hardcore_pool_ids.txt` — the 18-task measured-failure optimize pool used by
  the ph7_hardcore18_leg1 run.
