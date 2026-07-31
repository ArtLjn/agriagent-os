---
name: web_search
type: read
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
      description: "搜索关键词。应包含核心实体、事件或主题；需要实时信息时保留“最新、今天、最近、价格、政策”等时效词。"
    categories:
      type: string
      description: "兼容旧参数。搜索类别: general/news/images/videos，默认 general。"
      default: "general"
    time_range:
      type: string
      description: "日期筛选。day/d=最近一天，week/w=最近一周，month/m=最近一月，year/y=最近一年。实时新闻优先 week/w；今天、刚刚、当天用 day/d；价格、行情、走势默认 month/m。"
    top_k:
      type: integer
      description: "筛选条数，默认 5，范围 1-20。普通事实 5 条；实时新闻、政策和行情建议 8-10 条；需要多来源交叉验证时最多 12 条；不要无理由传 20。"
    enable_fetch:
      type: boolean
      description: "是否请求 SearchHub 抓取网页正文。默认应传 true，以便获得更完整证据；只做极快标题级搜索或网络慢时才传 false。"
    enable_embedding_filter:
      type: boolean
      description: "是否启用 SearchHub embedding 精筛。开启后服务端会扩大候选，并按 query 与结果文本的向量相似度过滤排序；未显式传入时由运行时自动判断。"
    domain:
      type: string
      description: "领域参数，例如 agriculture。"
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
用户的问题依赖最新外部信息时使用本 Skill，例如农业政策、新闻、市场价格、上市时间、热点事件和实时资料。运行时通过 SearchHub `/search` 获取结构化结果、证据和可追踪信息。

## 不要使用
- 用户查询本农场内部账单、农事、茬口或天气时，不要用搜索，应使用对应内部 Skill。
- 用户问通用种植知识且不需要最新信息时，可直接回答或结合农场上下文。
- 用户只需要内部农场数据时，不要用外部搜索补答案。

## 参数推断
- “最近西瓜价格怎么样” -> `query=2026年 西瓜 价格`。
- “今年农业补贴政策” -> `query=2026年 农业补贴政策`。
- “番茄什么时候上市” -> `query=番茄 上市 时间`。
- 农业生产类实时搜索可补 `domain=agriculture`、`region`、`crop`，让 SearchHub 启用领域增强流程。

## 筛选条数
- 默认使用 `top_k=5`，适合普通事实查询、百科补充和低风险背景资料。
- 用户问“最新动态、新闻、政策、公告、价格、行情、走势”时，建议 `top_k=8`，提高多来源覆盖。
- 用户要求“多找几条、综合比较、交叉验证、来源充分”时，可用 `top_k=10` 到 `12`。
- 不要为了保险直接使用最大值；`top_k=20` 只适合用户明确要求大范围搜集资料。

## 日期筛选
- 用户说“今天、当天、刚刚、最新发布、实时直播”时，传 `time_range="day"`。
- 用户说“最新动态、最近新闻、近日消息、有什么新进展”时，传 `time_range="week"`。
- 用户说“价格、行情、走势、近期市场、最近政策汇总”时，传 `time_range="month"`。
- 用户说“今年、年度、全年政策、过去一年”时，传 `time_range="year"`。
- 如果用户没有时效要求，不要硬加日期筛选；让 SearchHub 返回更稳定的相关结果。
- 代码会兼容 `day/week/month/year` 和 `d/w/m/y`；在工具调用里优先写可读形式 `day/week/month/year`。

## 正文抓取
- 默认传 `enable_fetch=true`，特别是新闻、政策、价格、农业技术和需要引用来源的问题。
- 只有用户要求快速粗搜，或明确只要标题和链接时，才传 `enable_fetch=false`。
- 如果 SearchHub 返回 `agent.answerable=false`，下一轮可增加 `top_k`、打开 `enable_fetch=true`、放宽或调整 `time_range` 后重搜。

## Embedding 精筛
- 未显式传入 `enable_embedding_filter` 时，运行时会自动判断，普通低风险查询保持普通搜索速度和成本。
- 涉及重要信息且噪音高的查询会首轮自动开启精筛，例如“今天西瓜价格”“最新农业补贴政策”“苏州西瓜病害防治可靠资料”。
- 首轮普通搜索返回 `agent.answerable=false` 时，会自动补一次 `enable_embedding_filter=true` 的精筛重试，避免标题噪声或泛化结果漏掉关键信息。
- 用户明确要求“精筛、精排、相关性更准、减少标题噪声、多来源交叉验证”时，主动传 `enable_embedding_filter=true`。
- 用户明确要求快速粗搜、只要标题链接或关闭精筛时，可传 `enable_embedding_filter=false`，运行时会尊重显式值。
- 农业生产技术、政策解读、病虫害防治和价格行情等需要较强证据相关性的查询，可结合 `enable_fetch=true` 一起使用。
- 如果 SearchHub embedding 服务未配置或失败，应按搜索服务返回的错误或降级结果回答，不要在 Farm Manager 内部自行调用 embedding provider。

## 缺参策略
- 缺少搜索关键词时必须追问。
- 未说明类别时默认 `general`。

## 多工具协作
如果用户问“结合我农场情况看最近价格”，可先用 `get_farm_status` 获取农场作物，再搜索外部价格信息。

## Runtime 策略
- permission: read
- direct_call: false
- direct_return: false
- cache: none

## 失败处理
- 查询词不明确时，用中文追问用户想搜索的主题。
- 搜索失败时返回中文说明，不暴露内部异常。
- SearchHub 返回 `agent.answerable=false` 时，不要强答；应说明证据不足并建议缩小或改写查询。

## 示例
- 用户：“查询特朗普最新动态” -> `web_search(query="特朗普 最新动态", top_k=8, time_range="week", enable_fetch=true)`
- 用户：“最近西瓜价格怎么样” -> `web_search(query="2026年 西瓜 价格", top_k=8, time_range="month", enable_fetch=true)`
- 用户：“今天最新农业政策有什么” -> `web_search(query="2026年 最新农业政策", top_k=8, time_range="day", enable_fetch=true)`
- 用户：“苏州西瓜白粉病最新防治，帮我精筛可靠资料” -> `web_search(query="苏州西瓜白粉病最新防治", domain="agriculture", region="苏州", crop="西瓜", top_k=8, time_range="month", enable_fetch=true, enable_embedding_filter=true)`
