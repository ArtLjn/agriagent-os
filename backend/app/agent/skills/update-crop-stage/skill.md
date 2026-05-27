---
name: update_crop_stage
description: 更新茬口的生长阶段。触发词: 进XX期、到XX阶段、阶段更新、换阶段
triggers:
  - 进期
  - 到阶段
  - 阶段更新
  - 换阶段
  - 进了
parameters:
  type: object
  properties:
    cycle_id:
      type: integer
      description: "茬口ID（可选，不传则自动匹配活跃茬口）"
    stage_name:
      type: string
      description: "目标阶段名称，如'膨大期'、'伸蔓期'、'开花期'"
  required:
    - stage_name
---

# 更新生长阶段

## 功能
通过对话更新茬口的生长阶段。支持模糊匹配阶段名称，不传 cycle_id 时自动匹配活跃茬口。

## 参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| cycle_id | integer | 否 | 茬口ID（不传则自动匹配） |
| stage_name | string | 是 | 目标阶段名称，如'膨大期'、'伸蔓期'、'开花期' |

## 示例
- 「西瓜进膨大期了」→ update_crop_stage(stage_name="膨大期")
- 「辣椒到开花阶段了」→ update_crop_stage(stage_name="开花期")
