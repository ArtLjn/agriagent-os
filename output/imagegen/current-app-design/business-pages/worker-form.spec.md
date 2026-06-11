# 新增工人页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/business-pages/worker-form.png`
- Canvas: `1024x2224px`
- Intended platform: mobile Flutter app, `430x932` logical px target

## Interface Mapping

- Save endpoint: `POST /planting/workers`
- Update endpoint: `PUT /planting/workers/{worker_id}`
- Fields: `name`, `phone`, `default_pay_type`, `default_unit_price`, `note`, `status`

## Layout

- Header: back button, centered title `新增工人`.
- Soft profile banner: avatar, `工人档案`, helper text.
- Form groups: basic info, default wage, tags/note.
- Bottom helper card: `保存后可在记工资时直接选择`.
- Sticky bottom action: `取消`, `保存工人`.

## Exact Bottom Tabs

- `首页`
- `记录`
- `芽芽`
- `账本`
- `我的`

## Implementation Invariants

- Use friendly worker avatar treatment.
- Keep form calm and legible.
- Avoid industrial dashboard styling.
