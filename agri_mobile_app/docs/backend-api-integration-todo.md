---
last_updated: 2026-10-04
status: fixes_verified_database_blocked
---

# 移动端 v2 API 接入核查与待修复清单

## 结论与范围

本轮已修复已接页面的主要协议冲突、假成功回复、审批、分页和保存后刷新问题；业务数据库连接尚待恢复，因此真实账号写入验收未完成。以下前九节保留修复前的核查证据，第十节记录当前交付状态。
登录、资料、首页概览、账本读取、茬口和模板管理已有真实调用；记账、农事、工资和新增工人的表单存在确定的字段冲突。
芽芽已接聊天和审批，但审批解析、失败重试、答案合并和历史分页存在缺陷。

核查基于当前工作区，包含已有未提交修改。已查看全部移动端 Repository、API Client、主导航及相关业务页面、Business 路由与请求模型、Agent 聊天/审批/历史及 SSE 生产链路，并读取运行服务 OpenAPI。
Business 有 87 个路径/方法组合，Agent 有 22 个，包含管理、诊断和兼容端点；这些数字不能直接作为移动端必须接入的数量。
初始核查阶段未提交真实业务记录。本轮随后修改生产代码、迁移测试并构建安装调试包，具体结果见第十节。健康检查和模型校验不能替代数据库就绪与真实账号端到端验收。

## 一、直接导致保存失败的问题（P1）

后端 `StrictRequest` 使用 `extra="forbid"`。本次直接实例化后端真实请求模型，以下四类表单请求均被拒绝为 `extra_forbidden`；FastAPI 对这类请求校验失败返回 422。去除冲突字段后，同组基础输入校验通过，但未验证后续数据库处理。

| 业务 | 当前接口 | App 多传字段 | 后端请求模型 |
| --- | --- | --- | --- |
| 手动记账（收入/支出） | `POST /cost-records` | `settlement_status`、`recorded_at` | `CreateRecordRequest` |
| 记农事 | `POST /farm-logs` | `operation_time` | `CreateLogRequest` |
| 记工资 | `POST /labor/wages` | `recorded_at` | `WageRequest` |
| 新增工人 | `POST /workers` | `status` | `CreateWorkerRequest` |

工人编辑模型允许 `status`，本次校验通过，因此修复新增请求时应保留编辑状态能力。
收支结算状态已经由后端 `cost_service.settlement_status_for` 按金额计算，无需客户端提交。
修复阶段确认数据库、成本与工资服务已有时刻支持；本轮扩展 REST 请求模型，并补齐农事服务时间转发，保留页面选择的具体时刻。

证据：[记账提交](../lib/features/business/ledger_manual_create_page.dart)第 63–72 行、[农事提交](../lib/features/business/farm_log_create_page.dart)第 44–50 行、[工资提交](../lib/features/business/wage_create_page.dart)第 54–69 行、[工人提交](../lib/features/business/worker_pages.dart)第 403–413 行；后端对应 [收支模型](../../agri_backend_v2/business/api/costs.py)、[农事模型](../../agri_backend_v2/business/api/farm_logs.py)、[工资模型](../../agri_backend_v2/business/api/work_orders.py)、[工人模型](../../agri_backend_v2/business/api/workers.py)、[严格模型基类](../../agri_backend_v2/business/api/schemas.py)。

四个页面均把异常改成“保存失败，请稍后再试”，隐藏了字段错误。`ApiClient.userMessageFor` 也未展开 422 的字段错误数组，需要同步补足字段级提示。

## 二、芽芽协议与状态缺陷

| 优先级 | 问题 | 原因和影响 |
| --- | --- | --- |
| P1 | 审批参数丢失 | `YayaStreamEvent.fromJson` 的审批分支只取嵌套 `json['data']`。真实后端将参数直接放入 SSE `data:` JSON；平铺的 `params/action_id/skill_name` 被丢弃，确认卡不能展示完整参数。`turn_id` 仍可由其他分支解析 |
| P1 | 审批失败不能按提示重试 | `respondToPendingAction` 请求前清除所有待确认状态，失败不恢复；卡片消失，无法再次点击确认 |
| P2 | 回答重复 | 后端发送 `final_answer_delta` 后再发 `final_answer` 全文，控制器把两者都追加；完整增量“建议浇水”会变成“建议浇水建议浇水” |
| P2 | 终态和提交结果处理不全 | 忽略 `turn.failed/turn.terminated/timeout/cancelled/operation_committed` 的业务语义；遇到 `done` 未检查状态，无法完整区分执行成功、失败、超时及已写入但回复失败 |
| P2 | 未接断流恢复和运行态取消 | 没消费 SSE `id`，未调用任务状态、事件重放和取消接口；断流后无法恢复当前任务结果，审批等待中的任务缺少运行态取消入口 |
| P2 | 历史分页缺失 | 会话默认只取 20 个，详情默认只取最早 100 条；忽略 `has_more/next_cursor`，长会话最新内容会缺失 |

证据：[芽芽 Repository](../lib/data/repositories/yaya_repository.dart)、[控制器](../lib/features/yaya/yaya_controller.dart)、[确认卡](../lib/features/yaya/yaya_screen.dart)、[后端 SSE 格式](../../agri_backend_v2/agent/platforms/persistence/redis/sse.py)、[用户事件投影](../../agri_backend_v2/agent/domains/harness/runtime/projection.py)、[运行引擎](../../agri_backend_v2/agent/domains/harness/runtime/engine.py)。这些问题由生产和消费代码交叉核对，未在真实模型对话中逐项复现。

`GET /conversations/{id}` 本身有效：后端 `get_conversation` 确实返回 `items` 消息列表，不能误报为读取路径错误。需要完善分页，优先使用 `/conversations/{id}/messages` 的最新消息和游标能力。

## 三、实际业务接入矩阵

以下路径省略 `/api/v2`。“已调用”表示能从当前界面追踪到请求，不表示实际账号端到端验收已通过。

| 业务 | 当前接入 | 状态与缺口 |
| --- | --- | --- |
| 登录、注册 | `POST /auth/login`、`POST /auth/register` | 已接；Token 同步到两个服务 |
| 用户资料、助手偏好 | `GET/PATCH /users/me`、`GET/PATCH /users/me/settings` | 已接 |
| 农场地区、城市选择 | `PATCH /farms/{id}/location`、`GET /locations/search` | 已接；搜索参数 `keyword`，坐标 `lat/lon` |
| 首页概览、天气、未结工资 | `/dashboard`、`/weather`、`/work-orders`、`/labor/unsettled-summary` | 已接；天气失败可降级，工资摘要路径正确 |
| 收支汇总、流水 | `/cost-records`、`/cost-records/summary/yearly` | 已接读取；保存字段冲突；“全部交易”仅筛选最近 10 条 |
| 收支分类 | `GET/POST /cost-categories`、`DELETE /cost-categories/{id}` | 已接列表、新增和删除，未接修改 |
| 茬口 | `GET/POST /crop-cycles`、`PATCH/DELETE /crop-cycles/{id}` | 已接；阶段推进仅有 Repository 方法，无当前界面入口 |
| 作物模板 | `GET/POST /crop-templates`、`PATCH/DELETE /crop-templates/{id}` | 自建模板已接；系统模板列表和导入未接 |
| 种植单元 | 创建茬口后 `POST /planting-units` | 无完整独立管理/删除界面；Workbench Repository 有读取、修改方法 |
| 工人 | `/workers/summary`、`POST /workers`、`PATCH/DELETE /workers/{id}` | 新增字段冲突；编辑/删除已有调用 |
| 农事 | `POST /farm-logs` | 保存字段冲突；列表和修改仅有 Workbench 方法，无完整历史/详情/编辑/删除界面 |
| 工资 | `POST /labor/wages` | 保存字段冲突；修改仅有 Workbench 方法，列表/结算缺少界面闭环 |
| 作业单 | 首页读取；Repository 有创建和详情 | 缺完整创建/编辑/结算界面 |
| 欠款 | `GET /debts` 参与账本模型；Repository 有创建/结算 | 当前无完整新增/结算界面 |
| 茬口利润 | Repository 有 `/cost-records/cycles/{id}/profit` | 当前界面未调用 |
| 芽芽 | `/chat`、`/approve`、历史读取 | 已调用，存在第二节缺陷 |

当前记录主页面使用 `BusinessRepository` 打开实际表单。旧 `RecordFlowController` 虽能将多类场景路由到对应保存方法，但其智能解析直接抛不可用错误，当前主记录入口没有走该旧流程。因此不能将 Repository 中存在方法当成业务可用。

后端已提供、移动端尚缺完整接入的主要能力：系统模板列表/导入，`GET /labor/wages`，`POST /work-orders/{id}/settle`，账单修改/删除，分类修改，农事详情/删除，农场名称修改，种植单元删除，以及 Agent 任务查询/恢复/取消/重置。管理员技能、用户管理、Trace 诊断和 PUT/PATCH 替代方法不计为普通移动端缺陷。

## 四、已接入但业务结果不完整

1. **交易范围不完整（P1）**：`BillingController.load` 固定 `listCosts(size: 10)`；“全部交易”、日期筛选和搜索仅处理传入模型，没有请求其他页或后端日期过滤，较早记录可能被误认为不存在。
2. **茬口/模板分页不完整（P2）**：默认只加载 20 条，未根据 `total` 继续请求；搜索仅作用于当前页。模板选择最多请求 100 条，也无后续页。
3. **保存后列表未刷新（P2）**：茬口、模板、工人列表 Future 仅在初始化/删除时刷新，新增/编辑未回传保存结果并重新请求。手动记账已有账本刷新回调，不应混同。
4. **新建茬口部分成功风险（P2）**：先创建茬口，再创建单元；第二步失败时统一显示保存失败，没有保存第一步成功状态，重试可能重复创建茬口。该风险尚未做故障注入复现。
5. **茬口状态不一致（P2）**：后端为 `active/completed/cancelled`；界面“计划”没有对应状态，`cancelled` 被归入“在种”。
6. **茬口显示字段未对齐（P2）**：后端仅返回模板 ID、阶段等信息，没有列表卡使用的 `crop_name/crop_template_name/progress_percent`；未补关联查询时显示未命名模板和默认零进度。

证据：[账本控制器](../lib/features/billing/billing_controller.dart)、[交易页面](../lib/features/billing/billing_screen.dart)、[茬口页面](../lib/features/business/farm_cycle_pages.dart)、[模板页面](../lib/features/business/crop_template_pages.dart)、[工人页面](../lib/features/business/worker_pages.dart)、[茬口序列化](../../agri_backend_v2/business/services/cycle_service.py)。

## 五、后端尚未提供的普通移动端能力

独立智能填写解析/场景、智能记账及茬口解析、每日 AI 建议刷新/历史、报告生成/历史/列表、移动端版本检查、普通用户技能列表。Agent `/admin/skills` 是管理员接口，不能直接替代普通用户能力。
对应 Repository 当前抛 `UnsupportedApiException`，版本检查返回 unavailable。记录页将智能整理引导到芽芽，技能页使用本地场景说明，这属于界面降级，不能计为独立 REST 能力已接入。

## 六、验证结果与测试盲区

| 验证 | 结果 | 限制 |
| --- | --- | --- |
| 两服务 `/api/v2/health` | 均正常；Agent 报告 Redis/Mongo 可达 | 不代表具体业务读写正常 |
| 两服务 `/openapi.json` | 成功读取 | 用于交叉核对路由及请求字段 |
| 后端真实请求模型 | 四类新增请求拒绝；去除冲突字段后通过；工人编辑通过 | 未写入数据库 |
| `flutter analyze --no-pub` | 通过，无问题 | 不验证后端契约 |
| `flutter test --no-pub --reporter expanded test/data test/features test/app` | 283 通过、28 失败 | 此范围未含 shared/theme/golden，不是完整测试套件 |
| backend_connectivity、v2_repository_contract、yaya_v2_contract 三组 | 11 项全部通过 | 只覆盖有限路径和解析规则 |

28 项失败主要集中在旧路径、旧数据格式、智能填写和版本等旧能力用例，不能全部认定为真实后端故障；定向测试通过也不能证明核心表单可用。
`RecordingAdapter` 按路径返回成功，不校验请求 Schema。页面测试还主动断言后端不接受的 `recorded_at/operation_time`，固化了错误契约。审批测试使用嵌套结构，真实 SSE 则为平铺 JSON；答案测试只测 Repository 事件，没有验证控制器合并后的正文。

日志：[范围测试](/tmp/agri-mobile-api-audit-tests.log)、[静态检查](/tmp/agri-mobile-api-audit-analyze.log)、[v2 定向测试](/tmp/agri-mobile-api-audit-v2.log)。日志在临时目录，不入库。

## 七、修复顺序与验收

1. 修复四个核心表单请求及字段级错误提示。验证正常保存、缺少必填、错误金额、重复点击和失败重试。
2. 修复真实 SSE 审批解析、失败后保留审批状态、最终全文替换及终态处理。用真实 wire 格式覆盖确认/取消、审批失败重试、增量加全文和断流恢复。
3. 补齐真实分页/服务端过滤和保存后刷新。用超过 10 条账单、20 条茬口/模板、100 条历史消息验证；对茬口部分成功做故障注入。
4. 依业务优先级补工资结算、账单修改删除、农事历史、系统模板导入和欠款结算界面，验证实际业务结果。
5. 迁移旧协议测试，让请求验证与后端契约一致，再用受控测试账号做实际设备端到端验收。

后续修改生产代码时需运行项目复杂度预算、对应测试及文档同步检查；本次只有文档更新，未运行代码修改门禁。

## 八、当前网络配置

Android 模拟器默认 Business `http://10.0.2.2:9876/api/v2`、Agent `http://10.0.2.2:8000/api/v2`；其他平台默认 `127.0.0.1`。USB Android 真机经启动脚本使用 `127.0.0.1` 加 `adb reverse`。
直接 Flutter 启动使用 `BUSINESS_API_BASE_URL`、`AGENT_API_BASE_URL` 编译参数。`deploy/flutter-android.sh` 接受 `BUSINESS_API_URL`、`AGENT_API_URL` 环境变量并转换为对应编译参数。
实体手机直接安装默认包时，不能靠模拟器别名或自身回环地址访问电脑；需按设备配置远程/局域网地址或 USB 转发。
本说明此前的固定局域网地址及 `/work-orders/labor/unsettled-summary` 描述已过时，当前工资摘要路径是 `/labor/unsettled-summary`。

## 九、截图中的硬编码成功回复：已由真实 Trace 确认

通过 `trace-chain-debugger` 只读查询 Mongo，找到与截图三轮提问完全匹配的会话 `app-1791101693279611`。以下结论为真实事件证据，不再只是代码推断。

| 用户输入 | Trace | 实际链路 |
| --- | --- | --- |
| 今天适合干什么 | `trace_d9394a067e03` | `get_farm_status` 成功 → 错误产生 `operation_committed` → 收尾模型仍请求工具 → 固定种植计划成功回复 |
| who are you | `trace_94aecb4edcef` | 正常生成自我介绍；同一正文分别通过 `final_answer_delta` 和 `final_answer` 发送，数据库仅保存一次 |
| my message | `trace_6259736cf54d` | `get_weather`、`get_farm_status` 成功 → 错误产生 `operation_committed` → 收尾模型仍请求工具 → 同一固定种植计划成功回复 |

两次异常回复的 LLM 节点均成功；实际触发原因不是模型服务报错，而是最终收尾仍返回工具调用。
事件 `write_committed_reply_failed` 明确记录：“写入已成功，但收尾模型仍请求调用工具；已阻止重复写入。”
但此前 `operation_committed.result` 的字段实际上是农场只读概览（`active_cycles/weather_today/workers_summary/cost_summary` 等），不是种植计划提交结果。
这两条链路没有种植计划写入工具或审批事件，不能把成功文案当成真正创建了种植计划。

具体根因：

1. `agent/tools/farm-status/skill.md` 第 6–7 行同时声明 `risk_level: read` 和 `finalize_after_success: true`，意图是查询完成后停止扩展工具调用。
2. Runtime `_post_process_skill_result`（engine.py 第 1418 行）把所有 `finalize_after_success` 都送入 `_mark_committed`，混淆“查询后收尾”和“写入已提交”。
3. 收尾轮仍请求工具时触发 `_finalize_committed_with_fallback`。
4. `_structured_commit_answer`（engine.py 第 2781 行）只支持种植计划结果，固定生成“种植计划已提交成功”，缺字段就填“未知”和“-”。以农场概览调用当前函数可精确复现截图文案。

正确修复边界：区分只读查询完成与真实业务提交；只在真实写入成功后产生 `operation_committed`；按结果类型生成降级答复，字段缺失不得宣告种植计划成功。简单删除文案或关闭查询收尾开关会掩盖状态语义问题。
同时修复移动端增量/最终全文合并：截图的双份自我介绍来自 App 重复追加，数据库和模型实际只有一份正文。
初始 Trace 核查未重放工具或写入 Trace；本轮已按上述边界修复 Runtime 和移动端控制器。


## 十、2026-10-04 修复与交付状态

### 已完成

- 收支创建接收 `recorded_at`，客户端停止提交服务端计算的 `settlement_status`。
- 农事创建/编辑接收 `operation_time` 并传入业务服务；SQLite 回归验证选择时刻实际持久化。
- 工资创建/编辑接收 `recorded_at`；新增工人接收已受领域服务支持的在职/离职状态。
- 六类业务表单显示服务端错误及 422 中文字段提示；登录过期与连接失败单独提示。
- 查询后的 Agent 收尾不再产生业务提交事件，并通过 `tool_choice=none` 禁止继续调用工具；固定种植成功兜底要求真实模板、茬口、单元 ID。
- SSE 支持平铺/嵌套审批参数，确认卡展示真实 `arguments`；审批失败保留卡片重试；最终全文覆盖流式草稿，失败终态不再静默忽略。
- 账单、模板、茬口和聊天历史加载后续页；旧消息页插在最新页前；修正后端会话列表游标反复返回先前页面的问题。
- 管理页面从新增/编辑返回后重新读取列表；已取消茬口归入结束状态；种植单元保存失败后复用已创建茬口，避免重试重复创建。
- 将旧路径、旧分页参数和不存在能力的测试迁移到当前 v2 契约。缺少独立帮填、报告或版本服务时验证明确不可用，不配置虚假的成功接口。

分页集中在现有 `ApiClient`，由账本、茬口和模板 Repository 复用；没有新增生产文件或抽象层。

### 验证与环境限制

- Flutter 全量 328 项回归（包括 golden）、静态检查通过，调试 APK 构建成功并覆盖安装到 `emulator-5554`。
- 后端 REST、Agent 收尾/流式、种植计划、身份边界与 Mongo 游标共 95 项回归通过；农事选择时刻有真实 SQLite 持久化验证。
- 修改文件 Ruff 检查通过。复杂度预算检查的尺寸/方法预算通过，但整体被工作区既有缓存污染阻挡，另外有归档与双锁警告；未清理其他任务遗留文件。
- 文档新鲜度脚本因根目录不存在旧版 `docs/` 而跳过；已手动同步本文、App README 和当前后端接口规范。
- 本机 MySQL 原先未运行，已启动 `mysql@8.0`；当前 `business/config.yaml` 指向 `localhost:3306/farm_manager`，数据库拒绝配置账号，报 1045。Business 正常入口的启动检查因此失败。
- Agent 服务已重新加载修复代码，Redis/Mongo 健康；App 已安装且登录界面可启动、无 Android 崩溃记录。尚未验证真实登录和业务写入，需提供有效数据库配置后启动 Business 并继续设备验收。

以上验证不意味着所有后端能力都已有独立移动端页面；第五节的后端缺口和第三节未有界面的扩展能力仍需单独产品实现。
