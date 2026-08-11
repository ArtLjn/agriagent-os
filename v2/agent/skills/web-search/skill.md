---
schema_version: 1
name: web_search
kind: local
mcp_tool: null
risk_level: read
description: 搜索互联网获取实时信息。用于农资价格、新品种、病虫害防治、农业政策、新闻热点等需要外部最新资料的问题。
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
  - 怎么防治
operations: {}
parameters:
  type: object
  properties:
    query:
      type: string
      description: "搜索关键词。应包含核心实体、事件或主题；需要实时信息时保留'最新、今天、最近、价格、政策'等时效词。"
    top_k:
      type: integer
      description: "返回结果数，默认 5，范围 1-10。普通事实 5 条；实时新闻、政策和行情建议 8 条；需要多来源交叉验证时最多 10 条。"
      minimum: 1
      maximum: 10
    time_range:
      type: string
      description: "日期筛选。day=最近一天，week=最近一周，month=最近一月，year=最近一年。实时新闻优先 week；今天/当天用 day；价格/行情/走势默认 month。"
      enum: [day, week, month, year]
    enable_fetch:
      type: boolean
      default: true
      description: "是否抓取网页正文。默认 true，获得更完整证据；只做标题级快搜时传 false。SearchHub 和 DuckDuckGo fallback 均支持。"
    content_mode:
      type: string
      enum: [none, evidence]
      default: evidence
      description: "返回模式。默认 evidence，只返回摘要和结构化证据，不把网页正文回传给主 Agent。"
    enable_embedding_filter:
      type: boolean
      description: "是否启用 SearchHub embedding 精筛。开启后按 query 与结果文本的向量相似度过滤排序，减少标题噪声。"
    domain:
      type: string
      description: "领域参数，例如 agriculture。让 SearchHub 启用领域增强流程。"
    region:
      type: string
      description: "地区参数，例如 苏州。"
    crop:
      type: string
      description: "作物参数，例如 西瓜。"
  required:
    - query
---

# 网络搜索

## 何时使用
用户的问题依赖最新外部信息时使用本 skill，例如农业政策、新闻、市场价格、上市时间、病虫害防治、热点事件和实时资料。

Provider 优先级：
1. **SearchHub** — 配置 `SEARCHHUB_API_KEY` + `SEARCHHUB_BASE_URL` 时启用，支持 time_range / embedding / fetch 等高级功能
2. **DuckDuckGo HTML** — 无需 key，作为 fallback，只支持基本关键词搜索

## 不要使用
- 农场内部数据（账单、农事、茬口、工人）→ 用对应业务 MCP tool
- 天气预报 → 用 `get_weather`
- 纯数学计算 → 用 `calculate_arithmetic`
- 通用种植知识且不需要最新信息 → 可直接回答

## 参数推断
- "最近西瓜价格怎么样" → `query="2026年 西瓜 价格"`, `time_range="month"`, `top_k=8`
- "今年农业补贴政策" → `query="2026年 农业补贴政策"`, `time_range="year"`, `top_k=8`
- "番茄什么时候上市" → `query="番茄 上市 时间"`, `top_k=5`
- "苏州西瓜白粉病最新防治" → `query="苏州西瓜白粉病最新防治"`, `domain="agriculture"`, `region="苏州"`, `crop="西瓜"`, `time_range="month"`, `enable_embedding_filter=true`

## 筛选条数
- 默认 `top_k=5`：普通事实查询、百科补充
- `top_k=8`：最新动态、新闻、政策、价格、行情（多来源覆盖）
- `top_k=10`：用户要求"多找几条、综合比较、交叉验证"

## 日期筛选
- "今天/当天/刚刚/最新发布/实时" → `time_range="day"`
- "最新动态/最近新闻/近日消息" → `time_range="week"`
- "价格/行情/走势/近期市场" → `time_range="month"`
- "今年/年度/全年政策" → `time_range="year"`
- 用户没有时效要求时不传 time_range，让 SearchHub 返回更稳定的相关结果

## 正文抓取
- 默认传 `enable_fetch=true`，特别是新闻、政策、价格、技术资料
- 只要标题和链接时传 `enable_fetch=false`
- SearchHub 由服务端抓取；DuckDuckGo fallback 由 Agent 直接抓取结果页面
- 主 Agent 默认只接收 `content_mode="evidence"` 的摘要、证据和来源，完整正文不进入工具结果

## Embedding 精筛
- 用户要求"精筛、精排、相关性更准、减少标题噪声、交叉验证"时，传 `enable_embedding_filter=true`
- 农业技术、政策解读、病虫害防治等需要较强证据相关性的查询，结合 `enable_fetch=true` 一起使用
- 仅 SearchHub provider 生效

## 多工具协作
用户问"结合我农场情况看最近价格"时，可先用 `get_farm_status` 获取农场作物，再搜索外部价格信息。

## 失败处理
- 搜索失败时返回中文说明，不暴露内部异常
- SearchHub 返回空结果时自动降级到 DuckDuckGo
- DuckDuckGo 也无结果时返回"未找到关于「{query}」的结果"

## 示例
- 用户："最近西瓜价格怎么样" → `web_search(query="2026年 西瓜 价格", top_k=8, time_range="month", enable_fetch=true)`
- 用户："今天最新农业政策" → `web_search(query="2026年 最新农业政策", top_k=8, time_range="day", enable_fetch=true)`
- 用户："苏州西瓜白粉病最新防治" → `web_search(query="苏州西瓜白粉病最新防治", domain="agriculture", region="苏州", crop="西瓜", top_k=8, time_range="month", enable_fetch=true, enable_embedding_filter=true)`
