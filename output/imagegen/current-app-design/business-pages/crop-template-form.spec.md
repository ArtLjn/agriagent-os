# 新建作物模板页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/business-pages/crop-template-form.png`
- Canvas: `1024x2224px`
- Intended platform: mobile Flutter app, `430x932` logical px target

## Interface Mapping

- Save endpoint: `POST /crops/templates`
- Update endpoint: `PUT /crops/templates/{template_id}`
- Smart-fill parse: `POST /smart-fill/parse` with `scene=crop.template`
- Fields: `name`, `variety`, `stages[]`
- Stage fields: `name`, `duration_days`, `order_index`, `key_tasks`

## Layout

- Header: back button, centered title `新建模板`.
- Assist strip: `输入作物名称，AI生成阶段`.
- Form card: crop name, variety, season/tag.
- Stage editor: editable rows, duration, key task, add-stage row.
- Sticky bottom action: `预览`, `保存模板`.

## Exact Bottom Tabs

- `首页`
- `记录`
- `芽芽`
- `账本`
- `我的`

## Implementation Invariants

- Stage rows should be easy to scan and reorder later.
- AI assist only generates draft stages; saving still uses template endpoint.
