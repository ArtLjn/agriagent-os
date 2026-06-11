# 农场管家记录页 Redesign V2 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/main-pages/record-redesign-v2.png`
- Canvas: `1024x2224px`
- Intended platform: mobile Flutter app, `430x932` logical px target

## Layout

- Page: white-to-`#F7FAFC` vertical app background, no device frame.
- Safe content: horizontal padding `20px`, bottom nav height `82px`.
- Header: height `54px`, logo `40x40`, title left aligned, history icon `32x32`.
- Primary action grid: two columns, gap `14px`, each card `186x188`, radius `20`.
- Voice input: full width `390x64`, margin top `16`, radius `18`.
- Quick record grid: 3 columns x 2 rows, tile `116x116`, gap `12`, card radius `18`.
- AI confirmation card: full width, radius `20`, padding `18`, rows for content, amount, supplier, then two buttons.
- Bottom nav: fixed `82px`, five equal tabs.

## Design Tokens

### Colors

- `--color-bg`: `#F7FAFC`
- `--color-surface`: `#FFFFFF`
- `--color-primary`: `#1677FF`
- `--color-primary-dark`: `#0D63E8`
- `--color-green`: `#12B76A`
- `--color-text`: `#101828`
- `--color-muted`: `#667085`
- `--color-border`: `#E6EDF5`
- `--color-purple`: `#7C5CFF`
- `--color-amber`: `#FF9F1C`

### Typography

- Font family: platform Chinese sans-serif.
- Page title: `28px / 36px / 800`
- Action title: `24px / 32px / 800`
- Section title: `18px / 26px / 800`
- Body: `15px / 22px / 500`
- Caption: `13px / 18px / 500`

### Shape And Effects

- Card radius: `18-20px`
- Button radius: `18px` or pill for primary action.
- Borders: `1px #E6EDF5`
- Shadows: subtle only, `0 8 24 rgba(16, 24, 40, 0.06)`

## Components

- Header logo: generated farm brand mark, `40x40`.
- AI primary card: blue gradient, white text, subtle waveform, small assistant/microphone illustration. CTA pill at bottom.
- Manual primary card: soft green background, green title, notebook-pencil illustration. CTA green pill at bottom.
- Voice input: mic icon left, placeholder text center-left, waveform icon right.
- Quick tile: icon `38-44px`, title `18px`, subtitle `13px muted`.
- AI confirmation: sparkle icon, `待确认` status pill, three detail rows, secondary outline button and primary blue button.
- Bottom nav: five tabs, active tab blue icon, label, and underline.

## Exact Text

- `农场管家`
- `AI帮我填`
- `说一句，自动整理成记录`
- `开始说话`
- `自己填`
- `手动记录，快速便捷`
- `立即记录`
- `例如：今天买饲料 3680 元`
- `记账`
- `记录收支明细`
- `记农事`
- `记录农事活动`
- `记工资`
- `记录工资发放`
- `建批次`
- `创建生产批次`
- `新增工人`
- `添加工人信息`
- `建模板`
- `创建记录模板`
- `AI待确认`
- `待确认`
- `内容`
- `饲料采购`
- `金额`
- `¥3,680`
- `供应商`
- `XX饲料厂`
- `改一下`
- `保存`
- `首页`
- `记录`
- `芽芽`
- `账本`
- `我的`

## Implementation Invariants

- Keep the first screen useful: primary action cards, voice input, quick grid, and AI card top must all be visible above bottom nav on `375x812`.
- Do not use oversized 3D hero illustrations; use compact illustration accents only inside the two primary cards.
- Preserve all record actions and labels.
- Keep fallback Lucide icons for any generated image asset load failure.
