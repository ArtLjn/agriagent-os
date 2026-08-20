# Agent Harness 方法论

> **目标：建立一张完整的 Agent Harness 架构地图。**
>
> 本文不以某个框架为中心，而是从系统工程视角理解 Harness：一个 Agent 从用户请求进入，到 Context 构建、模型决策、工具执行、状态更新、记忆沉淀，再到 Trace 与 Evaluation 的完整生命周期。

---

# 1. Harness 是什么

Agent Harness 可以理解为：

> **围绕 LLM Agent 构建的一套运行时、上下文、状态、工具、控制、记忆、观测和评估基础设施。**

简单来说：

```text
LLM 提供“智能”
        +
Harness 提供“运行环境”
        =
可运行、可控制、可观测、可评估的 Agent
```

因此：

```text
Agent ≠ LLM

Agent
=
LLM
+
Prompt
+
Tools
+
Memory
+
State
+
Runtime
```

而：

```text
Agent Harness
=
Context
+
Runtime
+
Memory
+
State
+
Tools
+
Control
+
Observability
+
Evaluation
```

Harness 的核心目标不是让模型“更聪明”，而是让 Agent：

* 知道自己现在在做什么
* 知道自己可以使用什么信息
* 知道自己可以执行什么操作
* 知道操作失败后怎么办
* 能够持续执行多步任务
* 能够保存和恢复状态
* 能够使用短期和长期记忆
* 能够受到权限和安全控制
* 能够被追踪和调试
* 能够被评估和持续优化

---

# 2. Harness 总体架构

先建立最重要的一张总图。

```text
┌──────────────────────────────────────────────────────────────────────┐
│                         AGENT HARNESS                                │
│                                                                      │
│                         用户 / 外部事件                              │
│                                │                                     │
│                                ▼                                     │
│                       ┌─────────────────┐                            │
│                       │     SESSION     │                            │
│                       │                 │                            │
│                       │ User            │                            │
│                       │ Conversation    │                            │
│                       │ Task            │                            │
│                       │ Session State   │                            │
│                       └────────┬────────┘                            │
│                                │                                     │
│                                ▼                                     │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │                     CONTEXT ENGINEERING                          │ │
│ │                                                                  │ │
│ │ System Prompt                                                   │ │
│ │ Task Context                                                    │ │
│ │ Conversation History                                            │ │
│ │ Short-term Memory                                               │ │
│ │ Long-term Memory                                                │ │
│ │ RAG / Knowledge                                                 │ │
│ │ Tool Results                                                    │ │
│ │ Current State                                                   │ │
│ └──────────────────────────────┬───────────────────────────────────┘ │
│                                │                                     │
│                                ▼                                     │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │                       AGENT RUNTIME                              │ │
│ │                                                                  │ │
│ │                 Observe → Decide → Act → Observe                │ │
│ │                                                                  │ │
│ │ Planner / Agent Loop / State Machine / Scheduler                │ │
│ └───────────────┬──────────────────────────────┬───────────────────┘ │
│                 │                              │                     │
│                 ▼                              ▼                     │
│          ┌─────────────┐                ┌──────────────┐             │
│          │ MODEL / LLM │                │    TOOLS     │             │
│          │             │                │              │             │
│          │ Reasoning   │                │ Search       │             │
│          │ Decision    │                │ Database     │             │
│          │ Generation  │                │ API          │             │
│          └──────┬──────┘                │ Computer     │             │
│                 │                       └──────┬───────┘             │
│                 └──────────────┬───────────────┘                     │
│                                ▼                                     │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │                         CONTROL                                  │ │
│ │                                                                  │ │
│ │ Permission / Policy / Guardrail / Validation                    │ │
│ │ Human-in-the-loop / Approval / Safety                           │ │
│ │ Retry / Timeout / Recovery                                      │ │
│ └──────────────────────────────┬───────────────────────────────────┘ │
│                                │                                     │
│                                ▼                                     │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │                          STATE                                   │ │
│ │                                                                  │ │
│ │ Task State / Agent State / Tool State / Execution State          │ │
│ │ Checkpoint / Recovery / Resume                                   │ │
│ └───────────────┬──────────────────────────────┬───────────────────┘ │
│                 │                              │                     │
│                 ▼                              ▼                     │
│       ┌───────────────────┐          ┌──────────────────────┐        │
│       │      MEMORY       │          │     SESSION STORE    │        │
│       │                   │          │                      │        │
│       │ Short-term        │          │ Conversation         │        │
│       │ Long-term         │          │ Session Metadata     │        │
│       │ Summary           │          │ User Context         │        │
│       └─────────┬─────────┘          └──────────────────────┘        │
│                 │                                                    │
│                 ▼                                                    │
│       ┌───────────────────┐                                          │
│       │ KNOWLEDGE / RAG   │                                          │
│       │                   │                                          │
│       │ Documents         │                                          │
│       │ Vector DB         │                                          │
│       │ Search            │                                          │
│       │ Retrieval         │                                          │
│       └───────────────────┘                                          │
│                                                                      │
│ ─────────────────────────────────────────────────────────────────── │
│                                                                      │
│                     OBSERVABILITY                                   │
│                                                                      │
│ Trace / Span / Log / Metrics / Token / Cost / Latency               │
│ Tool Calls / Model Calls / State Changes / Errors                   │
│                                                                      │
│                                │                                     │
│                                ▼                                     │
│                          EVALUATION                                  │
│                                                                      │
│ Answer Eval / Tool Eval / Context Eval / Trajectory Eval            │
│ Regression / Online Evaluation / Quality / Reliability              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

这张图是整个 Harness 方法论的**总地图**。

后面的所有概念，都应该能够在这张图中找到位置。

---

# 3. 从用户请求到最终结果的完整流转

如果把 Harness 看成一条流水线：

```text
User Request
     │
     ▼
┌─────────────┐
│   Session   │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ Task / Intent    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Context Builder  │
└────────┬─────────┘
         │
         ├── System Instructions
         ├── Conversation
         ├── Short-term Memory
         ├── Long-term Memory
         ├── RAG
         ├── Tool Results
         └── State
         │
         ▼
┌──────────────────┐
│   Agent Runtime  │
└────────┬─────────┘
         │
         ▼
      Model
         │
         ▼
┌─────────────────────┐
│ Decision             │
│                     │
│ Final Answer?        │
│ Tool Call?           │
│ Ask User?            │
│ Continue?            │
└──────────┬──────────┘
           │
      ┌────┴────┐
      │         │
      ▼         ▼
   Answer      Tool
                │
                ▼
          ┌─────────────┐
          │   Control   │
          │ Permission  │
          │ Validation  │
          │ Guardrail   │
          └──────┬──────┘
                 │
                 ▼
            Execute Tool
                 │
                 ▼
            Tool Result
                 │
                 ▼
             Update State
                 │
                 ▼
          Update Memory
                 │
                 ▼
          Build New Context
                 │
                 ▼
              Model
                 │
                 ▼
                ...
```

因此 Agent 并不是：

```text
User → LLM → Answer
```

而更接近：

```text
User
 ↓
Session
 ↓
Context
 ↓
Runtime
 ↓
Model
 ↓
Decision
 ↓
Tool
 ↓
Observation
 ↓
State
 ↓
Memory
 ↓
Context
 ↓
Model
 ↓
...
 ↓
Final Answer
```

---

# 4. Harness 的核心分层

可以把整个系统分成八个核心领域：

```text
Agent Harness
│
├── 1. Session
│
├── 2. Context
│
├── 3. Runtime
│
├── 4. State
│
├── 5. Memory / Knowledge
│
├── 6. Tools / Control
│
├── 7. Observability
│
└── 8. Evaluation
```

其中：

```text
Session
   ↓
Context
   ↓
Runtime
   ↓
Model + Tools
   ↓
State / Memory
   ↓
Context
```

构成 Agent 的**运行主循环**。

而：

```text
Control
Observability
Evaluation
```

是横切能力。

---

# 5. Session

## 5.1 Session 是什么

Session 是 Agent 一次持续交互和执行的容器。

可以理解成：

```text
Session
=
“这一次 Agent 与用户之间的完整运行空间”
```

它通常包含：

```text
Session
├── session_id
├── user_id
├── conversation_id
├── messages
├── current_task
├── state
├── metadata
├── memory references
└── execution information
```

---

## 5.2 Session、Conversation、Message 的关系

不要把三个概念混在一起。

```text
User
 │
 └── Session
       │
       └── Conversation
              │
              ├── Message
              ├── Message
              ├── Message
              └── Message
```

可以简单理解为：

```text
Session
= 一次运行环境

Conversation
= 一段对话

Message
= 对话中的单条消息
```

---

# 6. Context Engineering

Context 是：

> **某一次 Model 调用时，真正送给模型的信息集合。**

这是非常重要的概念。

```text
Memory ≠ Context

Knowledge ≠ Context

History ≠ Context
```

这些都是 Context 的**来源**。

最终：

```text
Memory
History
RAG
State
Tool Result
System Prompt
Task
      │
      ▼
Context Builder
      │
      ▼
Final Context
      │
      ▼
LLM
```

---

## 6.1 Context 总图

```text
                    Context Builder
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
   Instructions         Memory           Knowledge
        │                 │                 │
        │          ┌──────┴──────┐          │
        │          │             │          │
        │          ▼             ▼          ▼
        │     Short-term    Long-term     RAG
        │       Memory       Memory
        │          │             │
        └──────────┴─────────────┴──────────┐
                                           │
                         ┌─────────────────┘
                         ▼
                     Task Context
                         │
                         ▼
                    Current State
                         │
                         ▼
                    Tool Results
                         │
                         ▼
                 Context Assembly
                         │
                         ▼
                       LLM
```

---

# 7. Memory

Memory 的核心目的是：

> **让 Agent 能够跨越当前 Context 保存和使用信息。**

Memory 可以分成：

```text
Memory
│
├── Short-term Memory
│
├── Working Memory
│
├── Summary / Compaction
│
└── Long-term Memory
```

---

# 8. Short-term Memory

短时记忆主要解决：

> **当前任务 / 当前对话，我刚刚知道了什么？**

典型内容：

```text
最近 N 条消息
最近工具结果
当前任务上下文
当前执行历史
临时事实
```

例如：

```text
User:
帮我分析这块地。

Agent:
好的。

User:
土壤湿度是 21%。

Agent:
21% 偏低。

User:
天气预报说明天下雨。

```

这些信息通常属于当前 Session 的短时信息。

---

# 9. Long-term Memory

长期记忆解决：

> **这个用户 / 实体过去长期积累了什么信息？**

例如：

```text
User
├── 姓名
├── 偏好
├── 常用地点
├── 农场信息
├── 种植习惯
└── 历史事实
```

长期记忆不应该简单理解成：

```text
所有历史聊天
```

更合理的是：

```text
Long-term Memory
=
经过提取、整理、筛选后的长期有效信息
```

---

# 10. Short-term 与 Long-term Memory 的关系

```text
                  Session
                     │
                     ▼
              Conversation
                     │
                     ▼
             Short-term Memory
                     │
                     │
              Summary / Extract
                     │
                     ▼
             Long-term Memory
```

典型生命周期：

```text
新消息
 ↓
进入 Session
 ↓
Short-term Memory
 ↓
Context Window 越来越大
 ↓
Summary / Compaction
 ↓
提取长期有效事实
 ↓
Long-term Memory
```

---

# 11. Working Memory

Working Memory 更接近：

> **Agent 当前正在处理的临时工作空间。**

例如任务：

```text
“帮我规划一个 100 亩西瓜种植方案”
```

Working Memory 可能包含：

```text
目标：100亩西瓜
地点：四川
品种：X
预算：Y
当前阶段：灌溉方案
已经完成：
  - 土壤分析
  - 天气查询
待完成：
  - 灌溉计算
  - 施肥方案
```

它通常属于当前任务 State 的一部分。

---

# 12. Knowledge / RAG

Memory 和 Knowledge 不应该混为一谈。

```text
Memory
=
关于用户、Agent、历史行为的记忆

Knowledge
=
外部知识
```

例如：

```text
Long-term Memory
→ 用户有 100 亩地

Knowledge Base
→ 西瓜最佳灌溉条件

RAG
→ 从知识库检索相关内容
```

关系：

```text
                   Context
                      ↑
          ┌───────────┴───────────┐
          │                       │
       Memory                 Knowledge
          │                       │
   用户/历史事实              外部知识
          │                       │
          │                      RAG
          │                       │
          └───────────┬───────────┘
                      │
                      ▼
                Context Builder
```

---

# 13. Agent Runtime

Runtime 是 Harness 的核心执行引擎。

它负责：

```text
什么时候调用模型
什么时候调用工具
什么时候继续
什么时候停止
什么时候重试
什么时候等待用户
什么时候恢复
```

最基本的 Agent Loop：

```text
        ┌─────────────┐
        │   Observe   │
        └──────┬──────┘
               ↓
        ┌─────────────┐
        │   Context   │
        └──────┬──────┘
               ↓
        ┌─────────────┐
        │    Model    │
        └──────┬──────┘
               ↓
        ┌─────────────┐
        │   Decide    │
        └──────┬──────┘
               ↓
       ┌───────┼────────┐
       │       │        │
       ↓       ↓        ↓
     Answer   Tool     Human
       │       │        │
       │       ↓        ↓
       │    Execute   Wait
       │       │
       │       ↓
       │   Observation
       │       │
       └───────┴──────────→ Context
```

---

# 14. State

State 解决的问题是：

> **Agent 当前执行到哪里了？**

例如：

```text
State
├── task
├── current_step
├── plan
├── variables
├── tool_results
├── pending_action
├── status
└── errors
```

例如：

```text
Task:
分析农场灌溉

State:

status = running

completed:
- weather_query
- soil_query

current_step:
- irrigation_calculation

pending:
- generate_recommendation
```

---

# 15. State 与 Memory 的区别

这是必须分清楚的一组概念。

```text
State
=
现在正在发生什么？

Memory
=
过去留下了什么？
```

例如：

```text
State:
当前正在分析 A 农场。

Memory:
用户过去种过西瓜。

Knowledge:
西瓜的灌溉知识。

Session:
用户当前这次对话。

Context:
这一次模型调用真正看到的信息。
```

这五个概念不要混在一起。

---

# 16. Tool Runtime

Tool 是 Agent 与外部世界交互的接口。

```text
Agent
  │
  ├── Search
  ├── Database
  ├── API
  ├── Calculator
  ├── Computer
  ├── File System
  └── Business System
```

工具调用生命周期：

```text
Model Decision
      │
      ▼
Tool Selection
      │
      ▼
Parameter Generation
      │
      ▼
Validation
      │
      ▼
Permission
      │
      ▼
Tool Execution
      │
      ▼
Tool Result
      │
      ▼
Observation
      │
      ▼
State Update
```

---

# 17. Control

Control 是 Harness 防止 Agent 失控的重要机制。

可以分为：

```text
Control
│
├── Permission
├── Policy
├── Guardrail
├── Validation
├── Approval
├── Human-in-the-loop
└── Recovery
```

---

## 17.1 Permission

解决：

> Agent 有没有权限做？

例如：

```text
普通 Agent
→ 可以查询

Admin Agent
→ 可以修改

高风险 Agent
→ 修改前必须审批
```

---

## 17.2 Guardrail

解决：

> Agent 的行为是否符合规则？

例如：

```text
输入 Guardrail
→ 用户输入是否危险

输出 Guardrail
→ 输出是否违反要求

Tool Guardrail
→ 工具调用是否危险
```

---

# 18. Human-in-the-loop

某些操作不能完全交给 Agent。

例如：

```text
Agent
 ↓
准备删除数据
 ↓
Risk Check
 ↓
需要人工确认
 ↓
Human
 ↓
Approve / Reject
 ↓
Agent Continue
```

因此：

```text
Agent
不一定总是
自动执行
```

成熟 Harness 应该允许：

```text
Continue
Pause
Ask Human
Resume
Reject
Abort
```

---

# 19. Retry / Timeout / Recovery

真实 Agent 必然会失败。

例如：

```text
Tool Timeout
API Error
Model Error
Invalid Parameters
Network Error
Permission Error
```

Harness 应该负责：

```text
Error
 ↓
Classify
 ↓
Retry?
 ├── Yes
 │    ↓
 │  Retry
 │
 └── No
      ↓
   Fallback
      ↓
   Human
      ↓
   Abort
```

---

# 20. Checkpoint

Checkpoint 用于保存 Agent 当前执行状态。

```text
Task
 ↓
Step 1
 ↓
Checkpoint
 ↓
Step 2
 ↓
Checkpoint
 ↓
Step 3
 ↓
Failure
```

恢复：

```text
Failure
 ↓
Load Checkpoint
 ↓
Restore State
 ↓
Continue Step 3
```

这样 Agent 才能支持长任务。

---

# 21. Observability

Agent 的运行过程必须能够被观察。

核心对象：

```text
Trace
│
├── Run
│
├── Span
│
├── Model Call
│
├── Tool Call
│
├── Retrieval
│
├── State Change
│
└── Error
```

例如：

```text
Trace: task-123

├── Session
│
├── Context Build
│
├── LLM Call
│
├── Tool: weather
│   ├── input
│   ├── latency
│   └── output
│
├── State Update
│
├── LLM Call
│
└── Final Answer
```

---

# 22. 为什么 Trace 很重要

如果 Agent 最终回答错误：

```text
“模型能力不行”
```

是不够的。

Harness Trace 应该让我们找到：

```text
到底哪里出了问题？

Context 错？
    ↓
Retrieval 错？
    ↓
Memory 错？
    ↓
Tool Selection 错？
    ↓
Tool Parameter 错？
    ↓
Tool Execution 错？
    ↓
State 错？
    ↓
Model Reasoning 错？
```

这就是 Agent Engineering 与普通 Chatbot 最大的区别之一。

---

# 23. Evaluation

Evaluation 不应该只评价最终答案。

应该评价整个 Agent Trajectory。

```text
Evaluation
│
├── Final Answer Eval
│
├── Context Eval
│
├── Retrieval Eval
│
├── Tool Selection Eval
│
├── Tool Argument Eval
│
├── State Transition Eval
│
├── Trajectory Eval
│
├── Safety Eval
│
└── Cost / Latency Eval
```

例如：

```text
任务
 ↓
Context
 ↓
Tool Selection
 ↓
Tool Arguments
 ↓
Execution
 ↓
State
 ↓
Final Answer
```

整个链路都可以被评估。

---

# 24. Harness 的横向关系

把所有东西重新压缩：

```text
                         AGENT HARNESS

 ┌────────────────────────────────────────────────────────────┐
 │                                                            │
 │                         SESSION                            │
 │                            │                               │
 │                            ▼                               │
 │                     CONTEXT ENGINE                         │
 │                            │                               │
 │          ┌─────────────────┼─────────────────┐             │
 │          │                 │                 │             │
 │       Memory            Knowledge          State           │
 │          │                 │                 │             │
 │          └─────────────────┼─────────────────┘             │
 │                            │                               │
 │                            ▼                               │
 │                      AGENT RUNTIME                         │
 │                            │                               │
 │                     ┌──────┴──────┐                        │
 │                     ↓             ↓                        │
 │                   MODEL         TOOLS                      │
 │                     │             │                        │
 │                     └──────┬──────┘                        │
 │                            ↓                               │
 │                         CONTROL                            │
 │                            │                               │
 │                            ↓                               │
 │                      STATE UPDATE                          │
 │                            │                               │
 │                  ┌─────────┴─────────┐                     │
 │                  ↓                   ↓                     │
 │                Memory              Session                 │
 │                  │                   │                     │
 │                  └─────────┬─────────┘                     │
 │                            ↓                               │
 │                       NEXT LOOP                            │
 │                                                            │
 │  ───────────────────────────────────────────────────────── │
 │                                                            │
 │                  OBSERVABILITY / TRACE                     │
 │                            │                               │
 │                            ↓                               │
 │                        EVALUATION                          │
 │                                                            │
 └────────────────────────────────────────────────────────────┘
```

---

# 25. 一次完整 Agent Run

假设用户说：

> “帮我判断我的西瓜地明天需不需要灌溉。”

Harness 可能经历：

```text
① Session

用户是谁？
当前是哪次 Session？
当前是哪段 Conversation？

        ↓

② Context

加载：
- 当前问题
- 最近对话
- 用户农场信息
- 土壤信息
- 必要历史信息

        ↓

③ Runtime

Agent 判断：
需要天气信息
需要土壤信息

        ↓

④ Tool

调用：
weather API
soil database

        ↓

⑤ Control

检查：
- Agent 是否有权限？
- 参数是否合法？
- 工具是否允许？

        ↓

⑥ Tool Result

返回：
天气
土壤湿度

        ↓

⑦ State

更新：
weather_checked = true
soil_checked = true

        ↓

⑧ Context

重新构建 Context

        ↓

⑨ Model

模型判断：
明天有降雨，因此暂不建议灌溉

        ↓

⑩ Final Answer

返回用户

        ↓

⑪ Memory

如果产生长期有效事实：
写入 Long-term Memory

        ↓

⑫ Trace

记录整个过程

        ↓

⑬ Evaluation

判断：
答案是否正确？
工具是否正确？
执行过程是否合理？
```

---

# 26. 一个关键概念：Context 是动态的

很多初学者会认为：

```text
Context
=
Prompt
```

实际上：

```text
Context
=
动态构建出来的模型输入
```

它可能随着 Agent Loop 不断变化：

```text
Context₀
   ↓
Model
   ↓
Tool Call
   ↓
Tool Result
   ↓
Context₁
   ↓
Model
   ↓
Tool Call
   ↓
Tool Result
   ↓
Context₂
   ↓
Model
   ↓
Final
```

所以 Context Engineering 和 Agent Runtime 是高度耦合的。

---

# 27. 一个关键概念：Memory 不等于数据库

数据库只是存储介质。

真正的 Memory 系统还需要：

```text
Write
 ↓
Extract
 ↓
Classify
 ↓
Store
 ↓
Retrieve
 ↓
Rank
 ↓
Inject
 ↓
Update
 ↓
Forget
```

因此：

```text
Memory System
=
Memory Policy
+
Storage
+
Retrieval
+
Context Integration
```

---

# 28. 一个关键概念：Runtime 不等于 Agent Loop

Agent Loop 只是 Runtime 的核心部分。

完整 Runtime 还可能包括：

```text
Runtime
│
├── Scheduling
├── Agent Loop
├── State Management
├── Tool Execution
├── Retry
├── Timeout
├── Checkpoint
├── Recovery
├── Concurrency
└── Cancellation
```

---

# 29. 一个关键概念：Harness 是横向系统

Harness 不是简单的一条流水线。

更准确地说：

```text
                    ┌───────────────┐
                    │    Session    │
                    └───────┬───────┘
                            │
                            ↓
                       Context
                            │
                            ↓
                        Runtime
                            │
                    ┌───────┴───────┐
                    ↓               ↓
                  Model           Tools
                    │               │
                    └───────┬───────┘
                            ↓
                          State
                            │
                    ┌───────┴───────┐
                    ↓               ↓
                  Memory         Session

════════════════════════════════════════════════════

          Control / Observability / Evaluation

        横向贯穿整个 Agent 生命周期
```

也就是说：

**Runtime 是纵向执行主线。**

**Control、Observability、Evaluation 是横向基础设施。**

这是理解 Harness 架构非常重要的一点。

---

# 30. Harness 与传统后端系统的区别

传统系统通常：

```text
Request
 ↓
Business Logic
 ↓
Database
 ↓
Response
```

流程比较确定。

Agent 系统：

```text
Request
 ↓
Agent
 ↓
Decision
 ↓
Tool
 ↓
Observation
 ↓
Decision
 ↓
Tool
 ↓
...
```

Agent 的下一步具有不确定性。

因此需要 Harness 提供：

```text
State
Control
Recovery
Memory
Observability
Evaluation
```

来把“不确定的模型行为”包裹在“确定的工程系统”里。

---

# 31. Harness 的本质

最终可以把 Harness 总结成一句话：

> **Harness 是把一个具有非确定性决策能力的 LLM，包装成一个具有状态、记忆、工具、控制、恢复、观测和评估能力的可靠 Agent Runtime。**

可以进一步抽象成：

```text
                 LLM
                  │
          非确定性决策能力
                  │
                  ▼
        ┌───────────────────┐
        │      Harness      │
        │                   │
        │ Context           │
        │ State             │
        │ Runtime           │
        │ Memory            │
        │ Tools             │
        │ Control           │
        │ Recovery          │
        │ Trace             │
        │ Evaluation        │
        └─────────┬─────────┘
                  │
                  ▼
           Reliable Agent
```

---

# 32. 学习路线

这份文档不应该一次全部学完。

应该按照架构地图逐个击破。

## Phase 1：基础对象

* [ ] Session
* [ ] Conversation
* [ ] Message
* [ ] Task
* [ ] State

## Phase 2：Context

* [ ] Context 是什么
* [ ] Context Builder
* [ ] Context Window
* [ ] Sliding Window
* [ ] Summary / Compaction
* [ ] Context Selection

## Phase 3：Memory

* [ ] Working Memory
* [ ] Short-term Memory
* [ ] Long-term Memory
* [ ] Memory Write
* [ ] Memory Retrieval
* [ ] Memory Update
* [ ] Memory Forgetting

## Phase 4：Knowledge

* [ ] Knowledge Base
* [ ] Retrieval
* [ ] RAG
* [ ] Ranking
* [ ] Context Injection

## Phase 5：Runtime

* [ ] Agent Loop
* [ ] Observe / Decide / Act
* [ ] State Machine
* [ ] Planner
* [ ] Execution
* [ ] Multi-step Task

## Phase 6：Tools

* [ ] Tool Definition
* [ ] Tool Selection
* [ ] Tool Arguments
* [ ] Tool Execution
* [ ] Tool Result
* [ ] Tool Error

## Phase 7：Reliability

* [ ] Retry
* [ ] Timeout
* [ ] Fallback
* [ ] Checkpoint
* [ ] Recovery
* [ ] Cancellation
* [ ] Idempotency

## Phase 8：Control

* [ ] Permission
* [ ] Policy
* [ ] Guardrail
* [ ] Validation
* [ ] Human-in-the-loop
* [ ] Approval

## Phase 9：Observability

* [ ] Trace
* [ ] Span
* [ ] Log
* [ ] Metrics
* [ ] Token
* [ ] Latency
* [ ] Cost
* [ ] Tool Trace
* [ ] State Trace

## Phase 10：Evaluation

* [ ] Final Answer Evaluation
* [ ] Context Evaluation
* [ ] Retrieval Evaluation
* [ ] Tool Evaluation
* [ ] Trajectory Evaluation
* [ ] Safety Evaluation
* [ ] Regression Evaluation
* [ ] Online Evaluation

## Phase 11：Architecture

* [ ] 单 Agent Harness
* [ ] Multi-Agent Harness
* [ ] Workflow + Agent
* [ ] Long-running Agent
* [ ] Event-driven Agent
* [ ] Production Agent Runtime

---

# 33. 最终学习目标

最终应该能够独立回答下面这些问题：

```text
Session 是什么？
        ↓
Conversation 是什么？
        ↓
State 是什么？
        ↓
Memory 是什么？
        ↓
Context 是怎么生成的？
        ↓
Agent Runtime 怎么运行？
        ↓
Model 如何决定下一步？
        ↓
Tool 如何执行？
        ↓
Control 如何限制 Agent？
        ↓
失败如何 Retry / Recovery？
        ↓
状态如何 Checkpoint？
        ↓
整个过程如何 Trace？
        ↓
如何 Evaluation？
```

最终形成：

```text
                     AGENT HARNESS

                           User
                            │
                            ▼
                         Session
                            │
                            ▼
                     Context Builder
                            │
            ┌───────────────┼───────────────┐
            │               │               │
         Memory          Knowledge        State
            │               │               │
            └───────────────┼───────────────┘
                            │
                            ▼
                       Agent Runtime
                            │
                     ┌──────┴──────┐
                     ↓             ↓
                   Model         Tools
                     │             │
                     └──────┬──────┘
                            ↓
                         Control
                            │
                            ↓
                         State
                            │
                    ┌───────┴───────┐
                    ↓               ↓
                  Memory          Session
                    │               │
                    └───────┬───────┘
                            ↓
                       Next Loop
                            │
                            ↓
                           ...

              ─────────────────────────

                Trace / Observability
                         │
                         ↓
                     Evaluation
```

**以后学习 Harness 时，就以这张图作为总地图。**

每一个 Todo 只解决其中一个节点，不再把整个体系重新展开。

例如下一步只学习：

> **Todo 01：Session**

只回答：

```text
Session 是什么？
为什么需要 Session？
Session 和 Conversation 有什么区别？
Session 里面保存什么？
Session 和 State / Memory / Context 的边界在哪里？
一次 Session 的生命周期是什么？
```

学完再进入 Todo 02，不提前跳到后面的内容。
