# 农场管家 Flutter 复刻规格

## 目标

以 `output/imagegen/current-app-design/main-pages/` 下 5 张标准手机图为视觉目标，在 Flutter 中复刻同一套移动端 UI。图片用于审美和布局参考，本文档是实现源，不允许只凭图片自由发挥。

## 参考图片

- 首页: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/main-pages/home.png`
- 记录: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/main-pages/record.png`
- 芽芽: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/main-pages/yaya.png`
- 账本: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/main-pages/ledger.png`
- 我的: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/main-pages/profile.png`

这些图是当前讨论确认后的设计归档，尺寸为 `1024 x 2224`，适合作为标准手机 UI 视觉目标。Flutter 视觉基准统一按 `390 x 844` 逻辑像素实现。

## 全局结构

- App 使用 5 个底部 Tab: `首页`, `记录`, `芽芽`, `账本`, `我的`。
- 现有 `工作台` 需要改名为 `记录`。
- 现有 `账单` 需要改名为 `账本`。
- 底部导航顺序固定: `首页`, `记录`, `芽芽`, `账本`, `我的`。
- 每页背景为浅灰，内容区为白色圆角卡片。
- 每页底部需要为导航预留 `96px` 空间。

## 全局设计 Token

### 颜色

- 背景: `#F7F9FC`
- 顶部背景/页面底色: `#FFFFFF` 到 `#F7F9FC` 的轻微纵向过渡，或者纯 `#F7F9FC`
- 卡片: `#FFFFFF`
- 主蓝: `#2F73F6`
- 主蓝深色: `#1F5FE8`
- 绿色: `#35C879`
- 橙色: `#FF9F1C`
- 紫色: `#7C5CFF`
- 红色: `#FF3B30`
- 正文: `#111827`
- 次级文字: `#6B7280`
- 弱文字: `#8B95A5`
- 边框: `#E8ECF2`
- 轻分割线: `#EEF2F6`
- 蓝色浅底: `#EEF4FF`
- 绿色浅底: `#EAF9F0`
- 橙色浅底: `#FFF4E5`
- 紫色浅底: `#F1EDFF`

### 字体

- 字体: Flutter system font / `PingFang SC` 风格。
- 页面标题: `22px`, `FontWeight.w800`, line height `28px`, color `#111827`。
- 日期/二级标题: `18px`, `FontWeight.w800`, line height `26px`。
- 卡片标题: `16px`, `FontWeight.w800`, line height `22px`。
- 列表主文字: `15px`, `FontWeight.w600`, line height `22px`。
- 正文: `14px`, `FontWeight.w500`, line height `21px`。
- 辅助文字: `12px`, `FontWeight.w500`, line height `16px`。
- 底部 Tab 文案: `11px`, `FontWeight.w600`, selected `FontWeight.w800`。
- 数字指标: `28-34px`, `FontWeight.w800`。

### 间距与形状

- 页面横向 padding: `20px`。
- 页面顶部内容起点: SafeArea 后 `20px`。
- 卡片圆角: `16px`，大卡片可用 `18px`。
- 卡片内边距: `16px`。
- 卡片间距: `14px`。
- 列表行高度: `54-64px`。
- 图标容器: `36-42px` 方形，圆角 `10-12px`。
- 底部导航高度: `76px`，包含 icon 和 label。
- 底部导航背景: 白色，顶部 `#EEF2F6` 分割线，不做悬浮胶囊。
- 卡片阴影: `Color(0x08000000)`, blur `16`, offset `(0, 6)`。

## 公共组件

### App Page

每个页面使用同一结构:

- `SafeArea`
- `SingleChildScrollView`
- `Padding(horizontal: 20)`
- 顶部 Header
- 若干 `ReferenceCard`
- 底部 padding `112`

### Header

字段:

- 左侧标题固定为 `农场管家`。
- 右侧根据页面放图标:
  - 首页: bell，红色角标 `3`
  - 记录: clock
  - 芽芽: more horizontal
  - 账本: calendar
  - 我的: settings 可选，参考图中顶部只保留标题也可

尺寸:

- Header 高度约 `52px`。
- 标题 `22px w800`。
- 右侧 icon `24px`，触达区域 `44px`。

### ReferenceCard

基于现有 `CardPanel` 修改:

- 默认圆角改为 `16`。
- 默认边框 `#EEF2F6`。
- 默认 shadow blur 提高到 `16`，透明度仍轻。
- 默认 padding `16`。

### Bottom Tab Bar

需要从当前悬浮胶囊改成参考图样式:

- 固定贴底，宽度撑满。
- 高度 `76px`。
- 背景白色。
- 顶部有 `#EEF2F6` 分割线。
- 每个 tab 平分宽度。
- icon `24px`。
- label `11px`。
- selected 使用主蓝 `#2F73F6`。
- unselected 使用 `#667085`。
- tabs:
  - `首页`: `home`
  - `记录`: `clipboard/list`
  - `芽芽`: `bot`
  - `账本`: `receipt/yen`
  - `我的`: `user`

## 页面规格

### 首页

目标: 首页作为 AI 增强数据驾驶舱，集中展示经营态势、AI 今日建议、资金/成本/茬口/风险洞察。不要依赖 MVP 尚未实现的 `今日待办` 和 `最近记录` 接口。

组件顺序:

1. Header: `农场管家` + bell badge `3`
2. Hero cockpit card:
   - 标题 `今日经营态势`
   - badge `AI分析`
   - 大数字评分 `86`
   - 状态文案 `经营稳定，注意午后天气`
   - 三列小指标: `收入趋势 +12%`, `成本压力 中`, `风险 1项`
   - 可包含轻量农场/数据插画，但不能做成土味农业背景，也不能压过数据层级
3. AI suggestion card:
   - 标题 `AI 今日建议`
   - 三条建议:
     - `午后避开露天作业`
     - `西瓜批次补充灌溉`
     - `本月饲料成本偏高`
   - 每条建议包含图标、主文案、短说明、右侧 chevron
4. Insight grid:
   - `资金概览`: `余额 12.8万` + sparkline
   - `成本分析`: `本月 +8%` + donut/progress
   - `茬口进度`: `已完成 68%` + progress bar
   - `风险预警`: `1项待关注` + 状态点
5. Quick action strip:
   - `问问芽芽` / `AI 农业助手`
   - `记一笔` / `快速记账`
   - `生成报告` / `经营分析报告`

首页禁用项:

- 不出现 `今日待办` 模块。
- 不出现 `最近记录` 模块。
- 不做密集列表、表格或旧后台风统计面板。

### 记录

目标: 手动记录和 AI 帮填共存。智能填写只放在这里。

组件顺序:

1. Header: `农场管家`
2. Two large action cards:
   - 左: `AI帮我填`, `智能识别，自动生成`, 蓝色背景
   - 右: `自己填`, `手动记录，快速便捷`, 绿色背景
   - 每张高度约 `118px`
3. Input card:
   - 左 microphone icon
   - placeholder `说一句，我帮你填好`
   - 右 chevron 或 wave icon
4. Manual quick card:
   - 标题 `手动快捷记录`
   - 2 行 3 列入口:
     - `记账`
     - `记农事`
     - `记工资`
     - `建批次`
     - `新增工人`
     - `建模板`
5. AI generated card:
   - 标题行: `AI 生成的记录`, badge `待确认`
   - 主标题: `5月18日 饲料采购单`
   - 明细:
     - `供应商：XX饲料厂`
     - `金额：¥3,680.00`
   - 底部两个按钮:
     - `改一下` outline
     - `保存` primary blue

### 芽芽

目标: 问答、建议、报告，不作为主写入页。

组件顺序:

1. Header: right more icon
2. Assistant identity:
   - robot avatar
   - `芽芽 AI助手`
   - online dot `在线`
3. Assistant greeting bubble:
   - `你好呀！我是芽芽，你的农场智能助手 🌱 有什么可以帮你的吗？`
4. User bubble:
   - `今天适合干什么`
5. Assistant answer bubble:
   - `今天多云转雷阵雨，22~29°C，东南风2级，午后有雷阵雨，建议你：`
   - bullet list:
     - `上午进行饲料采购和室内工作`
     - `下午注意防雨，关注牛舍通风`
     - `记得确认工人出勤哦 🙂`
6. Prompt chips:
   - `今天适合干什么`
   - `本月成本怎么看`
   - `生成周报`
7. Composer:
   - placeholder `请输入你的问题...`
   - left mic icon
   - right send button

### 账本

目标: 查看资金、交易、应收/欠款。这里不放 `AI帮我填`。

组件顺序:

1. Header: `农场管家` + calendar icon
2. Money summary card:
   - 标题 `资金概览`
   - 右侧 `本月`
   - 三列:
     - `收入(元)` `28,650`
     - `支出(元)` `18,240`
     - `欠款(元)` `6,410`
3. Recent transaction card:
   - 标题 `最近交易`
   - 右侧 `全部`
   - 四行:
     - `饲料采购` `5月18日 10:25` `-3,680.00`
     - `牛只销售` `5月17日 14:30` `+12,800.00`
     - `人工工资` `5月17日 10:10` `-5,760.00`
     - `水电费` `5月16日 16:45` `-680.00`
4. Reminder card:
   - `应收/欠款提醒`
   - `待收款 ¥6,800.00`
   - `待付款 ¥4,210.00`
5. Primary button:
   - `手动记一笔`

### 我的

目标: 个人和农场设置。

组件顺序:

1. Header: `农场管家`
2. Profile card:
   - avatar
   - `张三`
   - `农场负责人`
   - chevron
3. Location/weather card:
   - `所在位置` `广东省清远市`
   - `默认天气` `清远市`
4. Settings card:
   - `AI 偏好设置`
   - `数据备份`
   - `消息通知` `已开启`
   - `关于我们` `版本 1.2.0`
5. Logout button:
   - outline red `退出登录`

## 实现步骤建议

1. 先改全局 `AppColors` 和 `AppTextStyles`，建立参考图 token。
2. 改 `AppBottomTabBar` 为贴底白色导航，并把 `工作台/账单` 改成 `记录/账本`。
3. 调整 `CardPanel` 默认圆角、边框、阴影。
4. 按页面逐个替换当前 mock UI。
5. 运行 Flutter 截图，对照 5 张参考裁图微调。

## 验证要求

- 截图宽度以 `390px` 逻辑宽为基准。
- 每页内容和参考图模块顺序一致。
- `记录` 页必须包含 `AI帮我填` 和 `自己填`。
- `账本` 页不得出现 `AI帮我填` 或智能填写入口。
- 底部导航文案必须是 `首页 / 记录 / 芽芽 / 账本 / 我的`。
- 页面不要出现技术字段、API 字段、后台管理语气。
