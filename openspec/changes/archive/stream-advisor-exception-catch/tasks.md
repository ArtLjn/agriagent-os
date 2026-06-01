## 1. 代码修改

- [ ] 1.1 在 `advisor.py` 的 `stream_advisor` 函数中，`except GraphRecursionError` 块之后增加 `except Exception` 通用兜底，yield 错误提示并记录 error 日志

## 2. 测试验证

- [ ] 2.1 补充测试用例：模拟 `graph.astream()` 抛出 `APIConnectionError`，验证 yield 友好提示且 SSE 不断开
- [ ] 2.2 验证现有测试全部通过（确认正常流程未受影响）
