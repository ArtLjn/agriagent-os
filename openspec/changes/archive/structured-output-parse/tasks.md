## 1. 代码改造

- [ ] 1.1 改造 `app/api/crop.py` 的 `parse_crop_template`：用 `get_llm().with_structured_output(CropTemplateParseResponse)` 替代手动 JSON 解析链路，保留 fallback
- [ ] 1.2 改造 `app/api/cycle.py` 的茬口解析端点：同上模式
- [ ] 1.3 改造 `app/api/cost.py` 的记账解析端点：同上模式

## 2. Prompt 模板调整

- [ ] 2.1 精简 `crop_template_parse.j2`：去掉 JSON 格式约束说明（如 "只返回 JSON 对象"），保留业务指令
- [ ] 2.2 精简 `cycle_parse.j2`：同上
- [ ] 2.3 精简 `cost_parse.j2`：同上

## 3. 测试验证

- [ ] 3.1 更新 `tests/test_crop.py`：mock `get_llm` 返回支持 `with_structured_output` 的对象，验证返回 Pydantic 实例
- [ ] 3.2 确认现有测试全部通过（含 cycle/cost 相关测试）
