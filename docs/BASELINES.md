# Base baselines — Stirrup vs NexAU worker (GDPval finance, multimodal per-rubric grade)

Consolidated reference for the two worker substrates on the **same** GDPval finance
task set (~30 tasks, 6 occupations × 5), graded by the **same** runtime-independent
multimodal per-rubric pipeline (`qea/grading/render.py` + `qea/grading/multimodal_judge.py`,
judge `qwen/qwen3.7-plus`, k=2 median). Worker model `deepseek/deepseek-v4-pro`.

Source tables: Stirrup → [RESULTS_base_stirrup_e2b.md](RESULTS_base_stirrup_e2b.md);
NexAU → [RESULTS_gdpval_nexau.md](RESULTS_gdpval_nexau.md).

## Headline

| substrate | worker form | graded | mean multimodal | mean text-only | infra errors |
|---|---|---|---|---|---|
| **Stirrup** (code-first) | `qea/workers/stirrup_worker.py` on E2B | 26/30 | **0.807** | 0.787 | 4 (E2B timeout/disconnect/JSON) |
| **NexAU** (agent dir) | `qea/worker_gdpval/` (LocalSandbox) | 30/30 | **0.797** | 0.787 | 0 (after the connect-timeout fix) |

- **Port fidelity: −0.010 multimodal, statistically on par.** Migrating the worker
  substrate Stirrup→NexAU preserved deliverable quality. Text-only is identical (0.787).
- **Reliability differs by substrate, not by worker quality.** Stirrup lost 4 tasks to
  E2B infrastructure errors (sandbox timeout / server disconnect / a judge JSONDecodeError),
  excluded from its mean. NexAU (local sandbox) had 0 infra errors once
  `llm_config.timeout: 180` fixed the proxy TLS-handshake connect timeout.
- **Prior text-worker / text-grade baseline (no reference files): 0.618.** The
  file-producing worker + reference-file inputs lifted text-grade by **+0.169**; the
  multimodal grader input adds a further **+0.020** over text-only.

## Per-occupation (mean multimodal)

| occupation | Stirrup | NexAU |
|---|---|---|
| Personal Financial Advisors | 0.944 | 0.926 |
| Real Estate Brokers | 0.889¹ | 0.871 |
| Financial and Investment Analysts | 0.936¹ | 0.845 |
| Securities/Commodities Sales Agents | 0.768 | 0.777 |
| Financial Managers | 0.577¹ | 0.761 |
| Accountants and Auditors | 0.707¹ | 0.604 |

¹ Stirrup occupation means are over the tasks that graded (infra errors excluded), so
some occupations average fewer than 5 tasks — not directly comparable cell-by-cell to
NexAU's full 5. Use the per-task table below for like-for-like.

## Per-task (side by side; `—` = infra error, excluded from the mean)

| task_id | occupation | Stirrup mm | NexAU mm |
|---|---|---|---|
| 83d10b06-26d1-4636-a32c-23f92c57f30b | Accountants and Auditors | 0.992 | 0.611 |
| 7b08cd4d-df60-41ae-9102-8aaa49306ba2 | Accountants and Auditors | 0.742 | 0.843 |
| 7d7fc9a7-21a7-4b83-906f-416dea5ad04f | Accountants and Auditors | 0.842 | 1.000 |
| 43dc9778-450b-4b46-b77e-b6d82b202035 | Accountants and Auditors | 0.252 | 0.000 |
| ee09d943-5a11-430a-b7a2-971b4e9b01b5 | Accountants and Auditors | — | 0.568 |
| 8079e27d-b6f3-4f75-a9b5-db27903c798d | Financial and Investment Analysts | 0.927 | 0.691 |
| e21cd746-404d-4602-b9d2-01d2812c5b87 | Financial and Investment Analysts | 0.923 | 0.923 |
| 9e8607e7-a38a-491f-ace1-e5ea7dc477cb | Financial and Investment Analysts | 1.000 | 0.978 |
| c7d83f01-2874-4876-b7fd-52582ec99e1a | Financial and Investment Analysts | — | 0.755 |
| 46b34f78-6c06-4416-87e2-77b6d8b20ce9 | Financial and Investment Analysts | 0.895 | 0.878 |
| a1963a68-1bea-4bb1-b7e0-145c92a57449 | Financial Managers | 0.992 | 0.977 |
| 5f6c57dd-feb6-4e70-b152-4969d92d1608 | Financial Managers | 0.000 | 0.865 |
| b39a5aa7-cd1b-47ad-b249-90afd22f8f21 | Financial Managers | — | 0.645 |
| b78fd844-db76-448e-a783-5e9877cb74c2 | Financial Managers | 0.868 | 0.855 |
| 4520f882-715a-482d-8e87-1cb3cbdfe975 | Financial Managers | 0.446 | 0.463 |
| 9a0d8d36-6233-4c76-9107-0d1f783c7340 | Personal Financial Advisors | 0.962 | 1.000 |
| 664a42e5-3240-413a-9a57-ea93c6303269 | Personal Financial Advisors | 0.950 | 0.940 |
| feb5eefc-39f1-4451-9ef9-bffe011b71dd | Personal Financial Advisors | 0.971 | 0.981 |
| 3600de06-3f71-4e48-9480-e4828c579924 | Personal Financial Advisors | 0.887 | 0.849 |
| c657103b-b348-4496-a848-b2b7165d28b2 | Personal Financial Advisors | 0.948 | 0.862 |
| 46bc7238-3501-4839-b989-e2bd47853676 | Real Estate Brokers | 0.881 | 0.888 |
| 2d06bc0a-89c6-4e89-9417-5ffe725c1bc6 | Real Estate Brokers | 1.000 | 1.000 |
| fd3ad420-6f7d-43b1-a990-c0c5c047d071 | Real Estate Brokers | 0.871 | 0.871 |
| 0818571f-5ff7-4d39-9d2c-ced5ae44299e | Real Estate Brokers | 0.802 | 0.794 |
| 6074bba3-7e3a-4b1c-b8c6-a15bb6695c3b | Real Estate Brokers | — | 0.800 |
| 9efbcd35-186d-49b6-ac24-28ee2bc9a263 | Securities, Commodities, and Financial Services Sales Agents | 0.803 | 0.842 |
| 1d4672c8-b0a7-488f-905f-9ab4e25a19f7 | Securities, Commodities, and Financial Services Sales Agents | 1.000 | 1.000 |
| 4de6a529-4f61-41a1-b2dc-64951ba03457 | Securities, Commodities, and Financial Services Sales Agents | 0.441 | 0.475 |
| 4c4dc603-c21c-4284-8fb1-1b827c1fddf4 | Securities, Commodities, and Financial Services Sales Agents | 0.923 | 0.923 |
| bb499d9c-0263-4684-9238-75e8e86077b1 | Securities, Commodities, and Financial Services Sales Agents | 0.674 | 0.646 |

## Use as the Level-B headroom anchor

These are the **full-worker** ceilings. Phase 4 measures a deliberately **weakened**
seed worker (`qea/worker_gdpval_weak/`) against the NexAU 0.797 ceiling; the gap is the
headroom the evolve loop targets. Recorded separately in `docs/RESULTS_levelb_gdpval.md`.

## Other benchmarks (FAB)

FAB v2 public-27 base: Stirrup → [RESULTS_fab_base.md](RESULTS_fab_base.md) (generous
0.659 / strict 0.231); NexAU → [RESULTS_fab_nexau.md](RESULTS_fab_nexau.md) (generous
0.618 ≈ Stirrup, port fidelity confirmed).
