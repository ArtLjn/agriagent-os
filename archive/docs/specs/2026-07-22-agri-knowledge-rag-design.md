# 农业知识库与 RAG 向量库设计

| 项目 | 内容 |
| --- | --- |
| 日期 | 2026-07-22 |
| 状态 | Proposed |
| 目标 | 以徐州睢宁设施农业为服务基准，设计可逐步沉淀的结构化知识 + 向量检索方案 |
| 关联模块 | `backend/app/memory/`、`backend/app/context/`、`backend/app/domains/planting/`、`backend/app/domains/weather/`、外部 QuillRAG 服务 |

## 1. 背景

Farm Manager 需要支持面向农户的农业知识问答和农事建议。当前不追求“全国农业问答”或“多城市多作物百科”，而是先把服务边界收束到 **徐州睢宁设施农业**，用一个足够窄、足够真实的场景跑通知识沉淀、结构化抽取、RAG 检索和 Agent 回答闭环。

第一阶段优先服务的问题包括：

- 睢宁设施西瓜一般什么时候育苗、定植、授粉、采收。
- 睢宁当前气候和近期天气下，大棚西瓜是否需要防倒春寒。
- 睢宁魏集、周边镇村或合作社的真实种植节奏与公开农技资料如何互相印证。
- 后续再扩展到丰县、沛县、铜山、邳州、新沂等徐州县区和特色作物。

现有架构中，`memory/` 已预留长期记忆和检索端口，当前部署不内置 RAG。外部 QuillRAG 服务已有 Qdrant、SQLite 元数据、混合检索、rerank、评测等能力，可以作为农业知识库的 RAG 底座。本文定义 Farm Manager 侧如何组织农业知识、如何设计 Qdrant collection、如何处理多城市和多作物扩展。

## 2. 目标

1. 支持“县区/乡镇 + 作物 + 茬口 + 设施类型 + 生育阶段”的精准检索。
2. 第一阶段以“徐州睢宁 + 设施西瓜 + 春季/春提早”为核心服务基准。
3. 后续再扩展到丰县大棚西瓜、沛县设施西瓜、铜山区西瓜、邳州大蒜、新沂水蜜桃等本地场景。
4. 把稳定农时、气候平年值等确定性事实结构化保存，避免完全依赖向量相似度。
5. 公共知识、地区知识、用户私有经验分层隔离，避免权限和生命周期混乱。
6. 保持 Agent 平台边界：Runtime 不直接访问 Qdrant；通过 `MemoryService` 或独立检索端口接入。

## 3. 非目标

- 不做全国全作物的一次性完整知识库。
- 不在第一阶段覆盖徐州全部县区、全部作物或全部茬口。
- 不把每个城市或每个作物拆成独立 Qdrant 服务。
- 不把农时日程、气候平年值这类稳定事实只存进向量库。
- 不让模型在没有检索结果或工具结果时声称已查询资料。
- 不在 Agent Runtime 中直接拼接 RAG、天气、农场业务数据。
- 不在第一版实现复杂知识图谱、本体推理或自动生成农技结论。

## 4. 总体方案

采用“结构化事实层 + 向量知识层 + 用户经验层”的混合架构。

```text
用户问题
  -> 作物/地区/茬口归一化
  -> 查询结构化农时模板、气候参数、农场当前茬口
  -> 调用天气工具获取实时或预报数据
  -> 调用 QuillRAG 做农业知识检索
  -> 合并公共知识、地区知识和用户私有经验
  -> 生成带依据、带风险提示、带不确定性说明的回复
```

结构化层负责稳定输出“什么时候做什么”。向量层负责解释“为什么这么做、遇到异常天气怎么办、病虫害如何识别和处理”。用户经验层负责把农户自己的地块、品种、历史茬口和实际结果纳入建议。

## 5. 服务基准与扩展顺序

农业知识库第一阶段的服务基准是：

```text
地区：江苏省徐州市睢宁县，优先魏集镇等西瓜主产区
作物：西瓜
设施：大棚、多膜覆盖、小拱棚等设施栽培
茬口：春季、春提早、抢早上市
问题：育苗、定植、授粉、膨瓜、采收、倒春寒、连阴雨、病虫害、肥水
```

资料分级必须围绕这个服务基准判断：

| 等级 | 定义 | 入库策略 |
| --- | --- | --- |
| 核心资料 | 睢宁本地、徐州本地，且直接涉及设施西瓜、春提早、农时或管理事实 | 可进入结构化模板和核心 RAG |
| 本地补充 | 徐州本地案例、气象服务、合作社报道、种植户经验 | 可进入 RAG，但必须标注案例性质 |
| 区域 fallback | 江苏、淮北平原、苏北相近气候区的设施西瓜资料 | 只作为 fallback，不能伪装成睢宁本地结论 |
| 通用参考 | 全国论文、外省资料、通用设施西瓜研究 | 默认仅 source index，只有包含明确参数且被本地资料交叉验证后才可入库 |
| 拒绝资料 | 来源不明、广告软文、泛泛种植文章、无法打开正文、无法抽取事实 | 不入库 |

第一阶段不是“收集足够多的农业文章”，而是构建能回答睢宁设施西瓜关键问题的事实证据链。一个高质量本地资料优先于十篇外地泛文章。

后续扩展顺序：

1. 睢宁设施西瓜。
2. 丰县、沛县、铜山等徐州县区设施西瓜。
3. 邳州大蒜、新沂水蜜桃等徐州特色作物。
4. 徐州范围内豆角、小瓜、草莓等设施蔬果。
5. 江苏其他城市只作为后续复制验证，不进入第一阶段范围。

## 6. Qdrant Collection 设计

第一版使用 1 个 Qdrant 服务，优先建立 2 个 collection。

```text
public_agri_knowledge
farm_private_knowledge
```

### 6.1 `public_agri_knowledge`

存放公共农业知识：

- 农技文章。
- 地方农业技术资料。
- 作物栽培标准。
- 病虫害识别和防治资料。
- 品种、肥水、整枝、授粉、采收等管理资料。
- 本地案例和农技服务记录。

睢宁设施西瓜、徐州其他县区作物、后续豆角、小瓜、草莓都进入同一个 collection，通过 metadata 过滤，不按县区或作物拆 collection。

### 6.2 `farm_private_knowledge`

存放用户或农场私有经验：

- 用户历史茬口总结。
- 地块经验。
- 品种表现。
- 病害发生记录。
- 用户自己上传或沉淀的农事资料。

该 collection 必须包含 `farm_id`、`user_id` 或租户隔离字段。公共检索不能访问私有 collection，私有检索结果也不能泄漏到其他农场。

### 6.3 可选后续 Collection

当数据体量和职责明确后，可增加：

```text
regional_agri_profile
agri_glossary
```

`regional_agri_profile` 存放地区说明性资料，例如城市气候综述、土壤条件、设施类型资料。第一版也可以直接放在 `public_agri_knowledge`，用 `topic=气候` 和 `source_type=地区资料` 区分。

`agri_glossary` 存放作物别名、病虫害同义词、地方俗称和术语解释。如果术语规模较小，应优先结构化存表，不急于单独建 collection。

### 6.4 不按城市和作物拆 Collection 的原因

城市、作物、茬口、设施类型本质是过滤条件，适合放在 Qdrant payload metadata 中。如果按“徐州西瓜”“徐州草莓”“宿迁西瓜”拆 collection，会导致：

- 通用西瓜知识被重复入库。
- 新增城市时需要复制大量公共资料。
- 跨地区 fallback 很难做。
- 评测和运维对象数量膨胀。

只有以下情况才考虑拆 collection：

- 使用不同 embedding 模型或向量维度。
- 权限和生命周期完全不同。
- 数据量大到单 collection 维护困难。
- 检索策略差异非常大。

## 7. Metadata Schema

每个 chunk 必须带稳定 metadata。第一版字段如下：

| 字段 | 类型 | 示例 | 说明 |
| --- | --- | --- | --- |
| `crop` | string | `watermelon` | 归一化作物编码 |
| `crop_alias` | string/list | `西瓜` | 原文或用户常用名称 |
| `crop_group` | string | `瓜类` | 作物大类，用于 fallback |
| `region_country` | string | `CN` | 国家 |
| `region_province` | string | `江苏` | 省份 |
| `region_city` | string/null | `徐州` | 城市 |
| `region_county` | string/null | `睢宁` | 县区 |
| `region_town` | string/null | `魏集镇` | 乡镇，可选 |
| `climate_zone` | string/null | `淮北平原` | 气候或农区分区 |
| `season` | string | `春季` | 季节 |
| `crop_cycle` | string | `春提早` | 茬口类型 |
| `facility` | string | `大棚` | 露地、大棚、小拱棚、日光温室等 |
| `planting_mode` | string/null | `育苗移栽` | 直播、育苗移栽、基质栽培等 |
| `generic_stage` | string | `定植` | 跨作物通用阶段 |
| `crop_stage` | string | `伸蔓` | 作物特有阶段 |
| `topic` | string | `肥水` | 日程、气候、肥水、病虫害、品种、风险等 |
| `source_type` | string | `地方农技` | 标准、论文、农技文章、案例、气候资料 |
| `authority_score` | int | `4` | 来源权威度，1-5 |
| `valid_from` | string/null | `2024` | 资料适用开始时间 |
| `valid_to` | string/null | null | 资料适用结束时间 |
| `source_url` | string/null | `https://...` | 来源链接 |
| `source_title` | string | `徐州西瓜春提早栽培技术` | 来源标题 |

Qdrant payload index 第一批应覆盖：

```text
crop
crop_group
region_province
region_city
region_county
region_town
climate_zone
season
crop_cycle
facility
generic_stage
crop_stage
topic
source_type
authority_score
farm_id
user_id
```

## 8. 多作物设计

不同作物不能强行套同一套生育阶段。系统同时保留通用阶段和作物特有阶段。

| 作物 | `crop` | 通用阶段示例 | 作物特有阶段示例 |
| --- | --- | --- | --- |
| 西瓜 | `watermelon` | 育苗、定植、开花结果、采收 | 伸蔓、授粉、膨瓜 |
| 豆角 | `cowpea` | 播种、营养生长、开花结果、采收 | 抽蔓、结荚、连续采收 |
| 小瓜 | `zucchini` 或待确认 | 育苗、定植、开花结果、采收 | 结瓜、连续采收 |
| 草莓 | `strawberry` | 定植、开花结果、采收 | 花芽分化、保温促成、连续采收 |

“小瓜”是地方俗称，必须经过作物别名表归一化。小瓜、豆角、草莓不进入第一阶段核心范围，只作为后续扩展对象保留 schema 能力。

作物别名表示例：

| alias | crop | region_city | confidence | 说明 |
| --- | --- | --- | --- | --- |
| 西瓜 | `watermelon` | null | 1.0 | 通用 |
| 豆角 | `cowpea` | null | 0.9 | 可兼容豇豆 |
| 豇豆 | `cowpea` | null | 1.0 | 标准别名 |
| 小瓜 | `zucchini` | 徐州 | 0.7 | 需允许用户确认 |
| 草莓 | `strawberry` | null | 1.0 | 通用 |

## 9. 结构化事实层

以下数据不应只放向量库，应在 Farm Manager 侧结构化保存。

### 9.1 作物茬口日程模板

用于稳定回答“什么时候做什么”。

```text
crop_calendar_template
  id
  crop
  region_province
  region_city
  region_county
  region_town
  climate_zone
  season
  crop_cycle
  facility
  planting_mode
  stage
  date_window_start
  date_window_end
  relative_day_start
  relative_day_end
  condition
  risk
  source_refs
  status
```

示例：

```text
region_city=徐州
crop=watermelon
season=春季
crop_cycle=春提早
facility=大棚
stage=定植
date_window=3月中旬-3月下旬
condition=棚内夜温稳定，幼苗达到适宜苗龄
risk=倒春寒、缓苗慢
```

### 9.2 地区气候参数

用于判断地区适宜性和季节风险。

```text
regional_climate_profile
  region_province
  region_city
  region_county
  region_town
  climate_zone
  monthly_avg_temp
  monthly_avg_precipitation
  frost_free_period
  last_frost_window
  extreme_risk_notes
  data_source
  updated_at
```

### 9.3 作物阈值参数

用于结合实时天气做风险判断。

```text
crop_environment_threshold
  crop
  stage
  min_night_temp
  optimal_day_temp
  optimal_night_temp
  high_temp_risk
  low_temp_risk
  humidity_risk
  notes
```

## 10. 检索流程

### 10.1 查询归一化

用户问：“睢宁春提早大棚西瓜什么时候定植？”

系统先解析为：

```json
{
  "region_city": "徐州",
  "region_county": "睢宁",
  "region_province": "江苏",
  "crop": "watermelon",
  "season": "春季",
  "crop_cycle": "春提早",
  "generic_stage": "定植"
}
```

如果用户只说“小瓜”，先查别名表。低置信时向用户澄清，不直接编造作物类型。

### 10.2 结构化查询

优先查询：

- 当前农场所在城市和地块。
- 当前作物茬口。
- `crop_calendar_template`。
- `regional_climate_profile`。
- 近期天气或历史天气工具。

### 10.3 RAG 检索

第一轮精确过滤：

```json
{
  "collection": "public_agri_knowledge",
  "mode": "hybrid",
  "top_k": 10,
  "filters": {
    "crop": "watermelon",
    "region_city": "徐州",
    "region_county": "睢宁",
    "season": "春季",
    "crop_cycle": "春提早"
  }
}
```

如果结果不足，按以下顺序放宽：

1. `region_county=睢宁` 放宽到 `region_city=徐州`。
2. `region_city=徐州` 放宽到 `climate_zone=淮北平原` 或 `region_province=江苏`。
3. 保留 `crop=watermelon` 和 `facility=大棚/设施`，检索江苏设施西瓜资料。
4. 保留 `crop=watermelon`，检索通用设施西瓜资料；该层级默认只作解释性补充。

回复中必须说明依据层级，例如“睢宁本地资料不足，以下结合徐州案例、江苏设施西瓜资料和通用设施栽培资料判断”。

### 10.4 公共知识与私有经验合并

当用户登录且有当前农场时，可额外查：

```json
{
  "collection": "farm_private_knowledge",
  "mode": "hybrid",
  "top_k": 5,
  "filters": {
    "farm_id": "<current_farm_id>",
    "crop": "watermelon"
  }
}
```

私有经验只影响该农场建议，不回写公共知识库。模型回复要区分“公共农技资料”和“你家地块历史记录”。

## 11. QuillRAG 适配要求

现有 QuillRAG 可以作为底座，但农业知识库需要补强以下能力：

1. `/ingest` 支持 `metadata` JSON 字段，允许传入完整农业 metadata。
2. 解析器把文档级 metadata 合并到每个 chunk 的 `extra`，写入 Qdrant payload。
3. `/retrieve` 过滤语法支持等值、多值和基础范围条件。
4. 为高频 payload 字段创建 Qdrant payload index。
5. UI 的 ingest 页面支持填写或粘贴 metadata JSON。
6. 评测数据集支持按 `crop/region/season/topic` 分组统计召回质量。

第一版如只走服务层内部调用，可以先绕开 UI，只保证 ingest API 和 retrieve API 支持 metadata。

## 12. 文档体量估算

### 12.1 睢宁设施西瓜 MVP

以“徐州睢宁 + 设施西瓜 + 春季/春提早”为例，第一批追求小而精：

```text
核心源文档：10-25 篇
fallback 源文档：10-20 篇
chunk：200-800 个
```

建议构成：

| 类型 | 数量 |
| --- | ---: |
| 睢宁/徐州本地设施西瓜资料 | 5-12 篇 |
| 睢宁魏集、沛县、丰县等本地案例 | 5-10 条 |
| 徐州气象、倒春寒、防寒服务资料 | 3-8 份 |
| 江苏/淮北设施西瓜 fallback 资料 | 8-15 篇 |
| 病虫害、肥水、授粉等参数型资料 | 5-10 篇 |

### 12.2 徐州特色作物扩展

睢宁设施西瓜跑通后，再逐个扩展本地特色作物，不一次性并行采集。

```text
每个新作物核心源文档：10-30 篇
每个新作物 fallback 源文档：10-20 篇
```

建议构成：

| 知识包 | 数量 |
| --- | ---: |
| 丰县、沛县、铜山设施西瓜 | 每县区 10-20 篇 |
| 邳州大蒜 | 20-40 篇 |
| 新沂水蜜桃 | 20-40 篇 |
| 徐州设施豆角/小瓜/草莓 | 每作物 15-30 篇 |

该体量对 Qdrant 和 QuillRAG 较轻，核心风险不是容量，而是 metadata 标注质量和来源可靠性。

### 12.3 新增地区成本

新增一个徐州县区或乡镇时，不复制所有作物通用知识。只补：

```text
当地气候和农区资料：3-10 篇
当地设施和土壤资料：3-10 篇
目标作物本地茬口模板：每作物 5-15 篇
本地案例：按可获得数据补充
```

如果新县区与睢宁处于相近气候和设施条件，可复用徐州/江苏/淮北 fallback 资料。

## 13. 知识入库流程

1. 采集资料：优先官方农技、地方农科院、农业标准、合作社案例、气象资料。
2. 来源登记：记录标题、URL、发布日期、地区、权威度和适用范围。
3. 人工或半自动标注 metadata。
4. 调用 QuillRAG `/ingest` 入库。
5. 建立结构化农时模板和气候参数。
6. 编写 golden set，验证典型问题召回是否命中正确来源。
7. 进入可用状态前，至少通过核心作物、核心阶段、核心城市的检索评测。

## 14. 知识文档采集 SOP

知识采集不从“到处找文章”开始，而是从第一版要回答的问题倒推资料清单。第一版采集范围固定为：

```text
地区：徐州睢宁，优先魏集镇等西瓜主产区；必要时扩展到徐州其他县区、江苏、淮北平原
作物：西瓜
场景：春季、春提早、设施栽培为主
问题：日程、气候、定植、肥水、病虫害、采收、异常天气
```

### 14.1 资料类型

资料按 8 类收集，保证后续回答不是只有泛泛文章。

| 类型 | 内容 | 主要用途 |
| --- | --- | --- |
| 地区气候资料 | 徐州温度、降雨、霜期、极端天气、季节风险 | 结构化气候参数、天气风险判断 |
| 茬口日程 | 播种、育苗、定植、开花、坐果、采收窗口 | 结构化农时模板 |
| 品种资料 | 适合设施、春季、本地市场的品种说明 | 品种推荐、用户澄清 |
| 栽培管理 | 整枝、吊蔓、授粉、温湿度、通风、保温 | RAG 解释性知识 |
| 肥水管理 | 底肥、追肥、水肥一体化、控水节点 | RAG + 阈值模板 |
| 病虫害 | 常见病虫、发生时期、识别特征、防治方法 | 病虫害问答与风险提示 |
| 应急风险 | 倒春寒、连阴雨、高温、裂果、畸形果、沤根 | 天气联动建议 |
| 本地案例 | 睢宁、魏集、徐州周边农技服务、合作社经验、基地记录 | 地区化补充和案例依据 |

### 14.2 来源优先级

资料按可信度分层。不同来源可以同时入库，但 metadata 必须体现 `source_type` 和 `authority_score`，回答合成时优先使用高权威来源。

| 等级 | 来源 | 用法 |
| --- | --- | --- |
| S | 国家、省、市农业农村部门，农技推广总站，气象部门，地方标准 | 可作为结构化日程、气候参数和关键建议依据 |
| A | 江苏省农科院、中国农科院、农业大学、正式论文、技术规程 | 可作为主要 RAG 依据和参数校验来源 |
| B | 合作社、基地案例、地方农技站文章、示范园记录 | 可作为本地经验和案例补充 |
| C | 公众号、短视频、论坛经验、商业平台文章 | 只做参考，不单独作为权威建议依据 |

低权威资料入库时必须降权，不能覆盖 S/A 级资料。广告软文、来源不明、发布时间不清、带明显营销导向的内容默认不入库。

### 14.3 资料登记表

每找到一篇资料，先登记再决定是否入库。登记表可以先用表格或 JSONL，后续进入后台管理。

| 字段 | 示例 | 说明 |
| --- | --- | --- |
| `source_title` | `徐州西瓜春提早栽培技术` | 资料标题 |
| `source_url` | `https://example.com/article` | 来源链接或文件路径 |
| `source_type` | `地方农技` | 标准、论文、农技文章、案例、气候资料等 |
| `authority_score` | `4` | 1-5 分 |
| `publish_date` | `2025-03-12` | 发布日期，不明则为空 |
| `crop` | `watermelon` | 归一化作物编码 |
| `crop_alias` | `西瓜` | 原文作物名称 |
| `region_province` | `江苏` | 适用省份 |
| `region_city` | `徐州` | 适用城市，不限城市则为空 |
| `region_county` | `睢宁` | 适用县区，不限县区则为空 |
| `region_town` | `魏集镇` | 适用乡镇，不限乡镇则为空 |
| `climate_zone` | `淮北平原` | 适用农区或气候区 |
| `season` | `春季` | 适用季节 |
| `crop_cycle` | `春提早` | 茬口 |
| `facility` | `大棚` | 露地、大棚、小拱棚、日光温室等 |
| `topic` | `日程` | 日程、气候、肥水、病虫害、风险等 |
| `valid_from` | `2024` | 适用开始年份 |
| `valid_to` | null | 适用结束年份 |
| `use_for_calendar` | true | 是否可抽取结构化农时 |
| `use_for_vector` | true | 是否进入向量库 |
| `notes` | `与江苏设施西瓜资料一致` | 人工备注 |

### 14.4 入库判断

不同内容进入不同层，不能把所有资料都无差别丢进向量库。

| 内容 | 存储位置 |
| --- | --- |
| 播种窗口、定植窗口、采收窗口、苗龄、温度阈值 | 结构化表 + source_refs |
| 月均温、降雨量、霜期、极端天气风险 | `regional_climate_profile` |
| 睢宁/徐州本地栽培解释、管理方法、病虫害说明、异常天气处理 | `public_agri_knowledge` 核心知识 |
| 江苏/淮北/全国通用解释性资料 | `public_agri_knowledge` fallback 或仅 source index |
| 合作社、示范园、用户地块经验 | 公共案例或 `farm_private_knowledge`，按来源和权限区分 |
| 来源不明、广告软文、互相矛盾且无权威来源支撑的内容 | 暂不入库 |

如果同一问题存在冲突资料，优先采用高权威、近年份、地区更接近、设施类型更一致的来源；冲突不能静默合并，必须在登记表备注中记录。

### 14.5 第一批采集顺序

第一版按最短可验证链路推进：

1. 徐州气候资料、江苏/淮北设施农业资料。
2. 睢宁、魏集、徐州西瓜春提早资料。
3. 睢宁/徐州本地案例和合作社经验。
4. 江苏/淮北设施西瓜 fallback 资料。
5. 西瓜病虫害、肥水、授粉、采收参数专题。
6. 用户或一线农户经验访谈。

睢宁设施西瓜未通过 golden set 前，不进入豆角、小瓜、草莓等新作物采集。

### 14.6 第一批采集体量

第一批目标不是大而全，而是覆盖核心问题。

| 资料包 | 建议数量 |
| --- | ---: |
| 睢宁/徐州本地设施西瓜资料 | 10-25 篇 |
| 睢宁/徐州本地案例 | 5-10 条 |
| 徐州气象和防寒防灾资料 | 3-8 篇 |
| 江苏/淮北 fallback 资料 | 10-20 篇 |
| 通用设施西瓜参数资料 | 5-10 篇 |

采集完成后预计约 30-60 篇源文档，切分后约 200-800 个 chunk。第一批宁可少而准，不用低价值文章凑数量。

## 15. 回答合成规则

Agent 生成农业建议时必须遵守：

- 明确区分“结构化日程模板”“实时天气”“RAG 资料”“用户私有经验”。
- 如果只检索到通用资料，不能伪装成本地资料。
- 如果地区或作物别名不确定，先澄清。
- 对温度、日期、用药、肥料等高风险建议，优先给范围和注意事项，不给绝对化结论。
- 对缺少来源支撑的内容，回复中说明“当前资料不足”。

## 16. 验收标准

- [ ] 能用同一个 `public_agri_knowledge` collection 检索睢宁设施西瓜核心资料和江苏 fallback 资料。
- [ ] 能按 `crop/region_city/region_county/region_town/season/crop_cycle/facility/stage/topic` 做 metadata 过滤。
- [ ] 睢宁设施西瓜春提早问题优先命中睢宁或徐州资料；本地资料不足时能按规则 fallback。
- [ ] 农时日期来自结构化模板，不只来自向量检索结果。
- [ ] 私有经验必须按 `farm_id/user_id` 隔离，不能出现在其他农场检索中。
- [ ] 至少建立 20 条农业 RAG golden set，覆盖睢宁、设施西瓜、气候、病虫害、日程、肥水、风险、采收。
- [ ] Agent 回复能说明资料层级和不确定性，不编造“已查询”事实。

## 17. 分阶段落地

### Phase 1：睢宁设施西瓜知识包

- 建立 `public_agri_knowledge`。
- 建立农业 metadata 标准。
- 覆盖睢宁设施西瓜、徐州 fallback、江苏/淮北 fallback。
- 建立基础农时模板和气候参数。
- 完成 QuillRAG metadata 透传。

### Phase 2：农场私有经验

- 建立 `farm_private_knowledge`。
- 把用户历史茬口总结、地块经验、品种表现纳入私有检索。
- 在回复中区分公共资料和私有经验。

### Phase 3：徐州县区和特色作物扩展

- 新增丰县、沛县、铜山等县区设施西瓜资料。
- 扩展邳州大蒜、新沂水蜜桃等徐州特色作物。
- 按县区和作物组合扩充 golden set。

### Phase 4：质量治理

- 引入检索评测报表。
- 统计每个作物、城市、阶段的召回命中率。
- 对低质量或过期资料降权。
- 引入人工审核流程，避免错误农技资料进入高权威知识包。

## 18. 设计结论

农业知识库不应设计成“每个城市一个库”或“每个作物一个库”。第一版应采用：

```text
1 个 Qdrant 服务
2 个核心 collection
城市、作物、茬口、设施、阶段全部作为 metadata filter
稳定农时和气候参数结构化存储
RAG 负责解释性知识和证据补充
```

这个方案能先支撑“徐州 + 西瓜/豆角/小瓜/草莓 + 春季设施栽培”，也能在后续新增城市和作物时通过补资料、补 metadata、补结构化模板扩展，而不是重建知识库。
