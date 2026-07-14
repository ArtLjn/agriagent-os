## Context

当前架构：`agents/tools.py` 中 4 个 `@tool` 装饰的函数直接注册到 LangGraph `create_react_agent`。已有 [skillify](https://github.com/ArtLjn/skillify) SDK 提供 Skill 基类（ABC）、SkillRegistry 自动发现、PatternMatcher 快通道、SkillExecutor（含超时保护）、Harness 校验框架。本次复用 skillify 的注册和匹配能力，补充 skillify 缺少的 LangChain 桥接、缓存、熔断功能。

## Goals / Non-Goals

**Goals:**
- 复用 skillify SDK 的 Skill 基类和自动发现，迁移 4 个工具为 Skill 子类
- 桥接 skillify Skill → LangChain StructuredTool，供 LangGraph Agent function call
- 多 tool_calls 并行执行：asyncio.gather 并发
- LLM 熔断器：三态机 + 指数退避重试
- TTL 缓存：按 Skill 粒度配置，内存存储

**Non-Goals:**
- 不做分布式缓存（Redis），仅内存
- 不做 Skill 热重载
- 不做 Pattern 快通道（当前全部走 LLM function call）
- 不改变前端 API 接口

## Decisions

### D1: Skill 实现方式

继承 skillify 的 `Skill` 基类，放在 `backend/app/skills/` 目录。每个 Skill 文件导出一个实例，SkillManager 通过 `discover_python_package()` 自动发现。

```python
# skills/weather.py
from skillify.skills.base import Skill

class WeatherSkill(Skill):
    def name(self) -> str: return "weather"
    def description(self) -> str: return "获取未来7天天气预报。触发词: 天气、预报"
    def parameters_schema(self) -> dict: return {"type":"object","properties":{"location":{"type":"string"}}}
    def execute(self, params, context): ...
```

skillify SkillManager 初始化后通过桥接层转换为 LangChain Tool。

### D2: skillify → LangChain 桥接

```python
# core/bridge.py
def skills_to_langchain_tools(manager: SkillManager) -> list[StructuredTool]:
    tools = []
    for skill_def in manager.list_skills():
        skill = manager.get_skill(skill_def.name)
        tools.append(StructuredTool(
            name=skill.name(),
            description=skill.description(),
            args_schema=... # 从 parameters_schema 转换
            func=lambda **kw, s=skill: s.execute(kw, None).reply,
        ))
    return tools
```

### D3: 并行执行节点

自定义 LangGraph 节点替换 `create_react_agent` 的默认 tool 执行。当 LLM 返回多个 `tool_calls` 时用 `asyncio.gather` 并发：

```
LLM Node → [tool_call_1, tool_call_2, tool_call_3]
                ↓ asyncio.gather
         [result_1, result_2, result_3]  (并发)
                ↓
LLM Node (汇总生成回复)
```

### D4: 熔断器

三态机 `CLOSED → OPEN → HALF_OPEN`：

| 参数 | 值 | 说明 |
|------|-----|------|
| failure_threshold | 3 | 连续失败 3 次打开熔断 |
| recovery_timeout | 30s | OPEN 持续 30s 后进入 HALF_OPEN |
| retry_max | 3 | 最大重试次数 |
| retry_backoff_base | 2s | 指数退避基数（2s, 4s, 8s） |

包装 `ChatOpenAI` 的调用，在 `core/llm.py` 中集成。

### D5: 缓存装饰器

通用 TTL 缓存装饰器，装饰 Skill 的 `execute()` 方法：

| Skill | TTL | 理由 |
|-------|-----|------|
| 天气预报 | 30 min | 天气变化 ~小时级 |
| 种植周期信息 | 10 min | 阶段变更不频繁 |
| 农事记录 | 1 min | 可能有新写入 |
| 成本汇总 | 5 min | 收支变更不频繁 |

```python
@cached(ttl_seconds=1800, key_fn=lambda params: f"weather:{params.get('location','default')}")
def execute(self, params, context): ...
```

## Risks / Trade-offs

- **skillify 版本依赖**：使用本地安装，需确保版本稳定
- **并行执行 DB 连接**：每个 Skill 创建独立 Session，SQLite 可承受 4 并发
- **内存缓存重启丢失**：可接受，首次请求重新填充
- **LangChain 桥接维护**：skillify 的 `parameters_schema` (JSON Schema) 需转换为 Pydantic Model，新增 Skill 时需注意兼容
