## 1. 配置文件

- [ ] 1.1 创建 `backend/providers.json`，从 `model_list.json` 迁移数据，包含 3 个 provider（ollama / nvidia / dashscope），按设计文档 D1 格式
- [ ] 1.2 在 `.gitignore` 中添加 `providers.json` 排除规则

## 2. LLMClientManager 核心

- [ ] 2.1 创建 `backend/app/core/llm_client_manager.py`，实现 `providers.json` 加载 + 解析 + fallback 链构建
- [ ] 2.2 实现错误分类逻辑：Provider 级（ConnectionError/401/403）跳 provider，模型级（429/404/400）先换模型
- [ ] 2.3 实现指数退避 cooldown：base=2min, max=24h，成功重置，按 provider name / model id 索引
- [ ] 2.4 实现 API key 轮询（Round-Robin）
- [ ] 2.5 实现 `get_chat_model()` → ChatOpenAI
- [ ] 2.6 实现 `get_sync_client()` → OpenAI
- [ ] 2.7 实现 `get_async_client()` → AsyncOpenAI
- [ ] 2.8 实现 `get_model_info()` → dict
- [ ] 2.9 实现 config.yaml 兜底：providers.json 不存在或为空时回退到 settings.ai_api_key

## 3. 测试

- [ ] 3.1 编写 `backend/tests/test_llm_client_manager.py`：fallback 链构建、错误分类、cooldown 递增/重置、key 轮换、config.yaml 兜底

## 4. 调用点改造

- [ ] 4.1 改造 `llm.py`：`get_llm()` 优先通过 Manager 获取，失败回退 config.yaml
- [ ] 4.2 改造 `graph.py`：`_get_classifier()` 通过 Manager 获取参数
- [ ] 4.3 改造 `skills/__init__.py`：`build_skill_context()` 通过 Manager 获取 AsyncOpenAI
- [ ] 4.4 运行现有测试确认不破坏：`pytest tests/test_llm.py tests/test_tool_selector.py -v`

## 5. 收尾

- [ ] 5.1 运行全量测试：`pytest -v --tb=short`
- [ ] 5.2 Lint 检查：`ruff check . && ruff format .`
