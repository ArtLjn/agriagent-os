---
name: web_search
type: read-only
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
---

# web_search

## 类型
只读(read-only)

## 触发场景
- 用户问"最近有什么农业政策"时触发
- 用户问"今年西瓜价格怎么样"时触发
- 用户问"XX什么时候上市"时触发
- 用户问"最新新闻/热点"时触发
- 任何需要实时网络信息的问题

## 参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 搜索关键词 |
| categories | string | 否 | 搜索类别: general/news/images/videos，默认 general |

## 返回
成功时返回格式化的搜索结果，包含标题、摘要、链接、来源引擎。

## 依赖
- 自建 SearXNG (`http://47.98.253.236:8888`) — 百度 + 360搜索引擎
- `app/infra/skill_cache.py` — `@cached(ttl_seconds=600)` 10分钟缓存

## 错误处理
| 场景 | 返回 |
|------|------|
| query 为空 | FAILED + "请提供搜索关键词" |
| 请求超时 | FAILED + "搜索请求超时" |
| HTTP 错误 | FAILED + "搜索服务暂时不可用" |
| 连接失败 | FAILED + "搜索服务异常" |

## 示例对话
用户：「最近西瓜价格怎么样」
Agent → 调用 web_search(query="2026年西瓜价格")
返回：「搜索关键词: 2026年西瓜价格\n找到 5 条结果\n\n1. ...\n2. ...」
