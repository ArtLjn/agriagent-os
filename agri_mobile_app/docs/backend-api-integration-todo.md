# 移动端 v2 API 接入说明

当前移动端已按 `agri_backend_v2` 的真实路由接入。运行设备必须能访问开发机局域网地址：

| 服务 | 默认地址 | 用途 |
| --- | --- | --- |
| Business REST | `http://192.168.1.13:9876/api/v2` | 登录、用户、农场、看板、天气和农事业务 |
| Agent SSE | `http://192.168.1.13:8000/api/v2` | 芽芽对话、会话历史和 HITL 审批 |

可通过 Flutter define 覆盖：

```bash
flutter run \
  --dart-define=BUSINESS_API_BASE_URL=http://192.168.1.13:9876/api/v2 \
  --dart-define=AGENT_API_BASE_URL=http://192.168.1.13:8000/api/v2
```

## 已接入

- 认证：`/auth/login`、`/auth/register`；登录后将同一 Bearer token 同步到 Business 和 Agent 客户端。
- 用户与农场：`/users/me`、`/users/me/settings`、`/farms/{farm_id}/location`。
- 首页：`/dashboard`、`/weather`、`/work-orders`、`/work-orders/labor/unsettled-summary`。
- 账本：`/cost-records`、`/cost-records/summary/yearly`、`/cost-records/cycles/{cycle_id}/profit`、`/cost-categories`、`/debts`。
- 工作台：`/crop-cycles`、`/crop-templates`、`/planting-units`、`/workers`、`/work-orders`、`/farm-logs`、`/labor/wages`。
- 城市搜索：`/locations/search?keyword=...`，列表响应统一从 `{items, total}` 读取。
- 芽芽：`POST /chat` 的事件型 SSE；会话使用 `conversation_id`，审批使用 `POST /approve` 的 `turn_id/decision/reason`。

## 当前明确不可用能力

v2 当前没有以下旧接口，移动端不会请求旧路径，也不会伪造成功：

- 每日 AI 建议、报告、技能列表 REST 接口；首页显示 v2 `/dashboard` 的事实概览，具体建议从芽芽提问。
- `/smart-fill/parse` 与智能帮填场景；记录流会显示接口不可用错误，手动记账仍走 `/cost-records`。
- 移动端版本检查接口；个人页显示“版本未知”，不触发旧 `/api/app/version` 请求。

## 服务端网络要求

Business 和 Agent 进程需要绑定可被局域网设备访问的网卡地址（例如 `0.0.0.0` 或 `192.168.1.13`），仅绑定 `127.0.0.1` 时手机无法连接；同时确认防火墙放行 `9876` 和 `8000` 端口。
