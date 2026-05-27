---
name: create_crop_cycle
description: 创建种植周期（茬口），自动匹配作物模板生成阶段计划。触发词: 建茬口、种什么、开始种
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

## 参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| crop_name | string | 是 | 作物名称，如'辣椒'、'西瓜' |
| season | string | 否 | 季节，如'春季'、'秋季'，默认当前季节 |
| start_date | string | 否 | 开始日期 YYYY-MM-DD，默认今天 |
| field_name | string | 否 | 地块名称 |

## 示例
用户：「帮我建个秋季辣椒茬口」
→ create_crop_cycle(crop_name="辣椒", season="秋季")
返回：「已建茬口：秋季辣椒，共5个阶段：播种期→苗期→…」
