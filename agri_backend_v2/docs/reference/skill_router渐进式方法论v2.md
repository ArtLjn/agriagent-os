# Agent Harness：Skill / Tool Routing 方法论

## 1. 核心原则

Agent Harness 中是否需要 Skill Router，不应该由 Skill / Tool 数量单独决定。

正确的判断方式是：

> **Routing 带来的 Context、准确率和成本收益，是否大于 Routing 本身增加的延迟和 Token 成本。**

因此：

```text
不要：
“有很多 Skill → 一定需要 Router”

而应该：
“Main Agent 的 Tool Selection / Context 是否已经成为问题？”
                         │
                         ↓
                       Measure
                         │
              ┌──────────┴──────────┐
              ↓                     ↓
             No                    Yes
              │                     │
              ↓                     ↓
        保持当前架构          引入 Routing
```

---

# 2. 第一原则：先建立 Baseline

对于一个 Agent，最简单也是最重要的 Baseline 是：

```text
User
 │
 ▼
Context Builder
 │
 ├── System
 ├── Conversation
 ├── Memory
 ├── Task State
 └── Tool Schemas
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

也就是：

> **直接把可用 Tool Schema 提供给 Main Agent，让 Main Agent 自己完成 Tool Selection。**

这应该永远是 Routing 方案的对照组。

---

# 3. 为什么不能默认使用 Router

一个独立的 LLM Router 意味着：

```text
User
 ↓
Router LLM
 ↓
Context Builder
 ↓
Main Agent LLM
 ↓
Tool
```

相比 Baseline：

```text
User
 ↓
Context Builder
 ↓
Main Agent LLM
 ↓
Tool
```

增加了一次 LLM Call。

因此增加：

```text
Router Latency
+
Router Input Tokens
+
Router Output Tokens
+
额外失败概率
```

所以 Router 不是免费的。

---

# 4. Routing 的收益是什么

Router 只有在能够显著改善 Main Agent 时才值得引入。

主要收益包括：

### 4.1 降低 Main Agent Context

例如：

```text
53 Tool Schemas
        ↓
10 Relevant Tool Schemas
```

降低：

```text
Prompt Tokens
Context Pressure
Tool Selection Search Space
```

---

### 4.2 提高 Tool Selection

如果 Main Agent 面对大量 Tool：

```text
Tool A
Tool B
Tool C
...
Tool 53
```

开始出现：

```text
Wrong Tool
Tool Confusion
Argument Errors
```

Routing 可以提前缩小候选空间。

---

### 4.3 为大规模 Tool System 提供扩展能力

当系统从：

```text
53 Tools
```

增长到：

```text
300
500
1000+
```

全部 Schema 注入 Main Agent 的方式会越来越难以维持。

这时 Routing 才逐渐从：

```text
Optimization
```

变成：

```text
Architecture Requirement
```

---

# 5. Routing 的正确定位

Routing 不应该被理解成：

> “Agent 必须拥有的一个固定组件。”

而应该理解成：

> **一种用于控制 Agent Capability Space 的优化机制。**

因此：

```text
Routing
```

属于：

```text
Runtime Optimization
```

而不是：

```text
Agent Core Requirement
```

---

# 6. 推荐的架构演进路线

## Phase 1：Direct Tool Exposure

适合：

```text
少量 Skill
少量 / 中等 Tool
Main Agent Tool Selection 表现良好
```

架构：

```text
                 User
                  │
                  ▼
           Context Builder
                  │
                  ├── History
                  ├── Memory
                  ├── Task State
                  └── Tool Schemas
                         │
                         ▼
                    Main Agent
                         │
                         ▼
                     Tool Call
```

这是默认方案。

---

# 7. Phase 1 的评估指标

不要凭感觉判断是否需要 Router。

至少记录：

```text
Tool Selection Accuracy
Tool Argument Accuracy
Prompt Tokens
Context Tokens
Main Agent Latency
Tool Execution Latency
Total Cost
```

特别关注：

```text
Tool Selection Accuracy
Context Token Consumption
End-to-End Latency
```

---

# 8. Phase 2：Lightweight Tool Discovery

当 Tool 数量增长或者 Context 开始变大时，第一步不应该立即增加一个 LLM Router。

可以先做：

```text
User
 │
 ▼
Tool Discovery
 │
 │ BM25 / Vector / Metadata / Rules
 ▼
Candidate Tools
 │
 ▼
Context Builder
 │
 ▼
Main Agent
```

例如：

```text
53 Tools
   ↓
Candidate Retrieval
   ↓
10~20 Tools
   ↓
Main Agent
```

这里没有额外 LLM Call。

因此相比 LLM Router：

```text
Latency 增量 ≈ Retrieval Latency
```

而不是：

```text
Latency 增量 ≈ Another LLM Call
```

---

# 9. Retrieval 的正确定位

BM25、Vector、Hybrid Retrieval 不应该直接被定义为：

> Skill Router。

更准确的定义是：

> **Capability / Tool Discovery Mechanism**

它解决的是：

```text
从大量 Capability / Tool 中
快速召回可能相关的候选集合。
```

因此：

```text
Retrieval
     ↓
Recall
```

而不是：

```text
Retrieval
     ↓
最终 Tool Decision
```

最终 Tool Decision 仍然可以交给 Main Agent。

---

# 10. Phase 3：LLM-based Routing

只有当 Lightweight Discovery 不够时，再考虑独立的 LLM Router。

架构：

```text
                  User
                   │
                   ▼
            LLM-based Router
                   │
              Skill / Capability
                   │
                   ▼
             Tool Discovery
                   │
             Candidate Tools
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

这里 Router 的任务是：

> **根据任务语义判断 Main Agent 需要哪些能力。**

---

# 11. LLM Router 不应该执行任务

Router 应该是一个非常轻量的判定器。

它不负责：

```text
Tool Execution
Task Completion
User Conversation
Long-term Planning
```

它只负责：

```text
User Request
      ↓
Required Capability
      ↓
Relevant Skill
```

例如：

```text
User：

分析一下这个 GitHub 项目最近为什么社区活跃度下降。
```

Router：

```json
{
  "skills": [
    "github",
    "web"
  ]
}
```

然后 Main Agent 才获得对应 Tool。

---

# 12. Router 与 Context Builder 的关系

如果采用独立 LLM Router：

```text
User
 │
 ▼
Router
 │
 ▼
Selected Skills
 │
 ▼
Skill / Tool Registry
 │
 ▼
Context Builder
 │
 ▼
Main Agent
```

Router 必须发生在 Context Builder 决定最终 Agent Context 之前。

---

# 13. Router 是否“占用 Context”

需要区分：

### Router Context

Router 自己有一次 LLM Context：

```text
User Request
+
Skill Metadata
```

因此：

> Router 会消耗 Token。

### Main Agent Context

Router 的中间推理不会进入 Main Agent：

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
Selected Skills
+
Selected Tool Schemas
```

因此：

> **Router 不增加 Main Agent 的 Context，但会增加一次额外 LLM Call。**

---

# 14. LLM Router 的核心 Trade-off

Routing 的本质是：

```text
               Router Cost
                   │
                   │
                   ▼
         ┌────────────────────┐
         │ Context / Accuracy │
         │       Gain         │
         └────────────────────┘
```

只有：

```text
Routing Gain
>
Routing Cost
```

才值得使用。

可以抽象成：

```text
Routing Value
=
Context Savings
+
Tool Accuracy Improvement
+
Error Reduction
-
Router Latency
-
Router Token Cost
```

这不是严格的数学公式，而是架构决策模型。

---

# 15. 当前 15 Skill / 53 Tool 的建议

对于当前规模：

```text
15 Skills
53 Tools
```

不要默认使用独立 LLM Router。

推荐先采用：

```text
User
 ↓
Context Builder
 ↓
53 Tool Schemas
 ↓
Main Agent
 ↓
Tool Call
```

然后测量。

如果表现良好：

> **保持简单架构。**

如果 Context 或 Tool Selection 开始出现问题：

```text
User
 ↓
Lightweight Tool Discovery
 ↓
10~20 Candidate Tools
 ↓
Main Agent
```

如果进一步发现：

```text
Task Semantics Complex
+
Tool Discovery Recall 不足
+
Tool 数量持续增长
```

再升级：

```text
User
 ↓
LLM Router
 ↓
Skill / Capability
 ↓
Tool Discovery
 ↓
Main Agent
```

---

# 16. 推荐的最终演进模型

整个 Harness 可以采用渐进式架构：

```text
                    Agent Harness
                          │
                          ▼
                  ┌───────────────┐
                  │    Baseline   │
                  │               │
                  │ Main Agent    │
                  │ + All Tools   │
                  └───────┬───────┘
                          │
                       Measure
                          │
                          ▼
                 Tool Selection /
                 Context 是否成为问题？
                    /             \
                  No               Yes
                   │                 │
                   ▼                 ▼
               Keep Simple    Lightweight Discovery
                                     │
                                  Measure
                                     │
                                     ▼
                              是否仍然不足？
                                /       \
                              No         Yes
                               │           │
                               ▼           ▼
                           Keep        LLM Router
                                       │
                                       ▼
                                Skill / Capability
                                       │
                                       ▼
                                 Tool Discovery
                                       │
                                       ▼
                                  Main Agent
```

---

# 17. 大规模 Agent 的最终形态

当系统发展到：

```text
100+ Skills
500+ Tools
1000+ Tools
```

可以逐渐演进到：

```text
                         User
                          │
                          ▼
                    Domain Router
                          │
                          ▼
                    Skill Router
                          │
                          ▼
                 Capability Retrieval
                          │
                          ▼
                      Reranker
                          │
                          ▼
                   Relevant Tools
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

但这属于规模化阶段，而不是当前 15 Skill / 53 Tool 的默认架构。

---

# 18. 最终方法论原则

### 原则 1：Simple First

> **能用一次 Main Agent LLM 解决，就不要增加额外 LLM Call。**

---

### 原则 2：Measure Before Routing

> **是否需要 Router，由 Tool Selection、Context、Latency、Cost 数据决定，而不是由 Tool 数量决定。**

---

### 原则 3：Retrieval First, LLM Routing Later

当 Tool 数量增长时：

```text
All Tools
 ↓
Lightweight Discovery
 ↓
LLM Routing
```

而不是：

```text
All Tools
 ↓
LLM Router
```

直接增加额外模型调用。

---

### 原则 4：Routing 是优化，不是必选组件

```text
Agent
 ├── Context
 ├── Runtime
 └── Control

Runtime
 ├── Tool Registry
 ├── Tool Executor
 ├── Context Builder
 └── [Optional] Router
```

Router 是：

```text
Optional Runtime Component
```

而不是 Agent 必须具备的基础组件。

---

### 原则 5：Main Agent 永远负责最终任务执行

Router 可以缩小能力空间：

```text
Router
 ↓
Relevant Skills / Tools
```

但最终：

```text
Main Agent
 ↓
Reasoning
 ↓
Tool Selection
 ↓
Argument Generation
 ↓
Execution
```

仍然由 Main Agent 完成。

---

# 19. 一句话总结

> **Agent Harness 的正确路线不是“先设计一个 Router”，而是“先让 Main Agent 在完整能力空间中工作，测量问题，再逐步引入 Capability Discovery 和 LLM-based Routing 来控制 Context 与 Tool Selection Space”。**

对于当前：

```text
15 Skills
53 Tools
```

默认选择：

```text
All Tools → Main Agent
```

只有当测量证明：

```text
Context 成本 ↑
Tool Selection Accuracy ↓
```

才逐步引入：

```text
Lightweight Discovery
```

再进一步才是：

```text
LLM-based Skill Router
```

最终形成：

```text
Simple
  ↓
Discovery
  ↓
LLM Routing
  ↓
Hierarchical Routing
```

这是 Harness 中 **Routing 的渐进式演进方法论**。
