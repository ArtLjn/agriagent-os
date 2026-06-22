# 田掌柜天气数据页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/farm-weather-data-page.png`
- Canvas: `1024x2224px`
- Intended platform: mobile app
- Logical viewport reference: `430x932px`

## Scope

- This is an independent weather subpage.
- The page only displays weather data from the backend weather API.
- Do not include farm operation suggestions, AI advice, overdue task reminders, business scores, work counts, or pending counts.

## Layout

- Status bar: top safe area, white background.
- Header: height `64-88px`, title `天气`, optional location or notification action on the right.
- Current weather summary: top content card, full width, soft blue-to-white gradient, large current temperature, condition, location, update time, small sun/cloud illustration.
- Metric grid: four compact data cards in a `2x2` grid or one horizontal grid on wider devices: apparent temperature, humidity, wind, rainfall.
- Hourly forecast: horizontal scroll section with equal forecast cells for `10时`, `12时`, `14时`, `16时`, `18时`, `20时`.
- Seven-day forecast: white rounded list card with seven rows, each row showing day, weather icon/condition, and high-low temperature.
- Weather detail: compact two-column cards for UV, air quality, pressure, and visibility.
- Bottom tab bar: fixed bottom height `86px`, five tabs: `首页`, `记录`, `芽芽`, `账本`, `我的`.

## Design Tokens

### Colors

- `--color-bg`: `#F7FAFC`
- `--color-surface`: `#FFFFFF`
- `--color-weather-surface`: `#EAF6FF`
- `--color-primary`: `#0877FF`
- `--color-primary-soft`: `#D9ECFF`
- `--color-green`: `#08B67A`
- `--color-warning`: `#FF7A1A`
- `--color-text`: `#111827`
- `--color-text-muted`: `#667085`
- `--color-divider`: `#E8EEF5`

### Typography

- Font family: `PingFang SC`, `SF Pro Display`, system sans-serif.
- Page title: `28px / 36px / 600`
- Current temperature: `76px / 84px / 700`
- Section title: `22px / 30px / 600`
- Body: `17px / 25px / 500`
- Caption: `14px / 20px / 400`
- Bottom tab label: `12px / 16px / 600`

### Spacing And Shape

- Base grid: `8px`
- Page padding: `20px`
- Card padding: `16-20px`
- Hero radius: `24px`
- Data card radius: `18-20px`
- Section gap: `16px`
- Row height: `52-60px`
- Minimum tap target: `44px`

## Components

- Header title: plain app page title, no marketing hero treatment.
- Current weather card: large `28°C`, condition `晴`, location `东大棚8424`, update text `10:38更新`.
- Metric card: small icon, muted label, bold value. Four required metrics: `体感 30°C`, `湿度 62%`, `风速 2级`, `降水 0mm`.
- Hourly forecast cell: time, weather icon, temperature, compact rounded surface.
- Seven-day row: day label, condition, temperature range, subtle divider.
- Weather detail card: label plus value, two columns, low visual weight.
- Bottom navigation: preserve the app's existing order and visual style.

## Exact Text

- `天气`
- `东大棚8424`
- `10:38更新`
- `晴`
- `28°C`
- `体感 30°C`
- `湿度 62%`
- `风速 2级`
- `降水 0mm`
- `24小时预报`
- `7日天气`
- `天气详情`
- `今天`
- `明天`
- `周三`
- `周四`
- `周五`
- `周六`
- `周日`
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

- Use the current App's main color system and general mobile style, but do not copy the home dashboard card structure.
- Weather data is the only content domain on this page.
- Do not add `AI分析`, `AI今日建议`, `农事提醒`, `作业`, `待处理`, `今日经营态势`, or score-style dashboard content.
- The current weather card must be visually prominent, but the rest of the page should stay data-dense and scannable.
- Forecast sections should support backend-driven arrays: hourly forecast and daily forecast lengths may vary.
- Reserve stable heights for loading states to avoid layout shift.
- Error state should stay inside the affected data section with a retry action.
