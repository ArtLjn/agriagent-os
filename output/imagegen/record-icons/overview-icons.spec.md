# 记录页今日概览图标资产 Spec

## Source Images

- 今日已记: `/Users/ljn/Documents/demo/explore/output/imagegen/record-icons/overview-recorded-blue.png`
- 待确认: `/Users/ljn/Documents/demo/explore/output/imagegen/record-icons/overview-pending-orange.png`
- 工资待结: `/Users/ljn/Documents/demo/explore/output/imagegen/record-icons/overview-workers-green.png`
- 本周支出: `/Users/ljn/Documents/demo/explore/output/imagegen/record-icons/overview-wallet-purple.png`

## Intended Flutter Destination

Recommended directory:

- `mobile-app/assets/images/record/overview/`

Recommended final asset names:

- `overview_recorded_blue.png`
- `overview_pending_orange.png`
- `overview_workers_green.png`
- `overview_wallet_purple.png`

Recommended `AppAssets` constants:

- `recordOverviewRecordedBlue`
- `recordOverviewPendingOrange`
- `recordOverviewWorkersGreen`
- `recordOverviewWalletPurple`

## Usage

- Use these as decorative icon images inside the `今日概览` metric tiles.
- Render size: `42-52px` logical.
- Keep surrounding metric tile background, border, and text in Flutter code.
- Do not bake metric labels or values into image assets.

## Processing Notes

- Generated source files are high-resolution square PNGs.
- Before shipping in the app, export optimized `256x256` or `512x512` PNG versions.
- If transparent backgrounds are required, run a background removal pass or use the light background consistently inside a clipped icon badge.

## Metric Mapping

- `今日已记 3条` -> `overview_recorded_blue.png`
- `待确认 1条` -> `overview_pending_orange.png`
- `工资待结 2人` -> `overview_workers_green.png`
- `本周支出 ¥1,280` -> `overview_wallet_purple.png`
