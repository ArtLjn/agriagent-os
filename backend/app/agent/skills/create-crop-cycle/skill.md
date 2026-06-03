---
name: create_crop_cycle
description: 创建种植周期（茬口），自动匹配作物模板生成阶段计划。用户表达“我想种/我要种/准备种某作物”时优先理解为创建茬口，而不是创建模板。
triggers:
  - 建茬口
  - 种什么
  - 开始种
  - 建个
parameters:
  type: object
  properties:
    crop_name:
      type: string
      description: "作物名称，如'辣椒'、'西瓜'"
    season:
      type: string
      description: "季节，如'春季'、'秋季'，默认当前季节"
    start_date:
      type: string
      description: "开始日期 YYYY-MM-DD，默认今天"
    field_name:
      type: string
      description: "地块名称（可选）"
  required:
    - crop_name
---

# 建茬口

## 功能
创建种植周期（茬口），自动根据作物模板生成各生长阶段计划。作物名称必填，系统会模糊匹配已知模板。

## 意图判定
- 用户说“我想种玉米”“我要种小麦”“准备种辣椒”时，优先选择本 skill 创建茬口。
- 只有用户明确说“创建作物模板”“没有模板”“帮我加一个模板”时，才选择创建作物模板。
- 如果执行时发现没有对应作物模板，不要直接创建模板；先询问用户是否确认创建模板，模板创建完成后再继续确认创建茬口。

## 参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| crop_name | string | 是 | 作物名称，如'辣椒'、'西瓜' |
| season | string | 否 | 季节，如'春季'、'秋季'，默认当前季节 |
| start_date | string | 否 | 开始日期 YYYY-MM-DD，默认今天 |
| field_name | string | 否 | 地块名称 |

## 示例
用户：「帮我建个秋季辣椒茬口」
工具选择：创建茬口，作物为辣椒，季节为秋季。
面向用户确认：「🌱 确认创建茬口：辣椒 秋季」

用户：「我想种小麦」
工具选择：创建茬口，作物为小麦。
面向用户确认：「🌱 确认创建茬口：小麦」
