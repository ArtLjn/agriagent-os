# 田掌柜天气页 OPPO 风格打磨版 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/farm-weather-oppo-inspired.png`
- Canvas: `1024x2224px`
- Intended platform: mobile app
- Logical viewport reference: `430x932px`

## Design Direction

- Borrow the weather-first hierarchy from OPPO-style weather apps: immersive weather atmosphere, oversized temperature, translucent forecast cards, and clear multi-day forecast list.
- Keep the 田掌柜 app identity: bright blue primary color, restrained agriculture green accent, clean white surfaces, rounded mobile cards, existing bottom navigation style.
- This is not a copy of OPPO UI. It is an original weather data page adapted to the current app.

## Scope

- Display weather data only.
- Do not include farm operation suggestions, AI advice, overdue task reminders, business scores, work counts, pending counts, or home dashboard cards.

## Layout

- Status bar: top safe area.
- Header: height `88px`, left back arrow, title `天气`, right location selector `东大棚8424` and notification icon.
- Immersive hero: top `420-500px`, sky/weather gradient background, large current temperature, condition, high-low temperature, air quality, update time, and a small weather-status pill.
- Core metrics: translucent or white rounded card grid, four items: apparent temperature, humidity, wind, rainfall.
- Hourly forecast card: title `24小时预报`, horizontal forecast columns for now and five future times.
- Multi-day forecast card: title `多日天气预报`, segmented control `折线 / 列表`, list mode selected, seven daily rows.
- Weather details card: title `天气详情`, two-column compact metric cards.
- Bottom tab bar: fixed bottom height `86px`, labels `首页`, `记录`, `芽芽`, `账本`, `我的`.

## Design Tokens

### Colors

- `--color-bg-top`: `#DDF1FF`
- `--color-bg`: `#F7FAFC`
- `--color-surface`: `#FFFFFF`
- `--color-glass`: `rgba(255, 255, 255, 0.72)`
- `--color-primary`: `#0877FF`
- `--color-primary-soft`: `#D9ECFF`
- `--color-green`: `#08B67A`
- `--color-warning`: `#FF8A1F`
- `--color-text`: `#111827`
- `--color-text-muted`: `#667085`
- `--color-divider`: `#E8EEF5`

### Typography

- Font family: `PingFang SC`, `SF Pro Display`, system sans-serif.
- Header title: `28px / 36px / 600`
- Hero temperature: `112px / 116px / 700`
- Hero condition: `26px / 34px / 600`
- Section title: `22px / 30px / 600`
- Body: `17px / 25px / 500`
- Caption: `14px / 20px / 400`
- Bottom tab label: `12px / 16px / 600`

### Spacing And Shape

- Base grid: `8px`
- Page padding: `20px`
- Card padding: `18-22px`
- Large card radius: `24px`
- Small card radius: `18-20px`
- Inner chip radius: `18px`
- Section gap: `16px`
- Minimum tap target: `44px`

## Components

- Hero weather background: sky gradient with subtle sun/cloud weather illustration. It should carry atmosphere but must not reduce text readability.
- Weather status pill: compact rounded pill, e.g. `今日天气稳定`, using blue translucent fill.
- Metric card: icon, label, value. Required metrics: `体感 30°`, `湿度 62%`, `风速 2级`, `降水 0mm`.
- Hourly forecast column: time, weather icon, temperature. Required columns: `现在`, `12:00`, `14:00`, `16:00`, `18:00`, `20:00`.
- Multi-day forecast row: day label, weather condition/icon, temperature range.
- Segmented control: `折线` and `列表`; default selected state is `列表`.
- Detail metric card: compact label/value layout for UV, air quality, pressure, visibility.
- Bottom navigation: preserve current app order and icon-label composition.

## Exact Text

- `天气`
- `东大棚8424`
- `28°`
- `晴`
- `24° / 31° 空气优`
- `10:38更新`
- `今日天气稳定`
- `体感 30°`
- `湿度 62%`
- `风速 2级`
- `降水 0mm`
- `24小时预报`
- `现在`
- `12:00`
- `14:00`
- `16:00`
- `18:00`
- `20:00`
- `多日天气预报`
- `折线`
- `列表`
- `今天`
- `明天`
- `周三`
- `周四`
- `周五`
- `周六`
- `周日`
- `天气详情`
- `紫外线 强`
- `空气质量 优`
- `气压 1008hPa`
- `能见度 12km`
- `首页`
- `记录`
- `芽芽`
- `账本`
- `我的`

## Implementation Invariants

- The first screen must feel like a weather page, not a farm dashboard.
- The hero temperature is the primary visual anchor.
- Weather background is allowed only in the top hero area; lower sections should remain data-focused and readable.
- Do not add `AI分析`, `AI今日建议`, `农事提醒`, `作业`, `待处理`, `今日经营态势`, or score-style dashboard content.
- Do not include OPPO branding or copied proprietary icons.
- Forecast lists must be backend-driven and handle variable hourly/daily lengths.
- Loading states should preserve card heights to avoid layout shift.
- Error states should appear inside the affected section with a retry action.
