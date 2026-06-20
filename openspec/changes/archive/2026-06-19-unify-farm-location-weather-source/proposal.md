## Why

MVP 面向小农场主，用户所在城市与经营农场地区通常是同一概念；当前页面同时展示“所在城市”和“默认天气”会造成重复配置和语义冲突。天气、AI 今日建议和农事提醒应以稳定的经营地区为准，而不是随用户移动改变。

## What Changes

- 将产品概念收敛为“经营地区/农场地区”，用于资料展示、天气查询、AI 上下文和农事建议。
- 首次地区设置以“当前账号的默认农场缺少经营地区”为判断条件，而不是 App 首次安装或设备首次打开。
- App 在首次地区设置时请求定位权限，用当前位置初始化经营地区；初始化后不随用户移动自动覆盖，只有用户手动修改才更新。
- 天气来源优先使用当前农场经营地区；用户明确指定城市查询时仍可临时覆盖。
- 页面移除或弱化独立“默认天气”配置，天气位置默认跟随经营地区。
- 保留 Farm 作为业务数据归属和隔离边界，不因为 MVP 单农场而删除农场概念。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `user-settings-api`: 将默认城市/天气位置语义调整为经营地区初始化和用户手动修改规则。
- `user-profile`: 当前用户信息中的 farm location 成为“经营地区”的权威展示字段。
- `agent-weather-context`: 天气上下文优先使用当前农场经营地区，用户设置仅作为兼容兜底。
- `farm-context-injection`: 农场摘要中的天气使用当前农场经营地区，缓存失效覆盖经营地区变更。
- `gps-city-detection`: 定位只用于首次经营地区初始化和用户主动更新，不随用户移动自动覆盖。
- `user-settings`: 设置页合并“所在城市/默认天气”为单一经营地区入口。

## Impact

- 后端模型/API：需要明确 `farms.location` 或后续 `farms.lat/lon` 是经营地区主来源，`user_settings.default_city/default_lat/default_lon` 保留兼容或逐步迁移。
- 天气服务/Agent：WeatherSkill、farm context summary、daily advice 等读取位置来源的路径需要统一。
- 移动端：个人页/设置页文案和字段展示需要收敛，首次进入 App 的定位补全流程需要按账号农场状态判断。
- 数据迁移：已有 `user_settings.default_city/default_lat/default_lon` 可回填到当前用户默认农场；已有 `farm.location` 的用户不应被自动覆盖。
- 测试：需要覆盖首次定位初始化、已有地区不重复弹窗、手动修改后天气跟随、用户指定城市临时查询等场景。
