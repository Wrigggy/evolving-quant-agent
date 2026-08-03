# QFBench Successful-Usage Omission and Repetition 02 Design

> Date: 2026-08-03<br>
> Status: approved for implementation and paid repetition-02 execution<br>
> Run: `qfbench-rootless-base-85x5-official-deepseek-20260801`<br>
> Scope: accounting reconciliation, sentinel classification, and exact resume

## Goal and Frozen Boundaries

Preserve all 85 official repetition-01 scores, reconcile the observed official
DeepSeek accounting omission without inventing usage or cost, and resume the
same five-repetition baseline for repetition 02 only. The benchmark commit,
task roster, base-worker digest, model/provider identity, rootless images,
scheduler, worker/verifier concurrency, official rewards, verifier firewall,
and exact-ID cleanup policy remain unchanged. No repetition-01 worker or model
request may be replayed.

The formal run contains 79 normal worker/verifier attempts and six proven
worker-timeout zero scores. Six additional provider records across four normal
attempts are unambiguously `HTTP 200` and `completed`, but all four accounting
fields are `null`: input, output, and total tokens plus provider cost. The
responses were delivered and their attempts reached terminal official scores;
only provider accounting is unavailable.

## Approaches Considered

1. **Identity-bound lower-bound accounting (selected).** Keep every canonical
   record unchanged, count accepted requests, sum only available usage/cost,
   and enumerate missing successful-response accounting separately. This
   preserves scores and avoids a second model sample.
2. **Rerun repetition 01.** This would discard valid work, give affected tasks
   new stochastic samples, and violate the no-replay recovery contract.
3. **Infer or backfill usage/cost.** Estimating from text, later requests, or
   provider pricing would fabricate canonical telemetry and is prohibited.

## Accounting Contract

`audit_baseline_proxy_costs` accepts unavailable accounting only when one
canonical record satisfies every condition below:

- exact schema-v1 record and valid unique request identity;
- `request_state == "completed"` and `upstream_status_code == 200`;
- `failure_class is None`;
- `input_tokens`, `output_tokens`, `total_tokens`, and
  `provider_cost_usd` are **all** `null`.

A partial omission remains fatal. Non-200, non-completed, quarantined,
duplicate-identity, malformed, negative, non-finite, or inconsistent records
remain fatal. Existing timeout/quarantine handling is unchanged.

An accepted unavailable-accounting record increments `request_count` and
`completed_request_count`, but contributes nothing to token or dollar sums.
The audit adds `unreconciled_request_count` and an identity-only
`unreconciled_requests` list containing attempt, checkpoint, panel, repetition,
task, request identity, and reason. `cost_complete` is false and
`provider_cost_is_lower_bound` is true whenever either a supported timeout or
such a request exists. Unknown values are never translated to zero.

## Sentinel Contract

The sentinel currently treats the provider brand word `openrouter` as
credential material before it inspects the actual failure. Provider names are
not secrets. Remove that brand-only marker while retaining concrete markers
such as `api_key`, `authorization:`, `bearer`, `token=`, `.env`, `credentials`,
and `secret`. A log containing a provider-name information line followed by
`cost audit missing successful usage` must classify as
`unsupported_cost_omission`; a line containing `OPENROUTER_API_KEY` must still
be redacted and classified as `credential_exposure`.

The existing false-positive incident remains immutable evidence. Repetition 02
uses a new supervisor state directory and exact source commit rather than
rewriting the old incident.

## Validation and Resume

Local TDD must demonstrate both regressions fail before the fixes and pass
afterward, followed by the relevant baseline, sentinel, repair-supervisor, and
rootless suites. Deployment uses one exact Git commit and does not rebuild
images because worker, proxy-runtime, and verifier bytes do not change.

Before releasing repetition 02, run two no-model canaries on `bc`:

1. audit the preserved 85-attempt repetition-01 directory with the new code and
   require six timeout exceptions, six unavailable-accounting requests, unique
   identities, all 85 scores, and lower-bound labelling;
2. run a synthetic sentinel fixture proving provider-brand text is safe while
   concrete credential names remain redacted.

Then run the full repetition-01 acceptance audit: protected historical hashes,
worker-input firewall, offline verifier evidence, exact provider/model/runtime
identities, and zero run-owned containers/networks must pass. Resume the same
run with `--resume --stop-after-repetition 2`. The checkpoint must begin at
repetition 02 and end at `calibration_stop` with `next_repetition == 3`.

Repetition 02 is accepted only with 170 total official scores, no repetition-01
worker/model replay, all available costs validated, every unknown accounting
item explicitly enumerated, zero firewall findings, and zero residual run-owned
Docker resources. Any identity, firewall, ambiguous-request, partial-accounting,
or cleanup failure freezes the run and blocks repetition 03.
