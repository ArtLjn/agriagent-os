# AI 今日建议详情页 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/ai-daily-advice-detail.png`
- Canvas: `1024x2224px`
- Intended platform: mobile app, Flutter implementation baseline `390x844` logical pixels
- Entry: 首页 `AI 今日建议` 列表项点击进入，例如 `准备水稻采收`

## Layout

- Page background: full screen `#F6F8FB`, flat front-on mobile app UI.
- Top app bar: height `64px` logical, left back icon, centered title `建议详情`, right more/options icon.
- Scroll content: horizontal padding `20px`, vertical gap `12-14px`.
- Hero card: top large card, radius `18px`, light blue gradient, includes advice icon, title, priority pill, explanation, farmland/harvester illustration area, and 3 meta chips.
- Evidence card: white card, radius `16px`, title `AI 判断依据`, 3 rows with icon tile + reason text.
- Steps card: white card, radius `16px`, title `执行步骤`, 4 checklist rows with number badge, unchecked circle, step text, thin dividers.
- Related card: white card, radius `16px`, title `关联事项`, 2 linked rows with icon tile, title/value, right chevron.
- Bottom action bar: sticky above bottom navigation, two equal-height buttons. Left primary button `生成作业单`, right outlined button `问问芽芽`.
- Bottom navigation: same 5 tabs as current app, `首页` selected.

## Design Tokens

### Colors

- `--color-bg`: `#F6F8FB`
- `--color-surface`: `#FFFFFF`
- `--color-hero-start`: `#F4FAFF`
- `--color-hero-end`: `#EAF4FF`
- `--color-primary`: `#1677FF`
- `--color-success`: `#00A870`
- `--color-warning`: `#FF6500`
- `--color-text`: `#111827`
- `--color-text-muted`: `#6B7280`
- `--color-border`: `#E8EEF5`
- `--color-blue-soft`: `#EAF3FF`
- `--color-green-soft`: `#E7F8EF`
- `--color-amber-soft`: `#FFF1DC`

### Typography

- Font family: system sans-serif, Flutter default Chinese fallback.
- App bar title: `22px / 30px / w800`
- Hero title: `24px / 32px / w800`
- Section title: `18px / 26px / w800`
- Row title/body: `15-16px / 22px / w600`
- Caption/muted text: `13-14px / 20px / w500`
- Button text: `17px / 24px / w800`

### Spacing And Shape

- Base grid: `8px`
- Page padding: `20px`
- Card padding: `18-20px`
- Card radius: `16-18px`
- Card gap: `12-14px`
- Icon tile: `44-52px`, radius `12-14px`
- Minimum tap target: `44px`

## Components

- `AdviceDetailHero`: blue-tinted card with advice category icon, title, priority pill, short summary, illustration, and three meta chips.
- `MetaChip`: white chip, height `38-44px`, radius `12px`, subtle shadow/border, leading icon + text.
- `ReasonRow`: icon tile `44px`, text `成熟期：水稻已进入收割窗口`, divider except last row.
- `StepRow`: number badge `28px`, checkbox circle `24px`, step text, divider.
- `RelatedItemRow`: icon tile, label/value stack, right chevron, divider except last row.
- `BottomActionBar`: white/translucent surface with primary filled button and secondary outline button.
- `BottomNav`: keep current app tab labels `首页 / 记录 / 芽芽 / 账本 / 我的`.

## Exact Text

- `建议详情`
- `准备水稻采收`
- `高优先级`
- `夏季水稻已进入成熟期，建议今天完成收割前检查。`
- `睢宁县`
- `高温 32℃`
- `预计 2 小时`
- `AI 判断依据`
- `成熟期：水稻已进入收割窗口`
- `天气：晴热少雨，适合晾晒`
- `作业：今日已有 5 项待跟进`
- `执行步骤`
- `检查收割机与镰刀`
- `确认装袋和运输工具`
- `避开午后高温安排人员`
- `收割后记录产量与人工`
- `关联事项`
- `未结人工`
- `¥400`
- `风险预警`
- `1项待关注`
- `生成作业单`
- `问问芽芽`

## Implementation Invariants

- Do not copy generated text artifacts if the image text is slightly distorted; use the exact text in this spec.
- Keep the first viewport focused on one advice item and its reason for urgency.
- Keep detailed content scannable: one card for evidence, one card for steps, one card for related items.
- The page should be usable without the decorative hero illustration; implementation may reuse existing farm hero asset or a simpler illustration if no matching asset exists.
- `生成作业单` should be the primary action and route into the work-order creation flow with fields prefilled from the advice.
- `问问芽芽` should open the assistant with this advice context.
- Checklist rows are static guidance in the first implementation; later versions can support completion state if needed.
- Loading state: show skeleton cards preserving the same heights.
- Empty/error state: show a compact card with `建议详情加载失败，请稍后重试` and a retry button.
