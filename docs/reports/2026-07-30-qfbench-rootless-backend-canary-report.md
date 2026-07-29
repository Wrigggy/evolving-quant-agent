# 实验报告 / Experiment Report: QFBench Self-Hosted Rootless Backend Canary

> 日期 / Date: 2026-07-30<br>研究状态 / Research readiness: **NOT_READY**<br>Backend gate: **Not accepted for formal scoring**<br>Source commit: `5d3aa5fcd5ea66a02042ddafd003f651b78149a3`<br>QFBench commit: `024921eb507fcc0c4ffe3e0a96802724be1ae84a`<br>Main run: `qfbench-rootless-canary-20260730-r6`

## 1. 实验过程与结果 / Process & Results

### 目标与边界 / Objective and boundaries

本实验检查共享 `bc-server` 上的 rootless Docker backend 是否能在不削弱 evaluator firewall 的前提下，复现当前 E2B QFBench harness 的关键能力。Canary 只针对预注册五任务中的 `historical-var-data-prep` 做 artifact replay parity，并额外运行一次 fresh seed-worker attempt。它不是 30-task repetition，也不构成模型能力对比。

官方 tests 和 test reference data 固定在 QFBench commit `024921eb...`，只进入独立、rootless、`--network none` verifier container。Worker、evolver 和模型只能看到公开 instruction/environment 与 worker 自己生成的 artifacts。实验没有下载、checkout、上传或运行 official solutions。历史 artifact 中名为 `solution.json` 的文件是 worker 必须生成的任务输出，不是 QFBench official solution。

### 方法 / Method

执行链路为：

```text
public task bundle -> rootless worker -> artifact-only handoff
                                      -> offline rootless verifier
trusted tests/reference --------------^  (--network none)
```

我们构建了 immutable base、worker 和 verifier images，记录 image ID、dependency lock 和 spec identity；检查 cgroup 资源、只读根文件系统、bounded tmpfs、worker model-proxy egress、verifier raw DNS/TCP/HTTP/HTTPS denial、force-kill、exact-ID reaper/resume，以及 worker-visible bundle 的泄漏情况。为避免把 verifier 的预热 uv cache 变成可写镜像层，运行时只把 cache seed 复制到 bounded tmpfs；只有 uv cache/tools 两个声明路径带 `exec`，其余 tmpfs 保持 `noexec`。

### 数据、镜像与证据 / Data, images, and evidence

| Item | Recorded identity |
|---|---|
| Public manifest | `22609ed319e06ce1248c54cae65d4e732a18a250581d75b545dd509e16e463f0` |
| Trusted manifest | `2c0f65309fae66b173ab501f2b5f12a2d711a889190f195ce50f72e253a6b690` |
| Materialization audit | `8be9bed28ceed676a13ae62acd1eb16a358bf47907b65a0471bfe76f7747faa5` |
| Base image | `sha256:853c6d46...` |
| Worker image | `sha256:4f0cec930...` |
| Verifier image | `sha256:3c45670142e53e884823998d9c5a20b31ffe756c8f7c8b2e106fec22ee590cfc` |
| Official test hash | `067749b2a6de51c5ea7b27d74b3c5899af4e271dd44a3b15e07cfa35056f0f11` |
| Verifier dependency lock | `a353446ff3a2887edc934697633694b15043647b86d7ceef42050947ca0f7897` |
| Canary config | `6f382bea31f85c991ecb1ddf26feccc81812796191d1065ea7c5c80d6b38145c` |

Trusted data 位于 `/home/julius/qea/runtime/trusted-verifier/024921eb-five-task`，目录权限为 `700`、文件为 `600`。Public bundle 位于 `/home/julius/qea/runtime/qfbench-public/024921eb-five-task`。Materialization audit 证明 public root 不含 tests、reference data 或 solution paths；trusted root 只含已授权的 verifier inputs。

Final post-run permission audit 发现三个 upstream executable `test.sh` 最初保留为 `0700`。它们已经收紧为 `0600`，复核后的 trusted tree 唯一目录 mode 为 `0700`、唯一文件 mode 为 `0600`。Follow-up commit `dbff80d` 使 materializer 在 promotion 前强制该 at-rest contract。此修复不改变 file bytes、Git blob/hash 或已完成的 parity result；verifier 通过 `bash` 执行隔离副本，不依赖 trusted storage 的 execute bit。

### 结果 / Results

| Gate | Result | Evidence |
|---|---|---|
| Immutable image and lock identity | PASS | Three role images recorded; verifier lock matched E2B parity anchor |
| Exact resource and filesystem policy | PASS | Rootless cgroup limits, read-only root, bounded tmpfs, exec/noexec policy inspected |
| Worker restricted model-proxy route | PASS | Synthetic proxy canary succeeded; direct forbidden routes remained unavailable |
| Offline verifier isolation | PASS | DNS, raw TCP, HTTP, HTTPS and package access denied under `--network none` |
| Independent artifact-only handoff | PASS | Worker bundle contained one public task bundle and zero trusted/reference/secret matches |
| Force-kill, exact-ID reaper, resume | PASS | Managed lifecycle was killed, reaped and resumed without duplicate completed work |
| Historical official-test parity | PASS | Reward `1.0`, 12 passed, 0 failed; duration `3.496070s` |
| Fresh paid seed-worker attempt | **INFRA FAIL** | OpenRouter returned HTTP 403: `openai/gpt-5` unavailable in the server region |
| Formal backend acceptance | **FAIL** | No fresh artifact or fresh official score was produced |

Historical replay used source run `qfbench-pilot-3-20260724T102755`, attempt `fee302b0...`, artifact record `407ee9f8...`, and the E2B verifier parity anchor. The rootless verifier reproduced official reward `1.0` with 12/12 tests. Executed-test hash was `c562d351...`; the difference from the source script hash reflects the isolated materialized execution wrapper, not a test-content mismatch.

The fresh attempt made exactly one authorized provider request. It failed after `36.332486s` with HTTP 403 because `openai/gpt-5` was not available from the shared server's region. A proxy lifecycle and worker lifecycle were created and both cleaned. No worker task execution completed, no artifact was produced, and no verifier was created. This is an infrastructure/model-availability outcome, not official reward `0`. Provider and sandbox monetary totals were not exposed, so exact cost is **unknown**, not zero.

Final cleanup found zero managed containers and zero managed networks. Image-firewall audit `679457df...`, exposure/cleanup audit `3c7956e4...`, and gate summary `74524a79...` are stored under `/home/julius/qea/runs/qfbench-rootless-canary-20260730-r6/` with mode `600`.

## 2. 分析 / Analysis

### 结论解读 / Interpretation

这次 canary 证明了 self-hosted rootless Docker 可以承载 QFBench 的 trusted verifier path，并且能够复现一个已知 artifact 的官方确定性结果。Isolation evidence 也比“容器没有公网”更完整：tests/reference 没有进入 worker image、worker bundle 或 model request surface；verifier 使用独立 container、无网络、只读 root 和最小可执行 tmpfs；终止后的资源能够按 exact ID 清理。

但它还没有证明完整 backend parity。正式 scoring 的最小闭环是：模型生成成功、worker 在受限环境完成任务、artifact-only transfer、独立 verifier 产生 official score、生命周期与成本可追踪。r6 在第一个环节之后即被区域策略拒绝，因此不能用 replay parity 替代 fresh end-to-end evidence。E2B 仍是唯一通过完整正式评分路径的 measured reference backend。

前两次失败也帮助缩小了问题范围。r4 暴露 verifier uv cache 在只读层上的写入需求；r5 暴露 host-side worker identity 计算不应依赖完整 NexAU/PyYAML import graph。这两项已经通过 bounded writable cache 与 stdlib-only identity module 修复。r6 的 403 是新的外部可用性约束，不是继续修改 verifier 或隔离策略可以解决的问题。

### Quant research readiness gate

**Gate: NOT_READY**

| Checklist area | Status | Reason |
|---|---|---|
| Data contract and index hygiene | NEEDS_EVIDENCE | 本实验只审核 runtime transport 与 verifier firewall，没有重新审计任务数据语义 |
| Temporal split and leakage control | NEEDS_EVIDENCE | 没有提出收益、泛化或时间序列表现声明；原有 split contract 未在本 canary 重估 |
| Execution and cost realism | FAIL | Fresh model execution 被 region 403 中断；provider/sandbox exact cost 为 unknown |
| Benchmark attribution and uncertainty | FAIL | 只有一次 deterministic replay，fresh score 缺失，不能估计模型采样或 backend variance |
| Robustness and sensitivity | FAIL | 没有 independent seeds、model alternatives、egress routes 或 repeated runs |
| Reproducibility artifacts | PASS | Source/QFBench commit、images、locks、config、audits、lifecycle 和 hashes 均已固定 |

Top risks are: region-dependent provider availability, missing authoritative cost telemetry, and over-interpreting one deterministic replay as end-to-end equivalence. 对应修复是先预注册模型出口或新的 model identity，再执行一次新的单任务 canary；把 model/provider usage 与 container duration 写入 durable artifact；最后才扩展到 five-task matched panel。当前没有 performance metric 可供宣传，明确保留 `NOT_READY` 避免 reporting red flag。

## 3. 问题与困难（待讨论） / Problems & Open Questions (for discussion)

1. **Model egress location.** `bc-server` 的出口区域与本地/E2B 不同，OpenRouter 对 `openai/gpt-5` 返回 region 403。需要决定是仅给 model-proxy 配置合规的新加坡出口，还是预注册一个在该区域可用的模型。两者都会改变 runtime identity，不能静默重试。
2. **Backend identity versus model identity.** 如果更换模型，下一次结果可以验证 Docker/隔离闭环，但不能与既有 E2B GPT-5 result 做严格 matched performance comparison。若目标是 backend parity，优先保持 model identity 并修复合规出口。
3. **Cost observability.** 当前 rootless container 生命周期可追踪，但 OpenRouter 请求与共享主机的边际成本没有统一账本。正式 repetition 之前必须把 request ID、token usage、provider cost、CPU/memory wall time 和 verifier/worker attribution 写入 run summary。
4. **Shared-host trust boundary.** Rootless Docker 隔离了 worker 与 verifier，但共享主机管理员理论上仍能读取 julius 用户的 trusted files 和 secret。该风险已由用户知情接受，但它与 E2B microVM/provider boundary 不同，应继续在报告中显式披露。
5. **Scope control.** 本次只验证一个 task 的历史 artifact parity。即使 fresh retry 成功，也必须先完成同 public five-task panel 的 matched canary，才能讨论把正式 repetition 从 E2B 切到该 backend。

## 4. 下周计划 / Next Week's Plan

1. 预注册并选择一个不改变研究问题的 egress 方案：首选只代理 rootless model-proxy 到合规的新加坡出口，同时保持 `openai/gpt-5`、prompt、worker digest 和 task identity 不变。
2. 在不上传 official solutions 的前提下，运行一次新的 single-task fresh canary；要求 worker artifact、offline verifier score、cleanup、usage/cost telemetry 全部落盘。该运行应使用新的 run ID，不覆盖 r4-r6。
3. 若 single-task 闭环通过，执行 five-task matched panel，对 E2B 与 rootless backend 使用同一 worker digest、model settings、public inputs、official verifier hashes 和 preregistered resources。
4. 增加 durable cost schema，至少记录 provider request identity、input/output tokens、provider-reported charge、container start/stop、CPU/memory shape 与 role attribution。缺失值必须保持 `null/unknown`。
5. 只有在 five-task parity、isolation、recovery 和 telemetry 全部通过后，才提交新的 superseding decision；在此之前，正式 QFBench scoring 和 repetition 继续使用 E2B。
