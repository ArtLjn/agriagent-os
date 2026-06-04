---
name: create_crop_template
type: write
description: 创建作物模板，定义作物及其生长阶段，供后续创建茬口使用。
triggers:
  - 新作物
  - 没有模板
  - 创建模板
  - 新增模板
  - 作物模板
parameters:
  type: object
  properties:
    crop_name:
      type: string
      description: "作物名称，如西瓜、玉米、番茄。"
    variety:
      type: string
      description: "品种，可选，如 8424、圣女果。"
  required:
    - crop_name
---

# 创建作物模板

## 何时使用
用户明确要求创建作物模板，或系统在创建茬口时发现没有对应模板且用户确认要创建模板时使用本 Skill。

## 不要使用
- 用户只说“我想种玉米”“我要种小麦”时，不要优先使用本 Skill；这通常是创建茬口。
- 用户只是询问种植建议或作物知识时，不要创建模板。
- 用户未确认写入时，不要自动创建模板。

## 参数推断
- “帮我创建橘子模板” -> `crop_name=橘子`。
- “新增一个 8424 西瓜模板” -> `crop_name=西瓜`, `variety=8424`。
- “没有草莓模板，帮我加一个” -> `crop_name=草莓`。

## 缺参策略
- 缺少作物名称时必须追问。
- 缺少品种时可以不传。
- 作物模板已存在时，应返回已存在，不重复创建。

## 多工具协作
如果这是创建茬口过程中的补充动作，模板创建成功后应继续执行原来的 `create_crop_cycle`。

## 示例
- 用户：“帮我创建番茄模板” -> `create_crop_template(crop_name="番茄")`
- 用户：“新增 8424 西瓜模板” -> `create_crop_template(crop_name="西瓜", variety="8424")`
