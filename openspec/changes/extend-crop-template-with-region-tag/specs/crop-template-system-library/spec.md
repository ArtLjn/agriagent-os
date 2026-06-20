## MODIFIED Requirements

### Requirement: 系统模版库
系统 SHALL 提供一份由平台维护的系统模版库，以 `farm_id IS NULL` 标识，用户模版仍为 `farm_id = 用户 farm`。系统模版 SHALL 支持地域维度：每条系统模版 SHALL 携带 `region_tag` 字段（VARCHAR(32)，可为 NULL），约定取值为拼音小写的地域名（如 `xuzhou` / `hainan` / `guangdong`），NULL 视为 `default`。

系统 SHALL 通过单次 SQL 查询返回 `region_tag IN (user_region, 'default', NULL)` 的候选，按 `user_region → default → NULL` 优先级排序，应用层取首条作为推荐、其余作为 fallback。

系统 SHALL 禁止 LLM 自动生成模版塞入系统库（继承原 requirement）；地域变体 SHALL 由人工调研（如 WebSearch）后通过 seed 脚本录入，seed metadata SHALL 记录数据来源链接。

#### Scenario: 用户地域有匹配的系统模版
- **WHEN** 用户（region=xuzhou）调用 `GET /crops/templates/system?crop_name=西瓜&region=xuzhou`
- **THEN** 系统返回的列表中 `region_tag=xuzhou` 的模版排在 `region_tag=default` 之前

#### Scenario: 用户地域无匹配时 fallback 到 default
- **WHEN** 用户（region=hainan）查询西瓜系统模版，但系统库只有 `default` 和 `xuzhou` 两个变体
- **THEN** 系统返回 `default` 模版作为推荐，不返回 `xuzhou` 也不报错

#### Scenario: 现有数据 NULL 视为 default
- **WHEN** 系统库中某条模版 `region_tag IS NULL`
- **THEN** 该模版在查询时与 `region_tag='default'` 等价，参与 default fallback

#### Scenario: Skill 推荐按用户 region 优先
- **WHEN** `create_crop_template` Skill 精确查重未命中，且用户 region 有匹配的系统模版
- **THEN** Skill SHALL 优先推荐"导入 region 匹配的系统模版"；用户拒绝或无匹配时才走 LLM 兜底

#### Scenario: 导入副本保留 region_tag
- **WHEN** 用户从系统库导入一条 `region_tag='xuzhou'` 的模版到自己的模版库
- **THEN** 用户副本 SHALL 携带 `region_tag='xuzhou'`，便于后续追溯

### Requirement: 模版导入即副本
系统 SHALL 采用副本模式导入系统模版：从 `farm_id IS NULL` 复制一条到 `farm_id = 用户 farm`，用户可自由编辑。导入时 SHALL 一并复制 `region_tag` 字段到用户副本，便于后续追溯；用户可自由修订阶段天数等其他字段。

副本 SHALL 复用现有精确查重逻辑避免用户多次导入产生重复。

#### Scenario: 跨 region 重复导入
- **WHEN** 用户已导入 `region_tag='default'` 的西瓜模版，再次尝试导入 `region_tag='xuzhou'` 的西瓜模版
- **THEN** 系统 SHALL 视为不同模版（region_tag 不同），允许导入；用户模版库同时存在两个变体

#### Scenario: 同 region 重复导入
- **WHEN** 用户已导入 `region_tag='xuzhou'` 的西瓜模版，再次尝试导入同 region 的同名模版
- **THEN** 系统 SHALL 命中精确查重，告知用户"已有相同模版"，不新建

## ADDED Requirements

### Requirement: 用户 region 解析
系统 SHALL 从用户 `UserSettings.default_city` 解析 region_tag，通过城市 → region_tag 映射表查询。映射表 SHALL 在代码中 hardcode（路径如 `backend/app/seeds/region_mapping.py`），未匹配的城市 SHALL fallback 到 `default`，不抛错。

#### Scenario: 已映射城市
- **WHEN** 用户 `default_city='徐州'`
- **THEN** `resolve_region('徐州')` 返回 `'xuzhou'`

#### Scenario: 未映射城市 fallback
- **WHEN** 用户 `default_city='某未覆盖城市'`
- **THEN** `resolve_region` 返回 `'default'`，不抛错

#### Scenario: 用户未设置城市
- **WHEN** 用户 `default_city` 为 NULL 或空字符串
- **THEN** `resolve_region` 返回 `'default'`

### Requirement: region_tag 命名约定
系统 SHALL 使用拼音小写作为 `region_tag` 命名约定（如 `xuzhou` / `hainan` / `guangdong`），不使用行政区码、英文译名或拼音简写。CI SHALL 通过 lint 检查确保 seed 数据符合约定。

#### Scenario: seed 数据命名检查
- **WHEN** seed 脚本写入 `region_tag='XZ'` 或 `region_tag='32-03'`
- **THEN** CI lint 报错，要求改为 `'xuzhou'`

#### Scenario: 已有命名不在约定内
- **WHEN** 现有数据存在非约定命名（如旧数据 `region_tag='Xuzhou'`）
- **THEN** 不强制迁移，但 seed 与新写入 SHALL 严格按约定
