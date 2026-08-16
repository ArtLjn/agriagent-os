# 公网 Agent 鉴权配置

## 认证链路

浏览器访问 Agent 首页后，必须先调用同源 `POST /api/v2/auth/login`。Agent 将手机号和密码转发给内网 Business REST 的 `/api/v2/auth/login`，只返回 User Access JWT。之后所有会话、聊天、审批和 Trace 请求都携带：

```http
Authorization: Bearer <access_token>
```

浏览器只保存当前标签页的 `sessionStorage` 令牌。Service Token 和 Delegation Token 始终由 Agent 在服务端处理，不会返回页面。

## 生产环境变量

在 Agent 进程启动前配置，值通过部署密钥系统注入，不要写进仓库中的 YAML：

```bash
export AGENT_ENV=production
export BUSINESS_API__URL=http://127.0.0.1:9876/api/v2
export JWT_SECRET='<与 Business 相同的高强度 JWT 密钥>'
export AGENT_SERVICE_TOKEN='<Agent 调用 Business MCP 的服务令牌>'
export AGENT_DELEGATION_SECRET='<Agent 委托 JWT 密钥>'
```

`AGENT_ENV=production` 会让 `GET /api/v2/dev-users` 返回 404，避免公网泄露用户列表和可直接使用的开发令牌。Business 和 Agent 都应只监听 `127.0.0.1`，公网入口使用 [farm-manager-agent.nginx.example](../../deploy/farm-manager-agent.nginx.example) 的 HTTPS 反向代理。

## 上线验收

```bash
curl -i https://agent.example.com/api/v2/dev-users
curl -i https://agent.example.com/api/v2/conversations
curl -i https://agent.example.com/
```

预期分别为 `404`、`401` 和 `200`。首页应显示登录表单；登录成功后再加载会话。不要把 Business 的 `:9876` 或 Agent 的 `:8000` 直接暴露到公网。
