# Business Page Banner Assets

这些图片是业务页面 banner 中不适合用代码硬画的独立插画资产。Flutter 实现时建议用 `Image.asset` 叠放在 banner 右侧或背景角落，文字、渐变、卡片和统计信息仍由代码绘制。

## Assets

- `banner-ledger-illustration.png`
  - 用于：`ledger-manual-create`
  - 场景：手动记账 banner，账本、收据、金币、叶片元素。
- `banner-cycle-illustration.png`
  - 用于：`farm-cycle-list`、`farm-cycle-form`
  - 场景：茬口管理和新建茬口 banner，田垄、作物、日历元素。
- `banner-template-illustration.png`
  - 用于：`crop-template-list`、`crop-template-form`
  - 场景：作物模板 banner，模板册、幼苗、阶段点元素。
- `banner-worker-illustration.png`
  - 用于：`worker-list`、`worker-form`
  - 场景：工人管理 banner，工人帽、头像、工时/工资元素。

## Implementation Notes

- Banner 代码只负责容器、柔和渐变、文字和统计项。
- 插画建议放在右侧，宽度约 `120-160 logical px`，透明度 `0.9-1.0`。
- 小屏下可裁切插画右侧，但不要压住主文字。
- 不要在 Flutter 中重画这些复杂插画；只保留简单 Lucide 图标作为加载失败 fallback。
