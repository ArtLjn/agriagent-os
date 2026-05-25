## ADDED Requirements

### Requirement: 作物模板 Edit/Delete
Crops 页面 SHALL 支持编辑和删除作物模板。编辑 SHALL 复用创建表单（Modal 弹窗），删除 SHALL 使用 Popconfirm 二次确认。

#### Scenario: 编辑作物模板
- **WHEN** 用户点击模板行的"编辑"按钮
- **THEN** 弹出预填当前数据的 Modal，修改后提交 PUT /crops/templates/:id

#### Scenario: 删除作物模板
- **WHEN** 用户点击"删除"按钮并在 Popconfirm 中确认
- **THEN** 调用 DELETE /crops/templates/:id，列表刷新

#### Scenario: 删除被引用的模板
- **WHEN** 模板已被茬口引用时尝试删除
- **THEN** 后端返回 409 冲突错误，前端提示"该模板已被茬口引用，无法删除"

### Requirement: 茬口 Edit/Delete 和状态推进
Cycles 页面 SHALL 支持编辑和删除茬口，详情页 SHALL 支持"推进到下一阶段"操作。

#### Scenario: 编辑茬口
- **WHEN** 用户点击茬口行的"编辑"按钮
- **THEN** 弹出预填数据的 Modal，修改后提交 PUT /cycles/:id

#### Scenario: 删除茬口
- **WHEN** 用户点击"删除"并在 Popconfirm 中确认
- **THEN** 调用 DELETE /cycles/:id，列表刷新

#### Scenario: 推进阶段
- **WHEN** 用户在详情页点击"推进到下一阶段"
- **THEN** 调用 POST /cycles/:id/advance-stage，当前阶段标记完成，下一阶段设为 is_current

### Requirement: 农事日志 Edit/Delete
Logs 页面 SHALL 支持编辑和删除农事日志。

#### Scenario: 编辑日志
- **WHEN** 用户点击日志行的"编辑"按钮
- **THEN** 弹出预填数据的 Modal，修改后提交 PUT /logs/:id

#### Scenario: 删除日志
- **WHEN** 用户点击"删除"并在 Popconfirm 中确认
- **THEN** 调用 DELETE /logs/:id，列表刷新

### Requirement: 成本记录 Edit/Delete
Costs 页面 SHALL 支持编辑和删除成本/收入记录。

#### Scenario: 编辑成本记录
- **WHEN** 用户点击记录行的"编辑"按钮
- **THEN** 弹出预填数据的 Modal，修改后提交 PUT /costs/:id

#### Scenario: 删除成本记录
- **WHEN** 用户点击"删除"并在 Popconfirm 中确认
- **THEN** 调用 DELETE /costs/:id，列表刷新

### Requirement: 列表分页
所有列表页（Crops、Cycles、Logs、Costs）SHALL 支持分页，默认每页 20 条。后端 SHALL 返回 `{ items: [], total: number }` 格式。

#### Scenario: 第一页加载
- **WHEN** 用户打开列表页
- **THEN** 显示前 20 条数据，Table 底部显示分页器

#### Scenario: 切换页码
- **WHEN** 用户点击分页器第 2 页
- **THEN** 请求带 `page=2&size=20` 参数，显示第 21-40 条数据

#### Scenario: 总数不足一页
- **WHEN** 总数据量少于 20 条
- **THEN** 不显示分页器

### Requirement: 统一错误处理
Admin-web SHALL 使用 Axios 响应拦截器统一处理错误。网络错误和 5xx 错误 SHALL 显示"服务器异常，请稍后重试"，422 错误 SHALL 显示具体字段错误信息。

#### Scenario: 网络错误
- **WHEN** 请求因网络问题失败
- **THEN** 弹出 message.error("服务器异常，请稍后重试")

#### Scenario: 422 验证错误
- **WHEN** 后端返回 422，body 包含字段错误列表
- **THEN** 弹出 message.error，显示后端返回的具体错误信息

#### Scenario: 429 限流错误
- **WHEN** 后端返回 429
- **THEN** 弹出 message.error("请求过于频繁，请稍后重试")

### Requirement: TypeScript 类型补全
Admin-web 的 agent.ts 和 weather.ts API 层 SHALL 定义完整的返回类型接口。页面组件中的 `any` 类型 SHALL 替换为具体接口。

#### Scenario: Agent API 有返回类型
- **WHEN** 开发者调用 agent 相关 API
- **THEN** IDE 能自动补全返回类型字段

#### Scenario: 页面无 any 类型
- **WHEN** TypeScript 严格模式编译
- **THEN** agent 和 weather 相关页面无 `any` 类型错误
