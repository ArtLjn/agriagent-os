# 全部交易页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/farm-manager-all-transactions.png`
- Canvas: `1024x2224px`
- Intended platform: mobile app

## Layout

- Top app bar: white background, 88px visual height below status area, left back chevron, centered title `全部交易`, right calendar/filter action.
- Page content: 48px horizontal padding on image canvas, translated to 20px logical padding in Flutter.
- Summary strip: rounded white card below app bar with three compact metrics: `本月`, `支出 ¥11.6万`, `收入 ¥5500`.
- Filter row: segmented controls below summary, `全部` selected, followed by `支出`, `收入`, `欠款`.
- Main list card: white card with 18px logical radius, title `2026年6月`, repeated transaction rows and indented dividers.
- Bottom action: rounded primary button `手动记一笔` above bottom safe area.

## Design Tokens

### Colors

- `--color-bg`: `#F7F9FC`
- `--color-surface`: `#FFFFFF`
- `--color-primary`: `#1473FF`
- `--color-income`: `#08A66A`
- `--color-expense`: `#F04438`
- `--color-orange`: `#F97316`
- `--color-text`: `#101828`
- `--color-text-muted`: `#667085`
- `--color-border`: `#E4EAF2`

### Typography

- Font family: system sans-serif, same as current Flutter app.
- Page title: 20px / 28px / 800.
- Section title: 18px / 26px / 800.
- Row title: 16px / 22px / 700.
- Amount: 17px / 24px / 800, tabular figures.
- Caption: 13px / 18px / 500.

### Spacing And Shape

- Base grid: `8px`.
- Logical page padding: `20px`.
- Card padding: `16px`.
- Card radius: `18px`.
- Row height: `68px` to match existing transaction row component.
- Icon square: `44x44px`, radius `14px`.

## Components

- App bar: `ReferenceHeader`-style title row, but with a back button on the left and a single icon action on the right.
- Metric chip: compact rounded pill/card, neutral border, text must stay single-line.
- Filter segment: four chips, selected state uses blue text and pale blue background.
- Transaction row: reuse existing `TransactionRow` geometry. Amount is right aligned and uses `FittedBox(scaleDown)` to avoid overflow.
- List preview rule:账本首页只展示最近 5 条；`全部交易` 页面展示完整 `model.transactions`。

## Exact Text

- `全部交易`
- `本月`
- `支出 ¥11.6万`
- `收入 ¥5500`
- `全部`
- `支出`
- `收入`
- `欠款`
- `2026年6月`
- `饲料`
- `2026-06-09 · 日常支出`
- `-¥3680`
- `种子`
- `2026-06-08 · 张三`
- `-¥130`
- `还款`
- `2026-06-08`
- `¥500`
- `化肥`
- `2026-06-08 · 日常支出`
- `-¥100`
- `人工`
- `2026-06-07 · 李师傅`
- `-¥800`
- `手动记一笔`

## Implementation Invariants

- Do not add a nested scrollbar inside the homepage transaction card.
- Keep the homepage `最近交易` as a preview, with `查看全部` as the transition.
- Reuse the existing billing row visual language and color tokens.
- Amount text must never overflow horizontally; use compact money formatting and scale-down protection.
- Empty state should remain simple: one card line `暂无交易` plus optional action later.
