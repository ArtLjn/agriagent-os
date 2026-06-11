# 记录页当前页打磨 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/main-pages/record-current-page-polish-colored-actions.png`
- Canvas: `1024x2224px`
- Intended platform: mobile Flutter app
- Screen state: record/workbench tab, text smart fill available, voice input not available

## Scope

- This is a polish of the current page, not a new page structure.
- Do not change the shared header logo, header title, history clock button, or bottom tab bar component.
- Only refine the content inside the record tab.

## Layout

- Keep the existing `ReferencePage` shell.
- Top area remains two cards:
  - `AI帮我填`: blue generated background asset, text-based smart fill, CTA `立即识别`.
  - `自己填`: mint generated background asset, CTA `立即记录`.
- The two top cards use image backgrounds only for visual depth. Flutter must still render the title, subtitle, and button text as real UI text.
- Card background assets:
  - Design source: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/main-pages/assets/record-ai-card-bg.png`
  - Flutter asset: `/Users/ljn/Documents/demo/explore/mobile-app/assets/images/record/ai_card_background.png`
  - Design source: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/main-pages/assets/record-manual-card-bg.png`
  - Flutter asset: `/Users/ljn/Documents/demo/explore/mobile-app/assets/images/record/manual_card_background.png`
- Keep one full-width input bar under the two cards:
  - Placeholder `输入一句话记录，芽芽会帮你整理`.
  - Use sparkle or keyboard icon, not microphone or waveform.
- Keep six workbench entries in a 3x2 grid:
  - `记账`, `记农事`, `记工资`, `建批次`, `新增工人`, `建模板`.
  - Entries should not be pure white cards.
  - Use soft tinted gradients, same-color borders, and icon badges for each entry.

## Interaction

- Tapping `立即识别` or submitting the input calls `RecordFlowController.parse(text)`.
- Empty input shows `先输入一句话记录`.
- While parsing, disable the input and show a small loading indicator.
- `自己填` opens the manual ledger create page.
- Six workbench entries continue navigating to their existing backend-backed business pages.

## Do Not Change

- Header logo asset and brand lockup.
- Header title text `农场管家`.
- Clock icon placement.
- Bottom tab bar layout, icons, labels, selected state, and navigation logic.
- Backend parse/confirm/save flow.

## Remove

- `开始说话`.
- Microphone icon and waveform icon on the record page.
- Any fake AI confirmation card.
- Any sample business data such as `XX饲料厂`, fixed money amounts, or mock pending records.
