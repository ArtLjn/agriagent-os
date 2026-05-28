---
name: create_crop_template
description: 创建作物模板（定义作物及其生长阶段），系统自动生成合理的生长阶段。触发词: 新作物、没有模板、帮我创建模板
triggers:
  - 新作物
  - 没有模板
  - 帮我创建模板
parameters:
  type: object
  properties:
    crop_name:
      type: string
      description: "作物名称，如'西瓜'、'玉米'、'番茄'"
    variety:
      type: string
      description: "品种（可选），如'8424'、'圣女果'"
  required:
    - crop_name
---

# 创建作物模板

## 功能
根据作物名称自动生成合理的生长阶段，创建作物模板。创建成功后可直接用于建茬口。

## 示例
用户：「我要种玉米但没有模板」
→ create_crop_template(crop_name="玉米")
返回：「已创建玉米模板，生长阶段：播种期→苗期→拔节期→抽穗期→灌浆期→成熟期」
