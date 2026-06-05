---
name: update_crop_cycle
type: write
description: 修改已有种植周期（茬口）的开始日期、播种期或起始日期，并同步重算阶段计划。
triggers:
  - 修改茬口
  - 调整茬口
  - 更正茬口
  - 改开始日期
  - 改播种期
  - 起始日期
  - 9月1开始
parameters:
  type: object
  properties:
    cycle_id:
      type: integer
      description: "茬口 ID，可选。传入时只会在当前农场内查找。"
    crop_name:
      type: string
      description: "作物名称，如玉米、辣椒。未传 cycle_id 时用于匹配活跃茬口。"
    cycle_name:
      type: string
      description: "茬口名称，如夏季玉米。未传 cycle_id 时用于匹配活跃茬口。"
    start_date:
      type: string
      description: "新的开始日期 YYYY-MM-DD。上游模型必须把年份补全。"
  required:
    - start_date
---

# 更新茬口开始日期

## 何时使用
用户明确要修改、调整、更正已有茬口的开始日期、播种期或起始日期时使用本 Skill。典型表达包括“修改玉米茬口9月1开始”“把夏季玉米播种期改到9月1日”“把 3 号茬口开始日期调到 2026-09-01”。

## 不要使用
- 用户要新建一轮种植时，应使用 `create_crop_cycle`。
- 用户只是查询茬口阶段或当前状态时，应使用 `get_crop_cycle_info` 或 `get_farm_status`。
- 用户要更新当前生长阶段时，应使用 `update_crop_stage`。
- 用户没有明确表达修改已有茬口时，不要执行写入。

## 参数推断
- “修改玉米茬口9月1开始” -> `crop_name=玉米`, `start_date=2026-09-01`。
- “把夏季玉米播种期改到9月1日” -> `cycle_name=夏季玉米`, `crop_name=玉米`, `start_date=2026-09-01`。
- “3 号茬口开始日期改成 2026-09-01” -> `cycle_id=3`, `start_date=2026-09-01`。

## 缺参策略
- 缺少 `start_date` 时必须追问，不要默认今天。
- `start_date` 必须是 `YYYY-MM-DD`；用户只说“9月1日”时，上游模型应结合当前年份或上下文补全。
- 缺少 `cycle_id` 时，可用 `crop_name` 或 `cycle_name` 在当前农场活跃茬口中匹配。
- 匹配到多个活跃茬口时，必须让用户选择具体茬口。
- 没有匹配到茬口时，提示用户提供茬口 ID 或更完整名称。

## 确认策略
本 Skill 是写操作，权限等级为 `write_confirm`，风险等级为 `medium`。确认信息应展示目标茬口、旧开始日期、新开始日期、推断出的作物或茬口名称，并提示修改开始日期会同步重算该茬口所有阶段起止日期。可编辑字段包括 `cycle_id`、`cycle_name`、`crop_name` 和 `start_date`。

## 多工具协作
执行成功后，`crop_cycle` 和 `get_farm_status` 相关缓存应失效。用户继续询问整体情况时，可调用 `get_farm_status` 读取最新状态；用户查询该茬口详情时，可调用 `get_crop_cycle_info`。

## 示例
- 用户：“修改玉米茬口9月1开始” -> `update_crop_cycle(crop_name="玉米", start_date="2026-09-01")`
- 用户：“把夏季玉米播种期改到9月1日” -> `update_crop_cycle(cycle_name="夏季玉米", crop_name="玉米", start_date="2026-09-01")`
