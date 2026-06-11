# 茬口管理列表页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/business-pages/farm-cycle-list.png`
- Canvas: `1024x2224px`
- Intended platform: mobile Flutter app, `430x932` logical px target

## Interface Mapping

- List endpoint: `GET /cycles`
- Create action target: `POST /cycles`
- Card actions:
  - `记农事`: navigate to operation/work-order form, saving to `POST /planting/work-orders`
  - `查看账本`: navigate to ledger filtered by `cycle_id`, using `GET /costs?cycle_id=...`

## Layout

- Header: back button, centered title `茬口管理`, trailing filter icon.
- Banner: soft agricultural banner with leaf/crop illustration background.
- Summary values: `在种茬口 3`, `总面积 18.6亩`, `今日阶段 苗期管理`.
- Search: `搜索作物、地块、茬口`.
- Status chips: `全部`, `在种`, `计划`, `已结束`.
- List cards include crop avatar, crop/template text, field/area, status pill, progress bar, quick actions.
- Floating action: `新建茬口`.

## Exact Bottom Tabs

- `首页`
- `记录`
- `芽芽`
- `账本`
- `我的`

## Implementation Invariants

- Keep `记录` selected.
- Banner must feel like a farm/crop card, not an AI analytics panel.
- Do not change bottom tab labels.
