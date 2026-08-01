# QFBench Official-Provider Rerun Design

> Date: 2026-08-01<br>
> Status: approved<br>
> Backend: trusted shared-host rootless Docker on `bc`

## Goal

Rerun the frozen all-task base-worker baseline using only DeepSeek's
first-party OpenRouter endpoint, with no provider fallback and no worker control
over routing.

## Enforcement Design

The trusted model proxy receives an optional `required_provider` policy. When
set, it rejects any inbound request already containing `provider`, injects
`{"only":[required_provider],"allow_fallbacks":false}`, recomputes content
length and request identity over the forwarded bytes, and sends only that body
upstream. Invalid provider slugs fail during configuration before any sandbox
or request is created.

The policy flows through `SandboxProxyConfig`, the public proxy plan, the proxy
image entrypoint, and rootless full-harness schema version 2. Schema version 1
remains readable for historical diagnostics, but the new formal config must be
version 2 and name `required_provider: "deepseek"`. Route and runtime digests
include the normalized policy.

## Rerun Protocol

Build a new immutable proxy image and image-set manifest while reusing the
unchanged worker/verifier/evolver images. Run a small paid first-party canary,
verify proxy-route identity, model/cost audit, firewall, and exact-ID cleanup,
then create a fresh formal run and execute repetition one at worker concurrency
4 and verifier concurrency 3. Continue repetitions two through five only after
the existing 85/85, cost-completeness, firewall, cleanup, and USD 60 projection
gates pass.

No official solution is uploaded or run. Official tests and reference data
remain confined to independent, no-network verifier sandboxes. Default-route
and Nitro artifacts remain diagnostic and are never relabeled as formal
official-provider repetitions.
