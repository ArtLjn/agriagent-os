# 田掌柜官网 V3 优化计划

## 核心变更

### 1. 品牌全面改名
- Farm Manager → 田掌柜
- 英文副标保留：Tian Zhang Gui / Farm Management
- 所有文案、导航、按钮、页脚全面替换

### 2. 深色主题统一（解决白色刺眼问题）
- 所有白色（#FFFFFF）背景 → #013A33（深绿）或 #0a2520（更深绿）
- 所有 cream（#F9F9F9）背景 → #0d2e28 或 #0a2520
- 卡片背景：从白色/cream → #0d2e28（带微妙边框 #1a4540）
- 文字颜色：深色文字 → 白色/浅绿白色
- FAQ区域：白色 → 深绿
- 功能区域：白色 → 深绿
- 场景区域：白色 → 深绿
- 保持整体统一的深绿色沉浸体验

### 3. 配色方案 V3
| Token | 值 | 用途 |
|-------|-----|------|
| --color-bg-primary | #013A33 | 主背景 |
| --color-bg-secondary | #0a2520 | 次级深色背景（区块交替） |
| --color-bg-card | #0d2e28 | 卡片背景 |
| --color-border-card | #1a4540 | 卡片边框 |
| --color-text-primary | #FFFFFF | 主文字 |
| --color-text-secondary | rgba(255,255,255,0.65) | 次级文字 |
| --color-text-muted | rgba(255,255,255,0.4) | 辅助文字 |
| --color-accent-lime | #BFFF00 | CTA/强调 |
| --color-accent-blue | #22AED1 | 链接/次强调 |
| --color-accent-gold | #FFD15C | 标签/高亮 |

### 4. AI助手标题截断修复
- 增加section padding-top
- 修复z-index
- 确保标题不被截断

### 5. 其他打磨
- 下载中心回到深绿主题（不是白色）
- SVG描边动画在深绿背景上的可见性
- 整体对比度和可读性检查
