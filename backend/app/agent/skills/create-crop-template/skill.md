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
- 系统模板库有精确匹配时，应返回 `NEED_CLARIFY` 推荐导入，不直接创建。
- 生成阶段后发现农场内已有完全相同模板时，应返回已存在，不重复创建。

## 多工具协作
如果这是创建茬口过程中的补充动作，模板创建成功后应继续执行原来的 `create_crop_cycle`。

## Runtime 策略
- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: none；写入成功后使作物模板和茬口创建候选相关缓存失效。
- 查找系统模板时使用 `crop_service.find_system_template_match(db, crop_name, variety)`，只做 `name + variety` 精确匹配，不使用 `find_template_by_name` 或 `ilike` 模糊匹配。
- 命中系统模板时返回 `ResultStatus.NEED_CLARIFY`，回复“系统库已有 {crop_name} 的成熟模版（阶段：...），要导入吗？”，不调用 LLM、不写入数据库。
- 未命中系统模板后再调用 LLM 生成 stages；LLM 不可用或输出不可解析时使用内置 fallback stages，保证仍可进入创建流程。
- 生成 stages 后调用 `crop_service.find_exact_duplicate(db, farm_id, crop_name, variety, stages)` 做完全相同模板查重；命中则返回 `SUCCESS`，回复包含已有模板 ID 与阶段链，不新建。
- 精确查重未命中时才调用 `crop_service.create_crop_template(...)` 创建用户农场模板。
- 由于运行初始尚无 stages，无法先做“完全相同”精确查重；本 Skill 实际顺序为“系统模板精确匹配 → LLM/fallback 生成 stages → 完全相同精确查重 → 创建”。这与设计文档中的“精确查重 → 系统模板库匹配 → LLM”顺序略有差异，用于避免无 stages 时伪精确查重。

## 失败处理
- 作物名称不明确时，用中文追问必要信息。
- 缺少农场上下文时拒绝执行，返回中文失败说明，不打开数据库连接。
- 系统模板推荐属于澄清态，必须等待用户确认导入；本 Skill 不直接导入系统模板。
- LLM 生成失败时记录日志并使用 fallback stages；fallback 仍失败或无阶段时返回失败说明。
- 创建失败时返回中文说明和可重试建议，不暴露敏感信息。

## 示例
- 用户：“帮我创建番茄模板” -> `create_crop_template(crop_name="番茄")`
- 用户：“新增 8424 西瓜模板” -> `create_crop_template(crop_name="西瓜", variety="8424")`
