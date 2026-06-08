# 农场管家 MVP 整体 UI 布局规格

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/farm-app-mvp-overall-layout.png`
- Canvas: `2048x1152px`
- Intended platform: mobile app overview board

## Product Positioning

- MVP 阶段所有能力默认免费。
- AI 是效率加速器，不是唯一入口。
- 手动录入必须作为稳定兜底存在。
- 用户不需要理解后端对象和技术口径，页面应使用现实语言。

## Main Navigation

- `首页`: 今天该做什么、有什么提醒、有哪些待确认。
- `记录`: 创建入口，包含 AI 帮填和手动填写。
- `芽芽`: 问答、建议、分析、报告。
- `账本`: 收支、欠款、人工结算、流水纠错。
- `我的`: 账号、农场、默认城市、AI 偏好、版本。

## Page Layout

### 首页

- Title: `今日`
- Modules:
  - `今天该做什么`
  - 天气/风险提醒
  - 待确认事项
  - 最近记录
- Avoid dense dashboard metrics.

### 记录

- Title: `记录`
- Primary choices:
  - `AI帮我填`
  - `自己填`
- AI input:
  - `说一句，我帮你填好`
- Manual quick actions:
  - `记账`
  - `记农事`
  - `记工资`
  - `建批次`
  - `新增工人`
  - `建模板`
- Confirmation card:
  - Natural-language extracted fields
  - Actions: `保存`, `改一下`

### 芽芽

- Title: `芽芽`
- Purpose: open-ended questions and analysis.
- Prompt chips:
  - `今天适合干什么`
  - `本月成本怎么看`
  - `生成周报`
- Should not look like another write form.

### 账本

- Title: `账本`
- Modules:
  - Cashflow summary
  - Income/cost/debt
  - Recent transactions
  - Unpaid wages/debt reminders
  - `手动记一笔`

### 我的

- Title: `我的`
- Modules:
  - User/farm profile
  - Default city/weather
  - AI preferences
  - App settings
  - Version info

## Design Tokens

- `--color-bg`: `#F8F9FB`
- `--color-surface`: `#FFFFFF`
- `--color-primary`: `#3478F6`
- `--color-primary-soft`: `#EEF4FF`
- `--color-text`: `#111827`
- `--color-muted`: `#6B7280`
- `--color-border`: `#E5E7EB`
- `--color-warning`: `#F59E0B`
- `--color-success`: `#16A36A`

## Visual Constraints

- Avoid agricultural illustration: no crops, leaves, soil, field photos, cartoon vegetables.
- Avoid industrial/admin style: no dark dashboards, dense tables, factory/machinery cues.
- Avoid technical labels: no `record_type`, `source_id`, API terms, or backend object names unless user-facing.
- Keep labels short and legible.
- Favor large clear actions over dense feature grids.

## Implementation Invariants

- The `记录` tab is the primary creation surface.
- `AI帮我填` and `自己填` must coexist.
- Manual entry is free and reliable; AI entry accelerates but can fall back to manual correction.
- AI confirmation cards and manual forms should write to the same underlying domain models.
