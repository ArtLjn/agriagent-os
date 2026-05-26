## Tasks

### Phase 1: 基础设施（无业务影响）

- [ ] **T1**: 安装 skillify SDK 到 backend venv
  - `pip install -e /Users/ljn/Documents/demo/skillify`
  - 验证 `from skillify.skills.base import Skill` 可导入
  - 更新 requirements.txt

- [ ] **T2**: 实现缓存装饰器 `core/skill_cache.py`
  - 创建 `cached(ttl_seconds, key_fn)` 装饰器
  - 内存字典 + TTL 过期检查
  - 日志输出 CACHE HIT/MISS

- [ ] **T3**: 实现熔断器 `core/circuit_breaker.py`
  - CircuitBreaker 类：CLOSED/OPEN/HALF_OPEN 三态
  - 指数退避重试包装函数 `with_retry_and_breaker(callable)`
  - 配置参数从 config.yaml 读取
  - 状态变化日志

### Phase 2: Skill 迁移

- [ ] **T4**: 创建 `skills/` 包和 SkillManager 初始化
  - 创建 `backend/app/skills/__init__.py`
  - 实现 SkillManager 单例初始化函数
  - 实现 LangChain 桥接函数 `skills_to_langchain_tools()`

- [ ] **T5**: 迁移 WeatherSkill
  - 继承 Skill 基类，从 tools.py 搬运天气逻辑
  - 加 @cached(ttl_seconds=1800) 装饰器
  - 加执行日志

- [ ] **T6**: 迁移 CropCycleSkill
  - 从 tools.py 搬运，加 @cached(ttl_seconds=600)

- [ ] **T7**: 迁移 FarmLogSkill
  - 从 tools.py 搬运，加 @cached(ttl_seconds=60)

- [ ] **T8**: 迁移 CostSummarySkill
  - 从 tools.py 搬运，加 @cached(ttl_seconds=300)

### Phase 3: Agent 重构

- [ ] **T9**: 重构 `core/llm.py` 集成熔断器
  - get_llm() 返回的 ChatOpenAI 实例包装熔断器
  - invoke/stream 调用走 with_retry_and_breaker

- [ ] **T10**: 重构 `agents/graph.py`
  - 替换 create_react_agent 为自定义 StateGraph
  - 实现 LLM 节点 + 并行 Skill 执行节点
  - 工具列表从 SkillManager 桥接获取

- [ ] **T11**: 更新 `agents/advisor.py`
  - 适配新的 graph 接口
  - invoke_advisor / stream_advisor 保持对外接口不变

### Phase 4: 清理和验证

- [ ] **T12**: 删除旧 `agents/tools.py`，更新所有 import
  - 确认无残留引用

- [ ] **T13**: 端到端测试
  - 测试 chat 接口（流式+非流式）
  - 测试 daily advice
  - 验证缓存命中日志
  - 验证并行执行日志（问需要多工具的复杂问题）
  - 模拟 LLM 超时验证熔断器
