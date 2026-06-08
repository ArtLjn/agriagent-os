# 农场管家参考风格总览图 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/farm-app-reference-style-overview.png`
- Canvas: `2048x1152px`
- Format: five mobile screens overview board

## Visual Direction

- Match the provided reference: white phone-like screens, soft shadows, light gray background, blue primary actions, green secondary action.
- Friendly consumer app feeling, not old admin dashboard.
- Avoid industrial style and rustic agricultural visuals.

## Navigation

- Bottom tabs: `首页`, `记录`, `芽芽`, `账本`, `我的`.
- Page labels under screens: `首页`, `记录`, `芽芽`, `账本`, `我的`.

## Page Rules

### 首页

- Header: `农场管家`
- Date: `今日 · 5月18日 星期日`
- Blue status card:
  - `今日待办 3`
  - `风险提醒 1`
  - `待确认 2`
- Weather strip:
  - `22~29°C`
  - `午后有雷阵雨`
- Task card:
  - `确认工人出勤`
  - `饲料采购单确认`
  - `5月第2批次记录`
- Recent records card.

### 记录

- This is the intelligent filling and manual entry hub.
- Top actions:
  - `AI帮我填`
  - `自己填`
- Input:
  - `说一句，我帮你填好`
- Manual quick grid:
  - `记账`
  - `记农事`
  - `记工资`
  - `建批次`
  - `新增工人`
  - `建模板`
- AI generated record card:
  - `待确认`
  - `改一下`
  - `保存`

### 芽芽

- Chat/assistant page only.
- Use assistant identity `芽芽 AI助手`.
- Suggested questions:
  - `今天适合干什么`
  - `本月成本怎么看`
  - `生成周报`
- Do not make this page the primary write form.

### 账本

- Finance view only.
- Must not show `AI帮我填` here.
- Modules:
  - `资金概览（本月）`
  - `收入 28,650`
  - `支出 18,240`
  - `欠款 6,410`
  - Recent transactions
  - Receivable/debt reminder
  - Button: `手动记一笔`

### 我的

- Profile/settings page.
- User: `张三`, `农场负责人`
- Rows:
  - `所在城市`
  - `默认天气`
  - `回答风格`
  - `数据分析深度`
  - `自动生成报表`
  - `数据备份与恢复`
  - `消息通知`
  - `关于农场管家`

## Design Tokens

- `--color-bg`: `#F7F9FC`
- `--color-card`: `#FFFFFF`
- `--color-primary`: `#2F73F6`
- `--color-green`: `#35C879`
- `--color-orange`: `#FF9F1C`
- `--color-purple`: `#7C5CFF`
- `--color-text`: `#111827`
- `--color-muted`: `#6B7280`
- `--color-border`: `#E8ECF2`

## Invariants

- 智能填写只集成到 `记录` 页。
- `账本` 页只负责查看资金、交易、欠款，并提供 `手动记一笔`。
- 不要出现暗色后台、工业风、农田插画、农作物装饰。
- 不要出现技术字段或 API 口径。
