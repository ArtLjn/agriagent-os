# 首页 AI 数据驾驶舱 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/main-pages-v3/home-ai-cockpit.png`
- Canvas: `1024x2224px`
- Intended Flutter logical canvas: `390x844`
- Status: 候选优化稿，确认后替换 `current-app-design/main-pages/home.png`

## Design Direction

首页不再以 `今日待办`、`最近记录` 为核心，因为当前 MVP 没有稳定接口支撑这些列表。首页定位调整为 AI 增强的数据驾驶舱，用已有经营数据和 AI 聚合结果呈现农场经营状态。

## Layout

- Top app bar: `56-64px`，左侧品牌和标题 `农场管家`，右侧通知入口。
- Page padding: `20px` logical px。
- Hero cockpit card: 顶部主卡，约 `250-280px` logical px，高视觉优先级。
- AI recommendations card: 主卡下方，展示 3 条今日建议，不使用长列表。
- Insight grid: `2 x 2` 小仪表卡，展示资金、成本、茬口、风险。
- Quick action area: 底部靠近拇指区，放 `问问芽芽`、`记一笔`、`生成报告`。
- Bottom tab bar: 保持 `首页 / 记录 / 芽芽 / 账本 / 我的`。

## Design Tokens

### Colors

- Background: `#F7FAFC`
- Surface: `#FFFFFF`
- Primary: `#2F73F6`
- Green: `#35C879`
- Orange: `#FF9F1C`
- Text primary: `#111827`
- Text secondary: `#6B7280`
- Border: `#E8ECF2`

### Typography

- Font family: Flutter system / PingFang SC style
- Page title: `22px`, `FontWeight.w800`
- Card title: `16px`, `FontWeight.w800`
- Metric number: `28-36px`, `FontWeight.w800`
- Body: `14px`, `FontWeight.w500`
- Caption: `12px`, `FontWeight.w500`

## Components

- `经营态势 HeroCard`: 包含 `今日经营态势`、AI badge、经营评分、状态说明、3 个小指标。
- `AI 今日建议 Card`: 3 条短建议，使用图标 + 短文案，不做长段落。
- `InsightMetricCard`: 四个固定卡片，分别是 `资金概览`、`成本分析`、`茬口进度`、`风险预警`。
- `QuickAction`: `问问芽芽` 作为主入口，`记一笔`、`生成报告` 作为辅助入口。

## Exact Text

- `农场管家`
- `今日经营态势`
- `AI分析`
- `86`
- `经营稳定，注意午后天气`
- `AI 今日建议`
- `午后避开露天作业`
- `西瓜批次补充灌溉`
- `本月饲料成本偏高`
- `资金概览`
- `成本分析`
- `茬口进度`
- `风险预警`
- `问问芽芽`
- `记一笔`
- `生成报告`

## Implementation Invariants

- 不出现 `今日待办`。
- 不出现 `最近记录`。
- 首页首屏必须像 AI 数据仪表盘，不像管理后台列表。
- 只展示可由 AI 聚合或已有账本/批次/风险数据推导的内容。
- 保留手动功能入口，但不要抢首页主视觉；手动创建主要放在 `记录` Tab。
