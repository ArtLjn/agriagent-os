# AI First 填写页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/farm-app-ai-first-entry.png`
- Canvas: `1024x2224px`
- Intended platform: mobile app screen
- Product direction: AI-first natural-language record entry for low-complexity farm users.

## Product Principle

用户不需要先理解 `茬口`、`作物模板`、`工人工资`、`账务记录` 等系统对象。用户只说一句现实语言，AI 负责判断口径、抽取字段并生成确认卡。

## Layout

- Top app bar: title `填写`, subtitle `说一句，我帮你记好`.
- Main input hero card:
  - Placeholder: `例如：今天老王给西瓜授粉，工钱200，先付100`
  - Input modes: `说话`、`打字`、`拍照`
- Quick intent chips:
  - `记账`
  - `记农事`
  - `记工资`
  - `建批次`
  - `新增工人`
  - `建模板`
- AI recognition preview card:
  - Title: `我理解为：农事 + 工资`
  - Rows: `作业 授粉`, `批次 春茬西瓜`, `工人 老王`, `应付 200元`, `已付 100元`, `待付 100元`
  - Actions: `改一下`, `保存`
- Recent pending section:
  - `复合肥 128.5元`
  - `8424西瓜建批次`
- Bottom navigation:
  - `首页`, `填写`, `芽芽`, `账本`, `我的`
  - `填写` selected.

## Design Tokens

### Colors

- `--color-bg`: `#F8F9FB`
- `--color-surface`: `#FFFFFF`
- `--color-primary`: `#3478F6`
- `--color-primary-soft`: `#EEF4FF`
- `--color-text`: `#111827`
- `--color-muted`: `#6B7280`
- `--color-border`: `#E5E7EB`
- `--color-warning`: `#F59E0B`
- `--color-success`: `#16A36A`

### Typography

- Font family: `PingFang SC`, `Inter`, system sans-serif
- Page title: `24px / 32px / 800`
- Section title: `16px / 24px / 700`
- Body: `14px / 22px / 500`
- Caption: `12px / 18px / 500`

### Spacing And Shape

- Base grid: `8px`
- Page padding: `16px`
- Main card padding: `20px`
- Secondary card padding: `16px`
- Card radius: `22px`
- Minimum tap target: `48px`

## Implementation Invariants

- This page replaces the old function-grid workbench as the primary creation surface.
- Do not expose technical fields such as `record_type`, `source_type`, `source_id`, or API concepts.
- Confirmation cards should use natural-language labels and human-readable values.
- Keep the visual style warm, simple, and consumer-product-like.
- Avoid old admin dashboard, dense forms, dark industrial panels, rustic agricultural visuals, and heavy green palette.
- All create flows should eventually be represented as variants of the same AI recognition and confirmation pattern.
