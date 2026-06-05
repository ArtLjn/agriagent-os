## Purpose

定义 gps-city-detection 能力的行为要求。

## Requirements

### Requirement: 注册后自动定位
移动端 SHALL 在用户注册成功后请求 GPS 位置权限。若用户授权，获取当前经纬度并匹配到最近的城市设为默认城市。

#### Scenario: 用户授权定位
- **WHEN** 用户注册成功并授权位置权限
- **THEN** 移动端获取 GPS 经纬度，通过就近匹配算法从城市列表中找到最近城市，设为 `default_city`

#### Scenario: 用户拒绝定位
- **WHEN** 用户注册成功但拒绝位置权限
- **THEN** 移动端不请求定位，使用城市列表的默认值（列表第一个城市），用户可在设置中手动修改

### Requirement: 老用户首次定位补全
移动端 SHALL 在已登录用户首次打开时检查服务端是否有 `default_city`。若无，触发定位流程。

#### Scenario: 老用户无城市设置
- **WHEN** 已登录用户打开 App 且服务端 `user_settings` 中无 `default_city`
- **THEN** 移动端请求 GPS 定位权限，获取坐标后匹配城市并同步到服务端

#### Scenario: 老用户已有城市设置
- **WHEN** 已登录用户打开 App 且服务端已有 `default_city`
- **THEN** 跳过定位流程，直接使用服务端设置

### Requirement: 就近匹配城市算法
移动端 SHALL 使用 Haversine 公式计算 GPS 坐标与 `cities.ts` 列表中每个城市的距离，选择最近的城市。

#### Scenario: GPS 坐标附近有城市
- **WHEN** GPS 坐标为 (33.9, 117.95) 且列表中有"睢宁" (33.9, 117.95)
- **THEN** 匹配结果为"睢宁"，精确匹配

#### Scenario: GPS 坐标不在列表城市中
- **WHEN** GPS 坐标为 (33.8, 118.3) 且最近的城市是"睢宁" (33.9, 117.95)
- **THEN** 匹配结果为"睢宁"（距离最近）

### Requirement: 城市设置同步到服务端
移动端 SHALL 在城市设置变更时（GPS 自动设置或用户手动修改）同步到后端 `PUT /settings` API。

#### Scenario: 用户手动切换城市
- **WHEN** 用户在设置页选择新城市"杭州"
- **THEN** 移动端调用 `PUT /settings { default_city: "杭州", default_lat: 30.27, default_lon: 120.15 }` 同步到服务端

#### Scenario: 网络不同步时本地降级
- **WHEN** 用户修改城市但网络不可用
- **THEN** 本地先更新设置，下次网络恢复时自动同步
