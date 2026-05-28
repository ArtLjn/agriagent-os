## 1. 创建 tool_selector.py 核心模块

- [ ] 1.1 创建 `backend/app/agent/tool_selector.py`，定义 `WRITE_PATTERNS` 常量（5 个写操作 Tool 的 regex pattern 列表）
- [ ] 1.2 定义 `QUERY_TRIGGERS` 常量（5 个查询 Tool 的策划触发词表，从 base.j2 映射表同步）
- [ ] 1.3 实现 `select_tools(user_message, all_tools, top_k=3)` 函数：Layer 1 regex → Layer 2 keyword → 合并去重 → fallback

## 2. 单元测试

- [ ] 2.1 创建 `backend/tests/test_tool_selector.py`，编写 `TestWritePatternMatching`：覆盖记账（含金额/无金额/口语5w）、还账（标准/变体"账结了"）、建茬口（含作物名/季节）、记农事（浇水/施肥/打药）、更新阶段（进苗期/到开花期）
- [ ] 2.2 编写 `TestQueryKeywordMatching`：覆盖天气、余额、月额、多意图、趋势分析
- [ ] 2.3 编写 `TestFallback`：覆盖"你好"、"西瓜怎么种"等无匹配场景，验证返回全量 Tool

## 3. graph.py 集成

- [ ] 3.1 修改 `backend/app/agent/graph.py` 的 `_llm_node`：在 `bind_tools()` 前调用 `select_tools()`，传入最后一条 HumanMessage 的内容
- [ ] 3.2 添加 INFO 日志：`tool_pre_filter | candidates=[...] | total=N`
- [ ] 3.3 更新 `tests/test_function_calling_e2e.py`：验证预筛后 tool call 仍正常触发

## 4. 端到端验证

- [ ] 4.1 ruff 检查 `app/agent/tool_selector.py` + `app/agent/graph.py` + `tests/test_tool_selector.py`
- [ ] 4.2 全量测试 `pytest tests/` 通过
- [ ] 4.3 手动验证回归 case："我的余额" → get_cost_summary、"卖西瓜收入5w" → create_cost_record、"你好" → 无 tool call
