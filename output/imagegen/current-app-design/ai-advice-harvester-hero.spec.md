# AI 建议收割机 Hero 插画资产

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/ai-advice-harvester-hero.png`
- Canvas: `1536x1024px`
- Intended use: 首页建议详情页 hero card 右侧/背景插画

## Content

- 蓝白色收割机位于画面右中部。
- 背景包含浅绿色山丘、稻田、云朵和太阳。
- 前景包含成熟稻穗和绿色叶片。
- 无文字、无按钮、无卡片边框、无应用导航。

## Implementation Notes

- 该资产适合放在浅蓝或白色 hero card 中，建议使用 `BoxFit.cover` 或 `BoxFit.contain`。
- Flutter 中建议定位在 hero 卡片右侧，设置 `opacity: 0.78-0.92`，并用渐变 mask 让左侧文字区域保持可读。
- 图片背景是非常浅的透明感纹理，不是真 alpha 透明；如果后续需要叠在深色背景上，应另行做透明抠图版本。
- 推荐裁切区域：右侧 65% 用于展示收割机和稻穗；左侧可被渐变遮罩淡出。
