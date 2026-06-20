# Base-harness test — vanilla Stirrup on E2B + multimodal per-rubric grade

Tasks graded: 3/5  |  judge k=2

- **Mean multimodal rubric %:** 0.833
- **Mean text-only rubric % (ablation):** 0.872
- **Prior text-worker/text-grade baseline:** 0.618
- **Worker effect (text-grade − prior):** +0.254
- **Grader-input effect (mm − text):** -0.039

| task | subtype | multimodal % | text-only % | var | files | imgs | degraded | error |
|------|---------|-------------|------------|-----|-------|------|----------|-------|
| 83d10b06-26d1-4636-a32c-23f92c57f30b | Accountants and Auditors | 0.659 | 0.778 | 0.001 | 2 | 8 | False |  |
| 8079e27d-b6f3-4f75-a9b5-db27903c798d | Financial and Investment Analysts | 0.982 | 0.973 | 0.000 | 3 | 8 | False |  |
| a1963a68-1bea-4bb1-b7e0-145c92a57449 | Financial Managers | — | — | — | 0 | 0 | True | ReadError:  |
| 9a0d8d36-6233-4c76-9107-0d1f783c7340 | Personal Financial Advisors | — | — | — | 0 | 0 | True | RemoteProtocolError: Server disconnected |
| 46bc7238-3501-4839-b989-e2bd47853676 | Real Estate Brokers | 0.858 | 0.866 | 0.000 | 1 | 8 | False |  |
