# 移动端后端接口接入待办清单

> 范围：`mobile-app/` 对接 `backend/app` 已暴露的用户侧业务接口。
> 状态说明：
> - `已封装`：移动端 repository 已有方法。
> - `已触发`：当前 App 入口或页面流程已经会调用。
> - `待接页面`：repository 已有方法，但页面仍使用静态展示或未绑定真实数据。
> - `待补 repository`：后端有接口，移动端数据层还没有方法。
> - `页面冲突`：需要先定页面/交互设计，本清单只记录，不改页面。

## 0. 接入基础

| 待办 | 状态 | 备注 |
| --- | --- | --- |
| `ApiClient` 支持 baseUrl、Token Header、GET/POST/PUT/PATCH/DELETE | 已封装 | `API_BASE_URL` 来自 Dart define。 |
| `AppDependencies` 统一创建共享 `ApiClient` 和 repository | 已触发 | 登录后 token 可被所有仓库复用。 |
| 登录成功后进入主应用并后台预热数据 | 已触发 | 预热失败当前静默，不影响 UI。 |
| API 错误统一展示策略 | 待接页面 | 目前登录/注册有简单失败文案，其他页面未统一处理。 |
| Token 本地持久化与启动态恢复 | 待补 repository | 当前 token 只在内存中，重启后需重新登录。 |
| 退出登录/清空 token | 待接页面 | 后端无专门 logout，前端清 token 即可。 |

## 1. 认证与个人资料

| 后端接口 | 移动端状态 | 页面待办 |
| --- | --- | --- |
| `POST /auth/login` | 已封装、已接页面 | 登录页已提交手机号/密码。 |
| `POST /auth/register` | 已封装、已接页面 | 注册页已提交手机号/密码/昵称。 |
| `GET /auth/me` | 已封装、已触发 | 个人页仍是静态展示，需绑定昵称、手机号、头像、角色、状态。 |
| `PUT /auth/me` | 已封装 | 待设计“编辑个人资料”入口和保存反馈。 |
| `GET /settings` | 已封装、已触发 | 个人页“所在城市/默认天气/AI 偏好”仍静态。 |
| `PUT /settings` | 已封装 | 首次设置页和个人设置页需绑定保存。 |
| `GET /api/app/version` | 已封装、已触发 | “关于农场管家”版本展示/更新弹窗待设计。 |

## 2. 芽芽对话、建议、报告

| 后端接口 | 移动端状态 | 页面待办 |
| --- | --- | --- |
| `POST /agent/chat` | 已封装 | 芽芽输入框仍未提交真实消息。 |
| `POST /agent/chat/stream` | 待补 repository | 如要打字机/SSE 流式输出，需要新增 stream client。 |
| `GET /agent/conversations` | 已封装、已触发 | 历史抽屉待绑定真实会话列表。 |
| `GET /agent/conversations/{session_id}/messages` | 已封装 | 点击历史会话后加载消息待接。 |
| `GET /agent/daily` | 已封装、已触发 | 首页/芽芽“今日建议/简报”仍是静态文案。 |
| `POST /agent/daily/refresh` | 已封装 | 刷新按钮/重新生成状态待设计。 |
| `POST /agent/report` | 已封装 | “生成周报/报告”按钮待绑定。 |
| `GET /agent/advice-history` | 已封装 | 建议历史页/列表待设计。 |
| `GET /agent/report-history` | 已封装 | 报告历史入口待绑定。 |
| `GET /agent/reports` | 已封装 | 分页报告列表待绑定。 |
| `DELETE /agent/reports/{report_id}` | 待补 repository | 报告删除/确认交互待设计。 |
| `POST /agent/feedback` | 待补 repository | 对回复点赞/点踩/反馈入口待设计。 |
| `GET /agent/feedback/stats` | 不建议移动端接 | 偏管理/统计用途，先放管理端。 |

页面冲突：
- `YayaSkillsPage` 和 `AppAssets.yayaSkillsBanner` 目前被测试期待，但页面/资产尚未完整实现；需要你先设计“全部技能页”和 banner。
- 芽芽首页是否显示“今日简报”、技能入口、历史抽屉，需要统一信息架构后再绑定接口。

## 3. 首页/看板/天气

| 后端接口 | 移动端状态 | 页面待办 |
| --- | --- | --- |
| `GET /weather/forecast` | 已封装、已触发 | 首页天气卡/个人默认天气仍未绑定真实数据。 |
| `GET /agent/daily` | 已封装、已触发 | 首页 AI 建议卡待绑定。 |
| `GET /planting/work-orders` | 已封装、已触发 | 首页待办/近期作业待绑定。 |
| `GET /planting/labor/unsettled-summary` | 已封装、已触发 | 首页或账本的未结人工提醒待绑定。 |

页面冲突：
- 首页当前是视觉稿卡片，真实数据字段可能改变卡片密度和优先级，建议先定“首页核心指标”。

## 4. 账本、成本、赊账

| 后端接口 | 移动端状态 | 页面待办 |
| --- | --- | --- |
| `GET /costs` | 已封装、已触发 | 账本交易列表仍静态，需绑定分页与筛选。 |
| `POST /costs` | 已封装 | 手动记账保存待绑定。 |
| `DELETE /costs/{record_id}` | 待补 repository | 交易删除/撤销待设计。 |
| `GET /costs/summary/{year}` | 已封装、已触发 | 资金概览仍静态，需绑定年度汇总。 |
| `GET /costs/cycles/{cycle_id}/profit` | 已封装 | 周期利润页/卡片待设计。 |
| `POST /costs/parse` | 已封装 | 可作为 AI 记账兼容入口；当前记录流未绑定。 |
| `GET /cost-categories` | 已封装 | 分类选择器待绑定真实分类。 |
| `POST /cost-categories` | 已封装 | 新建分类入口待设计。 |
| `DELETE /cost-categories/{category_id}` | 待补 repository | 分类删除确认和系统分类限制提示待设计。 |
| `GET /debts` | 已封装、已触发 | 待收款/赊账列表仍静态。 |
| `POST /debts` | 已封装 | 新建赊账记录待绑定。 |
| `POST /debts/settle` | 已封装 | 结清/部分结算交互待设计。 |

页面冲突：
- 账本页当前“最近交易/待收款提醒”是固定卡片，真实数据需要空状态、筛选、分页、删除、结算等完整交互。

## 5. 茬口、作物模板、种植单元

| 后端接口 | 移动端状态 | 页面待办 |
| --- | --- | --- |
| `GET /cycles` | 已封装、已触发 | 工作台/首页周期选择仍未绑定。 |
| `POST /cycles` | 已封装 | 新建茬口表单待绑定。 |
| `GET /cycles/{cycle_id}` | 已封装 | 茬口详情页待设计或绑定。 |
| `PUT /cycles/{cycle_id}` | 已封装 | 编辑茬口待设计。 |
| `DELETE /cycles/{cycle_id}` | 待补 repository | 删除确认和关联数据影响提示待设计。 |
| `POST /cycles/{cycle_id}/advance-stage` | 已封装 | 推进阶段按钮/确认态待设计。 |
| `POST /cycles/parse` | 已封装 | AI 创建茬口可用，记录流未接。 |
| `GET /crops/templates` | 待补 repository | 作物模板列表待接。 |
| `POST /crops/templates` | 待补 repository | 新建作物模板待接。 |
| `GET /crops/templates/{template_id}` | 待补 repository | 作物模板详情待接。 |
| `PUT /crops/templates/{template_id}` | 待补 repository | 编辑作物模板待接。 |
| `DELETE /crops/templates/{template_id}` | 待补 repository | 删除作物模板待接。 |
| `POST /crops/templates/parse` | 待补 repository | AI 作物模板解析待接。 |
| `GET /planting/units` | 已封装、已触发 | 种植单元列表/选择器待绑定。 |
| `POST /planting/units` | 已封装 | 新建种植单元表单待绑定。 |
| `PUT /planting/units/{unit_id}` | 已封装 | 编辑种植单元待绑定。 |
| `DELETE /planting/units/{unit_id}` | 待补 repository | 删除确认待设计。 |

页面冲突：
- 工作台目前是“记录入口”主导，茬口/种植单元/模板管理入口位置需要你定。

## 6. 农事作业、日志、智能填写

| 后端接口 | 移动端状态 | 页面待办 |
| --- | --- | --- |
| `GET /planting/operation-types` | 已封装、已触发 | 作业类型选择器待绑定。 |
| `GET /planting/work-orders` | 已封装、已触发 | 作业单列表待绑定。 |
| `POST /planting/work-orders` | 已封装 | 创建作业单待绑定。 |
| `GET /planting/work-orders/{work_order_id}` | 已封装 | 作业单详情待设计。 |
| `GET /planting/recent-operations` | 已封装 | 最近农事卡片待绑定。 |
| `GET /logs` | 已封装、已触发 | 旧农事日志列表待绑定。 |
| `POST /logs` | 已封装 | 创建日志待绑定。 |
| `PUT /logs/{log_id}` | 已封装 | 编辑日志待绑定。 |
| `DELETE /logs/{log_id}` | 待补 repository | 删除日志待设计。 |
| `GET /smart-fill/scenarios` | 已封装 | AI 帮填场景选择待绑定。 |
| `POST /smart-fill/parse` | 已封装 | 记录流“AI 帮我填”待绑定真实解析结果。 |

页面冲突：
- 记录流目前三页闭环是静态样稿；接真实 AI 解析后，需要设计“不确定字段/缺字段/保存失败/重复提交”的状态。

## 7. 工人与工资

| 后端接口 | 移动端状态 | 页面待办 |
| --- | --- | --- |
| `GET /planting/workers` | 已封装、已触发 | 工人选择器/工人列表待绑定。 |
| `POST /planting/workers` | 已封装 | 新建工人待绑定。 |
| `GET /planting/workers/summary` | 已封装 | 工人摘要页待设计。 |
| `PUT /planting/workers/{worker_id}` | 已封装 | 编辑工人待设计。 |
| `DELETE /planting/workers/{worker_id}` | 待补 repository | 停用工人确认待设计。 |
| `POST /planting/labor/wages` | 已封装 | 保存工资记录待绑定。 |
| `PATCH /planting/labor/wages/{labor_entry_id}` | 已封装 | 更新工资/结算状态待绑定。 |
| `GET /planting/labor/unsettled-summary` | 已封装、已触发 | 未结人工摘要待绑定到账本/首页。 |

## 8. 管理端/仿真接口处理建议

以下接口后端存在，但不建议接入普通移动端，除非你要在 App 内做管理端能力：

| 模块 | 后端接口范围 | 建议 |
| --- | --- | --- |
| 管理配置 | `/admin/config/*` | 保持在 `admin-web`。 |
| 管理统计 | `/admin/stats/*` | 保持在 `admin-web`。 |
| 用户管理 | `/admin/users/*` | 保持在 `admin-web`。 |
| Trace 监控 | `/admin/trace/*` | 保持在 `admin-web`。 |
| Guardrails 日志 | `/admin/guardrails-logs` | 保持在 `admin-web`。 |
| Agent Simulation | `/simulation/*` | 保持测试/管理工具，不进普通移动端。 |
| 健康检查 | `/health` | 可用于开发诊断，不建议进入用户页面。 |

## 9. 建议处理顺序

1. 认证闭环：token 持久化、启动恢复、退出登录。
2. 记录流闭环：`smart-fill/parse` → 手动修正 → `costs`/`logs`/`work-orders` 保存。
3. 账本页：`costs`、`summary`、`debts`、分类选择与结算。
4. 首页：每日建议、天气、近期作业、未结人工摘要。
5. 芽芽：非流式 chat 先接通，再决定是否接 SSE。
6. 工作台管理：茬口、种植单元、作物模板、工人和工资。
7. 删除类接口：统一确认弹窗、乐观更新、失败恢复后再补。

## 10. 当前最明确的页面设计决策点

- 芽芽“全部技能页”：是否需要独立页面、banner、技能分类和搜索。
- 首页真实数据优先级：天气、建议、待办、账本摘要哪个是主卡。
- 账本列表交互：筛选、分页、删除、结算、空状态。
- 记录流保存目标：同一次 AI 解析如何选择保存为账本、农事日志、工资或作业单。
- 工作台是否承担“管理入口”，还是只做“记录入口”。
