# 关于田掌柜版本更新页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/about-version-update-page.png`
- Canvas: `1024x2224px`
- Intended platform: Flutter mobile app

## Layout

- Top app bar: safe-area below status bar, 52px height, left back icon, centered title `关于田掌柜`.
- Content padding: 20px horizontal, 8px top, 40px bottom.
- Hero card: full-width surface card with app mark, product name, subtitle, and current version status pill.
- Version card: grouped settings list with 64px rows and 1px dividers.
- Update dialog: centered modal, rounded corners, update title, version summary, changelog, optional force-update badge, and primary action.

## Design Tokens

### Colors

- `--color-bg`: `#F7FAFF`
- `--color-surface`: `#FFFFFF`
- `--color-primary`: `#2F80ED`
- `--color-success`: `#12A66A`
- `--color-danger`: `#FF3B30`
- `--color-text`: `#101828`
- `--color-text-muted`: `#667085`
- `--color-border`: `#E6EDF5`

### Typography

- Font family: system sans-serif.
- Page title: 20px, 700 weight.
- Product title: 24px, 800 weight.
- Row title: 16px, 700 weight.
- Body/caption: 14px, 400-500 weight.

### Spacing And Shape

- Base grid: 8px.
- Page padding: 20px.
- Card padding: 18-20px.
- Card radius: 20px for hero, 16px for grouped list.
- Row height: 64px.
- Icon badge: 36px rounded square.

## Components

- About entry row: main profile page only shows `关于田掌柜` and version status; it must not show `下载地址`.
- Version detection row: label `版本更新检测`, value `可更新` / `已是最新`; tapping refreshes check.
- Update summary row: label `更新说明`, value `更新至 v{latest_version}` when an update exists.
- Update dialog: shows `发现新版本`, version summary, changelog, and `立即更新`; download URL is never rendered as visible text.

## Exact Text

- `关于田掌柜`
- `田掌柜`
- `智能种植运营助手`
- `版本更新检测`
- `更新说明`
- `发现新版本`
- `更新至 v0.1.0`
- `立即更新`
- `稍后`

## Implementation Invariants

- Do not render the raw `download_url` anywhere in the app UI.
- Main profile page keeps version details collapsed into the single `关于田掌柜` row.
- About page performs the version check automatically and shows the update dialog when `hasVersionUpdate` is true.
- Do not present `force_update` as a forced update in the mobile app.
- The dialog may use the download URL internally in future, but visible labels must remain semantic.
