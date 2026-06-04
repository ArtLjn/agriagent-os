---
name: web_search
type: read-only
description: 搜索实时网络信息，适合农业政策、新闻、价格、上市时间、热点等需要外部最新资料的问题。
triggers:
  - 最新
  - 新闻
  - 价格
  - 上市
  - 政策
  - 热点
  - 搜索
  - 查一下
  - 最近
  - 实时
parameters:
  type: object
  properties:
    query:
      type: string
      description: "搜索关键词。"
    categories:
      type: string
      description: "搜索类别: general/news/images/videos，默认 general。"
      default: "general"
  required:
    - query
---

# 网络搜索

## 何时使用
用户的问题依赖最新外部信息时使用本 Skill，例如农业政策、新闻、市场价格、上市时间、热点事件和实时资料。

## 不要使用
- 用户查询本农场内部账单、农事、茬口或天气时，不要用搜索，应使用对应内部 Skill。
- 用户问通用种植知识且不需要最新信息时，可直接回答或结合农场上下文。
- 当前工具在路由层可能被禁用；禁用时不要声称已经搜索。

## 参数推断
- “最近西瓜价格怎么样” -> `query=2026年 西瓜 价格`。
- “今年农业补贴政策” -> `query=2026年 农业补贴政策`。
- “番茄什么时候上市” -> `query=番茄 上市 时间`。

## 缺参策略
- 缺少搜索关键词时必须追问。
- 未说明类别时默认 `general`。

## 多工具协作
如果用户问“结合我农场情况看最近价格”，可先用 `get_farm_status` 获取农场作物，再搜索外部价格信息。

## 示例
- 用户：“最近西瓜价格怎么样” -> `web_search(query="2026年 西瓜 价格")`
- 用户：“最新农业政策有什么” -> `web_search(query="2026年 最新农业政策", categories="news")`
