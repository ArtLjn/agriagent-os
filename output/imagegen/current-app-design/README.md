# 农场管家 App 当前设计归档

这个目录只放当前实施需要的 UI 图片。候选稿、旧总览和被丢弃版本已移到 `output/imagegen/archive/2026-06-08-current-app-design-candidates/`。

## 当前实现基线

### 品牌素材

- `brand/app-logo.png`：农场管家 App Logo，蓝绿叶片 + 数据节点 + 太阳，适合作为当前品牌图和 App 图标方向。

### 主 App 五个底部 Tab 页面

- `main-pages/home.png`：首页，当前确认为 AI 数据驾驶舱版本
- `main-pages/record.png`：记录/工作台，AI 帮填与手动免费路径并存
- `main-pages/yaya.png`：芽芽助手 Tab，极简聊天首页，留白更大，聚焦输入与少量快捷提示
- `main-pages/ledger.png`：账本，财务洞察仪表盘，不放智能填写
- `main-pages/profile.png`：我的，个人资料、农场资料与 AI 偏好设置

对应规格文档：`docs/ui/reference-style-flutter-spec.md`

### 登录注册与首次设置

- `auth/login.png`：登录页
- `auth/register.png`：注册页
- `auth/setup.png`：首次设置页

对应规格文档：`docs/ui/auth-reference-style-flutter-spec.md`

### 记录创建闭环

- `record-flow/ai-confirm.png`：AI 识别后的确认页
- `record-flow/manual-edit.png`：手动编辑/校正页
- `record-flow/save-success.png`：保存成功页

对应规格文档：`docs/ui/record-flow-flutter-spec.md`

### 芽芽助手专项

- `yaya/home-compact.png`：当前推荐的助手首页，和 `main-pages/yaya.png` 是同一版设计，来源为 `archive/2026-06-08-current-app-design-candidates/main-pages-v5/yaya-minimal-chat.png`
- `yaya/yaya-mascot-logo.png`：芽芽灵宠视觉
- `yaya/history-drawer.png`：左侧历史聊天抽屉，已按更强设计感的 AI 侧边栏风格打磨
- `yaya/skills.png`：全部技能页，已按极简聊天首页风格打磨
- `yaya/skills-banner.png`：全部技能页顶部 banner 独立资产，供 Flutter 直接作为图片使用

对应规格文档：`docs/ui/yaya-assistant-flutter-spec.md`

## 旧稿位置

旧探索稿统一放在 `output/imagegen/archive/`。后续讨论和 Flutter 实施默认只看本目录。

## Flutter 复刻原则

- 以 `390x844` 逻辑像素作为主要实现基准。
- 图片是视觉目标，不要求逐像素照抄背景噪点和生成瑕疵，但布局比例、字号层级、卡片圆角、主色和交互结构要稳定复刻。
- MVP 默认所有能力免费，但 UI 结构需要保留手动功能与 AI 功能两套路径。
