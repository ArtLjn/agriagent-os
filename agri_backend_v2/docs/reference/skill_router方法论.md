# LLM-based Skill Router 方法论

## 1. 核心结论

对于当前 Agent：

* **15 个 Skill**
* **53 个 Tool Schema**

推荐采用：

> **LLM-based Skill Router + Dynamic Context Construction**

核心思想是：

```text
User Request
      │
      ▼
LLM-based Skill Router
      │
      │ 选择相关 Skill
      ▼
Skill Registry
      │
      │ 获取对应能力 / Tool
      ▼
Context Builder
      │
      │ 只注入本轮相关 Context
      ▼
Main Agent LLM
      │
      ▼
Tool Call
```

Router 的职责不是执行任务，而是回答：

> **“为了完成当前任务，Main Agent 需要获得哪些 Skill / Capability？”**

---

# 2. 为什么需要 Skill Router

如果不做 Router，最简单的实现是：

```text
User
  │
  ▼
Context Builder
  │
  ├── History
  ├── Memory
  ├── 15 Skills
  └── 53 Tool Schemas
          │
          ▼
      Main Agent
```

这种方式在 Tool 数量较小时完全可行。

但随着 Tool 增长，会产生两个问题：

### 2.1 Context 膨胀

大量 Tool Schema 会进入 Main Agent Context：

```text
System Prompt
+
Conversation
+
Memory
+
Task State
+
15 Skills
+
53 Tool Schemas
```

Tool Schema 本身可能占据大量 Token。

---

### 2.2 Tool Selection 搜索空间扩大

Main Agent 每一轮都需要从：

```text
53 Tools
```

中判断：

```text
哪个 Tool 能完成当前任务？
```

随着 Tool 数量增长，Tool Selection 会越来越困难。

因此可以在 Main Agent 之前增加一个：

```text
Capability Routing Layer
```

提前缩小能力空间。

---

# 3. LLM-based Router 的定位

LLM-based Router 不应该被理解成一个完整的 Agent。

它更准确的定义是：

> **Semantic Capability Planner**

即：

```text
User Request
      ↓
Task Understanding
      ↓
Required Capabilities
      ↓
Relevant Skills
```

它：

* 不执行 Tool
* 不完成任务
* 不和用户进行多轮对话
* 不维护完整 Agent State
* 不需要完整 Tool Schema
* 不负责最终 Tool 参数生成

它只负责：

> **能力选择。**

---

# 4. Router 与 Main Agent 的职责分离

这是整个设计最重要的原则。

## Router

负责：

```text
“需要什么能力？”
```

例如：

```text
用户：

帮我看看这个 GitHub 项目最近有哪些问题。
```

Router：

```json
{
  "skills": [
    "github"
  ]
}
```

---

## Main Agent

负责：

```text
“具体怎么完成？”
```

例如 Main Agent 获得：

```text
github.issue_search
github.repository_info
github.code_search
```

然后决定：

```text
调用 github.issue_search
```

并生成参数。

---

# 5. 推荐的整体架构

```text
                         User Request
                              │
                              ▼
                  ┌─────────────────────┐
                  │  LLM-based Router   │
                  │                     │
                  │ Skill Metadata      │
                  │ Capability Info     │
                  └──────────┬──────────┘
                             │
                      Selected Skills
                             │
                             ▼
                  ┌─────────────────────┐
                  │   Skill Registry    │
                  │                     │
                  │ Skill → Capabilities│
                  │ Skill → Tools       │
                  └──────────┬──────────┘
                             │
                       Relevant Tools
                             │
                             ▼
                  ┌─────────────────────┐
                  │   Context Builder   │
                  │                     │
                  │ System              │
                  │ Conversation        │
                  │ Memory              │
                  │ Task State          │
                  │ Selected Skills     │
                  │ Selected Schemas    │
                  └──────────┬──────────┘
                             │
                             ▼
                       Main Agent LLM
                             │
                             ▼
                         Tool Call
                             │
                             ▼
                       Tool Executor
```

---

# 6. 最关键的设计：Router 在 Context Builder 之前

推荐的数据流：

```text
Request
   │
   ▼
Router
   │
   ▼
Skill IDs
   │
   ▼
Registry
   │
   ▼
Context Builder
   │
   ▼
Main Agent
```

而不是：

```text
Request
   │
   ▼
Context Builder
   │
   ├── 全部 Skills
   ├── 全部 Tools
   │
   ▼
Main Agent
   │
   ▼
Router
```

后者已经失去了 Routing 的主要价值。

---

# 7. “Router 不占 Context”应该如何理解

这里需要准确区分两个概念。

### 错误理解

> Router 不消耗 Context。

这是不准确的。

Router 本身也是一次 LLM 调用，因此：

```text
Router Context
```

仍然存在。

---

### 正确理解

> **Router 的 Context 不进入 Main Agent Context。**

例如 Router：

```text
Router Context

User Request
+
15 Skill Metadata
```

输出：

```json
{
  "skills": ["github"]
}
```

然后 Main Agent：

```text
Main Agent Context

System
+
Conversation
+
Memory
+
Task State
+
GitHub Skill
+
Relevant Tool Schemas
```

因此可以理解为：

```text
Router Context
      │
      │ 只产生 routing decision
      ▼
Skill IDs
      │
      ▼
Main Agent Context
```

Router 的中间推理不需要进入 Main Agent。

---

# 8. Router 应该看到什么

Router 不应该看到完整的 53 个 Tool Schema。

推荐给 Router：

```text
Skill Metadata
```

例如：

```json
{
  "name": "github",
  "description": "Interact with GitHub repositories and development workflows",
  "capabilities": [
    "repository",
    "issue",
    "pull_request",
    "code_search"
  ]
}
```

另一个：

```json
{
  "name": "slack",
  "description": "Search and interact with Slack conversations",
  "capabilities": [
    "message_search",
    "channel_search",
    "conversation"
  ]
}
```

Router 只需要理解：

```text
Skill 能做什么
```

而不需要理解：

```text
Tool 参数具体是什么
```

---

# 9. Router 输出什么

推荐输出结构保持简单。

例如：

```json
{
  "skills": [
    "github"
  ]
}
```

对于多 Skill 任务：

```json
{
  "skills": [
    "github",
    "browser"
  ]
}
```

如果需要置信度，可以：

```json
{
  "skills": [
    {
      "name": "github",
      "confidence": 0.96
    },
    {
      "name": "browser",
      "confidence": 0.72
    }
  ]
}
```

但在第一版实现中，**不一定需要 confidence**。

优先保持 Router 简单。

---

# 10. 单 Skill 与多 Skill

Router 不应该强制：

```text
每次只能选择一个 Skill
```

因为真实任务可能天然需要多个能力。

例如：

```text
分析一个 GitHub 项目最近为什么社区讨论度下降。
```

可能需要：

```text
github
+
browser
```

因此 Router 应该输出：

```text
Top-K Skills
```

而不是：

```text
Top-1 Skill
```

推荐：

```text
K = 1~3
```

对于当前 15 Skill 的规模已经足够。

---

# 11. Router Prompt 的核心原则

Router Prompt 不需要复杂。

核心任务只有：

```text
Given the user request and available skills,
select the skills required to complete the task.
```

并明确：

```text
1. Select only relevant skills.
2. Multiple skills may be selected.
3. Do not execute tools.
4. Do not solve the task.
5. Return structured output only.
```

这样可以避免 Router 逐渐演化成一个完整 Agent。

---

# 12. 为什么 LLM Router 比纯 Vector Retrieval 更适合 Skill Routing

Vector Retrieval 本质上解决：

```text
Query
 ↓
Semantic Similarity
 ↓
Relevant Documents
```

而 Skill Routing 更接近：

```text
Query
 ↓
Task Understanding
 ↓
Required Capabilities
 ↓
Skills
```

例如：

```text
“帮我调查这个项目最近为什么活跃度下降。”
```

它不是简单寻找：

```text
最相似的 Skill
```

而是在判断：

```text
需要哪些能力完成调查？
```

这属于语义任务理解，因此 LLM 更适合承担最终 Routing Decision。

---

# 13. 但 LLM Router 不代表完全放弃 Retrieval

在未来 Skill 数量很大时，可以演进成：

```text
User Request
      │
      ▼
Candidate Retrieval
      │
      ▼
LLM Router
      │
      ▼
Selected Skills
```

其中 Retrieval 的职责：

> **提高召回率。**

LLM Router 的职责：

> **提高最终选择准确率。**

即：

```text
Retrieval → Recall
LLM Router → Precision
```

但是对于当前：

```text
15 Skills
```

没有必要为了 Routing 专门建立复杂的 Vector Database。

15 个 Skill Metadata 完全可以直接提供给 Router。

---

# 14. 当前规模的推荐方案

对于：

```text
15 Skills
53 Tools
```

推荐：

```text
                 User
                  │
                  ▼
           LLM Skill Router
                  │
             15 Skill Metadata
                  │
                  ▼
             Top 1~3 Skills
                  │
                  ▼
           Skill / Tool Registry
                  │
                  ▼
          Relevant Tool Schemas
                  │
                  ▼
            Context Builder
                  │
                  ▼
              Main Agent
                  │
                  ▼
              Tool Call
```

不推荐第一版就做：

```text
BM25
+
Vector
+
RRF
+
Reranker
+
LLM Router
```

因为对于 15 Skill 来说，这属于过度设计。

---

# 15. Context Builder 的位置

这是 Harness 中非常重要的一层。

推荐：

```text
Router
  ↓
Selected Skills
  ↓
Context Builder
  ↓
Main Agent
```

Context Builder 根据 Router 的结果决定：

```text
哪些 Skill 注入
哪些 Tool Schema 注入
哪些 Runtime State 注入
哪些 Memory 注入
```

因此 Context Builder 不应该简单理解成：

```text
拼接 Prompt
```

而应该理解成：

> **根据当前任务动态构建 Agent 可见世界。**

---

# 16. 最终 Harness 职责划分

可以形成以下职责边界：

```text
┌───────────────────────────────────────┐
│                Context                │
│                                       │
│ Conversation / Memory / Task State    │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│               Runtime                 │
│                                       │
│ Skill Registry                        │
│ Tool Registry                         │
│ Context Builder                       │
│ Tool Executor                         │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│                Router                 │
│                                       │
│ LLM-based Capability Selection        │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│              Main Agent               │
│                                       │
│ Reasoning / Tool Selection / Execution│
└───────────────────────────────────────┘
```

其中 Router 是 Runtime 中的一个**前置决策组件**。

---

# 17. 推荐的数据结构

Skill Registry：

```json
{
  "name": "github",
  "description": "Interact with GitHub repositories",
  "capabilities": [
    "repository",
    "issue",
    "pull_request",
    "code_search"
  ]
}
```

Tool Registry：

```json
{
  "name": "github.list_issues",
  "skill": "github",
  "description": "List issues in a GitHub repository",
  "input_schema": {}
}
```

Router：

```text
User Request
+
Skill Registry Metadata
        ↓
LLM
        ↓
["github"]
```

Context Builder：

```text
["github"]
        ↓
Skill Registry
        ↓
Tool Registry
        ↓
Relevant Tool Schemas
        ↓
Main Agent Context
```

---

# 18. 第一版实现原则

第一版不要追求复杂。

只实现：

```text
1. Skill Registry
2. Skill Metadata
3. LLM Skill Router
4. Context Builder
5. Dynamic Tool Schema Loading
```

暂时不需要：

```text
Vector DB
BM25
RRF
复杂 Reranker
Multi-level Router
Router Memory
```

---

# 19. 评估指标

是否应该保留 Router，不应该凭感觉决定。

至少记录：

```text
Skill Routing Accuracy
Tool Selection Accuracy
Tool Argument Accuracy
Main Agent Context Tokens
Router Tokens
Router Latency
End-to-End Latency
```

重点比较两个 baseline：

### Baseline A

```text
53 Tools
 ↓
Main Agent
```

### Baseline B

```text
Router
 ↓
Relevant Skills / Tools
 ↓
Main Agent
```

如果 B 能够：

```text
降低 Context Token
+
提高 Tool Selection Accuracy
+
可接受的 Router Latency
```

那么 Router 才真正产生价值。

---

# 20. 最终方法论

对于 Agent Harness，可以将 LLM-based Skill Router 总结为：

```text
                  User Request
                       │
                       ▼
              ┌────────────────┐
              │  Skill Router  │
              │                │
              │ LLM-based      │
              │ capability     │
              │ selection      │
              └───────┬────────┘
                      │
                Selected Skills
                      │
                      ▼
              ┌────────────────┐
              │ Skill Registry │
              └───────┬────────┘
                      │
                Relevant Tools
                      │
                      ▼
              ┌────────────────┐
              │ Context Builder│
              └───────┬────────┘
                      │
              Dynamic Context
                      │
                      ▼
              ┌────────────────┐
              │   Main Agent   │
              └───────┬────────┘
                      │
                      ▼
                 Tool Execute
```

核心原则只有四句话：

> **1. Router 负责“需要什么能力”，Main Agent 负责“怎么完成任务”。**

> **2. Router 在 Context Builder 之前运行。**

> **3. Router 的 Context 不进入 Main Agent Context，只输出 Skill Selection。**

> **4. 对 15 Skill / 53 Tool，优先使用简单的 LLM-based Router，不要过早引入复杂的 Vector/BM25/Reranker Pipeline。**

这套设计可以作为当前 Harness 的 **Skill Routing 基线架构**。当 Skill / Tool 数量继续增长，再逐步演进为：

```text
LLM Router
      ↓
Retrieval
      ↓
Reranker
      ↓
Hierarchical Skill / Tool Routing
```

而不需要推翻现有架构。
