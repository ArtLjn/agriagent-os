---
name: calculate_arithmetic
kind: local
risk_level: read
description: 确定性算术运算。涉及总价、单价、面积、数量、比例等数学计算必须用此工具，不要让 AI 心算。
triggers:
  - 计算
  - 多少钱
  - 总价
  - 单价
  - 面积乘以
parameters:
  type: object
  properties:
    expression:
      type: string
      description: 只含数字、+、-、*、/ 和括号的算术表达式。例 "36 * 1000 * 1.5"。
  required: [expression]
---

# calculate_arithmetic

用 Decimal 安全求值算术表达式。本地执行，不走 MCP。

## 何时使用

凡是涉及数字计算的，必须用此工具，避免 AI 心算错误：
- "5 亩地 × 每亩 200 元 = 多少钱"
- "总共 12 个工人，平均 80 元/天，3 天 = 多少"
- "面积 5.2 亩，单价 35.5 元/kg，产量 1200 kg，总收入多少"

## 不要使用

- 涉及业务数据查询的 → 调对应 MCP tool
- 涉及货币转换、汇率 → 不支持

## 安全约束

只允许 `0-9 + - * / ( ) .` 字符，不允许任何变量、函数、字母。
表达式解析失败时返回 error，agent 应提示用户重新表达。
