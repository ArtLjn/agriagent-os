## ADDED Requirements

### Requirement: 长期记忆保持外部服务预留
系统 SHALL 将长期记忆和检索视为 Memory Service 接口能力，当前部署 SHALL NOT 要求主 backend 内置 RAG、向量数据库、embedding 模型或重排服务。

#### Scenario: 长期记忆未启用
- **WHEN** Agent 请求长期记忆或检索结果
- **THEN** Memory Service SHALL 返回空上下文或空检索结果，且 Agent 请求 SHALL 正常继续

### Requirement: 短期记忆不依赖 RAG 基础设施
系统 SHALL 支持在没有外部 RAG 服务的情况下使用短期记忆、会话消息窗口和 observation event。

#### Scenario: 小规格服务器运行
- **WHEN** backend 运行在 2h4g 服务器且未配置 RAG 服务
- **THEN** Agent SHALL 继续支持当前会话上下文和写操作确认流程

### Requirement: 未来 RAG 服务通过端口接入
未来独立 RAG 或用户记忆服务 SHALL 通过 Memory Service 端口接入。Agent、Context Builder 和 Runtime 调用方 SHALL 只依赖 MemoryContext、MemorySearchQuery 和 MemoryHit 等稳定结构。

#### Scenario: 外部 RAG 服务接入
- **WHEN** 后续配置独立 RAG/memory 服务
- **THEN** backend SHALL 通过 Memory Service 实现替换接入检索和长期记忆，而不要求 Agent Runtime 直接依赖向量数据库
