# 新建茬口页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/business-pages/farm-cycle-form.png`
- Canvas: `1024x2224px`
- Intended platform: mobile Flutter app, `430x932` logical px target

## Interface Mapping

- Save endpoint: `POST /cycles`
- Update endpoint: `PUT /cycles/{cycle_id}`
- Smart-fill parse: `POST /smart-fill/parse` with `scene=crop.cycle`
- Fields: `name`, `crop_template_id`, `start_date`, `field_name`, `total_area_mu`, `season`, `batch_note`

## Layout

- Header: back button, centered title `新建茬口`, subtle smart-fill icon.
- Assist strip: `说一句生成茬口草稿`.
- Form cards: basic info, area/season/note, stage preview.
- Stage preview uses a gentle vertical timeline with green dots.
- Sticky bottom action: `保存草稿`, `创建茬口`.

## Exact Bottom Tabs

- `首页`
- `记录`
- `芽芽`
- `账本`
- `我的`

## Implementation Invariants

- Keep smart-fill visually secondary.
- Preserve a soft agricultural banner/card mood.
- Do not show unsupported AI save behavior; parse returns draft only.
