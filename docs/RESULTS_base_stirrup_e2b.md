# Base-harness test — vanilla Stirrup on E2B + multimodal per-rubric grade

Tasks graded: 27/30  |  judge k=2  |  E2B concurrency 16
Worker uploads GDPval reference INPUT files; E2B reconnects on disconnect (LLM output single-attempt).

- **Mean multimodal rubric %:** 0.689
- **Mean text-only rubric % (ablation):** 0.661
- **Prior text-worker/text-grade baseline (no ref files):** 0.618
- **Worker effect (text-grade − prior):** +0.043
- **Grader-input effect (mm − text):** +0.028

| task | subtype | multimodal % | text-only % | var | files | imgs | refs | degraded | error |
|------|---------|-------------|------------|-----|-------|------|------|----------|-------|
| 83d10b06-26d1-4636-a32c-23f92c57f30b | Accountants and Auditors | 0.992 | 0.968 | 0.000 | 2 | 8 | 1 | False |  |
| 7b08cd4d-df60-41ae-9102-8aaa49306ba2 | Accountants and Auditors | 0.713 | 0.567 | 0.000 | 1 | 1 | 1 | False |  |
| 7d7fc9a7-21a7-4b83-906f-416dea5ad04f | Accountants and Auditors | 0.853 | 0.842 | 0.000 | 1 | 8 | 6 | False |  |
| 43dc9778-450b-4b46-b77e-b6d82b202035 | Accountants and Auditors | 0.000 | 0.000 | 0.000 | 0 | 0 | 15 | True |  |
| ee09d943-5a11-430a-b7a2-971b4e9b01b5 | Accountants and Auditors | 0.000 | 0.000 | 0.000 | 0 | 0 | 17 | True |  |
| 8079e27d-b6f3-4f75-a9b5-db27903c798d | Financial and Investment Analysts | 0.909 | 0.909 | 0.000 | 8 | 8 | 0 | False |  |
| e21cd746-404d-4602-b9d2-01d2812c5b87 | Financial and Investment Analysts | 0.923 | 0.910 | 0.000 | 2 | 8 | 0 | False |  |
| 9e8607e7-a38a-491f-ace1-e5ea7dc477cb | Financial and Investment Analysts | 1.000 | 1.000 | 0.000 | 1 | 8 | 0 | False |  |
| c7d83f01-2874-4876-b7fd-52582ec99e1a | Financial and Investment Analysts | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 | True |  |
| 46b34f78-6c06-4416-87e2-77b6d8b20ce9 | Financial and Investment Analysts | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 | True |  |
| a1963a68-1bea-4bb1-b7e0-145c92a57449 | Financial Managers | 0.970 | 0.970 | 0.000 | 1 | 8 | 0 | False |  |
| 5f6c57dd-feb6-4e70-b152-4969d92d1608 | Financial Managers | — | — | — | 0 | 0 | 1 | True | RemoteProtocolError: Server disconnected |
| b39a5aa7-cd1b-47ad-b249-90afd22f8f21 | Financial Managers | — | — | — | 0 | 0 | 1 | True | JSONDecodeError: Expecting value: line 79 column 1 (char 429) |
| b78fd844-db76-448e-a783-5e9877cb74c2 | Financial Managers | 0.882 | 0.875 | 0.000 | 2 | 8 | 1 | False |  |
| 4520f882-715a-482d-8e87-1cb3cbdfe975 | Financial Managers | 0.686 | 0.406 | 0.099 | 1 | 8 | 2 | False |  |
| 9a0d8d36-6233-4c76-9107-0d1f783c7340 | Personal Financial Advisors | 0.962 | 0.760 | 0.000 | 1 | 8 | 0 | False |  |
| 664a42e5-3240-413a-9a57-ea93c6303269 | Personal Financial Advisors | — | — | — | 0 | 0 | 0 | True | RemoteProtocolError: Server disconnected |
| feb5eefc-39f1-4451-9ef9-bffe011b71dd | Personal Financial Advisors | 0.976 | 0.976 | 0.000 | 1 | 8 | 0 | False |  |
| 3600de06-3f71-4e48-9480-e4828c579924 | Personal Financial Advisors | 0.887 | 0.858 | 0.000 | 1 | 8 | 0 | False |  |
| c657103b-b348-4496-a848-b2b7165d28b2 | Personal Financial Advisors | 0.940 | 0.940 | 0.000 | 2 | 8 | 1 | False |  |
| 46bc7238-3501-4839-b989-e2bd47853676 | Real Estate Brokers | 0.873 | 0.888 | 0.000 | 1 | 8 | 0 | False |  |
| 2d06bc0a-89c6-4e89-9417-5ffe725c1bc6 | Real Estate Brokers | 1.066 | 1.082 | 0.000 | 1 | 5 | 0 | False |  |
| fd3ad420-6f7d-43b1-a990-c0c5c047d071 | Real Estate Brokers | 0.871 | 0.855 | 0.001 | 1 | 1 | 1 | False |  |
| 0818571f-5ff7-4d39-9d2c-ced5ae44299e | Real Estate Brokers | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 | True |  |
| 6074bba3-7e3a-4b1c-b8c6-a15bb6695c3b | Real Estate Brokers | 0.258 | 0.258 | 0.066 | 0 | 0 | 1 | True |  |
| 9efbcd35-186d-49b6-ac24-28ee2bc9a263 | Securities, Commodities, and Financial Services Sales Agents | 0.803 | 0.803 | 0.000 | 1 | 3 | 0 | False |  |
| 1d4672c8-b0a7-488f-905f-9ab4e25a19f7 | Securities, Commodities, and Financial Services Sales Agents | 0.992 | 1.000 | 0.000 | 2 | 8 | 0 | False |  |
| 4de6a529-4f61-41a1-b2dc-64951ba03457 | Securities, Commodities, and Financial Services Sales Agents | 0.441 | 0.441 | 0.000 | 1 | 1 | 1 | False |  |
| 4c4dc603-c21c-4284-8fb1-1b827c1fddf4 | Securities, Commodities, and Financial Services Sales Agents | 0.923 | 0.923 | 0.000 | 1 | 1 | 1 | False |  |
| bb499d9c-0263-4684-9238-75e8e86077b1 | Securities, Commodities, and Financial Services Sales Agents | 0.674 | 0.612 | 0.000 | 1 | 8 | 1 | False |  |
