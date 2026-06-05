## 1. 鉴权分类落地

- [ ] 1.1 在 `admin_config.py` 的 router 上添加 `require_admin` 管理员鉴权
- [ ] 1.2 在 `admin_trace.py` 的 router 上添加 `require_admin` 管理员鉴权
- [ ] 1.3 在 `admin.py` 的 router 上添加 `require_admin` 管理员鉴权
- [x] 1.4 确认现有 `admin_stats.py` 和 `admin_users.py` 继续使用管理员鉴权

## 2. 行为测试更新

- [ ] 2.1 更新 admin config API 测试：匿名访问返回 401，普通用户返回 403，管理员返回 200
- [ ] 2.2 更新 admin trace API 测试：匿名访问返回 401，普通用户返回 403，管理员返回 200
- [ ] 2.3 新增 guardrails log API 鉴权测试：匿名访问返回 401，普通用户返回 403，管理员返回 200
- [ ] 2.4 确认公开白名单接口匿名访问行为不变

## 3. 路由审计传感器

- [ ] 3.1 新增全量 API 路由鉴权分类测试，扫描 FastAPI 实际注册路由
- [ ] 3.2 在审计测试中维护公开接口白名单，并排除 OpenAPI/docs 内置路由
- [ ] 3.3 审计测试应识别 `get_current_user`、`get_current_farm`、`require_admin` 及 router 级依赖
- [ ] 3.4 审计失败时输出未归类路由的方法和路径

## 4. 对象级授权回归

- [ ] 4.1 抽查含路径 ID 的农场资源接口，确认服务层查询带当前 `farm.id`
- [ ] 4.2 如发现缺少跨农场访问测试，为对应接口补充 403 或 404 行为测试
- [ ] 4.3 确认 `/planting/operation-types` 仅返回内置类型且保留公开白名单

## 5. 前端兼容检查

- [x] 5.1 确认 admin-web 统一 API client 对 `/admin/*` 请求注入 Bearer token
- [x] 5.2 确认未登录或 token 过期时 admin-web 能处理 401 并回到登录态

## 6. 验证

- [ ] 6.1 运行 `ruff check . && ruff format .`
- [ ] 6.2 运行后端相关 API 测试
- [ ] 6.3 运行 `bash scripts/harness-check.sh`
- [ ] 6.4 运行 OpenSpec 状态或校验命令，确认 change apply-ready
