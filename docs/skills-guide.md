# Skill 使用指南 — Vibe Coding 速查手册

> 本文档汇总项目已安装的所有 Skill，帮助团队成员在 Vibe Coding 时快速判断「该用哪个 Skill」。

---

## 决策树：一句话定 Skill

```
任务类型判断：
│
├─ 移动端 App 界面设计？
│   ├─ 生成图片/mockup？      → html-to-image
│   └─ 设计 screen/flow？     → mobile-app-ui-design
│
├─ Web 前端 UI 实现？
│   ├─ 先定视觉方向？         → beautiful-ui
│   ├─ 用 shadcn/ui+Tailwind？→ ckm:ui-styling
│   └─ 直接写组件代码？       → frontend-ui-design
│
├─ Flutter App？
│   ├─ 布局适配不同屏幕？     → flutter-build-responsive-layout
│   └─ 修复 overflow/报错？   → flutter-fix-layout-issues
│
├─ 品牌/视觉识别？
│   ├─ 定义品牌声音/规范？    → ckm:brand
│   ├─ 设计系统/设计令牌？    → ckm:design-system
│   └─ Logo/CIP/横幅/图标？   → ckm:design
│
├─ 生成营销素材？
│   ├─ 横幅/广告图？          → ckm:banner-design
│   ├─ 社交图片/海报？        → ckm:design (social photos)
│   └─ 幻灯片/路演 deck？     → ckm:design-system (slides)
│
├─ 加动画/动效？              → ui-animation
│
└─ 不确定用什么？             → ui-ux-pro-max（兜底综合设计智能）
```

---

## Skill 速查表

| Skill | 一句话定位 | 典型触发词 | 不触发场景 |
|-------|-----------|-----------|-----------|
| **mobile-app-ui-design** | 移动端 App UI/UX 设计 | "设计App界面"、"做mockup"、"移动端屏幕" | Web后台管理界面 |
| **beautiful-ui** | 定义视觉方向、提升视觉品质 | "设计得更好看"、"重新设计"、"提升视觉" | 已有明确设计稿的纯编码 |
| **frontend-ui-design** | 实现前端 UI 组件和页面 | "实现组件"、"修复布局"、"写页面" | 纯视觉方向探索 |
| **html-to-image** | HTML/CSS 生成高清图片 | "生成截图"、"做分享卡片"、"mockup图片" | 不涉及图片生成的UI工作 |
| **ui-animation** | UI 动画、过渡、手势交互 | "加动画"、"让过渡更平滑"、"swipe手势" | 纯静态布局 |
| **ui-ux-pro-max** | 综合设计智能（兜底） | "设计页面"、"UI review"、"配色方案" | 有明确子 Skill 匹配时 |
| **ckm:brand** | 品牌识别、视觉规范 | "品牌规范"、"定义品牌色"、"品牌一致性检查" | 纯技术实现 |
| **ckm:design-system** | 设计令牌、组件规范、幻灯片 | "设计系统"、"CSS变量"、"做PPT/deck" | 一次性设计任务 |
| **ckm:design** | 统一设计入口（Logo/CIP/横幅/图标） | "设计Logo"、"做名片"、"生成图标" | 已有子 Skill 更精确匹配时 |
| **ckm:banner-design** | 横幅/广告/封面设计 | "设计banner"、"做封面"、"广告图" | 非横幅类设计 |
| **ckm:ui-styling** | shadcn/ui + Tailwind 实现 | "用shadcn"、"Tailwind样式"、"暗色模式" | 非 React 技术栈 |
| **flutter-build-responsive-layout** | Flutter 响应式布局 | "Flutter适配平板"、"响应式布局" | 非 Flutter 项目 |
| **flutter-fix-layout-issues** | Flutter 布局报错修复 | "RenderFlex overflowed"、"布局报错" | 非布局类 Flutter 问题 |

---

## 按场景详细使用说明

### 场景一：移动端 App 设计（Flutter）

本项目使用 Flutter 开发移动端 App，完整设计流程如下：

```
1. 定义视觉方向        → beautiful-ui
                        ↓
2. 设计具体 screen     → mobile-app-ui-design
                        ↓
3. 生成设计稿图片      → html-to-image
                        ↓
4. Flutter 编码实现    → ckm:ui-styling（如用 Web 预览）
                        ↓
5. 布局适配多设备      → flutter-build-responsive-layout
                        ↓
6. 修复布局报错        → flutter-fix-layout-issues
                        ↓
7. 添加交互动画        → ui-animation
```

**本项目已内置设计规范**：见 `.claude/rules/app-ui.md`
- 颜色：Primary `#4F8CFF`，Background `#F7F8FA`，Surface `#FFFFFF`
- 间距：4/8/12/16/24/32/40
- 圆角：20–28px
- 字体：SF Pro Display / SF Pro Text（fallback Inter）

---

### 场景二：品牌物料设计

```
1. 定义品牌基础        → ckm:brand
   - 品牌声音、视觉识别、消息框架
   - 输出：docs/brand-guidelines.md
                        ↓
2. 设计系统令牌        → ckm:design-system
   - 三层令牌：Primitive → Semantic → Component
   - 输出：assets/design-tokens.json / .css
                        ↓
3. 生成 Logo           → ckm:design (Logo)
   python3 ~/.claude/skills/design/scripts/logo/generate.py \
     --brand "品牌名" --style minimalist --industry tech
                        ↓
4. 生成 CIP 物料       → ckm:design (CIP)
   python3 ~/.claude/skills/design/scripts/cip/generate.py \
     --brand "品牌名" --logo logo.png --set
                        ↓
5. 设计横幅/广告       → ckm:banner-design
                        ↓
6. 生成图标            → ckm:design (Icon)
   python3 ~/.claude/skills/design/scripts/icon/generate.py \
     --prompt "settings gear" --style outlined
```

---

### 场景三：Web 管理后台开发

```
1. 设计视觉方向        → beautiful-ui
                        ↓
2. 定义设计系统        → ckm:design-system
                        ↓
3. 用 shadcn/ui 实现   → ckm:ui-styling
   - npx shadcn@latest init
   - npx shadcn@latest add button card dialog
                        ↓
4. 编写页面组件        → frontend-ui-design
                        ↓
5. 导出设计稿图片      → html-to-image
```

---

## Skill 调用方式

### 方式一：自然语言触发（推荐）

直接在对话中描述需求，AI 会自动匹配最合适的 Skill：

```
用户：帮我设计一个登录页面
→ 自动触发 beautiful-ui → frontend-ui-design

用户：这个按钮hover效果太生硬
→ 自动触发 ui-animation

用户：Flutter 布局报 RenderFlex overflowed
→ 自动触发 flutter-fix-layout-issues
```

### 方式二：显式调用

如果自动匹配不准，可以显式指定：

```
用户：用 mobile-app-ui-design 帮我设计首页
用户：调用 ckm:banner-design 设计一个 Instagram 广告横幅
```

### 方式三：组合使用

复杂任务可以串联多个 Skill：

```
用户：我要做一个品牌升级，先定品牌规范，再做一套 Logo
→ 依次触发 ckm:brand → ckm:design (Logo)
```

---

## 各 Skill 核心能力详解

### ui-ux-pro-max（综合设计智能）
- **50+ 设计风格**：glassmorphism、claymorphism、minimalism、brutalism、neumorphism、bento grid、dark mode 等
- **161 种配色方案**、57 种字体搭配
- **10 个技术栈**：React、Next.js、Vue、Svelte、SwiftUI、React Native、Flutter、Tailwind、shadcn/ui、HTML/CSS
- **25 种图表类型**
- **使用时机**：不确定用哪个子 Skill 时的兜底选择；需要综合设计建议时

### ckm:design（统一设计入口）
内置 5 个子能力：

| 子能力 | 功能 | 命令示例 |
|--------|------|---------|
| Logo | 55+ 风格、30 配色、AI 生成 | `scripts/logo/generate.py --brand "X" --style minimalist` |
| CIP | 50+ 物料、名片/信纸等 mockup | `scripts/cip/generate.py --brand "X" --set` |
| Slides | 战略演示文稿、Chart.js 图表 | 见 `references/slides-create.md` |
| Banner | 22 种艺术风格、多平台尺寸 | 由 `ckm:banner-design` 专门处理 |
| Icon | 15 种风格、SVG 输出、AI 生成 | `scripts/icon/generate.py --prompt "X" --style outlined` |
| Social Photos | 多平台社交图片 | HTML/CSS → 截图导出 |

**前置条件**：需要设置 `GEMINI_API_KEY`
```bash
export GEMINI_API_KEY="your-key"  # https://aistudio.google.com/apikey
pip install google-genai pillow
```

### ckm:design-system（设计系统）
- **三层令牌架构**：Primitive → Semantic → Component
- **组件状态规范**：Default / Hover / Active / Disabled
- **幻灯片系统**：BM25 搜索 + 上下文决策 + Chart.js
- **脚本工具**：
  - `generate-tokens.cjs`：JSON 生成 CSS
  - `validate-tokens.cjs`：检查硬编码值
  - `search-slides.py`：幻灯片内容搜索

### ckm:brand（品牌）
- 品牌声音定义、视觉识别标准
- 消息框架创建
- 品牌一致性审查
- **核心工作流**：
  ```bash
  # 1. 编辑 docs/brand-guidelines.md
  # 2. 同步到设计令牌
  node scripts/sync-brand-to-tokens.cjs
  # 3. 验证
  node scripts/inject-brand-context.cjs --json
  ```

### ckm:banner-design（横幅设计）
- **22 种艺术风格**：minimalist、gradient、bold typography、glassmorphism、neon 等
- **多平台尺寸**：Facebook Cover、Twitter Header、Instagram Story/Post、Google Ads 等
- **AI 视觉生成**：Standard (Flash) 用于背景/图案，Pro 用于复杂插画
- **导出流程**：HTML/CSS 设计 → Chrome 截图 → PNG

### ckm:ui-styling（UI 样式实现）
- **shadcn/ui**：Radix UI 基础 + Tailwind 样式
- **Tailwind CSS**：utility-first、零运行时开销
- **Canvas 视觉设计**：博物馆级视觉合成
- **核心脚本**：
  ```bash
  python scripts/shadcn_add.py button card dialog      # 安装组件
  python scripts/tailwind_config_gen.py --colors brand:blue  # 生成配置
  ```

### flutter-build-responsive-layout（Flutter 响应式）
- 使用 `LayoutBuilder`、`MediaQuery`、`Expanded/Flexible`
- 适配手机/平板/桌面多端

### flutter-fix-layout-issues（Flutter 布局修复）
- 修复 "RenderFlex overflowed"
- 修复 "Vertical viewport was given unbounded height"
- 修复类似布局约束错误

---

## 项目设计规范速查

### 颜色系统
| Token | 值 | 用途 |
|-------|-----|------|
| Primary | `#4F8CFF` | 主按钮、链接、强调 |
| Background | `#F7F8FA` | 页面背景 |
| Surface | `#FFFFFF` | 卡片、浮层背景 |

### 间距系统（8pt Grid）
`4 / 8 / 12 / 16 / 24 / 32 / 40`

### 圆角
- 卡片：`20–28px`
- 按钮：`12–16px`

### 阴影
```css
box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
```

### 字体层级
| 层级 | 大小 | 用途 |
|------|------|------|
| Hero | 28–34px | 页面大标题 |
| Section | 20–24px | 区块标题 |
| Body | 15–17px | 正文内容 |
| Caption | 12–13px | 辅助说明 |

---

## 常见问题

**Q：多个 Skill 都匹配，用哪个？**
> 按「精准度优先」原则：子 Skill > 父 Skill > 综合 Skill。例如要做横幅，优先用 `ckm:banner-design`，而不是 `ckm:design` 或 `ui-ux-pro-max`。

**Q：Skill 没自动触发怎么办？**
> 显式说出 Skill 名称，如「用 mobile-app-ui-design 帮我…」。

**Q：怎么知道某个 Skill 是否已经安装？**
> 看本文档的「Skill 速查表」，表中列出的都是已安装的。也可以问 AI「列出可用的 Skill」。

**Q：Gemini API 相关 Skill 需要什么配置？**
> 设置环境变量：`export GEMINI_API_KEY="your-key"`，并安装 `pip install google-genai pillow`。

---

*本文档随 Skill 安装情况更新。如有新增 Skill，请同步更新此文档。*
