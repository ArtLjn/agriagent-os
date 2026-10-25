---
schema_version: 1
name: companion_activity
kind: local
mcp_tool: null
risk_level: read
description: 根据用户当前状态推荐一个几分钟内能完成的小关怀动作，适合用户疲惫、焦虑、低落或想被照顾时使用。
triggers:
  - 有点累
  - 心情不好
  - 焦虑
  - 低落
  - 想放松
operations: {}
parameters:
  type: object
  properties:
    mood:
      type: string
      enum: [happy, okay, tired, low, anxious]
      description: 用户当前状态。happy=开心，okay=平静，tired=疲惫，low=低落，anxious=焦虑。
    minutes:
      type: integer
      minimum: 1
      maximum: 30
      default: 5
      description: 用户愿意留出的时间，单位分钟。
  required: [mood]
---

# companion_activity

按用户状态给出一个轻量、可执行、不说教的照顾动作。推荐内容不是医疗建议，
不承诺改善症状。

## 何时使用

- 用户说“有点累”“心里堵得慌”“不太想动”
- 用户愿意尝试一个小动作，但不需要长篇建议
- 对话需要从倾听自然过渡到一个可执行的小步骤

## 不要使用

- 用户只想倾诉，明确表示不需要建议
- 用户处于紧急危险中；先处理安全问题
