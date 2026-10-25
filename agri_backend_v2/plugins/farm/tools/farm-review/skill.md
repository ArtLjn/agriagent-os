---
schema_version: 1
name: get_farm_review
kind: mcp
mcp_tool: business.get_farm_review
risk_level: read
routing:
  use_when: [按时间区间回顾已经发生的农事并统计作业次数，用于周报或工作总结。]
  avoid_when: [个人备忘和未来提醒不是已完成农事，使用 query_memos；详细日志用 query_farm_logs。]
  examples: [总结这周的农事, 近一个月做了多少次浇水]
description: 回顾最近若干天的农事记录，统计各类作业次数并列出近期明细，适用于农事周报与近期工作总结。
triggers: [农事回顾, 农事周报, 工作总结]
operations: {}
parameters:
  type: object
  properties:
    days:
      type: integer
      minimum: 1
      maximum: 90
      description: 含今天在内的回顾天数，默认 7 天
---

按返回的起止日期总结；分类统计是全量，recent_logs 仅为最多 20 条预览，不能把预览条数当总量。没有记录时如实说明，不能推断没有干活。不得把建议描述为已执行的任务。
如果回顾已满足用户请求，直接回答；复合请求仍有未查信息时，继续调用对应工具补齐证据，不因本次查询成功而提前结束整轮。

## 工具使用方法

本目录由 SkillLoader 加载，McpSkill 提供执行封装，调用 Business 的 `get_farm_review`。

- “总结最近一周的农事” → `get_farm_review({"days":7})`。
- “看看近一个月做了什么” → `get_farm_review({"days":30})`。
- 省略 days 默认 7 天，范围为 1–90 天，含北京时间今天。工具自行取得当前农场身份，不接收模型传入的农场 ID。
- 使用 `start_date`、`end_date` 和 `total` 描述区间与总数，用 `by_operation` 分组汇总；按 `recent_logs` 展示近期明细并标明其为预览。
- `validation_error` 时修正天数；调用失败不能把失败解释为“没有农事记录”。
