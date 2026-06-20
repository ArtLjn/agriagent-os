## Context

当前系统已经有 `users`、`user_settings`、`farms` 三类数据：`users` 表示账号身份，`user_settings.default_city/default_lat/default_lon` 表示默认天气位置，`farms.location` 表示农场位置且通过 `farm_id` 隔离茬口、农事、账务和 Agent 上下文。MVP 用户主要是小农场主，经营地区与用户常住/所在城市通常一致，但农事天气需要稳定地跟随经营地区，而不是跟随手机实时位置。

现状的问题是产品层把“所在城市”和“默认天气”拆成两个设置，后端天气上下文又优先读取 `user_settings`，导致农场位置、用户城市、默认天气三个概念容易互相覆盖。

## Goals / Non-Goals

**Goals:**

- 产品上合并“所在城市”和“默认天气”为单一“经营地区/农场地区”概念。
- 后端以当前用户默认农场的经营地区作为天气和农事建议的权威位置来源。
- 首次定位只初始化缺失的经营地区，初始化后不随用户移动自动覆盖。
- 保留 `farm_id` 和 Farm 作为业务数据边界，继续支撑茬口、农事、账务、Agent 上下文隔离。
- 兼容已有 `user_settings.default_city/default_lat/default_lon` 数据，支持平滑回填和兜底。

**Non-Goals:**

- 不在本 change 引入多农场切换或跨城市多基地管理。
- 不要求实时后台定位或持续位置追踪。
- 不强制删除 `user_settings.default_city/default_lat/default_lon` 字段；字段可在兼容期保留。
- 不改变用户认证、角色权限、账务和茬口核心模型。

## Decisions

### 1. Farm location 是天气主来源

天气查询、农场摘要和 AI 今日建议 SHALL 优先使用当前登录用户关联 Farm 的经营地区。实现上可以先使用 `farms.location` 表示城市/区县文本；若需要更准确天气，新增或复用农场经纬度字段作为主坐标来源。

替代方案是继续以 `user_settings.default_city/default_lat/default_lon` 为主。该方案实现最小，但会把个人偏好误当成农场业务位置，用户移动或换设备时容易误覆盖农事天气。

### 2. UserSetting location 作为兼容兜底

兼容期内保留 `user_settings.default_city/default_lat/default_lon`。读取天气位置时优先级为：

1. 用户在本次请求中明确指定的城市或坐标。
2. 当前 Farm 的经纬度或 `location`。
3. 当前用户 `user_settings` 中的默认城市/坐标。
4. 系统默认坐标。

这样可以让旧用户继续拿到天气，同时逐步把位置语义迁移到 Farm。

### 3. 首次定义为“默认农场缺少经营地区”

移动端不以安装次数、设备状态或注册事件定义首次。系统 SHALL 以服务端当前账号默认 Farm 是否缺少经营地区作为触发条件：

- 新注册用户默认 Farm 无地区，首次进入主流程时触发定位初始化。
- 老用户、换手机用户、重装 App 用户只要 Farm 已有地区，就不再次自动定位覆盖。
- 老数据用户如果 Farm 缺少地区，则可触发一次补全。

### 4. 定位只初始化，不持续覆盖

GPS 授权结果只用于初始化缺失经营地区，或在用户主动点击“重新定位/修改经营地区”时更新。App 不根据用户移动自动改变经营地区。

该决策降低隐私风险，也避免用户去市场、县城或外地时把农场天气误改成当前位置。

### 5. 设置页只展示一个位置入口

个人页/设置页不再同时展示“所在城市”和“默认天气”。MVP 展示为“经营地区”或“农场地区”，天气位置可显示“跟随经营地区”但不作为单独可编辑字段。

## Risks / Trade-offs

- [Risk] `farms.location` 只有文本，天气 Provider 需要经纬度时仍要解析城市。→ Mitigation: 短期继续用城市名或旧 user_settings 坐标兜底；中期为 Farm 增加 lat/lon 并回填。
- [Risk] 旧数据只存在 `user_settings.default_city`，Farm 无 location。→ Mitigation: 迁移时按一人一农场关系回填 Farm；读取链路保留 user_settings 兜底。
- [Risk] 用户拒绝定位后无法拿到精准天气。→ Mitigation: 允许手动选择经营地区；拒绝定位不阻塞进入 App。
- [Risk] 用户真实有跨城市种植需求。→ Mitigation: MVP 明确不支持多农场位置；后续通过多 Farm/基地能力扩展，而不是恢复用户城市和天气城市双入口。
- [Risk] 缓存未失效导致 AI 建议继续使用旧地区。→ Mitigation: 修改 Farm 经营地区后必须失效 farm context、天气缓存和相关 Agent 上下文缓存。

## Migration Plan

1. 后端增加统一位置解析函数，按“请求指定 > Farm > UserSetting > 系统默认”返回城市和坐标。
2. 对已有一人一农场数据执行回填：当 Farm 缺少 location 且 user_settings 有 default_city 时，将 default_city 写入 Farm 经营地区。
3. 移动端个人页/设置页合并位置入口，隐藏独立默认天气设置。
4. 首次进入主流程时读取当前用户 farm 信息；仅当经营地区为空时触发定位初始化。
5. 手动修改经营地区时写入 Farm，并清理相关上下文缓存。
6. 保留旧 `/settings` location 字段一段兼容期；新客户端不再把它作为主天气配置。

Rollback 时可继续使用 `user_settings.default_city/default_lat/default_lon` 兜底天气，不影响账号登录和核心农事数据。

## Open Questions

- Farm 是否在本 change 内新增 `lat/lon` 字段，还是先复用 `location` 文本并继续保留 user_settings 坐标兜底？
- 移动端经营地区更新接口使用现有 `/auth/me`、`/settings`，还是新增更明确的 Farm settings API？
- “经营地区”在 UI 上最终采用“经营地区”还是“农场地区”文案？
