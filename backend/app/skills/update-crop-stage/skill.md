---
name: update_crop_stage
description: "更新茬口的生长阶段。当用户说进XX期了、到XX阶段了时使用。触发词: 进XX期、到XX阶段、阶段更新"
parameters:
  type: object
  properties:
    cycle_id:
      type: integer
      description: "茬口ID（可选，不传则自动匹配）"
    stage_name:
      type: string
      description: "目标阶段名称，如'膨大期'、'伸蔓期'、'开花期'"
  required:
    - stage_name
---

# 更新阶段 Skill

## 功能
通过对话更新茬口的生长阶段。

## 典型场景
- 「西瓜进膨大期了」
- 「辣椒到开花阶段了」
- 「阶段更新为伸蔓期」

## 执行逻辑

1. 如果提供了 `cycle_id` → 直接获取指定茬口
2. 如果没有 `cycle_id` → 查找当前农场的活跃茬口（status='active'）
   - 只有一个 → 自动匹配
   - 多个 → 返回 NEED_CLARIFY 让用户指定
   - 没有 → 返回失败提示
3. 在茬口的 stages 中查找 `stage_name` 匹配的阶段（支持模糊匹配）
4. 找到 → 清除当前 `is_current`，设置目标阶段 `is_current=1`
5. 返回成功消息

## 依赖
- CropCycle 模型：id, farm_id, name, status, stages
- CycleStage 模型：id, cycle_id, name, is_current, order_index
