## 1. 后端接口准备

- [ ] 1.1 在 `backend/app/api/agent.py` 的 `agent_chat_stream` 中增加可选 `user_id` 参数，支持按用户 ID 加载对应农场上下文
- [ ] 1.2 确认 `backend/app/api/admin_users.py` 的 `list_users` 接口已暴露，检查是否需要补充分页或过滤参数

## 2. 前端 API 层扩展

- [ ] 2.1 在 `admin-web/src/api/admin.ts` 中补充 `listUsers` 接口定义和请求函数
- [ ] 2.2 确认 `streamPlaygroundChat` 支持传递 `user_id` 参数

## 3. Skill 输出格式化（trace-skill-output-formatter）

- [ ] 3.1 创建 `admin-web/src/components/SkillOutputFormatter/index.tsx` 组件：解析 `output_data` JSON，提取 `reply_preview`，其余字段折叠
- [ ] 3.2 在 `TraceMonitor` 的节点详情 Drawer 中，对 `skill_call` 类型节点使用 `SkillOutputFormatter` 替代原始 JSON 展示
- [ ] 3.3 在 `Playground` 的节点详情 Drawer 中同步应用 `SkillOutputFormatter`
- [ ] 3.4 增加「复制格式化内容」按钮，将 `reply_preview` 写入剪贴板
- [ ] 3.5 增加解析失败回退逻辑（try/catch + 原始 JSON 展示）

## 4. 复制耗时分析（trace-copy-timing-report）

- [ ] 4.1 在 `TraceMonitor` 的列表头部（`toggleCard` 区域）增加「复制耗时」按钮
- [ ] 4.2 实现耗时汇总函数：遍历 `timeline.rounds[].nodes[]`，按 `node_type` 分组累加 `duration_ms`
- [ ] 4.3 生成 Markdown 表格（列：节点类型、累计耗时、占比、节点数），包含总耗时行
- [ ] 4.4 按钮状态管理：timeline 加载中禁用，加载完成后可用
- [ ] 4.5 剪贴板写入 + 成功/失败提示

## 5. Playground 用户选择器（playground-user-selector）

- [ ] 5.1 在 `Playground` 配置栏增加 `Select` 下拉框，调用 `listUsers` 加载用户列表
- [ ] 5.2 下拉框选项包含「匿名用户」+ 真实用户列表，默认选中「匿名用户」
- [ ] 5.3 修改 `streamPlaygroundChat`，将选中用户的 `user_id` 作为参数传递给后端
- [ ] 5.4 切换用户后清空当前对话上下文，避免上下文混淆
- [ ] 5.5 未选择用户时保持现有匿名行为（不传递 `user_id`）

## 6. 验证与收尾

- [ ] 6.1 在 Trace Monitor 中验证 Skill 输出格式化效果（正常解析 + 解析失败回退）
- [ ] 6.2 验证「复制耗时」按钮功能（生成 Markdown 表格正确性）
- [ ] 6.3 在 Playground 中验证用户选择器（切换用户、匿名模式、上下文生效）
- [ ] 6.4 运行前端 lint 检查，确保无类型错误
