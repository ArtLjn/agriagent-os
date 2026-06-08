# 首页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/farm-app-home-soft-ops.png`
- Canvas: `1024x2224px`
- Intended platform: mobile app screen
- Visual direction: 现代轻量经营工具，不要农业插画风或工业大屏风。

## Layout

- Top app bar: title `今日概览`, date/greeting, one right action icon.
- Content: vertical scroll, 16px logical page padding.
- Bottom navigation: `首页`、`工作台`、`芽芽`、`账单`、`我的`; `首页` selected.

## Design Tokens

- `--color-bg`: `#F7F8FA`
- `--color-surface`: `#FFFFFF`
- `--color-primary`: `#3B82F6`
- `--color-success`: `#12A36A`
- `--color-warning`: `#F59E0B`
- `--color-text`: `#111827`
- `--color-muted`: `#6B7280`
- `--color-border`: `#E5E7EB`
- Font: `PingFang SC`, `Inter`, system sans-serif
- Card radius: `18px`
- Base grid: `8px`

## Components

- AI brief card: title `芽芽今日建议`, short operational recommendation.
- Metric row: `天气 24℃`, `夜间 8℃`, `作业窗口 良好`.
- Risk card: `降温提醒`.
- Task timeline: `授粉复核`, `覆盖保温`, `人工待结`.
- Recent operations list.

## Invariants

- Avoid leaves, crops, soil, farm photos, rustic texture, heavy green palette, and industrial dark panels.
- Keep the screen useful as an operations dashboard, not a marketing hero.
