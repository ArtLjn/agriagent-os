# 记录工作台 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/record-workbench-redesign.png`
- Canvas: `1024x2224px`
- Intended platform: mobile

## Layout

- Header: preserve existing brand lockup and clock action from the current record page.
- Content area: replace the previous two large action cards with a denser recording workbench.
- Smart recording hub: first content card under the header, containing title, short helper copy, one-line input, primary recognition action, and compact manual shortcuts.
- Report shortcut: place below the input hub. Provide `生成周报` and `生成月报` as first-class actions with small contextual metrics.
- Today overview: compact metric tiles for current operational status.
- Common tools: compact grid for secondary actions such as batch, worker, template, recent records,补记录, and wage settlement.
- Bottom tab bar: preserve existing five-tab navigation and active `记录` state.

## Design Tokens

### Colors

- `--color-bg`: `#F6F9FC`
- `--color-surface`: `#FFFFFF`
- `--color-primary`: `#1677FF`
- `--color-primary-strong`: `#0F63F6`
- `--color-green`: `#08A969`
- `--color-amber`: `#F59E0B`
- `--color-text`: `#111827`
- `--color-text-muted`: `#7A869A`
- `--color-border`: `#E6EEF8`

### Typography

- Font family: system sans-serif.
- Page/card title: `22px/28px/800`.
- Section title: `16px/22px/800`.
- Body: `14px/20px/600`.
- Caption: `12px/16px/500`.

### Spacing And Shape

- Base grid: `8px`.
- Page padding: keep existing `20px` logical horizontal padding.
- Card padding: `16px`.
- Card radius: `18px` to `20px`.
- Control height: `44px` minimum tap target.
- Content gaps: `10px` to `14px`.

## Components

- Smart input card: rounded white card with light border/shadow. Contains a prominent text input and one primary blue action.
- Shortcut chips: three compact rounded buttons: `手动记一笔`, `记农事`, `记工资`.
- Report card: two equal action blocks for weekly and monthly reports. Each action should be tappable.
- Metric tile: compact surface tile with value, label, and small icon/accent color.
- Tool grid item: compact icon tile with label and optional caption.

## Exact Text

- `今天要记什么？`
- `说一句，自动归类成账目/农事/工资`
- `买肥料300，老王工资200...`
- `识别`
- `手动记一笔`
- `记农事`
- `记工资`
- `经营报告`
- `生成周报`
- `生成月报`
- `本周12条记录`
- `本月支出¥4,820`
- `今日概览`
- `今日已记3条`
- `待确认1条`
- `工资待结2人`
- `本周支出¥1,280`
- `常用工具`
- `建批次`
- `新增工人`
- `建模板`
- `最近记录`
- `补记录`
- `工资结算`

## Implementation Invariants

- Do not change the header brand area.
- Do not change the bottom tab bar structure, labels, or active `记录` tab.
- Do not restore the previous oversized `AI帮我填` and `自己填` cards.
- The primary AI action lives in the smart input card as `识别`.
- Manual entry remains available as a compact shortcut.
- Weekly and monthly report actions must appear in the first screen.
- Avoid a large empty lower half; the screen should read as a practical workbench.
