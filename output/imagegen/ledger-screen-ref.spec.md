# Ledger Screen Refined UI Spec

## Image

- Source image: `output/imagegen/ledger-screen-ref.png`
- Generation status: AISpeech gateway returned SSL EOF twice, no image was saved.
- Canvas: `1024x2224px`
- Intended platform: Flutter mobile app, logical width `430px`

## Layout

- Main ledger tab keeps the existing app shell and bottom navigation.
- Financial overview: dark ink-blue summary card, compact year pill, net profit as primary focus, three metrics in a translucent strip.
- Insight row: white card, blue icon tile, neutral `智能复盘` pill, two-line analysis copy.
- Recent transactions: white list card, semantic icons, thin dividers, compact row height.
- Receivable reminder: white card, blue person icon, amber amount, ink outline call action.
- Primary CTA: dark ink-blue button with pen icon, no green fill and no gradient.

## Design Tokens

- `--color-bg`: `#F6F7F9`
- `--color-surface`: `#FFFFFF`
- `--color-primary`: `#172A3A`
- `--color-primary-soft`: `#24384C`
- `--color-border`: `#E6EAF0`
- `--color-blue`: `#2F6FED`
- `--color-blue-soft`: `#EDF4FF`
- `--color-income`: `#16805D`
- `--color-income-soft`: `#EAF7F1`
- `--color-expense`: `#B85C2A`
- `--color-expense-soft`: `#FFF4E6`
- `--color-negative`: `#C43E35`

## Implementation Invariants

- Keep visible strings required by existing tests: `资金概览`, `AI财务洞察`, `最近交易`, `查看全部`, `待收款提醒`, `手动记一笔`.
- Do not reintroduce bright green summary cards or green primary CTA.
- Green is only semantic income coloring.
- Amounts continue using tabular figures and compact money formatting.
- All transactions page keeps the internal `Scrollbar` + `ListView`.
