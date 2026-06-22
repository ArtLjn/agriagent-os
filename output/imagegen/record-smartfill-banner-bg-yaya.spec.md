# 芽芽智能填写 Banner 背景资产 Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/record-smartfill-banner-bg-yaya.png`
- Reference card crop: `/var/folders/m4/h3g6s45x76x_z_s_4x5wd0qc0000gn/T/codex-clipboard-ca07aca5-a1c9-42b6-9a03-df91c09feead.png`
- Mascot reference: `/Users/ljn/Documents/demo/explore/mobile-app/assets/images/yaya/mascot_logo.png`
- Canvas: `1536x768px`
- Intended use: Flutter `Image.asset` background layer inside the record page smart-fill card.

## Recommended Implementation Model

Use a hybrid implementation:

- Image asset:
  - decorative rounded-card background
  - pale blue/white glow
  - right-side 芽芽 mascot
  - subtle sparkles/highlights
- Flutter widgets:
  - all text
  - input field
  - recognition button
  - shortcut buttons
  - tap states, loading states, disabled states

Do not bake interactive controls into the image.

## Flutter Asset Placement

Recommended destination:

- `mobile-app/assets/images/record/smartfill_banner_bg_yaya.png`

Recommended asset constant:

- `AppAssets.recordSmartfillBannerBgYaya`

## Card Geometry

- Logical card width: fill available content width.
- Logical card height: `188-212px`.
- Border radius: `20px`.
- Clip behavior: clip image to the same radius.
- Background fit: `BoxFit.cover`.
- Overlay padding: `16px`.

## Overlay Content

- Eyebrow chip: `芽芽智能填写`
- Title: `今天要记什么？`
- Helper: `说一句，芽芽会整理成账目、农事或工资`
- Input placeholder: `例：买肥料300，老王工资200`
- Primary button: `识别`
- Secondary shortcuts:
  - `手动记一笔`
  - `记农事`
  - `记工资`

## Layout Notes

- Keep text and controls on the left and lower area.
- Keep mascot on the right as decorative identity.
- Avoid placing live text over the mascot face.
- Use a subtle white scrim if text contrast is weak on smaller devices.
- Use real Flutter border/shadow for card if the image edge is not sufficient.

## State Requirements

- Empty state: placeholder visible, `识别` enabled only if current flow allows empty submit handling.
- Typing state: text replaces placeholder.
- Loading state: `识别` button shows progress or changes to `识别中`.
- Error state: keep text, show snackbar or inline compact error; do not encode error in image.

## Invariants

- Do not include readable text in the background asset.
- Do not include fake input boxes or fake buttons in the background asset.
- Do not use `AppAssets.recordAiRobot` for this card.
- Use the same 芽芽 identity as the chat page.
