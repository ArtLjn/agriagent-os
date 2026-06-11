# 工人管理列表页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/business-pages/worker-list.png`
- Canvas: `1024x2224px`
- Intended platform: mobile Flutter app, `430x932` logical px target

## Interface Mapping

- List endpoint: `GET /planting/workers/summary`
- Worker create target: `POST /planting/workers`
- Wage action target: `POST /planting/labor/wages`

## Layout

- Header: back button, centered title `工人管理`, trailing filter icon.
- Banner: soft labor/farm illustration card, not dark industrial dashboard.
- Summary values: `未结 1,260元`, `工人 8`, `本月用工 12`, `相关茬口 3`.
- Actions: `记一笔工资`, `新增工人`.
- Search: `搜索工人姓名`.
- Chips: `全部`, `有欠款`, `已结清`, `停用`.
- Worker rows show avatar, name, default pay, cycle relation, unpaid amount/status.

## Exact Bottom Tabs

- `首页`
- `记录`
- `芽芽`
- `账本`
- `我的`

## Implementation Invariants

- Keep `记录` selected.
- Unpaid amount should be visually clear but not alarming unless overdue.
- Do not change bottom tab labels.
