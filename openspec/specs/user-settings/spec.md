## Purpose

定义 user-settings 能力的行为要求。

## Requirements

### Requirement: 用户称呼设置
用户设置 SHALL 新增 `display_name` 字段，用于 Agent 回复时的个性化称呼。

#### Scenario: 设置称呼
- **WHEN** 用户在设置页输入 display_name="老李" 并保存
- **THEN** 后续 Agent 回复开头使用「老李」

#### Scenario: 默认称呼
- **WHEN** 用户未设置 display_name
- **THEN** Agent 使用默认称呼「农友」

#### Scenario: 修改称呼
- **WHEN** 用户将 display_name 从"老李"改为"李哥"
- **THEN** 后续 Agent 回复使用「李哥」

### Requirement: 经营地区作为新客户端位置主入口
系统 SHALL 将当前用户默认农场的经营地区作为新客户端的位置主入口，用于页面展示、天气查询、AI 今日建议和农事提醒。`user_settings.default_city/default_lat/default_lon` MUST NOT 在新客户端中作为独立“默认天气”入口展示。

#### Scenario: 新客户端展示经营地区
- **WHEN** 当前用户默认农场 location 为"睢宁县"且 `user_settings.default_city` 为"徐州市"
- **THEN** 新客户端个人页 SHALL 展示经营地区"睢宁县"，天气位置 SHALL 跟随"睢宁县"

#### Scenario: 农场地区缺失时兼容兜底
- **WHEN** 当前用户默认农场 location 为空且 `user_settings.default_city` 为"睢宁县"
- **THEN** 系统 MAY 使用 `user_settings.default_city` 作为显示和天气兜底，并 SHALL 支持后续回填到默认农场经营地区
