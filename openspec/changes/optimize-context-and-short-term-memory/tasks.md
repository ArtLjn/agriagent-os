## 1. Context Policy 基础

- [ ] 1.1 新增 ContextPolicy 或等价策略模块，定义热上下文、工作记忆、按需检索上下文三层分类
- [ ] 1.2 为 intent 和 selected tools 建立 selector 选择规则，覆盖闲聊、天气、账务、作物、农事建议和写操作确认
- [ ] 1.3 扩展 ContextBlock metadata，支持 layer、intent_tags、required_reason 和 cache_scope 等调试字段
- [ ] 1.4 调整 ContextBuilder，使其可接收 ContextPolicy 输出的 selector 列表和 token 预算

## 2. Token 预算与 Trace

- [ ] 2.1 扩展 TokenBudget，记录 required block 超预算、压缩原因和丢弃原因
- [ ] 2.2 增加最终 prompt 预算检查，覆盖 system prompt、热上下文、工作记忆、按需上下文和工具结果
- [ ] 2.3 改进 context_build trace，记录启用 selector、候选 block、保留 block、压缩 block、丢弃 block、token 估算和耗时
- [ ] 2.4 为 TokenBudget 添加单元测试，覆盖低于预算、超过预算、required block 超预算和可压缩 block 场景

## 3. 短时记忆

- [ ] 3.1 在 Memory Service 或 conversation service 旁新增短时记忆 session 视图接口
- [ ] 3.2 实现最近消息窗口读取，按 session_id 和 farm_id 获取最近 N 轮原文消息
- [ ] 3.3 实现窗口外会话摘要读取接口，第一阶段允许无摘要时返回空结果
- [ ] 3.4 将 pending action 和临时任务状态纳入短时记忆 block
- [ ] 3.5 为短时记忆添加测试，覆盖新会话、历史低于窗口、历史超过窗口、pending action 存在和过期

## 4. Agent Runtime 接入

- [ ] 4.1 在 agent/runtime 主链路中构建 ContextBundle，替代仅依赖 build_farm_runtime_context 的固定四字段路径
- [ ] 4.2 保持兼容渲染 system_base 所需变量，确保 display_name、farm_location、farm_coords、active_crops 继续可用
- [ ] 4.3 将 ConversationSelector 或短时记忆 block 接入 LangGraph messages 构造，替代纯固定条数历史注入
- [ ] 4.4 将 selected tools 传入 ContextPolicy，确保天气、账务、作物和日志上下文按需启用
- [ ] 4.5 保留回退开关，允许恢复旧的 farm runtime context 和 sliding_window_compact 路径

## 5. 用户与农场上下文准确性

- [ ] 5.1 明确用户上下文来源顺序：认证用户、当前 farm、UserSetting、Farm.location，不允许从自然语言推断身份或位置
- [ ] 5.2 调整用户位置注入规则，默认城市优先于 Farm.location，坐标优先供天气 provider 使用
- [ ] 5.3 增加缺失位置处理测试，验证天气问题在无 location 时追问或走安全错误路径
- [ ] 5.4 更新 farm context selector，确保普通闲聊只注入热上下文，业务问题才注入摘要候选

## 6. 缓存失效

- [ ] 6.1 新增统一 context/prompt cache invalidation helper
- [ ] 6.2 在用户设置变更后清理相关 farm context cache 和 prompt cache
- [ ] 6.3 在种植周期创建、更新、删除和推进阶段后清理相关缓存
- [ ] 6.4 在账务、债务和农事日志写操作后清理相关缓存
- [ ] 6.5 添加缓存失效测试，覆盖用户设置、活跃茬口、账务和日志变更

## 7. 验证与文档

- [ ] 7.1 添加 ContextBuilder 集成测试，覆盖不同 intent 下 selector 选择和 ContextBundle 输出
- [ ] 7.2 添加 Agent Runtime 集成测试，验证追问、天气、账务和闲聊场景的上下文注入差异
- [ ] 7.3 运行 `poetry run pytest -v` 或项目可用的后端测试命令
- [ ] 7.4 运行 `ruff check . && ruff format .`
- [ ] 7.5 更新后端架构文档，说明上下文和短时记忆的新边界
