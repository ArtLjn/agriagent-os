# Agent 问答助手 Context 运行时与存储设计

## 1. 文档目的

这份文档不是单纯给大模型看的实现提示，而是给工程师、产品、后续 Agent 都能读懂的运行时说明。

它要回答四个问题：

1. 用户发来一句话后，系统从哪里开始处理？
2. 每一层 Context 在什么时候加载、包含什么、来自哪里？
3. 哪些内容需要持久化到 MySQL、Mongo、RAG，哪些只在本轮请求中存在？
4. 一轮回答结束后，哪些状态会影响下一轮对话？

当前目标是做一个稳定可用的农场 Agent 问答助手，不是做复杂 Agent OS。因此设计重点是：

- 主链路可恢复。
- 上下文可解释。
- 失败可降级。
- 不把 MySQL、Mongo、RAG 做成三库强一致系统。

## 2. 一句话架构

```text
用户输入
  -> 请求解析
  -> 用户/农场/会话定位
  -> pending 优先处理
  -> 意图与上下文策略判断
  -> 加载六类 Context 来源数据
  -> 必要时调用外部 RAG
  -> ContextBuilder 组装 ContextBlock
  -> ContextRenderer 渲染为分区化 ContextDocument
  -> LLM / Tool 执行
  -> 收尾持久化
  -> 下一轮从 MySQL 主状态 + 短期窗口 + 摘要 + 长期记忆恢复
```

三类存储的边界：

```text
MySQL = state of record，保存系统当前相信的状态
Mongo = evidence store，保存当时发生了什么的证据
RAG = semantic recall，保存未来需要语义召回的知识
```

## 3. 运行时总流程

下面从用户 input 开始，按一次请求的生命周期拆开。

### 3.0 生命周期总览

```text
┌────────────────────────────────────────────────────────────┐
│ 0. 用户输入 message                                         │
└──────────────────────┬─────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────────┐
│ 1. 请求解析：user / farm / session / request_id             │
│    产出：请求边界、用户隔离、农场隔离                         │
└──────────────────────┬─────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────────┐
│ 2. pending 优先：是否在确认写操作或计划                       │
│    命中：执行 pending，不走普通 RAG 问答                       │
└──────────────────────┬─────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────────┐
│ 3. ContextPolicy：判断本轮需要哪些上下文                      │
│    业务查询 / 写操作 / 农技知识 / 任务延续 / 显式记忆 / 闲聊       │
└──────────────────────┬─────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────────┐
│ 4. 来源数据加载                                              │
│    MySQL: farm、cycle、user_settings、task、memory、messages │
│    RAG: 仅知识/诊断/方案类按需 retrieve                        │
│    Tool: 实时数据和写操作必须通过工具                           │
└──────────────────────┬─────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────────┐
│ 5. ContextBuilder                                           │
│    selector -> ContextBlock -> priority -> token budget      │
└──────────────────────┬─────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────────┐
│ 6. ContextDocument                                          │
│    [Role & Policies] [Task] [Evidence] [Context] [Output]    │
└──────────────────────┬─────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────────┐
│ 7. LLM / Tool 执行                                           │
│    读实时数据先调工具，写操作先确认                            │
└──────────────────────┬─────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────────┐
│ 8. 收尾持久化                                                │
│    MySQL 写状态，Mongo 写证据，RAG 后台同步高价值材料            │
└────────────────────────────────────────────────────────────┘
```

### 3.1 Step 0：用户输入进入系统

用户从前端发起请求，例如：

```text
记住我以后面积单位默认用亩
```

或者：

```text
天气如何，我想种水稻
```

后端首先拿到以下运行时字段：

| 字段 | 来源 | 用途 |
| --- | --- | --- |
| `message` | 用户输入 | 当前任务和意图判断的起点 |
| `session_id` | 前端传入 | 关联多轮会话、短期消息窗口、任务状态 |
| `current_user` | JWT / auth | 用户隔离、额度、权限 |
| `farm` | MySQL `farms` | 农场隔离、农场基础信息 |
| `request_id` | 后端生成 | 串联 trace、日志、工具调用 |
| `cycle_id` | 可选 | 当前请求关联的茬口 |

这一阶段只做身份和边界解析，不调用 LLM。

如果找不到用户或农场，主链路不能继续，应返回明确错误。这里不能降级，因为后续所有上下文都依赖用户和农场隔离。

### 3.2 Step 1：创建会话轮次

如果请求带了 `session_id`，系统会获取或创建会话：

```text
conversations
conversation_messages
session turn / flywheel turn
```

这一阶段会保存用户消息，或者至少创建本轮 turn 的记录，便于后续：

- 生成会话摘要。
- 恢复最近对话。
- 回看本轮 trace。
- 计算本轮延迟和工具调用。

注意：原始完整对话不进入 RAG。原始对话是会话证据，不是长期知识。

### 3.3 Step 2：pending 优先处理

系统先检查当前 session 是否存在待确认事项：

```text
pending_action
pending_plan
```

示例：

```text
上一轮：要不要帮你创建这个茬口？
这一轮：确认
```

这种情况下，本轮优先执行 pending 流程，而不是重新走普通问答或 RAG。

规则：

- pending action 是强状态，优先级高于普通聊天。
- pending action 未执行前，助手不能声称“已完成”。
- 处理 pending 的这一轮，不应被误判为“记住用户偏好”。

存储边界：

| 内容 | 存储 |
| --- | --- |
| 待确认动作本体 | 当前实现主要在短期记忆或 pending store 中，目标是可恢复 |
| 执行后的业务事实 | MySQL 业务表 |
| 执行证据和错误 | Mongo trace / 结构化日志 |

### 3.4 Step 3：判断本轮需要哪些 Context

如果没有 pending，系统进入普通 Agent 问答流程。

此时不是把所有上下文都塞给模型，而是先判断本轮需要什么：

| 判断项 | 示例 | 影响 |
| --- | --- | --- |
| 是否业务查询 | “本月花了多少钱” | 必须调用账务工具或读取业务表 |
| 是否写操作 | “帮我记一笔化肥 150 元” | 必须走工具和确认，不允许模型口头完成 |
| 是否农技知识 | “水稻高温怎么管” | 可触发 RAG |
| 是否任务延续 | “那我现在该怎么做” | 需要 active task state 和最近对话 |
| 是否显式记忆 | “记住我以后用亩” | 收尾阶段写 `memory_records` |
| 是否闲聊 | “hello” | 可只加载轻量上下文 |

这一层由 ContextPolicy 或等价策略承担。

第一版不要做复杂意图系统，只要能保守地区分：

- pending 确认
- 业务读写
- 农技知识 / 诊断 / 方案
- 普通聊天
- 显式记忆请求

### 3.5 Step 4：加载六类 Context 来源数据

策略判断后，系统开始加载本轮候选上下文。

这里要区分两个概念：

- 来源数据：MySQL、短期内存、RAG、工具结果里的原始状态。
- ContextBlock：经过 selector 处理后准备注入 prompt 的小块文本。

运行时不是直接把数据库记录塞进 prompt，而是：

```text
来源数据 -> selector -> ContextBlock -> budget/compress -> ContextDocument
```

六类 Context 在这一层陆续进入候选池。

## 4. 六类 Context 的运行时说明

### 4.1 System Context：系统规则和角色

System Context 是模型必须遵守的规则层。

典型内容：

- 助手角色，例如“芽芽，农场管理助手”。
- 语言规则。
- 安全护栏。
- 工具调用约束。
- 时间信息。
- 输出格式。

来源：

| 来源 | 说明 |
| --- | --- |
| 代码内 prompt 模板 | 固定安全规则和结构 |
| 配置 / MySQL user_settings | 角色偏好、语气、默认城市 |
| 当前时间服务 | 日期、星期、当前时间 |

存储边界：

| 存储 | 规则 |
| --- | --- |
| MySQL / config | 保存 prompt 版本、角色配置、用户设置 |
| Mongo | 保存每轮渲染摘要或 prompt scene trace |
| RAG | 不保存 System Context |

为什么不进 RAG：

System Context 必须确定性加载，不能靠语义召回。安全规则尤其不能被 RAG 命中率影响。

### 4.2 Task Context：当前正在办的事

Task Context 描述“用户当前想完成什么，以及还缺什么信息”。

示例：

```text
目标：帮用户判断现在是否适合种水稻
状态：waiting_user
已知信息：
- 用户位置：苏州市
- 当前时间：2026-07-23
- 用户意向：想种水稻
缺失信息：
- 面积
- 地块
- 是否是已有茬口收尾管理还是新建茬口
下一步：
- 先给规划建议，再澄清面积、地块、时间
```

Task Context 不是聊天摘要。它是任务状态。

来源：

| 来源 | 说明 |
| --- | --- |
| `agent_task_states` | 目标状态：可恢复的任务状态表 |
| pending action / pending plan | 待确认动作属于高优先级任务状态 |
| 当前用户输入 | 本轮可能更新目标、实体、缺失信息 |
| 工具执行结果 | 写入成功后更新任务状态 |

存储边界：

| 存储 | 规则 |
| --- | --- |
| MySQL | 保存 active task、状态、实体、缺失字段、下一步 |
| Mongo | 保存任务演进证据、失败原因、计划草稿 |
| RAG | 不保存 active task；任务完成后的高质量案例可异步入 RAG |

第一版约束：

- 每个 session 只维护一个 active task。
- 不做多任务图。
- 不做复杂 planner。
- pending action 优先级高于 active task。

### 4.3 Conversation Context：多轮对话

Conversation Context 解决“刚才聊到哪里”的问题。

它分两层：

| 层 | 内容 | 生命周期 |
| --- | --- | --- |
| 最近窗口 | 最近 12 条左右 user/assistant 消息 | 短期、会话内 |
| 会话摘要 | 超过阈值后生成 running summary | 持久化、跨进程恢复 |

示例：

```text
最近对话：
user：hello
assistant：你好呀...
user：天气如何我想种水稻
assistant：现在是 7 月下旬，苏州高温...
```

来源：

| 来源 | 说明 |
| --- | --- |
| `conversation_messages` | 原始消息 |
| `conversations.summary` | 会话摘要 |
| in-memory short term | 当前进程内最近窗口 |

存储边界：

| 存储 | 规则 |
| --- | --- |
| MySQL | 保存会话、消息、summary |
| Mongo | 保存摘要生成输入输出、压缩证据 |
| RAG | 原始对话不入；抽取并确认的事实才可能入 |

为什么原始聊天不直接进 RAG：

- 噪声大。
- 隐私风险高。
- 很多内容只在当时有效。
- 会让未来检索命中过时上下文。

### 4.4 Memory Context：用户长期记忆

Memory Context 解决“用户明确让我长期记住什么”的问题。

当前第一版只做显式长期记忆。

示例：

```text
用户说：记住我以后用亩
写入：memory_records(type=preference, content=以后用亩)
下一轮注入：偏好：以后用亩
```

当前 MySQL 表：

```text
memory_records
- memory_id
- farm_id
- user_id
- type
- content
- status
- source
- importance
- confidence
- superseded_by_id
- created_at
- updated_at
- archived_at
```

当前没有单独的 `key/value` 字段。用户偏好通过：

```text
type=preference
content=以后用亩
```

表达。

来源：

| 来源 | 说明 |
| --- | --- |
| 用户显式表达 | “记住”“以后默认”“帮我记一下” |
| `memory_records` | confirmed 长期记忆主账本 |
| 后续可选 candidate | 暂不做自动隐式记忆 |

存储边界：

| 存储 | 规则 |
| --- | --- |
| MySQL | 保存记忆主账本和状态流转 |
| Mongo | 保存记忆抽取、跳过、写入、归档、引用证据 |
| RAG | 只同步 confirmed 且高价值记忆，且异步执行 |

当前触发闭环：

```text
用户消息
  -> 聊天主流程生成回复
  -> 收尾阶段 record_explicit_memory_after_turn()
  -> 规则判断是否为显式记忆请求
  -> MemoryRecordStore.create_confirmed()
  -> 写入 MySQL memory_records
  -> 下一轮 MemoryService.build_context()
  -> MemorySelector 注入 long_term_memory block
```

不会写入的情况：

- 没有 `user_id`。
- 当前轮有 `pending_action` 或 `pending_plan`。
- 当前轮刚处理完 pending 决策。
- 用户表达“不要记”“别保存”。
- 输入只是普通偏好描述，但没有明确要求系统记住。

当前缺口：

- 写入失败只打日志，不会反馈给前端。
- 流式接口中写入发生在 SSE `done` 之后的后台收尾。
- trace 中缺少标准化 `memory_write` 节点。
- 管理端缺少按用户/农场查看长期记忆的入口。

借鉴 `mnemo-mcp` 的结论：

- 借鉴显式工具协议思想：不要让模型空口说“已记住”，后端要有可验证写入结果。
- 借鉴可观测性：记录 saved、skipped_reason、memory_id。
- 不照搬 FTS5、trust scoring、dream、实体图谱。
- 不做全自动隐式记忆，避免第一版噪声过多。

### 4.5 Knowledge Context：外部知识

Knowledge Context 解决“系统业务表里没有，但回答需要农技知识”的问题。

示例：

```text
用户问：水稻高温天气怎么管理？
系统判断：农技知识类问题
调用外部 RAG：farm_knowledge collection
返回：高温灌溉、病虫害、施肥风险等知识片段
注入：rag_knowledge block
```

来源：

| 来源 | 说明 |
| --- | --- |
| 外部 QuillRAG 服务 | `POST /retrieve` |
| 农技资料 collection | `farm_knowledge` |
| 后续可选 memory/case collection | `farm_memory` / `farm_cases` |

存储边界：

| 存储 | 规则 |
| --- | --- |
| MySQL | 只保存 RAG 配置、文档源元数据、开关 |
| Mongo | 保存 RAG 请求、响应摘要、耗时、warning、失败原因 |
| RAG | 保存知识主体和向量索引 |

第一版只在以下场景调用 RAG：

- 农技知识。
- 病虫害诊断。
- 用药、施肥、灌溉方案。
- 当前业务数据不足，需要外部知识补充。

不调用 RAG：

- hello 等闲聊。
- 简单查账。
- 简单记账。
- pending 确认。
- 可由业务工具确定回答的问题。

失败降级：

| 情况 | 行为 |
| --- | --- |
| RAG 超时 | 标记 `rag_unavailable=true`，基于已有上下文回答 |
| RAG 空结果 | 不注入 `rag_knowledge`，必要时说明知识库未命中 |
| RAG warning | 可用结果继续使用，warning 进 trace |
| RAG 服务关闭 | Knowledge selector 返回空 |

### 4.6 Tool Context：工具和业务事实

Tool Context 解决“实时数据必须通过工具或业务表确认”的问题。

示例：

```text
用户问：本月花了多少钱？
系统不能靠记忆回答
必须调用账务工具或读账务业务表
工具结果进入当前轮 Evidence
```

Tool Context 分三类：

| 类型 | 示例 | 存储 |
| --- | --- | --- |
| 当前轮工具结果 | 本月花费 150 元 | Prompt Evidence + Mongo trace |
| 工具写入后的业务事实 | 新增账单、作业记录 | MySQL 业务表 |
| 高质量归纳案例 | 某次诊断流程 | 可确认后异步入 RAG |

规则：

- 工具未执行前，不要声称写操作已完成。
- 实时数据必须先查工具或业务表。
- 原始 tool JSON 不直接进入 RAG。
- Prompt 只注入工具结果摘要。

## 5. ContextBuilder 如何组装 Prompt

六类 Context 加载完成后，系统进入 ContextBuilder。

### 5.1 候选 Block

各 selector 产生 ContextBlock：

```text
farm
cycle
user_settings
short_term_recent
short_term_summary
long_term_memory
active_task_state
pending_action
rag_knowledge
tool_result_summary
```

每个 block 至少应有：

| 字段 | 说明 |
| --- | --- |
| `key` | 稳定标识，例如 `long_term_memory` |
| `source` | 来源，例如 `memory.long_term` |
| `purpose` | 用途，例如“长期记忆” |
| `content` | 准备注入的文本 |
| `priority` | 预算紧张时的保留优先级 |
| `required` | 是否不可丢弃 |
| `compressible` | 是否允许压缩 |
| `metadata` | section、cache_scope、fallback 等调试信息 |

### 5.2 选择、排序、压缩

ContextBuilder 不应该简单拼接所有 block，而是按策略处理：

```text
候选 blocks
  -> policy 过滤
  -> priority 排序
  -> required block 强保留
  -> token budget 裁剪
  -> compressible block 压缩或摘要
  -> dropped block 进入 trace
```

优先级建议：

| 优先级 | Context |
| --- | --- |
| P0 | `pending_action` / `active_task_state` |
| P1 | `farm` / `user_settings` / `active_cycle` |
| P2 | 当前用户问题和最近对话 |
| P3 | 会话摘要 |
| P4 | confirmed 长期记忆 |
| P5 | RAG 知识 |
| P6 | 历史工具摘要 |

### 5.3 渲染为 ContextDocument

最终 prompt 不应该是一段难读拼接文本，而应固定分区：

```text
[Role & Policies]
系统角色、硬约束、当前日期、输出规则。

[Task]
用户当前问题、当前任务状态、缺失信息、下一步动作。

[Evidence]
RAG 知识、工具结果、业务查询结果、来源和置信度。

[Context]
农场信息、茬口、用户设置、最近对话、会话摘要、长期记忆。

[Output]
回答要求、引用要求、不能编造、需要澄清时怎么问。
```

默认映射：

| Section | Block key |
| --- | --- |
| `Role & Policies` | system role、policy、date、output guard |
| `Task` | `active_task_state`、`temporary_task_state`、`pending_action`、当前用户问题 |
| `Evidence` | `rag_knowledge`、`tool_result_summary`、业务工具结果 |
| `Context` | `farm`、`user_settings`、`cycle`、`ledger`、`weather`、`short_term_recent`、`short_term_summary`、`long_term_memory` |
| `Output` | output contract、citation rule、clarification rule |

未知 block 默认进入 `Context`，并在 trace 标记 `section_fallback=true`。

### 5.4 Debug 输出

面向人看的 trace 不应打印完整 prompt，而应打印结构摘要：

```text
构建的上下文:

[Task]
- active_task_state required=false tokens=120 source=mysql.agent_task_states

[Evidence]
- rag_knowledge items=3 top_score=0.86 source=external_rag

[Context]
- farm tokens=30 source=mysql.farms
- short_term_recent compressed=true tokens=180 source=memory.short_term
- long_term_memory tokens=24 source=mysql.memory_records
```

这样工程师可以直接判断：

- 本轮有没有加载长期记忆。
- RAG 有没有调用。
- 哪些 block 被压缩或丢弃。
- 当前任务状态是否进入 prompt。

### 5.5 Context 最终注入位置

ContextBuilder 产出的 `ContextBundle` 不是单独发给模型，而是在 Runtime 里被渲染后追加到 system prompt 末尾。

当前实际注入链路：

```text
ContextBuilder.build_runtime_context_bundle()
  -> ContextBundle(blocks=[...])
  -> ContextRenderer.render_prompt_text(bundle)
  -> ContextDocument.render_prompt_text()
  -> _append_runtime_context(system_text, context_bundle)
  -> system prompt 末尾追加 <runtime_context>...</runtime_context>
  -> LLM 调用
```

最终注入形态：

```text
原始 system prompt

<runtime_context>
## Task

### active_task_state
目标：帮用户做水稻种植规划
状态：waiting_user
缺失信息：面积；地块；时间

## Evidence

### rag_knowledge
1. 高温天气下水稻管理需要关注灌溉、病虫害和施肥风险。
来源：agri-guide，score=0.86

## Context

### farm
农场：管理员农场；称呼：系统管理员；位置：苏州市

### cycle
活跃茬口：夏季水稻(成熟期)、夏季大豆(播种期)

### user_settings
用户设置；助手角色：温暖陪伴型；默认城市：苏州市

### short_term_recent
user：天气如何我想种水稻
assistant：现在已经是 7 月下旬，苏州高温...

### long_term_memory
偏好：以后面积单位默认用亩
</runtime_context>
```

几点规则：

- `<runtime_context>` 是动态上下文，不替代 system prompt 的固定安全规则。
- Section 名用于稳定结构，block key 用于明确来源。
- LLM 看到的是 `block.content`，不是 MySQL 原始行或完整 trace JSON。
- Trace 里保存的是 block 摘要、section 摘要和 preview，不应保存完整敏感正文。
- 如果 `ContextRenderer.render_prompt_text()` 返回空文本，就不追加 `<runtime_context>`。

### 5.6 用户习惯记忆如何注入

以“用户习惯/偏好记忆”为例，它的写入和注入是两条不同链路。

#### 写入链路：本轮结束后保存

用户输入：

```text
记住我以后面积单位默认用亩
```

收尾阶段：

```text
record_explicit_memory_after_turn()
  -> _explicit_memory_content()
  -> _classify_explicit_memory()
  -> MemoryRecordStore.create_confirmed()
  -> MySQL memory_records
```

写入后的主账本形态：

```text
memory_records
- farm_id = 当前农场
- user_id = 当前用户
- type = preference
- content = 以后面积单位默认用亩
- status = confirmed
- source = user_explicit
```

这一轮是否立刻进入 prompt 取决于写入发生时间。当前实现是在回复收尾阶段写入，因此通常影响的是下一轮，而不是已经生成的本轮回复。

#### 读取链路：下一轮构建 MemoryContext

下一轮用户继续提问时：

```text
MemoryService.build_context(user_id, farm_id, session_id)
  -> SQLLongTermMemoryStore.build_context(user_id, farm_id)
  -> MemoryRecordStore.build_context()
  -> 读取同 farm_id + user_id + status=confirmed 的 memory_records
  -> LongTermMemoryContext(user_preferences=[...])
```

隔离规则：

- 换用户看不到。
- 换农场看不到。
- `archived` 不注入。
- `candidate` 第一版不注入。

#### Selector 链路：变成 long_term_memory block

`MemorySelector._select_long_term()` 会把长期记忆格式化为一段短文本：

```text
偏好：以后面积单位默认用亩
事实：老王就是农资店老板
农场画像：用户常种水稻和大豆
```

然后生成：

```text
ContextBlock(
  key="long_term_memory",
  source="memory.long_term",
  purpose="长期记忆",
  content="偏好：以后面积单位默认用亩",
  priority=55,
  compressible=True,
  metadata={
    "layer": "working",
    "cache_scope": "farm_user"
  }
)
```

#### Renderer 链路：放入 Context section

`ContextRenderer.KEY_TO_SECTION` 把 `long_term_memory` 映射到 `Context`：

```text
long_term_memory -> Context
```

最终注入到模型：

```text
<runtime_context>
## Context

### long_term_memory
偏好：以后面积单位默认用亩
</runtime_context>
```

模型应该把它当作“用户偏好参考”，而不是实时业务事实。例如：

- 用户问面积规划时，默认用“亩”表达。
- 用户没有要求换单位时，不主动改成公顷。
- 如果用户本轮明确指定“平方米”，本轮显式输入优先于长期偏好。

#### 注入优先级和预算

长期记忆不是 required block：

| 属性 | 当前建议 |
| --- | --- |
| `priority` | 55 |
| `compressible` | true |
| `cache_scope` | `farm_user` |
| 默认条数 | 偏好最多 3 条，事实最多 3 条，总行数最多 5 条 |

预算紧张时，长期记忆可能被压缩或丢弃。因此判断“是否注入成功”不能只看 MySQL 是否有记录，还要看本轮 trace：

- `context_bundle.selected_keys` 是否包含 `long_term_memory`
- `context_type_summary.Memory Context` 是否是 `selected`
- `sections.Context.blocks` 是否包含 `long_term_memory`
- `dropped_blocks` 是否包含 `long_term_memory`

### 5.7 不同 Context 的注入位置速查

| Context 类型 | 常见 block key | 注入 section | 典型注入内容 |
| --- | --- | --- | --- |
| System Context | `assistant_role` / `policy` | `Role & Policies` 或原始 system prompt | 角色、安全护栏、语言规则 |
| Task Context | `active_task_state` / `pending_action` | `Task` | 当前目标、缺失信息、待确认动作 |
| Conversation Context | `short_term_recent` / `short_term_summary` | `Context` | 最近对话、会话摘要 |
| Memory Context | `long_term_memory` | `Context` | 用户偏好、别名、长期事实 |
| Knowledge Context | `rag_knowledge` | `Evidence` | RAG 召回知识、来源、置信度 |
| Tool Context | `ledger` / `weather` / `tool_result_summary` | `Evidence` 或 `Context` | 本轮工具结果、业务摘要 |

注入优先级原则：

- 本轮用户输入优先于长期记忆。
- 工具实时结果优先于会话摘要和长期记忆。
- pending action 优先于 active task。
- System 安全规则优先于所有 runtime context。
- RAG 是外部证据，不覆盖 MySQL 业务事实。

## 6. 一轮回答结束后写什么

LLM 或工具执行结束后，系统进入收尾阶段。

### 6.1 必须写入的状态

| 写入对象 | 存储 | 说明 |
| --- | --- | --- |
| assistant 回复 | MySQL conversation / agent record | 供历史回看和摘要 |
| conversation turn | MySQL | 记录本轮延迟、工具、状态 |
| 业务写操作结果 | MySQL 业务表 | 账务、农事、茬口等真实状态 |
| active task 更新 | MySQL `agent_task_states` | 目标、缺失信息、下一步 |
| 显式长期记忆 | MySQL `memory_records` | 用户明确要求记住时写入 |

### 6.2 可异步写入的证据

| 写入对象 | 存储 | 说明 |
| --- | --- | --- |
| context trace | Mongo / trace store | block、section、token、dropped |
| RAG trace | Mongo / trace store | query、results 摘要、warning、耗时 |
| tool trace | Mongo / trace store | 工具入参、结果摘要、错误 |
| summary trace | Mongo / trace store | 摘要输入范围、输出 |

Mongo 写失败不能影响用户问答。

### 6.3 可后置的 RAG 同步

以下内容可异步入 RAG：

| 对象 | 条件 |
| --- | --- |
| confirmed 长期记忆 | 用户明确确认、非敏感、去重通过 |
| 高质量案例 | 任务完成后抽取并确认 |
| 农技资料 | 后台管理或离线入库 |

普通用户请求不直接调用 `/ingest`，避免文件解析和向量化拖慢主链路。

## 7. 三类存储总边界

| Context 类型 | MySQL | Mongo | RAG |
| --- | --- | --- | --- |
| System Context | prompt 配置、角色配置、用户设置 | prompt 渲染摘要 | 不入 |
| Task Context | active task、pending 状态 | 任务演进证据 | 完成案例可入 |
| Conversation Context | conversations、messages、summary | 摘要和压缩证据 | 原始对话不入 |
| Memory Context | `memory_records` 主账本 | 抽取、写入、归档、引用证据 | confirmed 高价值记忆可入 |
| Knowledge Context | RAG 配置和文档元数据 | RAG 调用证据 | 主体在 RAG |
| Tool Context | 业务事实表 | 工具调用证据 | 稳定案例可入 |

禁止入 RAG：

- system prompt 和安全规则。
- 原始完整聊天记录。
- pending action。
- active task state。
- 原始 tool response JSON。
- token budget、ranking、trace 元数据。
- 未确认的 LLM 抽取记忆。

## 8. 关键场景串起来看

### 8.1 场景 A：用户要求记住偏好

用户输入：

```text
记住我以后面积单位默认用亩
```

运行时：

```text
Step 0 解析用户、农场、session
Step 1 记录用户消息
Step 2 检查 pending，没有 pending
Step 3 判断这是显式记忆请求
Step 4 本轮仍可正常回复
Step 5 收尾阶段提取 content=以后面积单位默认用亩
Step 6 写入 memory_records(type=preference, status=confirmed)
Step 7 下一轮 build_context 读取同 farm/user 的 confirmed memory
Step 8 prompt 中出现 long_term_memory：偏好：以后面积单位默认用亩
```

验收点：

- MySQL `memory_records` 有记录。
- trace 有 `memory_write` 成功记录。
- 下一轮 Context trace 有 `long_term_memory` block。

### 8.2 场景 B：用户想种水稻

用户输入：

```text
天气如何，我想种水稻
```

运行时：

```text
Step 0 解析用户、农场、位置
Step 1 记录用户消息
Step 2 检查 pending，没有 pending
Step 3 判断需要天气工具 + 农事规划建议
Step 4 加载 farm、cycle、user_settings、recent conversation
Step 5 必要时调用天气工具；农技解释可触发 RAG
Step 6 ContextDocument 中 Evidence 放天气/RAG，Context 放农场/茬口
Step 7 LLM 回答：先说明当前时间和天气，再给建议，再澄清面积、地块、时间
Step 8 收尾更新 task_state：目标=种植规划，缺失信息=面积/地块/时间/品种等
```

下一轮用户说：

```text
我有 3 亩地
```

系统应从 `agent_task_states` 知道这不是孤立句子，而是在补充上一轮的种植规划任务。

### 8.3 场景 C：用户问农技知识

用户输入：

```text
水稻高温天气怎么管理？
```

运行时：

```text
Step 0 解析用户和农场
Step 1 检查 pending
Step 2 ContextPolicy 判断为农技知识
Step 3 加载基础 Context
Step 4 调用 QuillRAG /retrieve
Step 5 标准化为 rag_knowledge block
Step 6 Evidence section 注入 3-5 条摘要事实和来源
Step 7 LLM 基于 RAG + 当前农场季节回答
Step 8 RAG trace 写入 Mongo 或 trace store
```

如果 RAG 失败：

```text
rag_unavailable=true
基于已有农场信息和通用经验回答
必要时说明知识库暂不可用
```

### 8.4 场景 D：用户查询账务

用户输入：

```text
本月花了多少钱？
```

运行时：

```text
Step 0 解析用户和农场
Step 1 检查 pending
Step 2 判断为业务查询
Step 3 调用账务工具或读取业务表
Step 4 工具结果进入 Evidence
Step 5 LLM 根据工具结果回答
Step 6 工具调用证据写 trace
```

不应调用 RAG，也不应凭记忆回答。

## 9. 压缩和“失忆”机制

模型看到的是本轮 prompt，不是完整数据库。

因此系统会有三类“看起来失忆”的情况：

| 情况 | 原因 | 是否真实丢失 |
| --- | --- | --- |
| 最近聊天没出现在 prompt | 超出最近窗口或被压缩 | 不一定，MySQL 可能仍有原始消息 |
| 普通闲聊细节没记住 | 没有写长期记忆，也没进 task state | 是预期行为 |
| 用户偏好没出现 | 没显式写入、写入失败、farm/user 不一致或被预算裁剪 | 需要 trace 排查 |

第一版的稳定记忆优先级：

1. pending action
2. active task state
3. 业务事实表
4. confirmed long-term memory
5. conversation recent window
6. conversation summary
7. RAG knowledge

不要指望会话摘要保存所有细节。摘要只保留对后续有用的信息。

## 10. 当前实现状态与下一步

### 10.1 已完成

| 能力 | 状态 |
| --- | --- |
| Sectioned Context 输出 | 已完成基础实现 |
| `agent_task_states` | 已完成基础表和状态流 |
| 外部 RAG retrieve | 已完成只读接入 |
| `memory_records` | 已完成显式长期记忆最小闭环 |
| Context trace 展示 | 已完成基础 block/section 展示 |

### 10.2 仍需补齐

| 优先级 | 任务 | 原因 |
| --- | --- | --- |
| P0 | `memory_write` trace | 解决“模型说记住了但不知道是否写库”的问题 |
| P0 | Admin 长期记忆只读查询 | 方便按 farm/user 排查 |
| P1 | 显式记忆跳过原因标准化 | 区分 pending、无 user_id、取消表达、非显式 |
| P1 | RAG trace 更清晰展示 | 展示 query、collection、top_k、actual_mode、warning |
| P2 | confirmed memory 异步同步 RAG | 后置增强，不影响当前问答稳定性 |
| P2 | candidate 记忆和人工确认 | 等显式记忆稳定后再做 |

### 10.3 第一优先级实施建议

下一步先做“显式记忆可观测闭环”，不要先上复杂自动记忆。

建议最小改动：

```text
record_explicit_memory_after_turn()
  -> 返回 MemoryWriteResult
  -> 记录 trace node: memory_write
  -> 标准化 skipped_reason
  -> admin trace 展示
  -> 增加 tests
```

`MemoryWriteResult` 示例：

```json
{
  "triggered": true,
  "saved": true,
  "memory_id": "xxx",
  "type": "preference",
  "status": "confirmed",
  "skipped_reason": null
}
```

跳过示例：

```json
{
  "triggered": false,
  "saved": false,
  "memory_id": null,
  "type": null,
  "status": null,
  "skipped_reason": "not_explicit_memory"
}
```

## 11. 测试和验收

### 11.1 单轮 Context 验收

- Trace 能看到 `[Role & Policies]`、`[Task]`、`[Evidence]`、`[Context]`、`[Output]`。
- 每个 section 能看到 block key、source、priority、compressed、dropped。
- 未知 block 有 fallback 标记。

### 11.2 多轮任务验收

- 用户提出规划问题后，`agent_task_states` 生成 active task。
- 用户补充面积、地块等信息后，任务状态更新。
- 进程重启后，同 session 可恢复 active task。

### 11.3 显式记忆验收

- 用户说“记住我以后用亩”，MySQL `memory_records` 有 confirmed 记录。
- 下一轮同 farm/user 的 Context 中有 `long_term_memory`。
- 换 farm 或 user 后不能看到这条记忆。
- pending 确认流程不会误写长期记忆。
- trace 能看到写入成功或跳过原因。

### 11.4 RAG 验收

- 农技问题触发 RAG。
- 账务查询不触发 RAG。
- RAG 超时不导致主问答崩溃。
- RAG warning 进入 trace，不污染用户 prompt。

### 11.5 安全验收

- 文档、代码、trace 不写入真实 API key。
- system prompt 不进入 RAG。
- 原始完整聊天不进入 RAG。
- 原始 tool JSON 不进入 RAG。
- Mongo 写失败不影响主问答。

## 12. 不做项

第一版明确不做：

- 不把所有 ContextBundle 全文存起来。
- 不把 Mongo 作为主链路读取依赖。
- 不把所有会话摘要同步 RAG。
- 不做全自动隐式长期记忆。
- 不做 trust scoring、dream、实体图谱。
- 不在 Farm Manager 内部实现向量库或 embedding 服务。
- 不做多 Agent context isolation。
- 不做三库强一致补偿。

## 13. 总结

这套 Context 架构的核心不是“多存一点”，而是把一轮请求的运行时状态讲清楚：

```text
用户输入是什么
系统识别它属于什么任务
哪些状态必须读
哪些知识可以召回
哪些证据进入 prompt
哪些结果要写回
下一轮靠什么恢复
```

稳定可用的第一版应该优先保证：

- MySQL 中的任务、业务事实、长期记忆可靠。
- Mongo 中的 trace 能解释本轮为什么这么答。
- RAG 只在需要知识召回时参与，并且失败可降级。
- ContextDocument 让人能看懂每轮 prompt 由哪些部分组成。

这样人能审，模型也能沿着同一条运行时链路继续实施。
