---
name: log_farm_activity
type: write
description: 记录农事操作，如浇水、施肥、打药、除草、翻地等，可自动关联活跃茬口。
triggers:
  - 农活
  - 浇水
  - 施肥
  - 打药
  - 追肥
  - 除草
  - 翻地
  - 记录农事
parameters:
  type: object
  properties:
    operation_type:
      type: string
      description: "农事操作类型，如浇水、施肥、打药。"
    operation_date:
      type: string
      description: "操作日期 YYYY-MM-DD，默认今天。"
    note:
      type: string
      description: "备注详情。"
    cycle_id:
      type: integer
      description: "关联茬口 ID，可选。不传则自动关联第一个活跃茬口。"
  required:
    - operation_type
---

# 记录农事

## 何时使用
用户要新增一条农事操作记录时使用本 Skill，例如“今天浇了水”“刚给西瓜打药”“昨天追肥了”。

## 不要使用
- 用户只是查询最近农事记录时，应使用 `get_recent_farm_logs`。
- 用户只是询问种植建议、天气或病虫害知识时，不要写入农事记录。
- 用户描述不包含已发生或明确要记录的操作时，不要执行写入。

## 参数推断
- “今天浇了水” -> `operation_type=浇水`, `operation_date=今天`。
- “昨天给辣椒打药，防蚜虫” -> `operation_type=打药`, `operation_date=昨天`, `note=防蚜虫`。
- “3 号茬口施肥了” -> `cycle_id=3`, `operation_type=施肥`。

## 缺参策略
- 缺少操作类型时必须追问。
- 未说明日期时默认今天。
- 未说明茬口时，可让系统自动关联活跃茬口；如果没有活跃茬口，执行结果应提示用户。

## 多工具协作
记录后用户追问“最近都干了什么”，调用 `get_recent_farm_logs` 查询最新记录。

## Runtime 策略
- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: none；写入成功后使农事记录、茬口和农场状态相关查询缓存失效。

## 失败处理
- 操作类型、日期或茬口无法确定时，用中文追问必要信息。
- 写入失败时返回中文说明和可重试建议，不暴露内部异常。

## 示例
- 用户：“今天浇了水” -> `log_farm_activity(operation_type="浇水")`
- 用户：“昨天给 3 号茬口打药防蚜虫” -> `log_farm_activity(cycle_id=3, operation_type="打药", operation_date="昨天", note="防蚜虫")`
