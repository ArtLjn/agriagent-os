# 农业 AI App 全套 UI 设计规范（ClaudeCode 可直接照着做）

你现在的方向已经对了：

> 首页不应该是“待办列表”
> 而应该是“AI 助手入口”

这一步非常关键。

你现在已经从：

❌ 管理系统
升级成：

✅ AI 农业助手

下面我给你完整的：

* 每页 UI 结构
* 配色
* 卡片设计
* 阴影
* 字体
* 圆角
* 动效
* AI 感
* ClaudeCode 可直接实现的描述

你直接丢给 ClaudeCode 就能做。

---

# 一、整体设计语言（全局统一）

# 设计关键词

```text
轻 AI
天气感
柔和
低饱和
呼吸感
卡片化
智能助手
```

---

# 全局背景

不要纯白。

全局背景统一：

```css
background: #F6F8FC;
```

或者：

```css
background:
linear-gradient(
180deg,
#F7FAFF 0%,
#F9FBFD 40%,
#FFFFFF 100%
);
```

---

# 全局圆角

这是高级感核心。

| 元素        | 圆角   |
| --------- | ---- |
| 大卡片       | 28px |
| 小卡片       | 22px |
| 按钮        | 18px |
| 输入框       | 20px |
| BottomBar | 30px |

---

# 全局阴影

不要安卓那种重阴影。

统一：

```css
box-shadow:
0 8px 30px rgba(91,140,255,0.08);
```

轻一点：

```css
0 4px 16px rgba(0,0,0,0.04)
```

---

# 全局主色（非常重要）

只允许：

# 主蓝色

```css
#5B8CFF
```

# AI紫色

```css
#8B5CF6
```

# 农业绿色

```css
#3BB273
```

其它颜色全部降饱和。

---

# 字体规范

# 一级标题

```css
font-size: 32px;
font-weight: 700;
letter-spacing: -0.5px;
```

---

# 二级标题

```css
font-size: 22px;
font-weight: 600;
```

---

# 卡片正文

```css
font-size: 15px;
color: #6B7280;
line-height: 1.6;
```

---

# 页面结构（核心）

你以后所有页面：

不要：

❌ 一屏很多信息

而是：

# 1 个重点

# 2~3 个操作

# 大留白

这是 AI App 的核心。

---

# 二、首页 UI（最关键）

# 首页核心逻辑

你现在首页：

❌ 农业后台

应该改：

✅ AI 晨间助手

---

# 首页结构（正确）

```text
顶部问候
↓
天气大卡片
↓
AI 晨间简报卡片（重点）
↓
快捷功能
↓
底部导航
```

---

# 顶部区域

## 背景

透明。

---

## 左侧

```text
早上好，农友
今天适合播种豆角
```

第二行灰色：

```css
color: #94A3B8;
```

---

## 右侧

小 AI 图标按钮：

背景：

```css
#EDF4FF
```

点击进入 AI 聊天。

---

# 天气大卡片（首页核心）

# 卡片颜色

```css
background:
linear-gradient(
135deg,
#5B8CFF 0%,
#7AA8FF 100%
);
```

---

# 卡片内部

左边：

```text
23°
多云
体感 25°
```

右边：

大云朵插画。

---

# 卡片底部

小天气趋势：

```text
今天 明天 后天
```

图标不要复杂。

---

# AI 晨间简报卡片（重点）

这是你现在最该替换的部分。

你之前：

❌ 列表

现在：

✅ 一张情绪卡片

---

# 卡片结构

```text
今日农事建议
↓
今天上午有雾
降温啦，体感更舒适
↓
一句简短说明
↓
去咨询 AI 按钮
```

---

# 卡片背景（超级重要）

用渐变：

# 雾天

```css
background:
linear-gradient(
135deg,
#EAF3FF,
#F7F9FF
);
```

---

# 晴天

```css
background:
linear-gradient(
135deg,
#FFF4D6,
#FFF9EA
);
```

---

# 雨天

```css
background:
linear-gradient(
135deg,
#DCEBFF,
#EEF5FF
);
```

---

# 降温

```css
background:
linear-gradient(
135deg,
#E7F2FF,
#F3F8FF
);
```

---

# 标题文字（关键）

不要黑字。

用渐变字。

例如：

```css
background:
linear-gradient(
90deg,
#4DA2FF,
#C26CFF
);

-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
```

---

# AI 小宠物

右下角放：

* 小黑球 AI
* 半透明
* 漂浮感

大小：

```css
72px
```

透明度：

```css
0.9
```

---

# 按钮

不要实心大按钮。

用：

```css
background: rgba(255,255,255,0.7);
backdrop-filter: blur(10px);
```

高级很多。

---

# 快捷功能区

不要列表。

改：

```text
种植规划
农事提醒
天气趋势
病虫害识别
```

横向滑动卡片。

---

# 卡片颜色

全部低饱和：

| 功能  | 背景      |
| --- | ------- |
| 种植  | #EDFDF3 |
| 提醒  | #EEF4FF |
| 天气  | #FFF8E8 |
| 病虫害 | #FFF1F2 |

---

# 三、AI 聊天页（第二重点）

这个页面决定你 App 高不高级。

---

# 页面背景

不要白。

```css
background:
linear-gradient(
180deg,
#F7FAFF,
#FFFFFF
);
```

---

# 顶部

```text
AI 农事助手
在线
```

在线状态：

```css
#3BB273
```

小绿点。

---

# AI 头像

不要普通机器人。

建议：

* 小黑球
* 圆润
* 有眼睛
* 类似小布助手

这是记忆点。

---

# AI 回复卡片

```css
background: #FFFFFF;
border: 1px solid #EEF2F7;
```

---

# 用户气泡

```css
background:
linear-gradient(
135deg,
#5B8CFF,
#7A7DFF
);
```

白字。

---

# 输入框

```css
background: #F3F6FB;
```

圆角：

```css
24px
```

---

# 发送按钮

```css
background:
linear-gradient(
135deg,
#5B8CFF,
#7A7DFF
);
```

---

# 推荐问题（重要）

聊天页顶部：

不要空。

放：

```text
帮我规划秋种
今天适合施肥吗
未来一周天气
```

做成胶囊卡片。

---

# 四、天气详情页

这个页面：

一定要高级。

---

# 顶部大温度

```text
23°
多云
```

字体超大。

---

# 背景渐变

```css
background:
linear-gradient(
180deg,
#BFD8FF 0%,
#EAF3FF 60%,
#FFFFFF 100%
);
```

---

# 小时天气卡片

半透明：

```css
background:
rgba(255,255,255,0.25);
backdrop-filter: blur(20px);
```

---

# 图表

线条：

```css
#7AA8FF
```

节点：

```css
#FFFFFF
```

---

# 五、账本页面（轻财务）

你现在太像 ERP。

---

# 正确方向

像：

* iOS 财务
* 支付宝账单
* Notion finance

---

# 页面结构

```text
总资产卡片
↓
本月收支
↓
分类标签
↓
流水记录
```

---

# 收入卡片

```css
background: #EDFDF3;
```

数字：

```css
#16A34A
```

---

# 支出卡片

```css
background: #FFF1F2;
```

数字：

```css
#EF4444
```

---

# 浮动按钮

右下角：

```css
background:
linear-gradient(
135deg,
#5B8CFF,
#8B5CF6
);
```

---

# 六、设置页（极简）

不要复杂。

---

# 背景

```css
#F8FAFC
```

---

# 用户卡片

顶部：

* 头像
* 农友
* AI 农场等级

---

# 设置项

全部白卡片。

高度：

```css
64px
```

---

# 图标颜色

统一：

| 类型 | 颜色      |
| -- | ------- |
| AI | #8B5CF6 |
| 农场 | #3BB273 |
| 城市 | #5B8CFF |
| 时间 | #14B8A6 |

---

# 七、BottomBar（超级重要）

这是高级感核心。

---

# 背景

```css
background:
rgba(255,255,255,0.7);
backdrop-filter: blur(20px);
```

---

# 高度

```css
72px
```

---

# 选中态

不要小蓝点。

用：

# 浮动胶囊

```css
background:
linear-gradient(
135deg,
#5B8CFF,
#7A7DFF
);
```

白色图标。

---

# 八、动效（高级感来源）

ClaudeCode 最容易忽略这个。

但：

# 动效 = 高级感

---

# 卡片进入

```text
淡入 + 上移
```

时长：

```css
0.45s
```

---

# AI 卡片

轻微浮动：

```text
上下 4px 呼吸
```

---

# 点击按钮

缩放：

```css
scale(0.96)
```

---

# 九、你这个 App 最适合的最终风格

# 风格名字

```text
轻 AI 农业助手
```

融合：

* 小布助手
* OriginOS
* HarmonyOS
* iOS Weather
* 小米澎湃OS

---

# 十、最后一个最关键建议（真的很重要）

你以后：

# 所有信息都不要直接展示

而是：

# “先一句话”

# “再点击进入 AI”

例如：

❌

```text
欠款555元
未来3天有雨
建议施肥
建议播种
```

✅

```text
今天适合开始秋种 →
```

点击进入：

AI 给详细方案。

这是：

# AI 产品

和

# 传统管理系统

最大的区别。
