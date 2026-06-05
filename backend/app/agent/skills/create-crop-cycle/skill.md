---
name: create_crop_cycle
type: write
description: 创建种植周期（茬口），自动匹配作物模板生成阶段计划。用户说“我想种/我要种/准备种某作物”时优先理解为创建茬口。
triggers:
  - 建茬口
  - 创建茬口
  - 开始种
  - 我想种
  - 我要种
  - 准备种
  - 春茬
  - 夏茬
  - 秋茬
  - 冬茬
parameters:
  type: object
  properties:
    crop_name:
      type: string
      description: "作物名称，如辣椒、西瓜、番茄。"
    season:
      type: string
      description: "季节，如春季、夏季、秋季、冬季，默认当前季节。"
    start_date:
      type: string
      description: "开始日期 YYYY-MM-DD，默认今天。"
    field_name:
      type: string
      description: "地块名称，可选。"
  required:
    - crop_name
---

# 建茬口

## 何时使用
用户要开始一轮种植、创建茬口、建立某作物种植周期时使用本 Skill。用户说“我想种玉米”“帮我建西瓜茬口”“准备种辣椒”通常都是创建茬口。

## 不要使用
- 用户明确说“创建作物模板”“没有模板”“新增模板”时，应使用 `create_crop_template`。
- 用户只是询问某作物怎么种、是否适合种、注意事项时，不要创建茬口。
- 用户只是查询已有茬口状态时，应使用 `get_crop_cycle_info` 或 `get_farm_status`。

## 参数推断
- “帮我建个秋季辣椒茬口” -> `crop_name=辣椒`, `season=秋季`。
- “我想种小麦” -> `crop_name=小麦`，季节默认当前季节。
- “今天开始种西瓜” -> `crop_name=西瓜`, `start_date=今天`。
- “三号棚种番茄” -> `crop_name=番茄`, `field_name=三号棚`。

## 缺参策略
- 缺少作物名称时，必须追问。
- 缺少季节时默认当前季节。
- 缺少开始日期时默认今天。
- 模板不存在时，不要直接创建模板；先提示用户确认创建模板。

## 多工具协作
如果创建茬口时发现模板不存在，可引导用户确认 `create_crop_template`，模板创建后再继续创建茬口。

## Runtime 策略
- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: none；写入成功后使茬口、阶段计划和农场状态相关查询缓存失效。

## 失败处理
- 作物、地块或开始日期不明确时，用中文追问必要信息。
- 创建失败时返回中文说明和可重试建议，不暴露内部异常。

## 示例
- 用户：“帮我建一个秋季辣椒茬口” -> `create_crop_cycle(crop_name="辣椒", season="秋季")`
- 用户：“我想种小麦” -> `create_crop_cycle(crop_name="小麦")`
