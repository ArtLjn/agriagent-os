# 田掌柜天气页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/farm-weather-page.png`
- Canvas: `1024x2224px`
- Intended platform: mobile app
- Logical viewport reference: `430x932px`

## Layout

- Status bar: top `0-48px`, white background, system status content only.
- App header: height `88px`, horizontal padding `24px`, left product logo/text, right notification bell with red badge.
- Scroll content: starts below header, page padding `20px`, vertical gap `16px`.
- Page title block: title `天气`, subtitle `未来7天天气与农事风险`.
- Current weather hero: full-width rounded card, about `390x220px` logical size, sky-blue gradient, farm landscape illustration on the right, current weather and metrics on the left/lower area.
- Hourly forecast strip: inside or immediately below hero, five equal columns for `10:00`, `12:00`, `14:00`, `16:00`, `18:00`.
- Seven-day trend card: white rounded card, section title `7日趋势`, five visible daily rows with icon, high/low temperature, precipitation probability, and short risk tag.
- Farm advice card: white rounded card, section title `农事提醒`, three compact rows.
- Bottom tab bar: fixed bottom height `86px`, five equal tabs: `首页`, `记录`, `芽芽`, `账本`, `我的`.

## Design Tokens

### Colors

- `--color-bg`: `#F7FAFC`
- `--color-surface`: `#FFFFFF`
- `--color-weather-surface`: `#EAF6FF`
- `--color-weather-surface-end`: `#F8FCFF`
- `--color-primary`: `#0877FF`
- `--color-green`: `#08B67A`
- `--color-warning`: `#FF7A1A`
- `--color-text`: `#111827`
- `--color-text-muted`: `#667085`
- `--color-border`: `#D9ECFF`
- `--color-divider`: `#E8EEF5`

### Typography

- Font family: `PingFang SC`, `SF Pro Display`, system sans-serif.
- Page title: `30px / 38px / 600`
- Hero temperature: `72px / 80px / 700`
- Section title: `22px / 30px / 600`
- Body: `18px / 26px / 500`
- Caption: `15px / 22px / 400`
- Bottom tab label: `12px / 16px / 600`

### Spacing And Shape

- Base grid: `8px`
- Page padding: `20px`
- Card padding: `20px`
- Hero card radius: `24px`
- Standard card radius: `20px`
- Inner chip radius: `16px`
- Section gap: `16px`
- Row divider inset: `16px`
- Minimum tap target: `44px`

## Components

- Header logo: left aligned, preserves existing `田掌柜` visual identity; do not introduce a new brand style.
- Notification button: `44x44px`, transparent, bell icon `24px`, red badge `18px`.
- Hero weather card: light sky gradient, subtle border `1px #D9ECFF`, soft shadow, right-side farm/weather illustration.
- Metric chips: small rounded tiles for `湿度 62%`, `东南风 2级`, `降雨 0mm`, using blue/green/orange icon accents.
- Hourly forecast cell: equal-width column, time label, weather icon, temperature; active/current hour uses pale blue fill.
- Daily forecast row: height `56-64px`, icon left, day/weather text center, temperature and precipitation/risk text right.
- Advice row: `56-64px`, pale green icon tile, title, short supporting text or status badge, chevron when navigable.
- Bottom tab item: icon above label; active state uses `#0877FF`, inactive state uses `#667085`.

## Exact Text

- `田掌柜`
- `天气`
- `未来7天天气与农事风险`
- `晴 28°C`
- `西瓜田 · 东大棚8424`
- `湿度 62%`
- `东南风 2级`
- `降雨 0mm`
- `逐小时预报`
- `7日趋势`
- `今天`
- `明天`
- `周三`
- `周四`
- `周五`
- `农事提醒`
- `适宜灌溉`
- `午后注意遮阳`
- `48小时无强降雨`
- `首页`
- `记录`
- `芽芽`
- `账本`
- `我的`

## Implementation Invariants

- The page is a real app screen, not a presentation mockup: no device frame, no floating background, no perspective.
- Keep the existing app visual language from the home screen: white base, soft blue cards, rounded surfaces, blue primary, green farm status accents, orange warning accents.
- Weather data must remain scannable: current condition first, hourly forecast second, daily forecast third, farm advice fourth.
- Bottom navigation labels and order must match the existing app.
- Do not hide critical forecast content behind decorative illustration; illustration stays secondary and should not occlude text.
- Cards should be implemented with fixed spacing and responsive width, not absolute pixel-only positioning.
- Loading state should reserve the same card heights to avoid layout shift.
- Empty/error state should show a compact inline message inside the forecast card, with retry action.
