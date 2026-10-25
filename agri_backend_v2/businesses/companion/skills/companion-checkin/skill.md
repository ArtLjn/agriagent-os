---
schema_version: 1
name: companion_checkin
kind: local
mcp_tool: null
risk_level: read
description: 生成一段温和的陪伴问候，适合用户想被关心、想聊几句或不知道说什么时使用。
triggers:
  - 陪我
  - 在吗
  - 关心
  - 问候
  - 今天怎么样
operations: {}
parameters:
  type: object
  properties: {}
  required: []
---

# companion_checkin

按当前时段生成一段简短的陪伴问候和一个开放式问题。只提供语言上的陪伴，
不做情绪判断、心理诊断或医疗建议。

## 何时使用

- 用户说“陪我一会儿”“在吗”“今天有点空”
- 用户情绪低落但还没有明确要解决的问题
- 对话刚开始，需要一个自然、不冒犯的开场

## 不要使用

- 用户明确要求查询业务数据、天气或执行操作
- 用户处于紧急危险中；应先按 system prompt 的危机边界回应
