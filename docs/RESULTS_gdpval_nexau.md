# GDPval base test — NexAU worker (file-producing) + multimodal grade

Graded 30/30 | judge k=2
Stirrup comparison: mean multimodal 0.807.

- **Mean multimodal:** 0.797  (Stirrup 0.807 → −0.010, statistically on par)
- **Mean text-only:** 0.787
- **Median multimodal:** 0.859
- **Reliability:** 0 LLM timeouts, 0 task failures (after the connect-timeout fix below).
- **Degraded (files=0):** 2/30 — `43dc9778` (0.000, a 16-PDF tax-return task the weak
  worker abandoned in 4 turns) and `c7d83f01` (0.755, still scored from the text answer).

## Per-occupation (n=5 each)
| occupation | mean mm | range |
|---|---|---|
| Personal Financial Advisors | 0.926 | 0.85–1.00 |
| Real Estate Brokers | 0.871 | 0.79–1.00 |
| Financial and Investment Analysts | 0.845 | 0.69–0.98 |
| Securities/Commodities Sales Agents | 0.777 | 0.47–1.00 |
| Financial Managers | 0.761 | 0.46–0.98 |
| Accountants and Auditors | 0.604 | 0.00–1.00 |

## Engineering note — the connect-timeout fix
First launch produced 16+ `APITimeoutError`s with 0 completions. Root cause: the OpenAI
SDK default `connect=5.0s`; at startup N sandboxes + N concurrent TLS handshakes through the
local SOCKS proxy fire at once and the proxy can't finish the handshake in 5s →
`httpcore.ConnectTimeout` on `start_tls` → every retry fails. Fix: `llm_config.timeout: 180`
in `qea/worker_gdpval/agent.yaml` (connect 5s→180s) + per-task startup stagger and a
whole-task retry safety net in `scripts/nexau_gdpval_run.py`. Re-run: clean, 30/30, 0 timeouts.
The judge (`qea/llm.py`) was already safe (`timeout=90` + its own 5-retry loop; it absorbed
a couple of transient `APIConnectionError`s mid-run with no impact).

## grader 60k cap
The deliverable-text cap (`MAX_DELIVERABLE_CHARS=60000`, `qea/grading/multimodal_judge.py`)
is applied silently (no truncation logging), so hit-frequency is not instrumented. No grader
errors occurred (0/30), so where it bit it did not break scoring. If hit-frequency matters,
add a one-line log when `len(text) > MAX_DELIVERABLE_CHARS`.

| task | subtype | multimodal | text | files | imgs | degraded | error |
|---|---|---|---|---|---|---|---|
| 83d10b06-26d1-4636-a32c-23f92c57f30b | Accountants and Auditors | 0.611 | 0.476 | 1 | 8 | False |  |
| 7b08cd4d-df60-41ae-9102-8aaa49306ba2 | Accountants and Auditors | 0.843 | 0.860 | 1 | 6 | False |  |
| 7d7fc9a7-21a7-4b83-906f-416dea5ad04f | Accountants and Auditors | 1.000 | 0.937 | 1 | 8 | False |  |
| 43dc9778-450b-4b46-b77e-b6d82b202035 | Accountants and Auditors | 0.000 | 0.000 | 0 | 0 | True |  |
| ee09d943-5a11-430a-b7a2-971b4e9b01b5 | Accountants and Auditors | 0.568 | 0.585 | 1 | 8 | False |  |
| 8079e27d-b6f3-4f75-a9b5-db27903c798d | Financial and Investment Analysts | 0.691 | 0.627 | 1 | 8 | False |  |
| e21cd746-404d-4602-b9d2-01d2812c5b87 | Financial and Investment Analysts | 0.923 | 0.923 | 2 | 8 | False |  |
| 9e8607e7-a38a-491f-ace1-e5ea7dc477cb | Financial and Investment Analysts | 0.978 | 1.000 | 2 | 8 | False |  |
| c7d83f01-2874-4876-b7fd-52582ec99e1a | Financial and Investment Analysts | 0.755 | 0.830 | 0 | 0 | True |  |
| 46b34f78-6c06-4416-87e2-77b6d8b20ce9 | Financial and Investment Analysts | 0.878 | 0.924 | 1 | 8 | False |  |
| a1963a68-1bea-4bb1-b7e0-145c92a57449 | Financial Managers | 0.977 | 0.977 | 1 | 8 | False |  |
| 5f6c57dd-feb6-4e70-b152-4969d92d1608 | Financial Managers | 0.865 | 0.876 | 1 | 8 | False |  |
| b39a5aa7-cd1b-47ad-b249-90afd22f8f21 | Financial Managers | 0.645 | 0.548 | 1 | 8 | False |  |
| b78fd844-db76-448e-a783-5e9877cb74c2 | Financial Managers | 0.855 | 0.914 | 2 | 8 | False |  |
| 4520f882-715a-482d-8e87-1cb3cbdfe975 | Financial Managers | 0.463 | 0.469 | 1 | 8 | False |  |
| 9a0d8d36-6233-4c76-9107-0d1f783c7340 | Personal Financial Advisors | 1.000 | 1.000 | 1 | 8 | False |  |
| 664a42e5-3240-413a-9a57-ea93c6303269 | Personal Financial Advisors | 0.940 | 0.920 | 1 | 8 | False |  |
| feb5eefc-39f1-4451-9ef9-bffe011b71dd | Personal Financial Advisors | 0.981 | 0.981 | 1 | 8 | False |  |
| 3600de06-3f71-4e48-9480-e4828c579924 | Personal Financial Advisors | 0.849 | 0.868 | 2 | 8 | False |  |
| c657103b-b348-4496-a848-b2b7165d28b2 | Personal Financial Advisors | 0.862 | 0.862 | 2 | 8 | False |  |
| 46bc7238-3501-4839-b989-e2bd47853676 | Real Estate Brokers | 0.888 | 0.881 | 1 | 8 | False |  |
| 2d06bc0a-89c6-4e89-9417-5ffe725c1bc6 | Real Estate Brokers | 1.000 | 1.000 | 1 | 5 | False |  |
| fd3ad420-6f7d-43b1-a990-c0c5c047d071 | Real Estate Brokers | 0.871 | 0.903 | 1 | 1 | False |  |
| 0818571f-5ff7-4d39-9d2c-ced5ae44299e | Real Estate Brokers | 0.794 | 0.845 | 1 | 8 | False |  |
| 6074bba3-7e3a-4b1c-b8c6-a15bb6695c3b | Real Estate Brokers | 0.800 | 0.650 | 1 | 5 | False |  |
| 9efbcd35-186d-49b6-ac24-28ee2bc9a263 | Securities, Commodities, and Financial Services Sales Agents | 0.842 | 0.842 | 1 | 5 | False |  |
| 1d4672c8-b0a7-488f-905f-9ab4e25a19f7 | Securities, Commodities, and Financial Services Sales Agents | 1.000 | 1.000 | 2 | 8 | False |  |
| 4de6a529-4f61-41a1-b2dc-64951ba03457 | Securities, Commodities, and Financial Services Sales Agents | 0.475 | 0.390 | 1 | 2 | False |  |
| 4c4dc603-c21c-4284-8fb1-1b827c1fddf4 | Securities, Commodities, and Financial Services Sales Agents | 0.923 | 0.885 | 1 | 1 | False |  |
| bb499d9c-0263-4684-9238-75e8e86077b1 | Securities, Commodities, and Financial Services Sales Agents | 0.646 | 0.652 | 1 | 8 | False |  |
