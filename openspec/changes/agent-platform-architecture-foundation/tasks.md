## 1. 架构文档与边界固化

- [x] 1.1 更新 `docs/architecture/overview.md`，记录目标目录、Agent 平台边界和迁移阶段
- [x] 1.2 更新 `docs/architecture/boundaries.md`，补充 Auth、Agent、Prompt、Context、Memory、Evaluation、Observability 的依赖方向
- [x] 1.3 更新 `AGENTS.md` 项目地图，加入新架构导航入口
- [x] 1.4 增加或更新架构约束检查脚本，确保新代码不把 Memory、Prompt、Context 逻辑塞回 API 或 Agent Runtime
- [x] 1.5 运行 `bash scripts/check-guide-sensor-pairing.sh` 和现有架构检查脚本，确认文档与检查规则配对

## 2. Auth 模块边界

- [x] 2.1 创建 `backend/app/modules/auth/`，包含 router、schemas、service、dependencies、password、tokens、permissions、errors
- [x] 2.2 将密码哈希与校验从 `core/security.py` 迁移到 Auth password 模块，保留兼容 re-export
- [x] 2.3 将 JWT 签发和验证迁移到 Auth tokens 模块，payload 增加 `type`、`iat`、`jti`
- [x] 2.4 将 `get_current_user` 和 `require_admin` 迁移到 Auth dependencies 模块，旧 `api/deps.py` 仅保留兼容导出
- [x] 2.5 将 `get_current_farm` 迁移到 Farm 模块依赖，确保 Auth 不直接承担农场上下文职责
- [x] 2.6 将注册创建默认农场改为调用 Farm 模块接口
- [x] 2.7 为 Auth 错误响应增加稳定 `code` 字段
- [x] 2.8 补充 Auth 单元测试和 API 测试，覆盖登录、注册、无 token、过期 token、禁用用户、管理员权限

## 3. Bootstrap 与 API 瘦身

- [x] 3.1 创建 `backend/app/bootstrap/`，迁移路由注册、middleware 注册、lifespan 初始化和后台任务启动
- [x] 3.2 将 `backend/app/main.py` 收敛为薄入口，只负责创建 app 并接入 bootstrap
- [x] 3.3 创建 Agent application use case，承接聊天、流式聊天、每日建议和报告生成入口
- [x] 3.4 将 `api/agent.py` 中的 SSE 事件编排、trace skill 查询、assistant 消息保存和 pending action 组装下沉到 Agent application
- [x] 3.5 确保 Agent API 路由只负责请求校验、依赖注入、调用 use case 和返回响应
- [x] 3.6 补充 `chat` 与 `chat/stream` 回归测试，固定响应结构和 SSE 事件格式

## 4. Agent Runtime 拆分

- [x] 4.1 创建 `backend/app/agent/runtime/`，拆出 graph factory、state、nodes、tool executor、stream events、errors
- [x] 4.2 将 `agent/graph.py` 中 LLM 节点、工具节点、路由判断和图编译拆成独立文件
- [x] 4.3 创建 `agent/planner/`，迁移意图识别、工具候选选择和任务规划逻辑
- [x] 4.4 创建 `agent/executor/`，统一 Skill 调用、并行执行、权限分级、参数校验和写操作确认
- [x] 4.5 创建 `agent/response/`，管理结构化回复、流式事件和输出格式约束
- [x] 4.6 创建 `agent/sessions/`，封装会话状态、pending action 和当前任务状态
- [x] 4.7 定义 `agent/ports.py`，Agent 通过端口访问业务模块，减少对 service 具体实现的直接依赖
- [x] 4.8 补充 Agent Runtime 单元测试，覆盖直接回复、多工具调用、工具失败、写操作 pending、quota 失败

## 5. Prompt 工程化

- [x] 5.1 创建 `backend/app/prompt/`，迁移 registry、renderer、composer 和 prompt cache
- [x] 5.2 将 prompt 片段按安全约束、角色设定、能力边界、工具约束、上下文、输出格式、风格要求分层管理
- [x] 5.3 增加 Prompt 版本注册和活跃版本选择能力
- [x] 5.4 增加 Prompt 渲染快照测试，覆盖关键 system prompt 和业务解析 prompt
- [x] 5.5 确保 Prompt 渲染只接收结构化输入，不在模板渲染阶段直接查询数据库
- [x] 5.6 增加 Prompt 变更回放评测入口，至少支持手动比较两个版本

## 6. Context 工程化

- [x] 6.1 创建 `backend/app/context/`，定义 `ContextBlock`、`ContextBundle`、Context Builder 和 token budget
- [x] 6.2 拆出 farm、cycle、weather、ledger、conversation、user settings、memory、retrieval selectors
- [x] 6.3 实现上下文优先级和预算策略，支持保留、压缩和丢弃低优先级 block
- [x] 6.4 将现有 farm context、prompt cache 和上下文预热逻辑迁移到 Context 模块
- [x] 6.5 Trace 记录每次请求的 ContextBundle 摘要、token 估算、压缩和丢弃原因
- [x] 6.6 补充 selector 单元测试和 Context Builder 集成测试

## 7. Memory 骨架

- [x] 7.1 创建 `backend/app/memory/`，包含 short_term、long_term、retrieval、consolidation、models、schemas、service、ports
- [x] 7.2 定义 Memory Service 接口：`build_context`、`observe_interaction`、`search`
- [x] 7.3 实现短时记忆最小能力：最近消息窗口、会话摘要占位、pending action 和临时任务状态
- [x] 7.4 预留长时记忆数据结构：用户偏好、农场画像、关键事实、周期摘要、账务摘要
- [x] 7.5 对话完成后提交 Memory observation event
- [x] 7.6 Context Builder 接入 Memory Service，长期记忆未启用时返回空上下文
- [x] 7.7 补充 Memory Service 单元测试，覆盖空记忆、短时记忆、观察事件和 search 空结果

## 8. Evaluation 与 Observability

- [x] 8.1 创建 `backend/app/evaluation/`，复用现有 simulation cases，整理 cases、runners、replay、metrics、reports、baselines
- [x] 8.2 定义 Agent 回放用例 schema，包含输入、上下文、预期 skill、预期写操作和回复断言
- [x] 8.3 增加 Prompt 版本对比评测，输出通过率、工具调用差异、token 成本和延迟
- [x] 8.4 增加 Context 质量指标：命中率、丢弃原因、预算使用、检索结果使用情况
- [x] 8.5 增加 Skill 调用质量指标：准确率、漏调率、误调率、参数正确率和写操作确认命中率
- [x] 8.6 将 trace 事件扩展为覆盖 context_build、prompt_render、llm_call、tool_call、memory_observe、response_format、evaluation_capture
- [x] 8.7 生成结构化评测报告，支持后续接入 CI 七道门

## 9. 验证与收尾

- [x] 9.1 运行 `ruff check . && ruff format .`
- [x] 9.2 运行 `poetry run pytest -v`
- [x] 9.3 运行架构约束、Guide+Sensor 配对和 Harness 全量检查
- [x] 9.4 检查所有旧兼容入口是否有后续删除任务或明确保留理由
- [x] 9.5 更新当前迭代计划，标记下一阶段优先从 Auth 模块化或 Bootstrap/API 瘦身开始
