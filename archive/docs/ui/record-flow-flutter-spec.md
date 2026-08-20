# 记录创建闭环 Flutter 规格

## 目标

补齐 `记录` 页之后的核心创建流程：AI 解析确认、手动编辑兜底、保存成功。

## 参考图

- AI确认 v2: `/Users/ljn/Documents/demo/explore/output/imagegen/record-flow-v2/ai-confirm.png`
- 手动编辑 v2: `/Users/ljn/Documents/demo/explore/output/imagegen/record-flow-v2/manual-edit.png`
- 保存成功 v2: `/Users/ljn/Documents/demo/explore/output/imagegen/record-flow-v2/save-success.png`

`record-flow-v2` 是推荐实现目标。旧版 `record-flow` 仅作历史参考。

图片为 `1024x2224` 标准移动端比例，Flutter 实现基准按 `390x844` 逻辑像素。

## 流程

1. 用户在 `记录` 页输入一句话。
2. AI 返回结构化解析结果，进入 `AI解析确认`。
3. 用户点 `保存`，写入成功后进入 `保存成功`。
4. 用户点 `改一下`，进入 `手动编辑兜底`。
5. 手动编辑保存后也进入 `保存成功`。

## AI解析确认页

### 页面

- Header: 返回按钮 + `农场管家`
- Title: `智能确认`
- Step indicator: `1 识别完成`, `2 确认保存`

### 内容

- Hero 理解结果卡:
  - `我理解为`
  - `记一笔支出`
  - `¥3,680`
  - chips: `饲料采购`, `今天`, `5月第2批次`
- 原话卡片:
  - `用户原话`
  - `今天买饲料花了3680，记到5月第2批次`
- 分组字段卡:
  - `账务信息`: `分类 饲料采购`, `金额 ¥3,680.00`, `付款 现金`
  - `关联信息`: `批次 5月第2批次`, `日期 今天`, `备注 饲料采购`
- 提示:
  - `不确定？点字段可以修改`

### 操作

- Sticky bottom:
  - `改一下`
  - `保存`

## 手动编辑兜底页

### 页面

- Header: 返回按钮 + `农场管家`
- Title: `改一下`
- Subtitle: `哪里不对，点哪里改`
- Context pill: `AI已帮你填好大部分`

### 内容

- 口径切换:
  - `记账`
  - `农事`
  - `工资`
- 分组校正卡:
  - `金额与分类`: `¥3,680.00`, `饲料采购`
  - `时间与归属`: `今天`, `5月第2批次`
  - `付款方式`: `现金`, `微信`, `赊账`
  - `备注`: `饲料采购`

### 操作

- Sticky bottom:
  - `保存修改`

## 保存成功页

### 页面

- Center success emblem
- Title: `记录已保存`
- Subtitle: `已同步到账本和最近记录`

### 内容

- Receipt summary card:
  - `饲料采购单`
  - `金额` `¥3,680.00`
  - `关联批次` `5月第2批次`
  - `日期` `今天`
  - `付款` `现金`
  - badge `已入账`
- Next actions:
  - `再记一笔`
  - `查看账本`
  - `回到首页`
- Tip:
  - `下次可以直接说 买饲料花了多少钱`

### 操作

- Primary button:
  - `完成`

## 设计 Token

- 背景: `#F7F9FC`
- 卡片: `#FFFFFF`
- 主蓝: `#2F73F6`
- 绿色: `#35C879`
- 橙色: `#FF9F1C`
- 正文: `#111827`
- 次级文字: `#6B7280`
- 边框: `#E8ECF2`
- 页面横向 padding: `20px`
- 卡片圆角: `16px`
- 大卡片圆角: `18px`
- Sticky bottom 高度: `88px`

## 实现约束

- 不显示技术字段、API 字段、数据库字段。
- 字段用自然语言标签。
- 手动编辑页不是后台表单，要用大触达列表行、chips、segmented controls 和分组卡片。
- AI 确认页需要有设计层次: hero 理解卡、原话卡、分组字段卡、底部操作。
- 保存成功页需要有完成感和下一步动作，不要只显示简单 toast。
- 这三页是 push flow，不显示底部 Tab。
- 需要支持后续扩展到 `农事`、`工资`、`建批次`、`新增工人`、`建模板` 等不同口径。
