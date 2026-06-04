---
name: get_crop_cycle_info
type: read-only
description: 查询种植周期（茬口）详细信息，包括阶段安排、地块、状态和进度。
triggers:
  - 周期
  - 阶段
  - 茬口
  - 种了什么
  - 当前阶段
  - 周期进度
cache_ttl: 600
parameters:
  type: object
  properties:
    cycle_id:
      type: integer
      description: "种植周期 ID。当前实现需要明确 ID。"
  required:
    - cycle_id
---

# 种植周期查询

## 何时使用
用户查询某个种植周期的详细信息、阶段安排、当前阶段、地块或周期状态时使用本 Skill。

## 不要使用
- 用户要创建新茬口时，应使用 `create_crop_cycle`。
- 用户要更新阶段时，应使用 `update_crop_stage`。
- 用户只是问农场整体情况时，可优先使用 `get_farm_status`。

## 参数推断
- “看一下 3 号茬口情况” -> `cycle_id=3`。
- “查询周期 5 的阶段” -> `cycle_id=5`。

## 缺参策略
- 当前实现需要 `cycle_id`。用户只说作物名或“当前茬口”时，不要编造 ID，可先使用 `get_farm_status` 获取上下文，或追问用户选择具体茬口。

## 多工具协作
如果用户不知道茬口 ID，可先调用 `get_farm_status` 获取活跃茬口摘要，再决定是否追问。

## 示例
- 用户：“看一下 3 号茬口阶段” -> `get_crop_cycle_info(cycle_id=3)`
