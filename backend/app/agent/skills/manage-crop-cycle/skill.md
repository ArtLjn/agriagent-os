---
name: manage_crop_cycle
type: write
description: 管理农场种植茬口，支持创建、查询、修改日期阶段状态和删除。
domain: crop
capability: manage_crop_cycle
triggers:
  - 茬口
  - 种植周期
  - 批次
  - 春茬
  - 秋茬
  - 生长阶段
  - 播种期
  - 膨大期
  - 采收期
parameters:
  type: object
  properties:
    operation:
      type: string
      description: "操作类型：create_cycle、query_cycles、query_cycle_info、update_cycle、update_stage、delete_cycle。"
      enum:
        - create_cycle
        - query_cycles
        - query_cycle_info
        - update_cycle
        - update_stage
        - delete_cycle
    cycle_id:
      type: integer
      description: 茬口 ID。
    crop_name:
      type: string
      description: 作物名称，如玉米、辣椒、西瓜。
    cycle_name:
      type: string
      description: 茬口名称，如夏季玉米。
    season:
      type: string
      description: 季节，如春季、秋季。
    start_date:
      type: string
      description: 开始日期 YYYY-MM-DD。
    field_name:
      type: string
      description: 地块名称。
    name:
      type: string
      description: 新的茬口名称。
    area:
      type: number
      description: 面积，亩。
    status:
      type: string
      description: 状态 active、planned 或 finished。
    current_stage:
      type: string
      description: 当前阶段名称。
    stage_name:
      type: string
      description: 目标阶段名称，兼容旧 update_crop_stage 参数。
    stage:
      type: string
      description: 当前阶段名称别名。
    note:
      type: string
      description: 批次备注。
    batch_note:
      type: string
      description: 批次备注。
    current_cycle_id:
      type: integer
      description: 上下文中的当前茬口 ID。
    context_cycle_id:
      type: integer
      description: 上下文补齐的茬口 ID。
    limit:
      type: integer
      description: 列表返回数量。
  required:
    - operation
---

# manage_crop_cycle

## 何时使用

用户要管理种植茬口或种植周期时使用本 Skill，包括新建一轮种植、查看茬口列表、查看单个茬口阶段详情、调整开始日期或阶段状态，以及删除茬口。

## 不要使用

- 创建或维护作物模板时使用作物模板能力。
- 记录浇水、施肥、打药、采收等农事日志时使用农事记录能力。
- 管理大棚、地块或种植单元时使用种植单元能力。
- 查询天气、账务、工人或作业单时使用对应业务能力。

## 参数推断

- “帮我建一个秋季辣椒茬口” -> `operation=create_cycle`, `crop_name=辣椒`, `season=秋季`。
- “我的茬口有哪些” -> `operation=query_cycles`。
- “看一下 3 号茬口阶段” -> `operation=query_cycle_info`, `cycle_id=3`。
- “把夏季玉米播种期改到 9 月 1 日” -> `operation=update_cycle`, `cycle_name=夏季玉米`, `start_date=2026-09-01`。
- “西瓜进入膨大期了” -> `operation=update_stage`, `crop_name=西瓜`, `current_stage=膨大期`。
- “3 号茬口到采收期了” -> `operation=update_stage`, `cycle_id=3`, `current_stage=采收期`。
- “删除茬口 12” -> `operation=delete_cycle`, `cycle_id=12`。

## 缺参策略

- 缺少 `operation` 时必须追问要新建、查询列表、查看详情、修改还是删除茬口。
- 新建茬口缺少 `crop_name` 时必须追问。
- 修改茬口缺少可定位目标时，要求提供茬口 ID、作物名称或茬口名称。
- 删除茬口缺少 `cycle_id` 时必须追问，不要猜测最近一个茬口。

## Runtime 策略

- permission: operation-aware
- direct_call: 读操作可直接执行，写操作必须进入确认。
- direct_return: false
- cache: 创建、修改和删除成功后清理茬口与农场状态缓存；删除还会清理农事和成本相关缓存。

## 失败处理

- 参数不完整时用中文追问必要信息。
- 数据库或业务服务失败时返回中文说明和可重试建议，不暴露内部异常。

## 示例

- 用户：“春茬种西瓜” -> `manage_crop_cycle(operation="create_cycle", crop_name="西瓜", season="春季")`
- 用户：“有哪些活跃茬口” -> `manage_crop_cycle(operation="query_cycles", status="active")`
- 用户：“看一下 3 号茬口” -> `manage_crop_cycle(operation="query_cycle_info", cycle_id=3)`
- 用户：“玉米茬口改到 9 月 1 开始” -> `manage_crop_cycle(operation="update_cycle", crop_name="玉米", start_date="2026-09-01")`
- 用户：“西瓜进入膨大期了” -> `manage_crop_cycle(operation="update_stage", crop_name="西瓜", current_stage="膨大期")`
- 用户：“3 号茬口到采收期了” -> `manage_crop_cycle(operation="update_stage", cycle_id=3, current_stage="采收期")`
- 用户：“删除茬口 12” -> `manage_crop_cycle(operation="delete_cycle", cycle_id=12)`
