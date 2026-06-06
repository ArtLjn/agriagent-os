---
name: manage_crop_templates
type: write
description: 更新或删除作物模板；删除模板会级联删除相关茬口、农事日志和成本记录。
triggers:
  - 修改作物模板
  - 更新模板
  - 删除作物模板
parameters:
  type: object
  properties:
    action:
      type: string
      description: 操作：update/delete。
    template_id:
      type: integer
      description: 作物模板 ID。
    name:
      type: string
      description: 作物名称。
    variety:
      type: string
      description: 品种。
    stages:
      type: string
      description: 阶段 JSON 数组。
  required:
    - action
---

# manage_crop_templates

更新或删除作物模板。

## 何时使用

用户明确要修改模板名称、品种、阶段，或删除作物模板时使用。

## 不要使用

用户要新建模板时使用 `create_crop_template`；用户只是查询模板时使用 `get_crop_templates`。

## 参数推断

- “把模板 5 名字改成麒麟西瓜” -> `action=update`, `template_id=5`, `name=麒麟西瓜`。
- “删除作物模板 5” -> `action=delete`, `template_id=5`。

## 缺参策略

缺少 `template_id` 时追问；更新时未提供阶段则保留原阶段。

## Runtime 策略

- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: 写入成功后刷新茬口、农事、账务和农场状态缓存。

## 失败处理

模板不存在或阶段格式错误时返回中文说明。

## 示例

- 用户：“删除 5 号作物模板” -> 待确认后执行高风险删除。
