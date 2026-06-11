# 记账手动填写页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/business-pages/ledger-manual-create.png`
- Canvas: `1024x2224px`
- Intended platform: mobile Flutter app, `430x932` logical px target

## Interface Mapping

- Save endpoint: `POST /costs`
- Required fields: `record_type`, `category`, `amount`, `record_date`
- Optional fields: `cycle_id`, `note`, `record_subtype`, `counterparty`, `due_date`
- Smart-fill parse: `POST /smart-fill/parse` with `scene=ledger.record`

## Layout

- Header: back button, centered title `记账`, trailing history icon.
- Soft ledger banner: notebook/receipt/farm icon background, no heavy dashboard styling.
- Form groups: record type, category, amount, date, cycle, counterparty, settlement, note.
- Sticky bottom action: secondary `取消`, primary `保存记录`.

## Exact Bottom Tabs

- `首页`
- `记录`
- `芽芽`
- `账本`
- `我的`

## Implementation Invariants

- Keep `记录` selected when bottom nav is visible.
- Preserve the soft white-card style and avoid strong industrial gradients.
- Use blue only for primary actions and active controls.
