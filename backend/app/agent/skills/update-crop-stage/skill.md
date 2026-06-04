---
name: update_crop_stage
type: write
description: 更新茬口的生长阶段，支持苗期、开花期、结果期、采收期等阶段名称。
triggers:
  - 进期
  - 到阶段
  - 阶段更新
  - 换阶段
  - 进了
  - 进入
parameters:
  type: object
  properties:
    cycle_id:
      type: integer
      description: "茬口 ID，可选。不传则自动匹配活跃茬口。"
    stage_name:
      type: string
      description: "目标阶段名称，如膨大期、伸蔓期、开花期。"
  required:
    - stage_name
---

# 更新生长阶段

## 何时使用
用户明确表示某个茬口已经进入新阶段，或要求把阶段更新为某个阶段时使用本 Skill。

## 不要使用
- 用户只是查询当前阶段时，应使用 `get_crop_cycle_info` 或 `get_farm_status`。
- 用户只是询问某阶段怎么管理时，不要更新阶段。
- 用户没有表达阶段已经变化或要更新时，不要执行写入。

## 参数推断
- “西瓜进膨大期了” -> `stage_name=膨大期`。
- “辣椒到开花阶段了” -> `stage_name=开花期`。
- “3 号茬口进入采收期” -> `cycle_id=3`, `stage_name=采收期`。

## 缺参策略
- 缺少阶段名称时必须追问。
- 缺少茬口 ID 时可自动匹配活跃茬口；如果无法匹配，应提示用户指定。

## 多工具协作
更新后用户问“现在整体情况”，调用 `get_farm_status` 查看最新状态。

## 示例
- 用户：“西瓜进膨大期了” -> `update_crop_stage(stage_name="膨大期")`
- 用户：“3 号茬口到采收期了” -> `update_crop_stage(cycle_id=3, stage_name="采收期")`
