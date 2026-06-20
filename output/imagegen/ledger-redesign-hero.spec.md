# 账本页面 UI 提升 — 方向 A · Apple Weather 极简

## 视觉产物

- 高保真 HTML 渲染：`output/imagegen/ledger-redesign-hero.html`（浏览器打开即可看 1:1 效果）
- Canvas：`430 x 932`（iPhone 14 Pro Max logical），可截图复用
- 目标平台：Flutter mobile app，`mobile-app/lib/features/billing/`
- 设计基调：Apple Weather + Linear calm-tech，对齐 `.claude/rules/app-ui.md`

> imagegen 通道：本次 AISpeech gateway 对 1024x2224 / 1024x1536 复杂 UI mockup 持续 502（简单 prompt 可过，复杂 UI 必失败），故改用 HTML 渲染作为视觉真相源。HTML 在浏览器打开即可看到 1:1 还原，且代码可直接复制到 Flutter。

---

## 当前页面问题诊断

| # | 问题 | 现状证据 | 视觉后果 |
|---|------|---------|---------|
| 1 | **缺焦点** | 年度净收益 `-¥12万` 与三个指标平铺，视觉权重相当 | 用户进来抓不到核心信号 |
| 2 | **卡片堆叠松散** | 资金概览卡 + AI 财务洞察卡 + 最近交易卡 三层独立卡 | 呼吸节奏混乱，像 demo |
| 3 | **数据平铺** | 收入/支出/欠款做成 3 个小卡片，每个独立 | 像报表，不像产品 |
| 4 | **交易列表信息密度低** | 每行只有"标题 + 日期 + 金额"，没有图标差异化 | 视觉单调，扫读疲劳 |
| 5 | **AI 卡视觉权重过大** | "智能复盘" 与"AI 财务洞察" 两个标题 + 一段文字，与资金概览抢戏 | 焦点模糊 |
| 6 | **缺少场景氛围** | 纯灰白卡片，没有 calm-tech 的呼吸感 | 像 admin 后台 |

---

## 重设计核心动作

1. **Hero 化净收益**：单一巨号 `-¥12万`（56px），配月度趋势 sparkline，赤字用克制暖红 `#E5484D`（不是亮红）
2. **三指标去卡片化**：去掉独立卡片，改为细分割线分隔的横向 strip，标签小、数字大
3. **AI 洞察弱化**：去掉第二个标题，用 soft blue gradient surface + 单标题"智能复盘" + 副标签 "AI 财务洞察"
4. **交易列表合并单卡**：3 条交易放进同一个白卡，行间用 1px hairline 分隔，左侧加语义化圆形图标
5. **底部 tab 强 active 态**：active tab 用品牌色填充图标，非 active 用 outline

---

## Layout（自顶向下）

| 区域 | 高度 | 关键说明 |
|------|------|---------|
| iOS status bar | 44px | 9:41 + signal/wifi/battery |
| App header | 60px | 左：「账本」28px bold；右：`本年 ▾` 筛选 pill + 历史按钮 |
| Hero 净收益卡 | ~340px | 白底 24px radius，shadow `0 4px 16px rgba(0,0,0,0.04)`，padding 28px |
| └ caption | 13px | "年度净收益" + 右侧 "FY 2026" 小标签 |
| └ 巨号 | 56px bold | `-¥12万` 颜色 `#E5484D` |
| └ 副标题 | 13px | "本年支出结构与待收款状态" |
| └ sparkline | 64px | 月度净收益趋势，红线 + soft red gradient fill |
| 三指标 strip | ~96px | 去卡片，1px 垂直分隔线 |
| AI 洞察卡 | ~130px | soft blue gradient + 1px border `#DCE7FF` + 20px radius |
| Section header | 56px | "最近交易" + "查看全部 >" |
| 交易列表卡 | ~260px | 单白卡 20px radius，3 行 × 72px，1px hairline 分隔 |
| 底部 tab bar | 84px | 5 tabs，账本 active 蓝 |

---

## Design Tokens

### Colors

```text
--bg:               #F7F8FA   /* 页面背景 */
--surface:          #FFFFFF   /* 卡片表面 */
--accent-surface:   linear-gradient(135deg, #EEF4FF 0%, #F5F9FF 100%)
--primary:          #4F8CFF   /* 品牌蓝，仅用于 active 态与主 CTA */
--deficit:          #E5484D   /* 赤字/支出，克制暖红，禁用亮红 */
--soft-red:         #FEEBEC   /* 工资/支出图标背景 */
--soft-orange:      #FEF3E0   /* 人工图标背景 */
--soft-green:       #EAF7F1   /* 收入图标背景（预留） */
--income:           #16A34A   /* 收入正向（预留） */
--text-1:           #1A1D24   /* 主文本 */
--text-2:           #6B7280   /* 次文本 */
--text-3:           #9AA1AB   /* 弱文本/标签 */
--divider:          #EFF1F4   /* 区域分隔线 */
--hairline:         #F3F4F6   /* 卡内行分隔 */
```

### Typography

```text
Font:              Inter + Noto Sans SC（系统 fallback: SF Pro Display / PingFang SC）
Hero number:       56px / 1.05 / 700 / tabular-nums / tracking-tight
Section title:     17px / 1.3 / 600
Body:              15px / 1.45 / 400
Caption:           13px / 1.4 / 500
Tiny label:        12px / 1.3 / 400
Tab label:         11px / 1.2 / 500-600
```

### Spacing & Shape

```text
Base grid:         8px
Page padding:      20px
Hero card padding: 28px
Inner card pad:    20px
List card pad:     16px (内边) / 14px (行)
Section gap:       24px (header → first card)
Card gap:          16px
Card radius:       20-24px (大卡) / 12px (小图标 tile)
Pill radius:       999px
Shadow (hero):     0 4px 16px rgba(15, 23, 42, 0.04)
Touch target:      44×44 min
```

---

## Components

### `NetIncomeHeroCard`
- 容器：白底，24px radius，padding 28px，hero-shadow
- 子元素：caption 行 + 巨号 + 副标题 + sparkline
- sparkline 用 SVG path，stroke `#E5484D` 1.6px，fill linear-gradient 18% → 0% opacity
- 末端数据点：白底 + 红 stroke 圆点 r=3

### `MetricsStrip`
- 三等分 grid，无卡片背景，仅 1px 垂直分隔线
- 每列：12px label + 20px semibold value
- 赤字列（支出）value 用 `--deficit`，其他用 `--text-1`

### `AiInsightCard`
- 背景：linear-gradient 135° `#EEF4FF → #F5F9FF`
- 边框：1px `#DCE7FF`
- 圆角：20px
- 头部行：28px 蓝色圆 icon（白 sparkle）+ "智能复盘" 16px semibold + 右侧"AI 财务洞察" 12px
- 正文：15px / line-height 22px / `#4B5563`

### `TransactionListCard`
- 单白卡，20px radius，padding 4px 16px
- 行高 72px，行间 1px hairline `#F3F4F6`
- 每行结构：40px 圆形语义图标 + (标题 + 副标题) + 右对齐金额
- 图标背景按交易类型：工资/支出 `--soft-red` + 红 glyph，人工 `--soft-orange` + 暖橙 glyph
- 金额一律赤字色（当前数据全为支出）

### `BottomTabBar`
- 84px 高，白底，顶部 1px `--divider`
- 5 tabs grid，icon 24px + label 11px
- active tab（账本）：填充图标 + `--primary` 色 + label 600 weight
- 非 active：outline 图标 + `--text-3` + label 500 weight
- iOS home indicator：120×5 px `--text-1` 圆角条

---

## 改造清单（按 mobile-app Flutter 落地）

> 优先级 P0 = 必须做，P1 = 强烈推荐，P2 = 可选

### P0 · 视觉层级修复

- [ ] **账本首页**：将 `年度净收益 -¥12万` 提为 hero card，字号 56px bold，颜色 `#E5484D`
  - 文件：`mobile-app/lib/features/billing/billing_screen.dart`
  - 当前是平铺在概览卡中，需拆出独立 hero 区
- [ ] **三指标去卡片化**：把 `收入 / 支出 / 欠款` 从 3 个独立小卡改为单一 strip + 1px 分隔线
- [ ] **AI 洞察卡**：删去副标题，只留主标题"智能复盘" + 副标签"AI 财务洞察"；背景换 soft blue gradient + 1px border

### P1 · 交易列表升级

- [ ] **合并单卡**：3+ 条交易合并到同一张白卡，行间 hairline 分隔
- [ ] **语义化图标**：按 `transaction.kind` 渲染左侧圆形图标：
  - 工资/日常支出 → `--soft-red` + 工资 glyph
  - 人工 → `--soft-orange` + 人工 glyph
  - 收入类（预留）→ `--soft-green` + 收入 glyph
- [ ] **金额排版**：用 tabular-nums，金额右对齐

### P1 · 配色规范统一

- [ ] **全局**：禁用 `#FF3B30`（iOS 系统红）做赤字，统一改 `#E5484D`（克制暖红）
- [ ] **全局**：禁用强渐变蓝/紫；AI 相关 surface 用 soft blue gradient (`#EEF4FF → #F5F9FF`)
- [ ] **全局**：阴影统一 `0 4px 16px rgba(15, 23, 42, 0.04)`，禁用 `BoxShadow blurRadius > 24`

### P2 · 趋势可视化

- [ ] **Hero sparkline**：在 hero card 底部加月度净收益 sparkline（用 `fl_chart` 或自定义 `CustomPainter`）
  - 数据源：按月聚合 `transactions`，y = `income - expense`
  - 末端点用白色 fill + 红 stroke，突出"当前"
- [ ] **筛选 pill**：顶部 `本年 ▾` 加 dropdown，支持 `本月 / 本季 / 本年` 切换

---

## Flutter 实现要点

```dart
// 1. Hero card
Container(
  padding: const EdgeInsets.all(28),
  decoration: BoxDecoration(
    color: Colors.white,
    borderRadius: BorderRadius.circular(24),
    boxShadow: [BoxShadow(
      color: const Color(0x0A0F172A),  // rgba(15,23,42,0.04)
      blurRadius: 16,
      offset: const Offset(0, 4),
    )],
  ),
  child: Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text('年度净收益', style: TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
      const SizedBox(height: 8),
      Text('-¥12万', style: TextStyle(
        fontSize: 56, fontWeight: FontWeight.w700,
        color: Color(0xFFE5484D),
        fontFeatures: const [FontFeature.tabularFigures()],
        letterSpacing: -0.5,
      )),
      // ... sparkline via CustomPainter
    ],
  ),
)
```

```dart
// 2. Metrics strip with dividers
Row(
  children: [
    _metricCell('收入', '¥5,500', Color(0xFF1A1D24)),
    Container(width: 1, height: 40, color: Color(0xFFEFF1F4)),
    _metricCell('支出', '¥12.6万', Color(0xFFE5484D)),
    Container(width: 1, height: 40, color: Color(0xFFEFF1F4)),
    _metricCell('欠款', '¥430', Color(0xFF1A1D24)),
  ].expand((w) => [Expanded(child: w)]).toList(),
)
```

```dart
// 3. AI insight gradient
Container(
  padding: const EdgeInsets.all(20),
  decoration: BoxDecoration(
    gradient: const LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFFEEF4FF), Color(0xFFF5F9FF)],
    ),
    borderRadius: BorderRadius.circular(20),
    border: Border.all(color: const Color(0xFFDCE7FF)),
  ),
  // ...
)
```

---

## Implementation Invariants（不要破坏）

- 保留测试可见文案：`资金概览`（或新的`年度净收益`，看测试用哪个）、`AI 财务洞察`、`最近交易`、`查看全部`、`工人工资`、`人工`
- 金额继续使用紧凑格式（万/亿）+ tabular figures
- 三个指标数据源不变，仅视觉重排
- 底部 tab 5 项顺序不变：`首页 / 记录 / 芽芽 / 账本 / 我的`
- 账本 tab active 态保持蓝色填充
- 不引入新图片资产；sparkline 用 SVG/CustomPainter 渲染
- 配色严格遵守 tokens 表，不引入第 6 个色相

---

## 风险与回退

- **风险 1**：移除"资金概览"卡片副标题"本年支出结构与待收款状态"位置，可能影响测试断言 → 检查 `billing_screen_test.dart` 是否引用该字符串，若引用则保留文案、只换层级
- **风险 2**：合并交易卡可能影响 `最近交易 → 查看全部` 跳转逻辑 → 跳转入口仍在 section header 右侧，不动路由
- **回退方案**：保留当前 `BillingSummaryWidgets` 文件，新建 `BillingSummaryWidgetsV2`，灰度切换；如出问题可立即回滚

---

## 参考文件

- 当前账本页源码：`mobile-app/lib/features/billing/billing_screen.dart`、`billing_summary_widgets.dart`
- 当前账本页测试：`mobile-app/test/features/business/business_pages_test.dart`
- 设计规范：`.claude/rules/app-ui.md`
- 前端编码规范：`.claude/rules/frontend-style.md`
- 旧探索（深色方向，未落地）：`output/imagegen/billing-ledger-redesign.spec.md`、`ledger-screen-ref.spec.md`
