## 1. Prompt 格式修复（Bug 1 + 4）

- [ ] 1.1 base.j2 的【回复格式】中添加移动端约束：禁止 Markdown 表格、禁止代码块、禁止嵌套列表，使用扁平短句
- [ ] 1.2 report.j2 添加格式约束：使用 Markdown 格式、用真实换行、禁用表格和代码块
- [ ] 1.3 MarkdownText.tsx 添加 `\n` 字面量预处理：`text.replace(/\\n/g, '\n')`

## 2. watchfiles 日志过滤（Bug 2）

- [ ] 2.1 llm_client_manager.py 的 start_file_watcher 中设置 watchfiles logger 为 WARNING 级别

## 3. 记账刷新修复（Bug 3）

- [ ] 3.1 CostListScreen.tsx 的 useEffect 替换为 useFocusEffect，每次获焦时刷新数据
- [ ] 3.2 CostCreateScreen.tsx 赊账路径成功后调用 costStore.fetchRecords() 刷新列表

## 4. 种植报告转义字符（Bug 4，已含在 1.2+1.3）

## 5. 首页昵称（Bug 5）

- [ ] 5.1 HomeScreen.tsx 的 getGreeting() 接收 displayName 参数，从 useSettingsStore 读取 displayName 替代硬编码"农友"

## 6. 天气城市传递（Bug 6）

- [ ] 6.1 graph.py 的 _llm_node 中将 UserSetting.default_city 注入 system prompt（替代或补充 Farm.location）
- [ ] 6.2 确认天气 skill 的降级机制（_get_user_location）仍正常工作

## 7. 记账删除（Bug 7）

- [ ] 7.1 cost_service.py 新增 delete_record(db, record_id, farm_id) 软删除函数
- [ ] 7.2 cost.py 新增 DELETE /{record_id} 端点
- [ ] 7.3 补充删除相关测试
