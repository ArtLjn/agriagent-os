# 记录工作台优化版 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/record-workbench-redesign-refined.png`
- Previous draft: `/Users/ljn/Documents/demo/explore/output/imagegen/record-workbench-redesign.png`
- Canvas: `1024x2224px`
- Intended platform: mobile

## Design Direction

- 去掉 `AI帮我填` / `自己填` 两张大卡。
- 将 AI 能力收敛到一句话输入卡里的 `识别` 主动作。
- 将手动录入降级为紧凑快捷入口 `手动记一笔`。
- 首屏必须出现 `生成周报` 和 `生成月报`。
- 页面目标是经营记录工作台，不是功能入口海报。

## Layout

- Header: keep the existing brand lockup, top safe area, and clock action unchanged.
- Smart input card: first content module below header. Approximate logical height `180-200px`.
- Report card: second module. Approximate logical height `112-128px`.
- Today overview: third module, with section title and a `2x2` metric grid.
- Common tools: final module in first screen, with section title and a compact `3x2` tool grid.
- Bottom tab bar: keep five tabs unchanged and keep `记录` active.

## Design Tokens

### Colors

- `--color-bg`: `#F6F9FC`
- `--color-surface`: `#FFFFFF`
- `--color-primary`: `#1677FF`
- `--color-primary-strong`: `#0F63F6`
- `--color-green`: `#08A969`
- `--color-amber`: `#F59E0B`
- `--color-teal`: `#06A6B7`
- `--color-text`: `#111827`
- `--color-text-muted`: `#7A869A`
- `--color-border`: `#E6EEF8`
- `--color-soft-blue`: `#EEF6FF`
- `--color-soft-green`: `#ECFBF4`
- `--color-soft-amber`: `#FFF7E8`

### Typography

- Font family: system sans-serif.
- Main card title: `22px/28px/800`.
- Section title: `16px/22px/800`.
- Body: `14px/20px/600`.
- Caption: `12px/16px/500`.
- Metric value: `18px/24px/800`.

### Spacing And Shape

- Base grid: `8px`.
- Page horizontal padding: keep current `20px` logical padding.
- Module gap: `12px`.
- Card padding: `16px`.
- Card radius: `18px` to `20px`.
- Input height: `46px` to `50px`.
- Button minimum tap target: `44px`.
- Tool tile radius: `16px`.

## Components

- SmartInputCard:
  - White surface with subtle border and shadow.
  - Title: `今天要记什么？`
  - Helper: `说一句，自动整理成账目、农事或工资`
  - Input placeholder: `例：买肥料300，老王工资200`
  - Primary button: `识别`
  - Shortcut pills: `手动记一笔`, `记农事`, `记工资`

- ReportShortcutCard:
  - White or very light blue surface.
  - Title: `经营报告`
  - Subtitle: `本周12条记录 · 本月支出¥4,820`
  - Actions: `生成周报`, `生成月报`
  - Actions should be visually equal; weekly can be slightly primary.

- TodayOverviewGrid:
  - `2x2` metric tiles.
  - Each tile has a small colored icon badge, one value, one label.
  - Metrics: `今日已记 3条`, `待确认 1条`, `工资待结 2人`, `本周支出 ¥1,280`.

- CommonToolGrid:
  - `3x2` compact grid.
  - Tools: `建批次`, `新增工人`, `建模板`, `最近记录`, `补记录`, `工资结算`.
  - Tool icons use line icons in tinted rounded badges.

## Exact Text

- `今天要记什么？`
- `说一句，自动整理成账目、农事或工资`
- `例：买肥料300，老王工资200`
- `识别`
- `手动记一笔`
- `记农事`
- `记工资`
- `经营报告`
- `本周12条记录 · 本月支出¥4,820`
- `生成周报`
- `生成月报`
- `今日概览`
- `今日已记`
- `3条`
- `待确认`
- `1条`
- `工资待结`
- `2人`
- `本周支出`
- `¥1,280`
- `常用工具`
- `建批次`
- `新增工人`
- `建模板`
- `最近记录`
- `补记录`
- `工资结算`

## Implementation Invariants

- Header and tab bar are out of scope; do not redesign them.
- Do not reintroduce the previous two large action cards.
- The first primary action is always the smart input `识别`.
- `生成周报` and `生成月报` must be visible without scrolling on a standard mobile viewport.
- The screen should avoid large decorative illustrations in the content area.
- Use compact, tappable business controls instead of marketing-style hero cards.
- Text must not overflow on narrow devices; use `FittedBox` only for values, not section labels.
