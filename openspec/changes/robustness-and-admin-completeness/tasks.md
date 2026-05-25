## 1. Agent 安全防护（P0）

- [ ] 1.1 LangGraph 编译增加 `recursion_limit=15` 参数，API 层捕获 `GraphRecursionError` 返回 429
- [ ] 1.2 创建 `app/core/guardrails.py`，实现输入注入检测（正则黑名单）和输出 PII 过滤（手机号/API Key 正则替换为 `[REDACTED]`）
- [ ] 1.3 在 `advisor.py` 的 `invoke_advisor` 和 `stream_advisor` 中调用输入检测，在返回前调用输出过滤
- [ ] 1.4 `ChatRequest.message` 增加 `max_length=2000` 校验
- [ ] 1.5 `CostRecordBase.record_type` 改为枚举校验，`amount` 增加 `gt=0, le=10000000` 约束
- [ ] 1.6 `cost_service.parse_record` 增加 `json.loads` try/except 保护 + 解析后字段二次校验（record_type 枚举、amount 正数）

## 2. 全局异常处理与限流（P0）

- [ ] 2.1 在 `main.py` 注册全局异常处理器：Exception → 500、HTTPException → 原样、RequestValidationError → 422、GraphRecursionError → 429
- [ ] 2.2 安装 `slowapi`，在 `main.py` 挂载限流中间件，全局 30/分钟/IP，Agent 接口 10/分钟/IP
- [ ] 2.3 `cost.py` 和 `cost_categories.py` 的 `farm_id: int = Query(...)` 改为 `farm: Farm = Depends(get_current_farm)`
- [ ] 2.4 所有 service 层 `db.commit()` 包裹 try/except，异常时 `db.rollback()`

## 3. LangSmith 可观测性（P1）

- [ ] 3.1 `requirements.txt` 新增 `langsmith` 依赖
- [ ] 3.2 `config.yaml` 新增 `langsmith` 配置段（api_key、project_name、enabled）
- [ ] 3.3 `app/core/config.py` 新增 LangSmith 配置模型，启动时根据配置设置环境变量（`LANGSMITH_API_KEY`、`LANGCHAIN_TRACING_V2`、`LANGSMITH_PROJECT`）
- [ ] 3.4 `advisor.py` 在 `invoke_advisor` / `stream_advisor` 调用时通过 LangSmith `run_name` 和 `metadata` 标注 farm_id 和 request_type
- [ ] 3.5 验证：配置 API Key 后发起对话请求，确认 LangSmith Dashboard 能看到完整 trace

## 4. 后端 CRUD 路由补全（P1）

- [ ] 4.1 `api/crop.py` 新增 `PUT /crops/templates/:id` 和 `DELETE /crops/templates/:id` 路由
- [ ] 4.2 `api/cycle.py` 新增 `PUT /cycles/:id`、`DELETE /cycles/:id`、`POST /cycles/:id/advance-stage` 路由
- [ ] 4.3 `api/log.py` 新增 `PUT /logs/:id` 和 `DELETE /logs/:id` 路由
- [ ] 4.4 `api/cost.py` 新增 `PUT /costs/:id` 和 `DELETE /costs/:id` 路由
- [ ] 4.5 对应 service 层实现 update/delete 逻辑，删除茬口时级联处理关联 stages
- [ ] 4.6 列表接口增加分页参数（page/size），返回 `{ items, total }` 格式

## 5. Admin-web CRUD 补全（P1）

- [ ] 5.1 API 层新增 PUT/DELETE 方法（crops.ts、cycles.ts、logs.ts、costs.ts）
- [ ] 5.2 Crops 页面增加编辑 Modal（复用创建表单）和删除 Popconfirm
- [ ] 5.3 Cycles 页面增加编辑 Modal 和删除 Popconfirm；Detail 页面增加"推进到下一阶段"按钮
- [ ] 5.4 Logs 页面增加编辑 Modal 和删除 Popconfirm
- [ ] 5.5 Costs 页面增加编辑 Modal 和删除 Popconfirm

## 6. Admin-web 分页与错误处理统一（P2）

- [ ] 6.1 后端列表接口返回 `{ items, total }` 后，前端 Table 组件接入 pagination prop
- [ ] 6.2 `client.ts` 新增 Axios 响应拦截器：5xx → "服务器异常"、422 → 具体字段错误、429 → "请求过于频繁"
- [ ] 6.3 `agent.ts` 定义完整返回类型接口（ChatResponse、DailyAdviceResponse、ReportResponse、HistoryItem）
- [ ] 6.4 `weather.ts` 定义返回类型接口，移除页面内重复的 `DayWeather` 定义
- [ ] 6.5 页面组件中的 `any` 类型替换为具体接口
