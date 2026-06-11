# 作物模板列表页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/business-pages/crop-template-list.png`
- Canvas: `1024x2224px`
- Intended platform: mobile Flutter app, `430x932` logical px target

## Interface Mapping

- List endpoint: `GET /crops/templates`
- Create target: `POST /crops/templates`
- Update target: `PUT /crops/templates/{template_id}`
- Smart-fill parse: `POST /smart-fill/parse` with `scene=crop.template`

## Layout

- Header: back button, centered title `作物模板`, trailing add icon.
- Banner: soft template-library card with crop/book illustration.
- Search: `搜索作物或品种`.
- Chips: `全部`, `瓜果`, `蔬菜`, `粮食`.
- Template cards show crop illustration, name, variety, stage count, total cycle days, usage count, mini stage timeline.
- Card actions: `新建茬口`, `编辑`.

## Exact Bottom Tabs

- `首页`
- `记录`
- `芽芽`
- `账本`
- `我的`

## Implementation Invariants

- Keep cards elegant and readable.
- Avoid excessive dashboard or AI visuals.
- Keep `记录` selected when bottom nav is visible.
