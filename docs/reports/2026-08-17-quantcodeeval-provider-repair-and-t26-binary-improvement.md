# QuantCodeEval provider repair and T26 binary improvement

## 结论先行

这轮完成了两个不同层级的目标。

第一，原先被称为“DeepSeek 限流”的阻断已经消除。模型仍固定为
`deepseek/deepseek-v4-flash-0731`，但 OpenRouter route 不再只允许单一
upstream provider；它优先 DeepSeek，并允许 Baseten、GMI Cloud 和
DeepInfra 作为 fallback。代理同时修复了一个本地截止时间错误：请求一旦
已经开始并最终返回 HTTP 200，就不会因为“是否还能开始下一次 retry”的
预算已经耗尽而被丢弃。修复后的五个真实 Evolver/Worker run 共完成 251
个请求，全部是 HTTP 200，proxy retry 为零；其中最长单次请求约 254 秒，
仍被完整接收。因此当前证据支持“route/transport blocker 已解决”，但审计
日志没有记录 OpenRouter 最终选择的 upstream provider，不能声称某个
fallback provider 实际承载了请求。

第二，T26 已在正式隔离 verifier 中从此前最佳的 16/17 提升到 17/17，
official binary reward 从 0 变为 1。最终 Type A 为 7/7，Type B 为 10/10，
没有失败、跳过或 verifier error。该成功是零模型 causal ablation：它从
Evolver 先前帮助 Worker 产出的 16/17 artifact 出发，利用 optimize-task
允许的 answer-rich diagnostic，逐项验证剩余 A10 数值差异。它还不是一次
从 shell-only H0 开始、由 Evolver 自主修改 harness、再由全新 blind Worker
产生 17/17 的完整 lineage。

## 1. 限流与长响应修复

历史故障并不只来自 OpenRouter 或 DeepSeek。旧 proxy 把一个截止时间同时
用于两个不同语义：

1. 是否还有预算开始下一次 rate-limit retry；
2. 已经发出的请求是否还允许继续读取完整响应。

这会造成一个反直觉结果：upstream 已经返回成功响应，但本地因为 retry
deadline 已过而把它改记为失败。现在 retry-start budget 只控制是否发起
下一次重试；已经开始的请求使用完整 read timeout。route 配置也从
DeepSeek-only 改为同模型的 provider order。模型身份没有变化，所以这批
run 是工程上的可用性修复，不应与固定 DeepSeek provider 的历史正式对照
合并成同一个实验 arm。

修复后的真实运行如下：

| Run | 角色 | 请求 | Tokens | Cost | 结果 |
|---|---:|---:|---:|---:|---:|
| `qce-t26-binary-gate-fallback-candidate-20260817-r1` | blind Worker | 59 | 2,677,999 | $0.154200756 | 9/17 |
| `qce-t26-binary-gate-fallback-candidate-20260817-r2` | blind Worker | 38 | 1,482,969 | $0.102054420 | 14/17 |
| `qce-t26-runtime-convergence-evolver-20260817-r2` | Evolver | 58 | 4,143,100 | $0.096463328 | admitted candidate |
| `qce-t26-grid-resolution-evolver-20260817-r1` | Evolver | 37 | 2,276,653 | $0.082239308 | admitted candidate |
| `qce-t26-grid-resolution-candidate-20260817-r2` | blind Worker | 59 | 2,867,826 | $0.114992344 | 13/17 |

合计 251 个请求、13,448,547 tokens、$0.549950156。所有请求均完成，且没有
再次出现旧的 `rate_limit_retry_deadline_expired`。这也说明“解除限流”本身
不会自动带来分数收益：三个 blind Worker 分别得到 9/17、14/17 和 13/17。

## 2. Evolver 搜索到了什么，哪里仍然不够

runtime-convergence Evolver 自主提出了 completion middleware，用于在反复
审计没有新信息时保留最新可执行 artifact。它形成了合法 ACT 和多组件
candidate，但该机制预计只能恢复到 16/17，不能解释 A10。

下一轮 Evolver 把 A10 归因为 κ 网格分辨率不足，增加了 grid-resolution
组件。这个假设有一定方向性，但单独增加网格并不成立：

- 只把 25 点网格改成 50 点，正式结果仍为 16/17；
- 新组件驱动的 blind Worker 反而只有 13/17，并重新丢失 B3、B5、B9；
- 因此“更多 grid points 就会解决 A10”被正式否证。

这条负结果很重要。它把搜索从表层超参数引回到 estimator semantics，也
说明 answer-rich evidence 需要帮助 Evolver区分“最终数值不一致”和“导致
该数值的训练/验证状态更新错误”。

## 3. A10 的真正原因

对 16/17 parent 做分组消融后，根因定位到 CV 补集的构造。

原实现先把三个 fold 的索引拼接成 complement，再用 complement 的首月和
末月构造一个连续日期区间。当 held-out fold 位于中间时，这个首末区间会
再次包含 held-out 月份。代码表面上写的是“two-fold complement”，实际的
二阶矩估计却使用了完整训练区间。这是典型的 transformation-state bug：
索引集合是正确的，但下游把非连续集合降成了连续 bounding interval。

修复由四个相互一致的数值语义组成：

- 用被选择月份的集合构造矩估计，不再用首尾日期包围盒；
- 每个 fold 用自己的训练补集重新计算 `trace(Sigma_fold)` 和 `T_fold`；
- 协方差采用任务方法所需的总体矩定义；
- 使用 50 点 log κ grid。

关键消融结果：

| Variant | κ* | γ* | OOS monthly mean | Official |
|---|---:|---:|---:|---:|
| retained parent | 0.121153 | 0.018756 | 0.006987 | 16/17 |
| grid-50 only | — | — | — | 16/17 |
| complement + fold-local scaling | 0.100000 | 0.027480 | 0.007525 | direct diagnostic |
| + population covariance + grid-50 | 0.095410 | 0.030184 | 0.007649 | **17/17** |

固定日历边界与近似等长连续块在这个数据上选择了相同的最终 κ/γ，因此它
不是 binary gain 的主因。真正有辨识力的是“集合不能退化为首尾区间”和
“fold-local state 必须由该 fold 的训练补集重算”。

## 4. 正式 verifier 结果与证据

零模型 replay run 为
`qce-t26-cv-semantics-verifier-replay-20260817-r4`。它使用原有的隔离
strategy RPC、可信 checker 和无网络 verifier；没有调用模型，也没有新增
模型费用。结果为：

- official reward: **1.0**；
- tests: **17 passed, 0 failed**；
- Type A: **7/7**；
- Type B: **10/10**；
- verifier exit code: 0。

仓库内证据位于
`results/quantcodeeval-t26-provider-and-binary-improvement-20260817/`：

- `RESULT.json`：本轮请求、费用、消融和 claim boundary；
- `candidate/strategy.py`：通过 17/17 的 exact candidate；
- `verifier-replay/`：官方 score 与 answer-free summary。完整 CTRF 继续留在
  `bc-server` 的 trusted experiment surface，不进入可被后续 Worker/Evolver
  扫描的仓库证据。

为避免重复跑 T27，verifier-only replay CLI 增加了 `--task` 过滤；它仍先
加载并验证原有 multi-task panel，只选择指定 task 重放。现有 replay 单测
通过，且 T26 live replay 正是该路径的端到端验证。

## 5. 对进化机制的含义与下一步

这轮已经满足“至少一个官方 binary task improvement”的工程门槛，但还不
满足 autonomous harness-benefit 的最终门槛。最有价值的方法结论不是一个
T26-specific 常数，而是一个可复用的组件假设：

> 对 CV、walk-forward、rolling estimation 等 quant pipeline，组件应跟踪
> 样本集合从 split 到 moment estimator 的状态；如果一个非连续集合在下游
> 被首尾边界重建，或 fold-local quantity 复用了 full-sample state，应将其
> 视为 estimator-scope inconsistency。

下一步应把这个规则加入 Evolver 可操作的 public-semantics audit，而不是把
T26 的期望 κ、γ 或答案交给 Worker。然后运行一个新的 blind T26 Worker：

1. Worker 只能看到 public task/data 与通用组件；
2. 组件检查 split membership、moment membership 和 fold-local state；
3. 若得到 17/17，再做一次 blind repeat；
4. repeat 成功后才进入 protection 和 matched-transfer；
5. 最后冻结机制，从 shell-only H0 完整重跑一次，作为论文级主结果候选。

因此当前最准确的结论是：**route blocker 已解决；binary solution mechanism
已被因果定位并通过官方 verifier；自主 Evolver-to-Worker 再现仍是下一道
门槛。**
