## Context

当前用户设置存储在移动端 AsyncStorage（settingsStore），换设备即丢失。后端 Agent 的天气上下文（`farm_context_service._build_weather_line`）和 `WeatherSkill` 都用硬编码坐标（苏州 31.3/120.6 或徐州 34.26/117.18），和移动端用户选择的城市不同步。

现有后端 `/settings` API 只处理 `display_name`，且存在 `Farm.name` 字段上，没有独立的设置表。

## Goals / Non-Goals

**Goals:**
- 用户城市偏好持久化到服务端，多设备同步
- 后端 Agent 使用用户真实坐标做天气建议
- 移动端首次使用时 GPS 自动定位设置默认城市
- 用户可随时通过城市选择器修改

**Non-Goals:**
- 不做推送通知系统（reminder_time / notification 等字段暂不加）
- 不做 crops 偏好同步（Agent 直接从 cycle 数据推导）
- 不做 GPS 持续追踪（只在首次定位一次）
- 不引入第三方地图 SDK（高德/百度），用客户端就近匹配

## Decisions

### 1. 新建 `user_settings` 表而非扩展 Farm 表

**选择**：新建独立表 `user_settings`（user_id unique）
**理由**：Farm 是多租户隔离实体，职责是数据分区。用户设置是偏好配置，职责不同。放在 Farm 上会导致模型膨胀。
**备选**：在 Farm 表加字段 — 耦合度高，后续加通知设置会更乱。

### 2. GPS 逆地理编码用客户端就近匹配

**选择**：移动端拿到 GPS 坐标后，遍历 `cities.ts` 列表找最近城市（Haversine 距离）
**理由**：零外部依赖，22 个城市覆盖主要农业区，农业天气到城市级精度够用。
**备选**：高德/百度逆地理编码 — 多一个 SDK + API Key，对当前规模不必要。

### 3. GPS 定位时机：注册后 + 首次无设置时

**选择**：
- 注册成功后：请求定位权限，获取坐标 → 匹配城市 → 存服务端
- 老用户首次打开：检查服务端无 `default_city` → 请求定位
- 用户拒绝定位：降级到城市列表手动选择

**理由**：注册后是自然时机，不打断核心流程。拒绝权限有降级方案。
**备选**：每次启动定位 — 农场位置固定，没必要。

### 4. 后端 Agent 读取用户坐标的路径

**选择**：`farm_context_service.build_summary(db, farm_id)` → 通过 `farm_id` 找到 `user_id` → 查 `user_settings` 表拿 lat/lon
**理由**：farm_context 已有 farm_id，链路最短。
**备选**：从 config.yaml — 就是现在的方式，不区分用户。

### 5. 数据模型设计

```python
class UserSetting(Base):
    __tablename__ = "user_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    default_city = Column(String(50), nullable=True)
    default_lat = Column(Float, nullable=True)
    default_lon = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### 6. API 设计

扩展现有 `/settings` 端点：
- `GET /settings` → 返回 `{ display_name, default_city, default_lat, default_lon }`
- `PUT /settings` → 接受 `{ display_name?, default_city?, default_lat?, default_lon? }`

不做新端点，复用现有路由，只是扩展字段。

## Risks / Trade-offs

- **[GPS 权限拒绝]** → 降级到城市列表手动选择，不影响核心功能
- **[cities 列表不全]** → 用户所在城市不在 22 城中时，就近匹配到最近的城市，精度够农业场景用
- **[user_settings 无记录时]** → 后端 Agent 降级回 config.yaml 默认坐标，不报错
- **[lat/lon 与城市名不一致]** → 以 lat/lon 为准（API 用坐标），城市名仅 UI 展示
