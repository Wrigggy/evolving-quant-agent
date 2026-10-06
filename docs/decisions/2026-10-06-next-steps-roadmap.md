# Next Steps Roadmap — Oct 6 2026

## Immediate: T29 QCE Directed E Round

**Status:** dispatch 失败，`ecaf965` release 没有 `RELEASE.json`，需要正确的 QCE release。

**Problem:** `run_quantcodeeval_v2_activation.py` 需要一个包含 `RELEASE.json` 的 QCE release 目录作为 `--release` 参数，但 `ecaf965` 是工程代码 release，没有这个文件。

**Fix:** 找到 bc-server 上正确的 QCE release，使用以下命令之一：

```bash
# 在 bc-server 上找到有 RELEASE.json 的 QCE release
find /home/julius/qea/deploy -name "RELEASE.json" 2>/dev/null | head -5

# 或者检查 qce-v2-ccd364c release 的完整路径
ls /home/julius/qea/deploy/releases/qce-v2-ccd364c/source/data/
```

**正确的 dispatch 命令（找到 QCE release 后执行）：**

```bash
python3 /home/julius/qea/deploy/releases/ecaf965/scripts/run_quantcodeeval_v2_activation.py \
  --config /data/qea-julius-storage/deploy/qr-evolver-pro-r2-20261005-r1/configs/quantcodeeval_deepseek_v4_flash_relation_policy_v6.json \
  --release <正确的QCE_RELEASE_DIR> \
  --run-dir /data/qea-julius-storage/runs/qr-t29-temporal-causality-directed-e-20261006-r1 \
  --evolver-image sha256:adb2a68688488fe94e0fffbe1ffecf8c5416a4c3d2325cee6379e854521b29d2 \
  --proxy-image sha256:9eae2354ea4882aa0249d17bf1467d57b2bba29d99dca5e75512f9da6c2b9b67 \
  --task T29 \
  --prior-scored-candidate-run /data/qea-julius-storage/runs/qr-family-own-pair-refinement-parent-qce-20261005-r1/episodes/qr-family-own-pair-refinement-pair-20261005-r1-parent-qce \
  --diagnosis-note 'T29 temporal_causality: shift(-1) pairs Dec1994 predictor with Jan1995 response via IS-mask on predictor date only. Oct6 audit confirms dependency. Requires executable fix in tools/ or validator/ — prompt-only ACT not acceptable per Oct6 prompt-skepticism policy.'
```

**T29 diagnosis:** `temporal_causality` failure class. `_is_pairs` 用 `shift(-1)` 把 return 列前移一行，然后只用 IS mask 过滤 predictor 日期，导致最后一个 IS predictor（Dec 1994）与第一个 OOS return（Jan 1995）配对。Oct 6 public audit（7 checks PASS）确认了这个依赖。**必须有 executable fix**（`tools/` 或 `validator/`），prompt-only ACT 不允许。

---

## BacktestBench Campaign R1

**Status:** 所有基础设施已准备好，campaign plan 已验证，需要在 bc-server 上执行。

**Campaign plan:** `data/backtestbench/CAMPAIGN_PLAN_R1.json`
- 12 dev tasks（8 train + 4 validation）
- 20 sealed test tasks（Oct 6 initial-vs-frozen-20 的那 20 个）
- 4 E rounds，net≥2 promotion gate
- Initial H: `fe81e756...`

**Launch script:** `scripts/run_backtestbench_campaign.py`

**bc-server 上执行：**

```bash
cd /home/julius/qea/deploy/releases/ecaf965

python3 scripts/run_backtestbench_campaign.py \
  --plan /home/julius/qea/deploy/releases/ecaf965/data/backtestbench/CAMPAIGN_PLAN_R1.json \
  --state-dir /data/qea-julius-storage/runs/bc-campaign-r1 \
  --config /data/qea-julius-storage/deploy/qr-evolver-pro-r2-20261005-r1/configs/quantcodeeval_deepseek_v4_flash_relation_policy_v6.json \
  --evolver-config /data/qea-julius-storage/deploy/qr-evolver-pro-r2-20261005-r1/configs/evolver-pro.json \
  --public-root <BACKTESTBENCH_PUBLIC_ROOT> \
  --trusted-root <BACKTESTBENCH_TRUSTED_ROOT> \
  --worker /data/qea-julius-storage/deploy/qr-backtest-initial-frozen20-20261006-r1/frozen-harnesses/initial \
  --worker-image sha256:adb2a68688488fe94e0fffbe1ffecf8c5416a4c3d2325cee6379e854521b29d2 \
  --evolver-image sha256:adb2a68688488fe94e0fffbe1ffecf8c5416a4c3d2325cee6379e854521b29d2 \
  --proxy-image sha256:9eae2354ea4882aa0249d17bf1467d57b2bba29d99dca5e75512f9da6c2b9b67
```

**需要确认的路径：**
- `<BACKTESTBENCH_PUBLIC_ROOT>` — BacktestBench public task data，可能在 `/data/qea-julius-storage/runtime/backtestbench/public` 或类似位置
- `<BACKTESTBENCH_TRUSTED_ROOT>` — 对应的 trusted root

**先用 `--dry-run` 验证：**

```bash
python3 scripts/run_backtestbench_campaign.py \
  --plan data/backtestbench/CAMPAIGN_PLAN_R1.json \
  --state-dir /tmp/bc-campaign-dryrun \
  --config ... --evolver-config ... \
  --public-root ... --trusted-root ... \
  --worker ... --worker-image ... --evolver-image ... --proxy-image ... \
  --dry-run
```

---

## Paper 剩余工作

### 1. Results section 历史 development log 瘦身

`paper/acl/sections/05_results.tex` 仍然包含大量历史开发日志（E1/E2/E3 时间戳、family pair 细节）。这些应该移到 appendix，main results section 只保留：

- BacktestBench 14→16 初始 vs 冻结结果
- 四个 consumer checks（08417/05973/14911/98403）
- QCE mixed results 摘要

**估计改动量：** 约 60 行删除，20 行新增。

### 2. TTS baseline arm citation

`paper/acl/sections/04_experiments.tex` 引用了 `\citep{rethinking2026harness}`，需要确认这个 citation key 在 `references.bib` 里存在，或者替换成正确的 citation。

```bash
grep -c "rethinking2026harness" paper/acl/references.bib
```

### 3. Method section campaign design subsection

`paper/acl/sections/03_method.tex` 目前没有 campaign-level 的设计说明（多少轮、promotion gate、如何保证 initial-vs-frozen 的 integrity）。需要加约 15 行说明。

---

## 工程剩余工作

### 1. BacktestBench data directory 完整化

`data/backtestbench/` 目前只有 `CAMPAIGN_PLAN_R1.json`，还需要：

- `MANIFEST_TRAIN.json` — 8 个 train task 的 manifest
- `MANIFEST_DEV.json` — 12 个 dev task 的 manifest
- `SEALED_20_MANIFEST.json` — 20 个 sealed test task 的 manifest

可从 bc-server 的现有 panel results 生成。

### 2. BacktestBenchBackend 的 run_evaluation 需要验证

`backtestbench_campaign_backend.py` 的 `_grade_panel_result` 方法从 panel state 提取 metrics，依赖 `official_evaluation` 字段的存在。需要用真实的 panel result 验证这个字段的结构与实际 bc-server panel result 匹配。

```bash
# bc-server 上验证
python3 -c "
import json
state = json.load(open('/data/qea-julius-storage/runs/.../BACKTESTBENCH-PANEL-STATE.json'))
cell = list(state['tasks'].values())[0]
print(json.dumps(cell.get('result', {}), indent=2)[:500])
"
```

### 3. `research_campaign.py` selection 接通 BacktestBench metrics

当前 `compare_benchmark_windows` 计算 `net_task_gains` 时依赖 `evaluation.metrics[task_id].get("binary_reward", 0)`，这个字段名需要与 `BacktestBenchBackend._grade_panel_result` 输出的 `asdict(TaskMetric)` 匹配。`TaskMetric.binary_reward` → `asdict` → `"binary_reward"` ✓。

### 4. TTS baseline wiring

`backtestbench_tts_baseline.py` 的 `_run_tts_workers` 方法使用了 `_PanelRuntime`、`_grade_attempt`、`_run_one_attempt` 这几个从 `backtestbench_panel` 导入的函数，但这些函数目前不是公开 export 的。需要在 `backtestbench_panel.py` 里确认它们是否存在，或者改用公开的 `run_backtestbench_panel`。

```bash
grep -n "_run_one_attempt\|_grade_attempt\|_PanelRuntime" qea/backtestbench_panel.py | head -5
```

---

## 优先级顺序

1. **今天** — 在 bc-server 上找到正确的 QCE release，dispatch T29 directed E round
2. **今天** — 找到 BacktestBench public/trusted root 路径，跑 campaign dry-run 验证
3. **本周** — 等 T29 E round 结果：如果 ACT 且有 executable component，注册 fresh T29 pair
4. **本周** — 等 BacktestBench campaign R1 第一轮结果
5. **论文截止前** — Results section 瘦身 + TTS citation fix + method campaign subsection

---

## Key Paths (bc-server)

| 资源 | 路径 |
|---|---|
| QCE config | `/data/qea-julius-storage/deploy/qr-evolver-pro-r2-20261005-r1/configs/quantcodeeval_deepseek_v4_flash_relation_policy_v6.json` |
| Evolver config | `/data/qea-julius-storage/deploy/qr-evolver-pro-r2-20261005-r1/configs/evolver-pro.json` |
| Evolver image | `sha256:adb2a68688488fe94e0fffbe1ffecf8c5416a4c3d2325cee6379e854521b29d2` |
| Proxy image | `sha256:9eae2354ea4882aa0249d17bf1467d57b2bba29d99dca5e75512f9da6c2b9b67` |
| T29 parent worker | `/data/qea-julius-storage/runs/qr-family-failure-research-20261005-r1/revisions/qr-family-failure-revision-20261005-r1/evolutions/iteration-0001/candidate` |
| T29 parent QCE episode | `/data/qea-julius-storage/runs/qr-family-own-pair-refinement-parent-qce-20261005-r1/episodes/qr-family-own-pair-refinement-pair-20261005-r1-parent-qce` |
| Research memory (latest) | `/data/qea-julius-storage/runs/qr-family-own-pair-refinement-20261005-r1/revisions/qr-family-own-pair-refinement-revision-20261005-r1/evolutions/iteration-0001/research-operation-memory.json` |
| Initial H (BacktestBench) | `/data/qea-julius-storage/deploy/qr-backtest-initial-frozen20-20261006-r1/frozen-harnesses/initial` |
| ecaf965 release | `/home/julius/qea/deploy/releases/ecaf965` |
| T29 run dir | `/data/qea-julius-storage/runs/qr-t29-temporal-causality-directed-e-20261006-r1` |
