---
last_updated: 2026-06-12
status: active
---

# Agent 数据飞轮工业级演进路线

本文定义 Farm Manager Agent 数据飞轮的完成态、模块边界和分阶段演进路线。目标是在 2 核 2G / 2 核 4G 小服务器约束下，让真实会话、调试证据、人工标注、AI 预标注、仿真回归和后续训练调优形成闭环。

## 完成态

工业级数据飞轮不是一个赞踩按钮，也不是一个日志列表。它是一条持续转动的数据链路：

```text
真实会话 / Playground / Simulation 失败
  → MySQL 热索引 + JSONL 原始事件
  → 规则初筛
  → LLM 自动预标注
  → 人工确认和根因标注
  → Bad Case / Tool Selection / Pending Safety / SFT 数据集
  → 生成 regression / evaluation case
  → Simulation 回归运行
  → Evaluation 汇总趋势
  → 修 prompt / router / skill / pending plan
  → 新会话继续回流
```

完成态必须同时满足四个要求：

- 快速发现：系统能自动捞出工具格式异常、幻觉执行、pending 漏拦截、禁用工人被使用、工资缺失等高价值坏例。
- 证据完整：每个样本能回溯到 `session_id`、`turn_id`、`request_id`、trace、tool input/output/error、pending lifecycle、token、latency、prompt/model 版本。
- 标注可信：AI 可以预标注，但最终训练和回归真值必须来自人工确认或确定性规则。
- 闭环可消费：标注样本能进入 regression case、evaluation replay、router 训练、pending safety 数据集和 SFT JSONL。

## 核心数据源

| 数据源 | 示例 | 用途 |
| --- | --- | --- |
| 显式用户反馈 | 赞、踩、Retry、用户主动纠错 | 判断回复质量和用户满意度 |
| 隐式用户反馈 | 复制回答、继续追问、中途退出、重复问同一问题 | 辅助判断回答是否有用或是否引发困惑 |
| Agent 内部链路 | selected tools、actual tool calls、pending plan、tool error、token、latency | 定位技术根因和生成可复现回归 case |
| 仿真与评测回流 | simulation failed result、evaluation replay failed case | 让历史坏例持续防回归 |

显式反馈信号稀疏，不能作为唯一来源。工业级飞轮必须依赖 Agent 内部链路和仿真回流补齐覆盖率。

## 模块边界

| 模块 | 职责 | 不负责 |
| --- | --- | --- |
| Playground | 手工发起对话、复制 debug JSON、复现用户输入 | 批量样本治理 |
| TraceMonitor | 定位单次请求链路、节点输入输出和耗时 | 标注队列和数据集版本管理 |
| DataFlywheel | 样本队列、根因标注、AI 预标注采纳、导出、生成 case 草稿 | 实际执行回归测试 |
| Simulation | 主动运行 regression case，验证当前 Agent 行为 | 真实会话样本筛选和人工标注 |
| Evaluation | 汇总通过率、工具选择准确率、pending 安全趋势和版本对比 | 单条 trace 调试 |
| Prompt/Router/Skill | 消费飞轮产出的修复信号并改进行为 | 直接写入标注真值 |

DataFlywheel 是样本加工台，Simulation 是回归执行台，Evaluation 是趋势评分台，TraceMonitor 是链路定位台。

## 自动标注策略

自动标注分三层，按可信度递增：

1. 规则候选：基于确定性事件和文本规则生成候选问题，例如“回复声称已执行但没有成功写工具调用”。
2. LLM 预标注：读取样本证据和 debug JSON，输出质量判断、根因、严重程度、置信度、建议标签和理由。
3. 人工最终标注：人工采纳、修改或驳回 AI 建议后，才进入训练集、回归集和评测真值。

标签必须记录来源：

| 来源 | 含义 | 是否可作为训练/回归真值 |
| --- | --- | --- |
| `rule` | 确定性规则命中 | 仅限高置信规则可直接入候选，进入真值仍建议人工确认 |
| `llm_judge` | LLM 自动预标注 | 不可直接作为真值 |
| `human` | 人工确认或修改 | 可作为真值 |

同一个模型不能既生产线上回复又把自己的评分直接作为最终真值。若使用同模型 judge，只能作为预标注和排序信号。

## 标签体系

MVP 使用固定枚举和备注，避免标签发散：

- `good_reply`：好回复。
- `bad_reply`：坏回复。
- `wrong_tool_selection`：工具选错。
- `pending_missed`：pending 漏拦截。
- `hallucinated_execution`：幻觉执行。
- `tool_error_ignored`：工具失败后回复仍称成功。
- `off_topic`：答非所问。
- `sensitive_info_leak`：参数、提示词或内部信息泄露。
- `missing_wage`：安排农事或工人但工资缺失。
- `disabled_worker_used`：禁用工人仍被安排或结算。
- `unclear_intent`：用户输入不足，无法可靠执行。
- `not_actionable`：暂不处理。
- `needs_regression`：需要沉淀为回归用例。

标注时区分两个维度：

- 用户输入是否可处理：例如 `unclear_intent`。
- Agent 输出是否合格：例如 `bad_reply`、`hallucinated_execution`。

## 存储与资源约束

小服务器部署继续使用轻量架构：

- MySQL 保存热索引、turn 元数据、标签、case draft、dataset 版本和评测摘要。
- JSONL 保存原始事件、tool payload、trace segment 和 debug evidence。
- 列表页只查 MySQL，不扫描全量 JSONL。
- 详情页按 `event_file + seq range` 读取局部 JSONL。
- 异步或手动触发同步任务，不引入 Kafka、ClickHouse、MongoDB、数据湖或重型队列。

数据保留策略：

- 热索引保留足够长时间，用于列表检索和标注。
- 原始 JSONL 可按日期、farm、session 分区。
- 导出训练数据前必须脱敏，保留来源引用而不是无节制复制全部原始上下文。

## 分阶段演进

### P0：证据完整化

目标：每轮会话都能被复盘。

交付物：

- `agent_turns`、`conversation_messages`、trace、JSONL event log 对齐。
- debug export v2 能导出本轮 session 使用的 skill、router、tool、pending 和消息上下文。
- pending plan 持久化，重启后仍能确认、取消或过期。
- DataFlywheel 详情页能展示缺失证据段，例如 `missing_event_segments`。

验收标准：

- 一条多意图对话能从 DataFlywheel 跳 TraceMonitor，并复制完整 debug JSON。
- 写操作是否经过 pending、是否执行成功、是否影响数据库可被复查。

### P1：人工标注闭环

目标：让坏例能进入回归草稿。

交付物：

- DataFlywheel 样本队列、详情、固定标签、备注和 session 级标注。
- 规则候选队列：工具格式异常、工具失败、幻觉执行、pending 漏拦截、写操作误触发。
- 当前样本 JSONL 导出。
- `case draft` 生成：包含 expected skills、expected pending、confirmation flow、reply assertions、expected db diff。
- 人工确认后加入 Simulation 或 Evaluation replay。

验收标准：

- 标注一条 `disabled_worker_used + pending_missed + needs_regression` 样本后，能生成可审查的 regression case 草稿。

### P2：AI 自动预标注

目标：降低人工标注成本，但不牺牲真值质量。

交付物：

- LLM judge prompt 和版本管理。
- 预标注 API：输入样本证据，输出 suggested labels、root cause、severity、confidence、reason、recommended fix。
- 前端展示“AI 预判”，支持采纳、修改、驳回。
- 标注来源记录 `rule`、`llm_judge`、`human`，并保留 judge model 和 prompt version。
- 低置信度样本进入人工优先队列，高置信规则候选进入快速确认队列。

验收标准：

- AI 预标注不会直接进入训练/回归真值。
- 人工采纳率、驳回率可统计，用于后续优化 judge prompt。

### P3：Dataset 与仿真评测闭环

目标：让修复效果可量化、可防回归。

交付物：

- 数据集版本管理：`dataset_name`、`version`、`split`、`source_sample_id`、`label_source`。
- DB-backed simulation cases，避免直接写部署包内 JSON 文件。
- Simulation 失败结果自动回流到 DataFlywheel。
- Evaluation 页面汇总版本趋势：通过率、工具选择准确率、pending 漏拦截率、幻觉执行率、token/latency。
- Prompt/router/skill 改动必须跑核心 regression suite。

验收标准：

- 修复一次 pending 漏拦截后，对应 regression case 在后续版本持续通过。
- Evaluation 能展示最近版本是否比上一版更好。

### P4：训练与调优出口

目标：把高质量标注数据转成模型、prompt、router 和 skill 的改进输入。

交付物：

- SFT JSONL 导出：包含 user input、必要上下文、tool result、人工修正回复。
- Router 训练/评测样本：input、expected tools、rejected tools、reason。
- Pending safety 数据集：写操作、确认话术、应拦截/应执行、期望数据库变化。
- Prompt A/B 与 pairwise 回复对比。
- 修复建议归档：每个 bad case 关联修复 PR、prompt version 或 skill version。

验收标准：

- 同一批 bad case 能被用于 prompt 回归、router 评测和 SFT 导出，且来源可追溯。
- 线上新坏例能在下一个迭代进入回归集。

## 工业级验收清单

- 每条样本都有 `session_id`、`turn_id`、`request_id` 和来源证据。
- 每条标注都有来源、操作者、时间、模型版本或规则版本。
- AI 预标注必须可采纳、修改、驳回。
- 训练和回归数据只使用人工确认或高置信规则确认后的标签。
- 能从坏例一键生成 regression case 草稿。
- Simulation 失败能自动回流 DataFlywheel。
- Evaluation 能展示趋势，而不是只展示单次结果。
- 列表查询不扫描 JSONL 全文。
- 导出数据有脱敏策略。
- 小服务器部署不依赖重型数据平台。

## 与当前问题的对应关系

当前多轮会话中暴露的问题应沉淀为以下飞轮样本：

| 问题 | 建议标签 | 回归断言 |
| --- | --- | --- |
| pending 没有拦截确认 | `pending_missed`、`needs_regression` | 写操作前必须创建 pending plan，用户确认后才执行 |
| 模型声称已执行但工具没成功 | `hallucinated_execution`、`bad_reply` | 没有成功写工具时不得回复“已完成” |
| 禁用工人仍参与安排 | `disabled_worker_used`、`needs_regression` | disabled worker 不得进入排班或工资结算 |
| 安排农户/工人但工资缺失 | `missing_wage`、`wrong_tool_selection` | 工人参与农事时必须确认工资或欠款记录策略 |
| 多意图导致确认流错乱 | `pending_missed`、`wrong_tool_selection` | 多步骤计划必须拆分 pending lifecycle 并逐步确认 |
| 工具调用格式异常 | `bad_reply`、`tool_error_ignored` | 工具格式错误时应进入可恢复错误或澄清，不得伪装成功 |

这些样本优先进入 Pending Safety、Tool Selection 和 Bad Case 数据集。
