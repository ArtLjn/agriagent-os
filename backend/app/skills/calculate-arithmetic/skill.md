---
name: calculate_arithmetic
type: read
description: 确定性数学运算，支持总价、单价、面积、数量、比例和单位换算后的算术计算。
domain: farm
capability: calculate_arithmetic
triggers:
  - 计算
  - 算一下
  - 总价
  - 单价
  - 多少钱
  - 合计
  - 换算
parameters:
  type: object
  properties:
    expression:
      type: string
      description: 只包含数字、+、-、*、/ 和括号的算术表达式。
    unit:
      type: string
      description: 可选结果单位，例如元、亩、米、个。
    precision:
      type: integer
      description: 小数位数，默认 2，允许 0-8。
      default: 2
  required:
    - expression
---

# calculate_arithmetic

## 何时使用

用户需要数学运算、总价估算、单价乘数量、面积/株数/米数换算、比例计算或校验数字时使用本 Skill。涉及金额、面积、长度、数量的答案必须先调用本工具计算，不要让 AI 自己心算。

## 不要使用

- 查询真实账务流水、成本分类、欠款或趋势时使用 `manage_cost`。
- 需要查询农场状态、种植单元或茬口事实时使用对应业务 Skill。
- 用户只是闲聊或不需要数字运算时不要调用。

## 参数推断

- “36 公里滴灌带，1.5 元一米，总价多少” -> `expression="36 * 1000 * 1.5", unit="元"`。
- “30 亩，每块 1.5 亩，要几块” -> `expression="30 / 1.5", unit="块"`。
- “一亩 2800 株，15 亩多少株” -> `expression="2800 * 15", unit="株"`。

## 缺参策略

- 无法确定数字或换算关系时必须追问，不要猜。
- 用户给出自然语言单位时，先转换成明确表达式再调用，例如 36 公里先转为 36 * 1000 米。

## Runtime 策略

- permission: read
- direct_call: true
- direct_return: false
- cache: none

## 失败处理

- 表达式为空、过长或包含非算术内容时返回带 code 的中文错误。
- 除数为 0 时返回 `DIVISION_BY_ZERO`。
- 不支持任意代码、函数调用、变量名或比较表达式。

## 示例

- 用户：“滴灌带 36 公里，1.5 元一米多少钱” -> `calculate_arithmetic(expression="36 * 1000 * 1.5", unit="元")`
- 用户：“30 亩按 1.5 亩一块分，要多少块” -> `calculate_arithmetic(expression="30 / 1.5", unit="块")`
