# 芽芽助手 Flutter 规格

## 目标

将 `芽芽` 从普通聊天页打磨为主流 AI 助手体验：助手首页、历史聊天侧边栏、全部技能页。

## 参考图

- 助手首页: `/Users/ljn/Documents/demo/explore/output/imagegen/yaya-v3/home.png`
- 助手首页 v4: `/Users/ljn/Documents/demo/explore/output/imagegen/yaya-v4/home-compact.png`
- 芽芽灵宠: `/Users/ljn/Documents/demo/explore/output/imagegen/yaya-v4/yaya-mascot-logo.png`
- 历史侧边栏: `/Users/ljn/Documents/demo/explore/output/imagegen/yaya-v3/history-drawer.png`
- 全部技能: `/Users/ljn/Documents/demo/explore/output/imagegen/yaya-v3/skills.png`

图片为 `1024x2224` 标准移动端比例，Flutter 实现基准按 `390x844` 逻辑像素。

`yaya-v4/home-compact.png` 是助手首页推荐实现目标。`yaya-v4/home.png` 和 `yaya-v3/home.png` 仅作历史参考。

## 助手首页

### 布局

- 顶部:
  - 左侧三横菜单，打开历史侧边栏。
  - 中间小型品牌: `农场管家` + 芽芽灵宠标识。
  - 右侧静音/语音开关与新建对话入口。
- 主体:
  - 使用专属 `芽芽灵宠`，不要通用机器人。
  - 灵宠宽度控制在约 `110-140px`，不能占据中屏主体空间。
  - Greeting: `周末愉快，我是芽芽`
  - Subtitle: `点击查看你的今日简报`
- 推荐问题:
  - `今天适合干什么`
  - `本月成本怎么看`
  - `查欠款风险`
  - 使用三条紧凑白色胶囊/小卡，不使用 2x2 大卡片网格。
  - 下方提供 `换一换`。
- 能力 chips:
  - `深度思考`
  - `经营分析`
  - `生成报告`
  - `全部技能`
- 底部输入:
  - Placeholder: `发消息或按住说话...`
  - 左侧助手图标
  - 语音按钮
  - 加号按钮

### 约束

- 助手页不是主写入页，不展示复杂写入表单。
- 可出现“转为记录”动作，但不能抢占 `记录` 页的主职责。
- 快捷提示词区域不能占据中屏大面积，首页重点是轻量问候、少量提示词和底部输入。
- 中屏需要保留明显空白，不要放大简报卡或大块业务卡片。
- 灵宠必须贴合系统主题: 智能、温和、记录/经营助手，不要普通机器人或农田吉祥物。

## 历史侧边栏

### 触发

- 点击左上角三横图标打开。

### 布局

- Drawer 占屏幕宽度约 `78%`。
- 右侧显示 dim overlay，背后主页面轻微变暗。
- 顶部:
  - 三横图标
  - 搜索
  - 新建对话
- 技能入口:
  - `全部技能`
- 对话列表:
  - Section `今天`
  - Section `7天内`
  - Section `30天内`
- 示例标题:
  - `今天适合干什么`
  - `本月成本怎么看`
  - `春茬西瓜授粉安排`
  - `人工工资怎么结`
  - `欠款风险提醒`
  - `生成5月周报`
  - `饲料采购记录确认`
- 底部账号:
  - `张三`
  - 设置齿轮

## 全部技能页

### 布局

- 顶部:
  - 返回按钮
  - Title: `全部技能`
- Search:
  - `搜索技能`
- Banner:
  - `芽芽能帮你做什么`
- Category chips:
  - `推荐`
  - `记录`
  - `经营`
  - `生产`
  - `设置`
- 技能列表:
  - `今日简报` `查看今天待办与风险`
  - `智能记账` `一句话生成账本记录`
  - `农事记录` `记录作业与备注`
  - `工资结算` `生成工人工资记录`
  - `批次管理` `创建和更新种植批次`
  - `成本分析` `看本月收支变化`
  - `生成报告` `自动生成经营周报`
  - `天气提醒` `查看天气和风险`

## 设计 Token

- 背景: `#F7F9FC`
- 卡片: `#FFFFFF`
- 主蓝: `#2F73F6`
- 绿色: `#35C879`
- 橙色: `#FF9F1C`
- 紫色: `#7C5CFF`
- 正文: `#111827`
- 次级文字: `#6B7280`
- 边框: `#E8ECF2`
- 输入框背景: `#FFFFFF`
- Chip 背景: `#EEF2F6`

## 实现建议

- `YayaScreen`: 助手首页与聊天输入。
- `YayaHistoryDrawer`: 侧边历史抽屉。
- `YayaSkillsScreen`: 全部技能页。
- 左上三横图标打开 drawer。
- `全部技能` chip 或 drawer 技能入口进入 `YayaSkillsScreen`。

## 验证要求

- 首页、历史抽屉、技能页都需要 mobile MCP 截图。
- 历史抽屉打开时右侧要有 dim overlay。
- 助手首页底部输入框不能被安全区遮挡。
- 不要把 `芽芽` 页面做成第二个 `记录` 页面。
