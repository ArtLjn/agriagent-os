## ADDED Requirements

### Requirement: 中国天气网预警爬虫
系统 SHALL 通过爬取 weather.com.cn 的 `/dingzhi/{city_code}.html` 页面获取中国官方气象预警数据，不消耗任何 API 配额。

#### Scenario: 获取城市预警
- **WHEN** `AlertScraper.fetch_alerts("苏州")` 被调用
- **THEN** 先查找苏州的 weather.com.cn 城市编号，请求 `/dingzhi/{code}.html`，解析返回数据为 `list[WeatherAlert]`

#### Scenario: 有预警时返回
- **WHEN** 苏州当前有"暴雨黄色预警"
- **THEN** 返回 `list[WeatherAlert(title="暴雨黄色预警", severity="yellow", description=...)]`

#### Scenario: 无预警时返回空列表
- **WHEN** 查询城市当前无任何预警
- **THEN** 返回空列表 `[]`

### Requirement: 预警爬虫独立缓存
预警数据 SHALL 独立缓存，TTL 为 10 分钟（预警官方更新频率约 5 分钟），不与天气预报缓存耦合。

#### Scenario: 缓存命中
- **WHEN** 10 分钟内再次查询同一城市预警
- **THEN** 直接返回缓存数据，不发起网络请求

#### Scenario: 缓存过期
- **WHEN** 缓存超过 10 分钟
- **THEN** 重新请求 weather.com.cn 获取最新预警

### Requirement: 预警爬虫降级容错
爬虫请求失败时 SHALL 静默降级，不影响天气预报功能。返回空预警列表 + 记录 warning 日志。

#### Scenario: 网络超时
- **WHEN** weather.com.cn 请求超时（>10s）
- **THEN** 返回空预警列表，记录 warning 日志，预报功能不受影响

#### Scenario: 页面结构变更解析失败
- **WHEN** `/dingzhi/` 页面 HTML/JS 结构变更，解析失败
- **THEN** 返回空预警列表，记录 warning 日志（含原始响应摘要），降级为 Open-Meteo 本地阈值检测

### Requirement: 城市名到 weather.com.cn 编号映射
系统 SHALL 维护城市名到 weather.com.cn 城市编号（101 开头 9 位数字）的映射。优先使用和风天气 GeoAPI 返回的城市信息中的 `adm1/adm2` 字段进行模糊匹配，匹配失败时回退到本地常见城市映射表。

#### Scenario: 城市名精确匹配
- **WHEN** 传入"苏州"
- **THEN** 映射到 `101190401`（苏州市编号）

#### Scenario: 城市名未匹配
- **WHEN** 传入"某某镇"且映射表中无记录
- **THEN** 跳过预警爬取，预报结果中 `alerts` 为空列表，不报错
