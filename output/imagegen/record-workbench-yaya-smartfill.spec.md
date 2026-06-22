# 记录页芽芽智能填写 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/record-workbench-yaya-smartfill.png`
- Base layout draft: `/Users/ljn/Documents/demo/explore/output/imagegen/record-workbench-redesign-refined.png`
- Mascot reference: `/Users/ljn/Documents/demo/explore/mobile-app/assets/images/yaya/mascot_logo.png`
- Canvas: `1024x2224px`
- Intended platform: mobile

## Scope

- 仅打磨记录页顶部智能填写模块。
- Header 和底部 tab bar 不改。
- 周报/月报、今日概览、常用工具的结构沿用优化版。

## Design Direction

- 智能填写应被表达为 `芽芽` 的场景能力，而不是一个独立的泛 AI 机器人。
- 记录页和聊天页使用同一个 AI 形象：`AppAssets.yayaMascotLogo`。
- 旧资产 `AppAssets.recordAiRobot` 不再用于记录页智能填写卡。
- 卡片应像真实可用的输入组件，不像营销 banner。

## Smart Fill Card Layout

- Card position: first content module under the existing header.
- Card surface: white, subtle border, soft shadow, radius `20px`.
- Card padding: `16px`.
- Mascot:
  - Use `AppAssets.yayaMascotLogo`.
  - Place near top-right.
  - Render size `56-64px`.
  - The mascot is an identity badge, not a large background illustration.
- Label: `芽芽智能填写`, placed near title area as a small blue/green chip or compact eyebrow.
- Main title: `今天要记什么？`
- Helper: `说一句，芽芽会整理成账目、农事或工资`
- Input row:
  - Rounded input field, height `48-52px`.
  - Placeholder: `例：买肥料300，老王工资200`
  - Primary action button: `识别`, blue fill, sparkle icon, height matches input row.
- Shortcut row:
  - Three secondary pill buttons: `手动记一笔`, `记农事`, `记工资`.
  - White fill or very light tint, subtle border.
  - Do not compete visually with the `识别` button.

## Exact Text

- `芽芽智能填写`
- `今天要记什么？`
- `说一句，芽芽会整理成账目、农事或工资`
- `例：买肥料300，老王工资200`
- `识别`
- `手动记一笔`
- `记农事`
- `记工资`

## Implementation Notes

- Flutter asset to use: `AppAssets.yayaMascotLogo`.
- Avoid using: `AppAssets.recordAiRobot`.
- The `识别` button submits the text input to the existing smart-fill parse flow.
- `手动记一笔` navigates to manual ledger entry.
- `记农事` navigates to farm log creation.
- `记工资` navigates to wage creation.
- Keep tap targets at least `44px`.
- On narrow screens, keep title and helper text left aligned; mascot may slightly overlap the top-right whitespace but must not cover text.

## Invariants

- Do not reintroduce `AI帮我填` and `自己填` large cards.
- Do not create a separate AI brand for record filling.
- Header and tab bar remain unchanged.
- Weekly/monthly report shortcuts remain visible in the first screen.
