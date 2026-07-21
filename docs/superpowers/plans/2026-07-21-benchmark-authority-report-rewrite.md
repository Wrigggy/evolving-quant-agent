# Benchmark Authority Report Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the benchmark authority report so Part 1 contains the detailed evidence and unresolved hypotheses, Part 2 is absent, Parts 3 and 4 contain only the approved questions and small-pilot plan, and the matching A4 PDF is visually verified.

**Architecture:** Treat the Markdown report as the authoritative editable source. Make the content changes first and validate them with exact text checks, then render the Markdown with the repository's existing `scripts/md_to_pdf.py` utility into a temporary A4 PDF, inspect every rendered page, and replace the stable report PDF only after both content and visual checks pass.

**Tech Stack:** Markdown, Python 3.12, the repository's `scripts/md_to_pdf.py`, headless Chrome, Poppler (`pdfinfo`, `pdftotext`, `pdftoppm`), and Git.

## Global Constraints

- Preserve the existing factual benchmark screen, source links, benchmark tables, provenance boundaries, and GDPval/BTB case studies in Part 1.
- Make only the minimum Part 0 edits needed to stop presenting a multi-layer benchmark suite as a finalized decision.
- Delete Part 2 in full and do not reintroduce its fixed weights, `UpgradeIndex`, adapter architecture, or multi-fidelity recommendation elsewhere.
- Keep the remaining open-question and next-week sections numbered as Parts 3 and 4.
- Part 3 must contain exactly two substantive questions.
- Part 4 must describe only a preliminary benchmark choice followed by a small pilot and effect review; do not add license work.
- Do not change benchmark code, framework code, canonical project memory, or the later QFBench/runtime decision record.
- Do not claim that a benchmark combination, aggregate reward, adapter, or evolution result has already been implemented or measured.
- Preserve the report's bilingual headings and stable filenames.

---

## File Map

- Modify: `docs/reports/2026-07-21-qea-benchmark-authority-screen-report.md` — authoritative report content.
- Regenerate: `docs/reports/2026-07-21-qea-benchmark-authority-screen-report.pdf` — final user-facing artifact.
- Reuse unchanged: `scripts/md_to_pdf.py` — existing Markdown-to-A4-PDF renderer.
- Temporary only: `tmp/pdfs/benchmark-authority-after/` — draft PDF, generated HTML, page PNGs, and extracted text used for QA.
- Temporary only: `tmp/pdfs/benchmark-authority-after/source-before.md` — pre-edit source snapshot used because the current dated report is untracked and therefore has no ordinary Git diff baseline.

### Task 1: Rewrite and validate the Markdown report

**Files:**
- Modify: `docs/reports/2026-07-21-qea-benchmark-authority-screen-report.md`

**Interfaces:**
- Consumes: the approved design in `docs/superpowers/specs/2026-07-21-benchmark-authority-report-rewrite-design.md` and the current source-backed tables/citations in the report.
- Produces: one internally consistent Markdown source that Task 2 renders without additional content transformation.

- [ ] **Step 1: Save the untracked source baseline and record the pre-edit structural assertions**

Run:

```bash
mkdir -p tmp/pdfs/benchmark-authority-after
cp docs/reports/2026-07-21-qea-benchmark-authority-screen-report.md \
  tmp/pdfs/benchmark-authority-after/source-before.md
rg -n '^## [0-4]\.|^### 1\.[1-5]|^### 2\.' docs/reports/2026-07-21-qea-benchmark-authority-screen-report.md
```

Expected before editing: headings for Parts 0, 1, 2, 3, and 4; subsections 2.1, 2.2, and 2.3; no subsection 1.5.

- [ ] **Step 2: Rewrite Part 0 as a candidate map rather than a finalized suite**

Replace the opening conclusion and pipeline in Part 0 with text carrying this exact meaning:

```markdown
**结论：本轮筛选已经明确了不同 benchmark 的权威性、任务形态、grader 和能力覆盖，但尚不能据此直接决定主演化应采用单一 benchmark 还是多个 benchmark。** 当前证据支持形成候选能力地图，而不是把某一种 benchmark suite 提前写成定案：

| 候选能力 | 代表 benchmark | 当前可支持的判断 |
|---|---|---|
| 确定性 quant 任务 | QFBench | reward 最适合观察代码、分析和产物执行能力是否发生变化 |
| 企业财务工作流 | FINCH / FinWorkBench | 更接近 spreadsheet、email、PDF 等组合式 enterprise workflow |
| 投行业务交付物 | BankerToolBench (BTB) | 更接近 banker-authored / banker-validated 的端到端交付任务 |
| 权威专业任务迁移 | GDPval Finance、PRBench Finance | 适合检验提升能否迁移到专家构造的专业任务，但不宜直接视为高频演化 reward |

单 benchmark 还是多 benchmark、是否需要 held-out、以及多 benchmark 应选择相近类别还是互补能力，仍需通过小规模实验决定。
```

Keep the three existing factual corrections immediately after this replacement.

- [ ] **Step 3: Expand Part 1 with the approved evidence-and-hypotheses subsection**

After Case B, add this subsection structure and content. Preserve the distinction between observed facts and proposed hypotheses:

```markdown
### 1.5 当前证据能回答什么、仍需验证什么 / What the Evidence Resolves and What Remains Open

本轮筛选已经回答了“每个 benchmark 更接近测什么”，但还没有回答“哪一种 benchmark 组织方式最适合驱动演化”。现有证据只能支持以下能力地图：QFBench 更接近确定性的 quant coding、risk、factor、backtesting 与多文件产物执行；FINCH 更接近企业财务与 accounting workflow；BTB 更接近投行业务交付物；GDPval/PRBench 更适合作为专业任务上的迁移观察。这里的定位不等于已经确定它们必须组成同一个 suite。

#### 单一 benchmark 演化：归因更清楚，但能力范围可能较窄

如果主演化只使用一个 benchmark，reward 定义、grader、任务格式和成本都更容易控制，也更容易判断一次 worker 修改是否真的改善了同一种任务分布。它的局限是：即使分数提高，也可能只能说明 worker 更适应该 benchmark，而不能说明 quant、企业财务 workflow 和 banking deliverable 等多种能力同时提高。

#### 多 benchmark 演化：可以探索多能力，但解释更复杂

如果同时使用多个 benchmark，可以把研究问题扩展为：同一个 evolver 能否改善多种能力，例如 QFBench 所代表的 quant 执行能力、FINCH 所代表的企业财务 workflow，以及 BTB 所代表的投行业务交付能力。与此同时，综合结果也可能受到 routing、benchmark 权重、grader 类型和输出格式差异影响。因此，多 benchmark 分数变好不一定等于底层能力普遍变好，需要通过逐 benchmark 结果和迁移测试拆开解释。

#### held-out 测试：单 benchmark 与多 benchmark 都需要明确边界

对于单一公开 benchmark，反复使用同一批任务进行演化容易把 benchmark-specific 适配误写成泛化，因此是否建立按 task family 或 workflow lineage 隔离的 held-out 测试，是首先要决定的方法学问题。对于多 benchmark，还需要进一步判断：每个 benchmark 是否都要保留自己的 held-out 部分，以及未参与主演化的另一个 benchmark 能否作为 cross-benchmark transfer test。当前报告只提出这些设计选项，不提前给出结论。

#### 多 benchmark 的两种候选组合

一种思路是选择任务类别相近的 benchmark，例如 GDPval Finance 与 FINCH，以观察同一大类专业 finance workflow 上的演化与迁移；另一种思路是选择能力互补的 benchmark，例如 QFBench、FINCH 与 BTB，分别覆盖 quant、企业财务 workflow 和 banking deliverable。前者更容易比较，后者覆盖面更广。具体采用哪一种，应由小规模 pilot 的实际效果决定。

**证据边界：** 本轮尚未运行上述单 benchmark / 多 benchmark 对照，也没有测得跨 benchmark transfer、统一 reward、adapter 兼容性或综合演化收益。以上内容是下一步实验需要检验的假设，不是已经成立的结果。
```

- [ ] **Step 4: Delete Part 2 completely**

Delete everything from this heading through the line immediately before Part 3:

```markdown
## 2. 分析 / Analysis
```

The deleted block includes subsections 2.1, 2.2, and 2.3, the role-assigned benchmark suite, `u_b`, `UpgradeIndex`, adapter recommendations, and multi-fidelity scheduling language.

- [ ] **Step 5: Replace Part 3 with exactly two numbered questions**

Use this content:

```markdown
## 3. 问题与困难（待讨论）/ Problems & Open Questions

1. **应该使用单一 benchmark 演化，还是使用多个 benchmark 演化？** 如果使用多个 benchmark，是否可以有意识地演化多种能力，例如 QFBench 对应的 quant 分析与执行能力、FINCH 对应的企业财务 workflow，以及 BTB 对应的 banking deliverable 能力？
2. **不同演化方案应如何设计测试边界？** 如果使用单一 benchmark，是否必须设置 held-out 测试，以区分真正的泛化与 benchmark-specific 优化？如果使用多个 benchmark，它们应该来自相同或相近类别，例如 GDPval Finance 与 FINCH，还是应该覆盖互补能力？
```

Remove every other current Part 3 bullet.

- [ ] **Step 6: Replace Part 4 with the small-pilot plan and no license work**

Use this content:

```markdown
## 4. 下周计划 / Next Week's Plan

> 以下是待讨论的初步计划；目标是先用最小实验观察实际效果，再决定是否扩大接入。

1. **初步敲定 benchmark 方案。** 选出一个单 benchmark 方案和一个多 benchmark 候选方案，明确各自希望观察的能力与最小任务集合。
2. **运行小规模测试。** 每个方案只选少量有代表性的任务，先比较演化前后的分数、完成情况和失败类型，不立即扩展到完整 benchmark。
3. **检查提升发生在哪里。** 区分提升只出现在主演化任务内，还是也能迁移到 held-out task 或另一 benchmark；同时记录结果是否稳定，而不只看一次均分。
4. **根据实际效果再做决定。** 如果小测能显示清楚的可恢复提升，再细化 benchmark、held-out 和后续接入方案；如果没有明显效果，先调整 benchmark 选择或任务组合。

**当前状态 / Current status：benchmark 方案尚未最终敲定；下一步只进行小规模效果测试，不开展 license audit 或大规模接入。**
```

- [ ] **Step 7: Run Markdown content assertions**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

path = Path("docs/reports/2026-07-21-qea-benchmark-authority-screen-report.md")
text = path.read_text()

assert "## 2. 分析 / Analysis" not in text
assert "### 2.1" not in text
assert "### 2.2" not in text
assert "### 2.3" not in text
assert "UpgradeIndex" not in text
assert "### 1.5 当前证据能回答什么、仍需验证什么" in text
assert "应该使用单一 benchmark 演化，还是使用多个 benchmark 演化" in text
assert "不同演化方案应如何设计测试边界" in text
assert "完成 license + provenance audit" not in text
assert "下一步只进行小规模效果测试，不开展 license audit 或大规模接入" in text

part3 = text.split("## 3. 问题与困难（待讨论）/ Problems & Open Questions", 1)[1]
part3 = part3.split("## 4. 下周计划 / Next Week's Plan", 1)[0]
questions = [line for line in part3.splitlines() if line.startswith(("1. ", "2. ", "3. ", "4. ", "5. "))]
assert len(questions) == 2, questions
print("markdown content assertions: PASS")
PY
```

Expected: `markdown content assertions: PASS`.

- [ ] **Step 8: Review the Markdown diff and commit the content**

Run:

```bash
git diff --no-index --check \
  tmp/pdfs/benchmark-authority-after/source-before.md \
  docs/reports/2026-07-21-qea-benchmark-authority-screen-report.md
git diff --no-index \
  tmp/pdfs/benchmark-authority-after/source-before.md \
  docs/reports/2026-07-21-qea-benchmark-authority-screen-report.md
git add docs/reports/2026-07-21-qea-benchmark-authority-screen-report.md
git commit -m "docs: refocus benchmark authority report"
```

Expected: no whitespace errors; the diff preserves Part 1 evidence, adds Part 1.5, removes Part 2, and replaces only Parts 3 and 4 as specified.

### Task 2: Regenerate the stable A4 PDF

**Files:**
- Regenerate: `docs/reports/2026-07-21-qea-benchmark-authority-screen-report.pdf`
- Reuse unchanged: `scripts/md_to_pdf.py`
- Create temporarily: `tmp/pdfs/benchmark-authority-after/report.pdf`
- Create temporarily: `tmp/pdfs/benchmark-authority-after/report.html`

**Interfaces:**
- Consumes: the validated Markdown source from Task 1.
- Produces: a stable A4 PDF whose selectable text matches the approved report content.

- [ ] **Step 1: Create an isolated rendering directory**

Run:

```bash
mkdir -p tmp/pdfs/benchmark-authority-after
```

Expected: the exact temporary directory exists; no report source or unrelated artifact is touched.

- [ ] **Step 2: Render the Markdown to a temporary PDF**

Run:

```bash
.venv312/bin/python scripts/md_to_pdf.py \
  docs/reports/2026-07-21-qea-benchmark-authority-screen-report.md \
  tmp/pdfs/benchmark-authority-after/report.pdf
```

Expected: `wrote .../tmp/pdfs/benchmark-authority-after/report.pdf (... KB)`. In the managed sandbox this command may require approval to launch headless Chrome; do not substitute a networked converter.

- [ ] **Step 3: Verify PDF structure before replacing the stable file**

Run:

```bash
pdfinfo tmp/pdfs/benchmark-authority-after/report.pdf
pdftotext tmp/pdfs/benchmark-authority-after/report.pdf tmp/pdfs/benchmark-authority-after/report.txt
```

Expected: unencrypted A4 pages, a nonzero file size, and extractable Chinese/English text.

- [ ] **Step 4: Assert final PDF content**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

text = Path("tmp/pdfs/benchmark-authority-after/report.txt").read_text()
assert "2. 分析 / Analysis" not in text
assert "UpgradeIndex" not in text
assert "当前证据能回答什么、仍需验证什么" in text
assert "应该使用单一 benchmark 演化" in text
assert "不同演化方案应如何设计测试边界" in text
assert "完成 license + provenance audit" not in text
assert "下一步只进行小规模效果测试" in text
print("pdf text assertions: PASS")
PY
```

Expected: `pdf text assertions: PASS`.

- [ ] **Step 5: Replace the stable PDF and commit it**

Run:

```bash
cp tmp/pdfs/benchmark-authority-after/report.pdf docs/reports/2026-07-21-qea-benchmark-authority-screen-report.pdf
git add docs/reports/2026-07-21-qea-benchmark-authority-screen-report.pdf
git commit -m "docs: regenerate benchmark authority report PDF"
```

Expected: only the stable PDF is added to the commit; the temporary HTML/PDF remain untracked under `tmp/` until visual QA is complete.

### Task 3: Render every page and complete visual QA

**Files:**
- Verify: `docs/reports/2026-07-21-qea-benchmark-authority-screen-report.pdf`
- Create temporarily: `tmp/pdfs/benchmark-authority-after/page-*.png`

**Interfaces:**
- Consumes: the stable PDF from Task 2.
- Produces: visual evidence that every page is legible, unclipped, correctly ordered, and free of removed content.

- [ ] **Step 1: Render every final page to PNG**

Run:

```bash
pdftoppm -png -r 150 \
  docs/reports/2026-07-21-qea-benchmark-authority-screen-report.pdf \
  tmp/pdfs/benchmark-authority-after/page
```

Expected: one `page-N.png` per PDF page and no Poppler rendering failure. Font-cache warnings are acceptable only if all PNGs render correctly.

- [ ] **Step 2: Inspect every page, not only the first and last**

Open each `tmp/pdfs/benchmark-authority-after/page-N.png` with the local image viewer and check:

- title and bilingual headings are legible;
- Part 1 tables do not clip or overlap;
- Part 1.5 begins at a readable section boundary;
- the document transitions directly from Part 1.5 to Part 3, with no Part 2 content;
- Part 3 contains exactly two questions;
- Part 4 contains the small-pilot plan and no license work item;
- no Chinese glyph is replaced by a box;
- no line, table cell, link, or footer is cut off at a page edge;
- no page is unexpectedly blank.

Expected: zero visual defects. If any defect is present, adjust only the Markdown wording/spacing needed to fix it, rerun Tasks 1 Step 7 and Tasks 2-3, and commit the corrected Markdown/PDF together.

- [ ] **Step 3: Run final repository checks**

Run:

```bash
git status --short
git log -3 --oneline --decorate
pdfinfo docs/reports/2026-07-21-qea-benchmark-authority-screen-report.pdf
pdftotext \
  docs/reports/2026-07-21-qea-benchmark-authority-screen-report.pdf \
  tmp/pdfs/benchmark-authority-after/final-report.txt
python3 - <<'PY'
from pathlib import Path

text = Path("tmp/pdfs/benchmark-authority-after/final-report.txt").read_text()
for required in (
    "1.5 当前证据能回答什么、仍需验证什么",
    "3. 问题与困难",
    "4. 下周计划",
    "下一步只进行小规模效果测试，不开展 license audit 或大规模接入",
):
    assert required in text, required
for forbidden in ("UpgradeIndex", "2. 分析 / Analysis", "完成 license + provenance audit"):
    assert forbidden not in text, forbidden
print("final report assertions: PASS")
PY
```

Expected:

- the two new report commits are visible;
- the final PDF is A4 and unencrypted;
- `final report assertions: PASS` confirms Parts 1.5, 3, and 4 are present;
- `UpgradeIndex`, Part 2, and the old license-audit plan are absent;
- `license audit` appears only in the explicit current-status sentence saying it will not be performed;
- unrelated pre-existing untracked files remain untouched.

- [ ] **Step 4: Remove only the report-specific temporary artifacts**

After all checks pass, remove these exact directories and no broader path:

```bash
rm -rf tmp/pdfs/benchmark-authority-before
rm -rf tmp/pdfs/benchmark-authority-after
```

Expected: the final Markdown and PDF remain under `docs/reports/`; no unrelated `tmp/` content is removed.
