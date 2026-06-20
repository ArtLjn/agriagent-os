# 账本页面颠覆性整改 UI Spec

## Image

- Source image: `output/imagegen/billing-ledger-redesign.png`
- Generation status: AISpeech gateway returned SSL EOF twice, no image was saved.
- Canvas: `1024x2224px`
- Intended platform: Flutter mobile app, logical width `430px`

## Visual Direction

- 产品气质：农场经营账册，可信、克制、可扫描，不做营销页和 AI 炫光。
- 当前问题：亮蓝 AI 胶囊、蓝绿大渐变按钮、圆润插画卡、重复橙色购物车图标，组合后显得像 demo。
- 整改方向：用深色账页式概览卡建立财务可信感；AI 作为「智能复盘」低饱和提示；交易列表改成语义图标和账务信息密度。

## Layout

- 页面宽度：最大 `430px`
- 页面 padding：`20px`
- 账本首页：
  - 顶部品牌 header：`52px`
  - 资金账册卡：约 `204px`，深色面板，顶部为标题、期间和智能复盘入口，中部为年度净收益，底部为三项指标。
  - 洞察条：约 `92px`，白色窄卡，左侧小图标，右侧标题与两行文案。
  - 最近交易：白色列表卡，5 条以内预览，`查看全部` 为轻量文本按钮。
  - 待收款提醒：紧凑提醒条。
  - 固定 CTA：`56px` 高，纯绿色，不使用蓝绿大渐变。
- 全部交易页：
  - App bar：`56px`
  - 汇总工具条：约 `88px`，显示本月、支出、收入。
  - 分段筛选：`48px`
  - 交易列表：固定内部滚动区域，保留月份标题和分隔。

## Design Tokens

### Colors

- `--color-bg`: `#F5F7F4`
- `--color-surface`: `#FFFFFF`
- `--color-ledger`: `#0B2B26`
- `--color-ledger-soft`: `#15483D`
- `--color-primary`: `#12A66A`
- `--color-primary-blue`: `#1F6FEB`
- `--color-expense`: `#E76F21`
- `--color-negative`: `#D92D20`
- `--color-text`: `#101828`
- `--color-text-muted`: `#667085`
- `--color-border`: `#E3E8EF`

### Typography

- Font family: system sans
- Page title: `22px / 28px / 800`
- Section title: `18px / 26px / 800`
- Body: `14px / 21px / 600`
- Caption: `12px / 16px / 600`
- Money: tabular figures, `30px` to `42px`, `800`

### Spacing And Shape

- Base grid: `8px`
- Card padding: `16px`
- Card radius: `18px` on large mobile cards
- Row height: `66px`
- Icon tile: `44px`, radius `12px`
- CTA height: `56px`, radius `16px`

## Components

- `LedgerSummaryCard`: deep ledger surface, no farm illustration, no bright AI pill.
- `AiFinanceInsightCard`: renamed visual treatment to smart review, subtle blue icon tile and border.
- `TransactionRow`: semantic icon by transaction kind; income green, debt blue, expense amber; red only for negative amount text.
- `_TransactionSummaryStrip`: tool strip rather than bulky white card pile.
- `_TransactionFilterBar`: segmented control with solid selected state and thin border.
- `_ManualLedgerButton`: pure green primary button with icon, no full-width gradient.

## Exact Text

- `资金账册`
- `本年`
- `智能复盘`
- `年度净收益`
- `收入`
- `支出`
- `欠款`
- `最近交易`
- `查看全部`
- `全部交易`
- `2026年6月`
- `本月`
- `全部`
- `手动记一笔`

## Implementation Invariants

- 不展示 `AI帮我填`、`AI待确认`、`智能记账`。
- 保持原有测试可见文案：`资金概览`、`AI财务洞察`、`最近交易`、`全部交易`、`待收款提醒`、`手动记一笔`。
- 金额必须继续使用紧凑格式和 tabular figures。
- 全部交易页继续使用内部 `ListView` 和 `Scrollbar`。
- 不引入新图片资产，不依赖生成图才能运行。
