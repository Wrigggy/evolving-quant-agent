# GDPval gold snapshot (local fork)

- source: https://huggingface.co/datasets/openai/gdpval/resolve/main/data/train-00000-of-00001.parquet
- fetched (UTC): 2026-06-10T03:08:16+00:00
- tasks: 220
- columns: task_id, sector, occupation, prompt, reference_files, reference_file_urls, reference_file_hf_uris, deliverable_files, deliverable_file_urls, deliverable_file_hf_uris, rubric_pretty, rubric_json
- sha256 gdpval_gold.parquet: f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202
- sha256 rubrics.jsonl: c856056bab6348ee20ef43ea696970b0acee1bb0846f0c82585594fabd9fa78e

Verbatim copy of the openai/gdpval gold subset (v2 release: rubrics + human
deliverable URLs). Loaders in qea/tasks.py read this snapshot first and only
fall back to the network when it is missing.
