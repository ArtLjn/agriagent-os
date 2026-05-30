## Why

当前 LLM 调用硬绑单一 provider（DashScope），`get_llm()` 只读 `settings.ai_api_key`。DashScope 免费额度耗尽后直接报错，无法自动切换到 Ollama 或 NVIDIA NIM 等备选 provider。项目已有多 provider 的 API key 和模型清单（`model_list.json`），但运行时完全不读取。4 个调用点（llm.py、graph.py、skills/__init__.py、tool_selector.py）各自独立实例化 OpenAI 客户端，无统一管理。

## What Changes

- 将 `model_list.json` 重新设计为运行时配置文件 `providers.json`，定义 provider 优先级、模型列表、API key 轮换
- 新增 `LLMClientManager`，统一管理所有 LLM 客户端实例，提供 `get_chat_model()` / `get_sync_client()` / `get_async_client()` 三个接口
- 实现智能 fallback：按错误类型分类（Provider 级 vs 模型级），Provider 级错误跳 provider，模型级错误先换模型再换 provider
- 实现指数退避 cooldown（base=2min，最大 24h），失败次数递增、成功重置
- 改造 4 个调用点全部接入 `LLMClientManager`
- 保留 config.yaml 作为兜底（providers.json 不存在或为空时回退）

## Capabilities

### New Capabilities
- `llm-provider-router`: 多 Provider LLM 路由 — 统一配置文件驱动、优先级排序、错误分类 fallback、指数退避 cooldown、API key 轮换

### Modified Capabilities
- `llm-tool-calling`: LLM 客户端获取方式从硬编码单 provider 改为通过 `LLMClientManager` 获取

## Impact

- **配置**: 新增 `backend/providers.json`（运行时 LLM 配置），`model_list.json` 可保留作为参考文档
- **代码**:
  - 新增 `app/core/llm_client_manager.py`（路由器 + cooldown）
  - 修改 `app/agent/llm.py`（接入 Manager）
  - 修改 `app/agent/graph.py`（`_get_classifier` 接入 Manager）
  - 修改 `app/agent/skills/__init__.py`（`build_skill_context` 接入 Manager）
  - 修改 `app/agent/tool_selector.py`（接入 Manager）
- **依赖**: 无新增依赖（使用现有的 langchain-openai / openai / httpx）
- **API**: 无公开 API 变更，纯内部重构
- **风险**: fallback 链路需要逐 provider 验证，错误分类可能不全（需迭代完善）
