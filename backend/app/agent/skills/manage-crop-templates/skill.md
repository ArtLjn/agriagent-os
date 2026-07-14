---
name: manage_crop_templates
type: write
description: 管理作物模板，支持查询、创建、更新和删除模板。
domain: crop
capability: manage_crop_templates
triggers:
  - 作物模板
  - 模板列表
  - 创建模板
  - 修改模板
  - 删除模板
parameters:
  type: object
  properties:
    operation:
      type: string
      description: "操作类型：query_templates、create_template、manage_template。"
      enum:
        - query_templates
        - create_template
        - manage_template
    action:
      type: string
      description: manage_template 下的动作：update 或 delete。
      enum:
        - update
        - delete
    template_id:
      type: integer
      description: 作物模板 ID。
    crop_name:
      type: string
      description: 创建模板时的作物名称。
    name:
      type: string
      description: 作物名称或更新后的模板名称。
    variety:
      type: string
      description: 品种。
    limit:
      type: integer
      description: 查询返回数量。
    stages:
      type: string
      description: 阶段 JSON 数组。
  required:
    - operation
---

# manage_crop_templates

## 何时使用

用户要处理作物模板能力时使用本 Skill，包括查看已有作物模板、创建新作物模板、修改模板名称或阶段，以及删除模板。

## 不要使用

- 用户要创建种植茬口、调整茬口阶段或查询茬口进度时使用茬口能力。
- 用户只是询问种植建议、栽培技术或病虫害知识时不要创建模板。
- 用户要记录浇水、施肥、打药、采收等农事时使用农事记录能力。

## 参数推断

- “有哪些作物模板” -> `operation=query_templates`。
- “帮我创建黑布林种植模板” -> `operation=create_template`, `crop_name=黑布林`。
- “新增 8424 西瓜模板” -> `operation=create_template`, `crop_name=西瓜`, `variety=8424`。
- “把模板 5 名字改成麒麟西瓜” -> `operation=manage_template`, `action=update`, `template_id=5`, `name=麒麟西瓜`。
- “删除作物模板 5” -> `operation=manage_template`, `action=delete`, `template_id=5`。

## 缺参策略

- 缺少 `operation` 时必须追问用户要查询、创建、修改还是删除模板。
- 创建模板缺少作物名称时追问 `crop_name`。
- 修改或删除模板缺少 `template_id` 时追问模板 ID，不要猜测最近一个模板。
- 修改模板未提供 `stages` 时保留原阶段。

## Runtime 策略

- permission: operation-aware
- direct_call: 读操作可直接执行，写操作必须进入确认。
- direct_return: false
- cache: 创建、修改或删除成功后刷新茬口、农事、账务和农场状态缓存。

## 失败处理

- 参数不完整时用中文追问必要信息。
- 模板不存在、阶段格式错误或业务服务失败时返回中文说明，不暴露内部堆栈。

## 示例

- 用户：“有哪些作物模板” -> `manage_crop_templates(operation="query_templates")`
- 用户：“帮我创建番茄模板” -> `manage_crop_templates(operation="create_template", crop_name="番茄")`
- 用户：“删除 5 号作物模板” -> `manage_crop_templates(operation="manage_template", action="delete", template_id=5)`
