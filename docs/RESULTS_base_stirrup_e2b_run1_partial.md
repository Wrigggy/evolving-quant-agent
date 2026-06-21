# Base-harness test — vanilla Stirrup on E2B + multimodal per-rubric grade

Tasks graded: 14/30  |  judge k=2  |  E2B concurrency 20
Worker uploads GDPval reference INPUT files; E2B reconnects on disconnect (LLM output single-attempt).

- **Mean multimodal rubric %:** 0.616
- **Mean text-only rubric % (ablation):** 0.622
- **Prior text-worker/text-grade baseline (no ref files):** 0.618
- **Worker effect (text-grade − prior):** +0.004
- **Grader-input effect (mm − text):** -0.006

| task | subtype | multimodal % | text-only % | var | files | imgs | refs | degraded | error |
|------|---------|-------------|------------|-----|-------|------|------|----------|-------|
| 83d10b06-26d1-4636-a32c-23f92c57f30b | Accountants and Auditors | — | — | — | 0 | 0 | 1 | True | RemoteProtocolError: Server disconnected |
| 7b08cd4d-df60-41ae-9102-8aaa49306ba2 | Accountants and Auditors | 0.669 | 0.781 | 0.003 | 1 | 1 | 1 | False |  |
| 7d7fc9a7-21a7-4b83-906f-416dea5ad04f | Accountants and Auditors | 0.000 | 0.000 | 0.000 | 0 | 0 | 6 | True |  |
| 43dc9778-450b-4b46-b77e-b6d82b202035 | Accountants and Auditors | — | — | — | 0 | 0 | 15 | True | RemoteProtocolError: Server disconnected |
| ee09d943-5a11-430a-b7a2-971b4e9b01b5 | Accountants and Auditors | — | — | — | 0 | 0 | 17 | True | RemoteProtocolError: Server disconnected |
| 8079e27d-b6f3-4f75-a9b5-db27903c798d | Financial and Investment Analysts | — | — | — | 0 | 0 | 0 | True | RateLimitException: 429: Rate limit exceeded, please try again later. - you have reached the maximum number of concurrent E2B sandboxes (20). If you need more, please visit 'https://e2b.dev/docs/billing' |
| e21cd746-404d-4602-b9d2-01d2812c5b87 | Financial and Investment Analysts | 0.923 | 0.923 | 0.000 | 2 | 8 | 0 | False |  |
| 9e8607e7-a38a-491f-ace1-e5ea7dc477cb | Financial and Investment Analysts | 1.000 | 1.000 | 0.000 | 2 | 8 | 0 | False |  |
| c7d83f01-2874-4876-b7fd-52582ec99e1a | Financial and Investment Analysts | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 | True |  |
| 46b34f78-6c06-4416-87e2-77b6d8b20ce9 | Financial and Investment Analysts | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 | True |  |
| a1963a68-1bea-4bb1-b7e0-145c92a57449 | Financial Managers | 0.992 | 0.985 | 0.000 | 3 | 8 | 0 | False |  |
| 5f6c57dd-feb6-4e70-b152-4969d92d1608 | Financial Managers | — | — | — | 0 | 0 | 1 | True | RemoteProtocolError: Server disconnected |
| b39a5aa7-cd1b-47ad-b249-90afd22f8f21 | Financial Managers | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 | True |  |
| b78fd844-db76-448e-a783-5e9877cb74c2 | Financial Managers | — | — | — | 0 | 0 | 1 | True | JSONDecodeError: Expecting value: line 709 column 1 (char 3894) |
| 4520f882-715a-482d-8e87-1cb3cbdfe975 | Financial Managers | 0.509 | 0.503 | 0.000 | 1 | 8 | 2 | False |  |
| 9a0d8d36-6233-4c76-9107-0d1f783c7340 | Personal Financial Advisors | — | — | — | 0 | 0 | 0 | True | RemoteProtocolError: Server disconnected |
| 664a42e5-3240-413a-9a57-ea93c6303269 | Personal Financial Advisors | 0.810 | 0.820 | 0.000 | 1 | 8 | 0 | False |  |
| feb5eefc-39f1-4451-9ef9-bffe011b71dd | Personal Financial Advisors | 0.962 | 0.971 | 0.000 | 1 | 8 | 0 | False |  |
| 3600de06-3f71-4e48-9480-e4828c579924 | Personal Financial Advisors | 0.943 | 0.943 | 0.000 | 1 | 8 | 0 | False |  |
| c657103b-b348-4496-a848-b2b7165d28b2 | Personal Financial Advisors | 0.888 | 0.905 | 0.000 | 2 | 8 | 1 | False |  |
| 46bc7238-3501-4839-b989-e2bd47853676 | Real Estate Brokers | 0.925 | 0.873 | 0.000 | 1 | 7 | 0 | False |  |
| 2d06bc0a-89c6-4e89-9417-5ffe725c1bc6 | Real Estate Brokers | — | — | — | 0 | 0 | 0 | True | RateLimitException: 429: Rate limit exceeded, please try again later. - you have reached the maximum number of concurrent E2B sandboxes (20). If you need more, please visit 'https://e2b.dev/docs/billing' |
| fd3ad420-6f7d-43b1-a990-c0c5c047d071 | Real Estate Brokers | — | — | — | 0 | 0 | 1 | True | RateLimitException: 429: Rate limit exceeded, please try again later. - you have reached the maximum number of concurrent E2B sandboxes (20). If you need more, please visit 'https://e2b.dev/docs/billing' |
| 0818571f-5ff7-4d39-9d2c-ced5ae44299e | Real Estate Brokers | — | — | — | 0 | 0 | 1 | True | RateLimitException: 429: Rate limit exceeded, please try again later. - you have reached the maximum number of concurrent E2B sandboxes (20). If you need more, please visit 'https://e2b.dev/docs/billing' |
| 6074bba3-7e3a-4b1c-b8c6-a15bb6695c3b | Real Estate Brokers | — | — | — | 0 | 0 | 1 | True | RateLimitException: 429: Rate limit exceeded, please try again later. - you have reached the maximum number of concurrent E2B sandboxes (20). If you need more, please visit 'https://e2b.dev/docs/billing' |
| 9efbcd35-186d-49b6-ac24-28ee2bc9a263 | Securities, Commodities, and Financial Services Sales Agents | — | — | — | 0 | 0 | 0 | True | RateLimitException: 429: Rate limit exceeded, please try again later. - you have reached the maximum number of concurrent E2B sandboxes (20). If you need more, please visit 'https://e2b.dev/docs/billing' |
| 1d4672c8-b0a7-488f-905f-9ab4e25a19f7 | Securities, Commodities, and Financial Services Sales Agents | — | — | — | 0 | 0 | 0 | True | RateLimitException: 429: Rate limit exceeded, please try again later. - you have reached the maximum number of concurrent E2B sandboxes (20). If you need more, please visit 'https://e2b.dev/docs/billing' |
| 4de6a529-4f61-41a1-b2dc-64951ba03457 | Securities, Commodities, and Financial Services Sales Agents | — | — | — | 0 | 0 | 1 | True | RateLimitException: 429: Rate limit exceeded, please try again later. - you have reached the maximum number of concurrent E2B sandboxes (20). If you need more, please visit 'https://e2b.dev/docs/billing' |
| 4c4dc603-c21c-4284-8fb1-1b827c1fddf4 | Securities, Commodities, and Financial Services Sales Agents | — | — | — | 0 | 0 | 1 | True | RateLimitException: 429: Rate limit exceeded, please try again later. - you have reached the maximum number of concurrent E2B sandboxes (20). If you need more, please visit 'https://e2b.dev/docs/billing' |
| bb499d9c-0263-4684-9238-75e8e86077b1 | Securities, Commodities, and Financial Services Sales Agents | — | — | — | 0 | 0 | 1 | True | RateLimitException: 429: Rate limit exceeded, please try again later. - you have reached the maximum number of concurrent E2B sandboxes (20). If you need more, please visit 'https://e2b.dev/docs/billing' |
