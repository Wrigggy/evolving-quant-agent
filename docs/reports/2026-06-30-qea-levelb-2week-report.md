# 实验报告 / Experiment Report — QEA 自演化 agent:从 baseline 到泛化 Level-B 演化机制
> 日期/Date: 2026-06-30 · 实验/Experiment: evolving-quant-agent (QEA) Phases 1–5 两周回顾 · 环境/Env: `.venv-nexau` (py3.14), worker `deepseek-v4-pro`, judge `qwen3.7-plus` k=2, OpenRouter via local SOCKS proxy

---

## 0. 背景一句话 / One-line context

我们要造一个**自演化的 agent harness**:一个 worker agent 做金融分析任务,一个 evolve agent
**改 worker 的定义文件**(prompt / 工具 / 配置)让它做得更好,中间夹一个**确定性的 loop**
负责打分、保留/回滚。核心研究问题:**这套演化机制能不能真产生提升,且能泛化到不同 base harness。**

```
            ┌──────────── 确定性 loop (代码,非 agent) ────────────┐
   weak worker ──run──> deliverable ──grade(独立 judge)──> 分数
        ▲                                                    │
        │  evolve agent 编辑 worker 目录 <── answer-free 诊断 ──┘
        │  (agent.yaml / systemprompt / tools)        keep/rollback 在 loop 里
        └────────── 保留则 worker 目录被替换 ───────────────────┘
```

---

## 1. 实验过程与结果 / Process & Results

### 目标 / Goal
两周内回答三件事:(1) worker 基底从 Stirrup 迁到 NexAU 后质量是否保真;(2) **怎么制造
Level-B headroom**(削弱 worker 让演化有东西可恢复);(3) 演化机制能否泛化 + 真跑通。

### 方法与过程 / Method & Process
按 Phase 推进,每步可量化:

- **Phase 1–3｜substrate 迁移**:worker 从 **Stirrup**(纯 Python 代码定义的 agent)迁到
  **NexAU**(agent = 一个目录:`agent.yaml` + `systemprompt.md` + `tool_descriptions/` + `tools/`)。
  迁移目的:让"可演化的 harness"本身就是**可编辑的文件目录**。架构定为**一个确定性 loop 编排
  两个平级 NexAU agent**(worker + evolve),不是 agent 套 agent。
- **Phase 4｜Level-B loop + 两个 weak worker 实验**:造削弱版 seed worker 制造 headroom,
  跑独立多模态 per-rubric 打分,加了 deliverable-format gate。
- **Phase 5(两周终点)｜把机制泛化 + 跑通**:对照 AHE/ADAS/DGM/AlphaEvolve/AFlow 文献设计,
  把 loop 做成 benchmark-无关,采用 AHE 的"预测-证伪"keep/rollback,补齐 evolve agent 到 AHE 形态。

### 数据与结果 / Data & Results

**(a) Substrate 保真 —— 迁移没掉质量。** GDPval finance ~30 任务,同一套多模态 per-rubric grader:

| substrate | worker 形态 | graded | mean multimodal | infra errors |
|---|---|---|---|---|
| Stirrup (code) | E2B sandbox | 26/30 | **0.807** | 4 (E2B 超时/断连) |
| NexAU (agent dir) | LocalSandbox | 30/30 | **0.797** | 0(修了 connect-timeout 后) |

迁移后质量持平(−0.010)。FAB v2 public-27 同样持平(Stirrup 0.659 vs NexAU 0.618)。

**一个通俗但关键的点:worker 现在能交出"多文件交付物"(xlsx/pdf 等),是因为它有了自己的
agentic 循环。** Stirrup / NexAU 形态的 worker 能**多轮地**读输入、建文件、存文件、检查;而更早的
"code agent"形态**没有自己的循环**——只能一次性吐文本,所以根本产不出文件。正是"给了 worker 一个
循环"这件事,把纯文本 baseline 的得分抬了 **+0.169**(多模态再 +0.020)。这条后面很重要:**worker 的
能力,很大一部分来自它的循环,而不只是它的 prompt。**

**(b) 两个 weak worker —— headroom 的关键发现。** 同一套机制,只换削弱方式:

| weak seed | 削弱方式 | weak | full | gap | 有 headroom? |
|---|---|---|---|---|---|
| GDPval | prompt 砍成一行 + 裸 shell | 0.791 / gated 0.771 | 0.797 / 0.772 | ~0 | ❌ 无 |
| FAB | 删 4 个 SEC 检索工具绑定,只留 fetch_page+web_search | **0.388** | **0.618** | **−0.230 (−37%)** | ✅ 有 |

**核心结论(说人话):想让"演化"有东西可恢复,就得削掉 worker 一轮之内自己补不回来的能力。**
- 砍 **prompt**(把指导砍成一行):没用。强 base model 一轮内自己就把套路想起来了 → GDPval ~0 gap。
- 砍 **工具/能力**(删掉 SEC 检索工具):有用。没有检索工具,worker 在一个 episode 里**重建不出**
  "找到 filing → 深读"的能力 → FAB 留下真 0.23 gap,13/27 任务直接塌成 ~45 字符的非答案。

换句话说:**worker 的能力主要长在"工具 + 循环"上,不在 prompt 文字上;所以削弱也要削在工具/循环上。**

### 案例研究 / Case Study

**Case A — "机制能工作":FAB weak 上 evolve agent 做出设计中的恢复编辑(Phase 5,本 session 实测)。**
weak FAB worker 缺检索工具,fab_00/fab_08 因够不着 SEC filing 塌成非答案。把 firewall-off 证据语料
(答案无关:失败 rubric 条目 + 进程观察 + worker 自己的产出,**不含 gold**)喂给 evolve agent 后,它:
- 正确诊断 `MissingRetrievalCapability`;
- **把目录里实现仍在、但 agent.yaml 未绑定的 `company_filings` + `retrieve_from_filing` re-wire 回去**
  (实测 diff:`+28/-7`,改 `agent.yaml` + `systemprompt.md` + 2 个 tool 描述;agent.yaml `tools:`
  从 2 个变 4 个);
- 重写 systemprompt 成"发现 filing URL → 深读 → 引用作答"4 步流程;
- 给出正确 prediction `{"predicted_fixes":["fab_00","fab_08"]}`,**零答案泄漏**。
> ⚠️ 诚实标注:这是**简单难度档**。削弱时只删了 agent.yaml 绑定,工具的实现和**描述文件都留在目录里**,
> 我写的 NexAU 参考又点名了"re-wire unbound tool"这个动作 —— 恢复目标被 signpost 了。所以本案证明的是
> **管道通了(诊断→编辑→落地→无泄漏),不是 evolve agent 的能力**。

**Case B — "机制在哪卡住":三个基础设施坑 + 一个吞吐瓶颈。** 端到端不是一次跑通的——evolve agent
推理一直是对的,但执行被三个 NexAU 基础设施坑挡住(都靠探针逐个定位、已修,细节在 commit / checkpoint):
provider 路由导致空响应、work_dir 用了相对路径导致读写全失败(agent 因此幻觉式报告"已编辑"实则没改)、
弱模型拼不对多行 shell 写入(改用结构化文件工具解决)。修完后管道才通。**最后卡在吞吐**:weak FAB worker
没检索工具时每个任务空转到 `max_iterations:40`(~10–17min/run),加上 noise-floor 重复评 + 串行,
小样本也要 ~80min,**所以"分数恢复"这一环还没测到**(已暂停,见 checkpoint)。

---

## 2. 分析 / Analysis

- **"削弱什么"比"削弱多少"重要。** prompt-weakening 在强 base model 上是无效削弱(它一轮自恢复),
  GDPval ~0 gap 就是证据;真正可演化的 headroom 必须来自**循环自恢复能力的硬缺口**(工具 / 迭代预算)。
  这把"该在哪个 benchmark 上跑演化"从直觉变成了判据:**FAB 是对的,GDPval 不是。**
- **早期 5 任务子集的 weak 0.743 > full 0.604 是假信号**,full-30 纠正为持平 —— 提醒小样本结论必须全集复核
  (这次 Phase-5 暂停的 n_tasks=2 同理,只能定性、不能下数值结论)。
- **机制泛化已在代码层兑现**:`Evaluator` 抽象把 benchmark-specific 评分(GDPval 多模态 render vs FAB 文本
  score_rubric)藏到接口后,`run_levelb(cfg, benchmark)` 换 Benchmark+seed 即可跑两个 benchmark,不改 loop。
- **反作弊我们其实超出公开文献。** ADAS/Gödel 无防硬编码机制;DGM 是反面教材(能写代码 + 能看 reward 检测器
  → agent 改代码把检测器致盲)。我们的 firewall(答案无关诊断)+ LeakageGuard 双层,且把 firewall 设为
  canonical 默认、`ahe_corpus` 仅作可切换的 firewall-off 实验档。
- **本质瓶颈与 AHE 一致:evolve-agent 强度。** deepseek 推理方向对(诊断/计划都对),但执行弱(空响应、
  heredoc、幻觉报成功)。三个 blocker 修完后管道才通 —— 这恰好印证 AHE "evolve-agent 是瓶颈"的结论。

---

## 3. 问题与困难（待讨论）/ Problems & Open Questions

- **[核心讨论] 削弱 base harness 该削"工具插件"还是"引擎循环能力"?** 这取决于最终科研目标。我们的
  目标是**保持泛化、把这套演化机制外推到多种 base harness**,而这两种削弱方式的泛化属性不同:
  - **削工具插件**(如 FAB 删 SEC 工具):headroom 是 **benchmark-specific** 的——只有 FAB 有 SEC 工具,
    GDPval 没有。当前简单档走的就是这条,好处是恢复路径清晰、deepseek 够得着。
  - **削引擎循环能力**(如砍掉 tracer / 砍迭代预算 / 砍掉"产出文件的循环"):headroom 是
    **benchmark-无关**的——**每个 agentic worker 都有循环**,这种削弱对 GDPval / FAB 一视同仁地制造
    headroom(回到 §1:GDPval worker 能产多文件正是靠循环,砍掉循环它就和早期 code-agent 一样产不出)。
    这更契合"外推到多 harness"的目标,但要小心别削过头超出 evolve agent 的重建能力(AHE 已证 evolve-agent
    是瓶颈)。**讨论点:为了泛化,是否应把削弱重心从"工具"移到"引擎循环"?**
  - **多个 base harness 候选(供外推验证,可扩展)**:① FAB worker(SEC 检索 / 文本作答);
    ② GDPval worker(多文件交付 / 多模态);③ AHE Terminal-Bench-2 coding harness(已复现,跨域到编程);
    ④ 其它通用 NexAU agent 目录。机制已 benchmark-无关,新增一个 = 加一个 `Benchmark` + seed 即可。
- **[已解决] 三个 NexAU 基础设施坑**(provider-pin / 绝对 work_dir / 结构化文件工具)已修并写入 checkpoint,
  属于"基底踩坑"而非机制问题。
- **[待讨论] 简单难度档signpost太强。** 当前 FAB weak 把恢复目标(工具描述文件)留在目录里 + 参考点名了招式,
  所以"它会 re-wire"不能解读成能力。**讨论点**:升难度档的顺序 —— 先删描述文件(逼它推断能力),还是直接
  删实现逼它写代码?后者很可能 deepseek 直接零增益(能力不足),那是否值得现在做,还是先用简单档拿到
  score-recovery baseline 更有价值?
- **[待讨论] firewall 成本未量化。** `ahe_corpus`(firewall-off,不给 gold)vs `sanitized`(firewall-on)
  谁的增益更高、firewall 到底"花"了多少分,需要一次对照。要不要把"让 evolve agent 读 gold"也作为上限消融
  (预期增益=硬编码)来夹出区间?
- **[待讨论] 吞吐 vs 保真的取舍。** 把 weak seed `max_iterations` 40→12 能省 3-4 倍时间,但会改 weak 的
  绝对分(0.388 是 40 轮下测的)。简单档"看管道是否恢复"用低轮次够吗,还是必须保 40 轮可比?

---

## 4. 下周计划 / Next Week's Plan

1. **打三个吞吐补丁 + 跑完简单档完整 loop,拿到 score-recovery baseline。** 补丁:weak seed
   `max_iterations` 40→~12、noise-floor 改固定小 margin(免跑第二遍 seed)、`evaluate_dir` 加并发。
   预期产出:`0.388 → ?` 的轨迹 + keep/rollback verdict,**首次量化"演化是否真恢复了分数"**。
2. **升难度档做干净的能力测试**(依赖 1 先拿到 baseline):tier 1 删工具描述文件;tier 2 删实现逼真代码合成;
   并软化 NexAU 参考(去掉"re-wire"招式提示)。目的:把"管道通"升级成"evolve agent 能力"的诚实证据。
3. **firewall ON/OFF + gold-reading 消融**:用 `evidence_mode` 一键切换,量化 firewall 成本与上限。
4. **合并 Phase-5 分支** `worktree-phase5-levelb-mechanism` 到 main(当前所有 Phase-5 工作未合并)。

> 阻塞项 / Blocked:无硬阻塞;计划 1 的吞吐补丁是后续一切跑分的前置。
