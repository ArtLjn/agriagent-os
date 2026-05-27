## Why

当前 FarmManager Mobile App 的视觉风格偏向传统管理工具（深青绿配色、密集信息布局），与产品定位"AI 农业助手"不匹配。用户反馈首页缺乏 AI 感，信息过载。通过引入轻 AI 设计语言，将首页从"待办列表"转变为"AI 晨间助手入口"，提升产品的智能感和易用性。

## What Changes

- **全局视觉升级**: 替换主色体系（深青绿 → 蓝紫绿三主色），统一低饱和背景、大圆角卡片、柔和阴影
- **首页重塑**: 
  - 天气卡片改为大渐变卡片（蓝紫渐变）
  - 农事建议改为情绪卡片（根据天气动态切换渐变背景：雾天/晴天/雨天/降温）
  - 快捷操作改为横向滑动卡片（替代 2×2 网格）
  - 添加 AI 小宠物浮动按钮（半透明、呼吸动效）
  - 标题文字使用渐变文字效果
- **BottomBar 改造**: 毛玻璃背景 + 胶囊选中态（蓝紫渐变背景 + 白色图标）
- **AI 聊天页升级**: 渐变背景、用户气泡蓝紫渐变、AI 卡片白底边框、顶部推荐问题胶囊
- **天气详情页新增**: 小时预报横向滚动、7 日趋势折线图、毛玻璃卡片
- **账本页轻财务风格**: 总资产卡片、收支卡片（绿/红）、分类标签、流水记录
- **设置页极简风格**: 白卡片、64px 高度、统一图标颜色
- **全局动效**: 卡片进入淡入+上移（0.45s）、AI 卡片呼吸浮动（上下 4px）、按钮点击缩放（0.96）

## Capabilities

### New Capabilities

- `ui-theme-system`: 全局主题系统升级，包括配色、圆角、阴影、字体规范
- `home-screen-redesign`: 首页 UI 重塑（天气卡片、农事建议卡片、快捷操作、AI 宠物）
- `bottom-bar-redesign`: 底部导航栏改造（毛玻璃、胶囊选中态）
- `ai-chat-ui-upgrade`: AI 聊天页视觉升级（渐变背景、胶囊推荐问题）
- `weather-detail-page`: 天气详情页新增（小时预报、7 日趋势图）
- `ledger-ui-redesign`: 账本页面轻财务风格改造
- `settings-ui-minimal`: 设置页极简风格改造
- `ui-animations`: 全局动效系统（进入动画、呼吸浮动、点击反馈）

### Modified Capabilities

- `agent-daily-advice`: 农事建议展示形式变更（从文本列表变为情绪卡片）

## Impact

- **FarmManagerMobile/src/theme/**: 主题系统全面替换
- **FarmManagerMobile/src/screens/home/**: HomeScreen 重写
- **FarmManagerMobile/src/navigation/**: MainTabNavigator 改造
- **FarmManagerMobile/src/screens/agent/**: AgentChatScreen 升级
- **FarmManagerMobile/src/screens/cost/**: 账本相关页面改造
- **FarmManagerMobile/src/screens/settings/**: SettingsScreen 简化
- **FarmManagerMobile/src/components/**: 新增 WeatherDetail 等组件
- **新增依赖**: `react-native-linear-gradient`、`react-native-chart-kit` 或 `victory-native`、`lottie-react-native`（AI 宠物动画）
- **后端影响**: 无（纯前端 UI 变更）
