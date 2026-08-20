---
name: trace-chain-debugger
description: Use when debugging farm-manager Agent request chains, trace evidence, request_id/session_id/turn_id investigations, MySQL trace_records, Mongo traceRecords, conversationMessages, JSONL agent-events, tool-call failures, missing context evidence, slow LLM/tool nodes, or Mongo/MySQL consistency gaps during Codex development work.
---

# Trace Chain Debugger

## 核心边界

用于 Codex 开发调试，不是项目运行时 Agent Skill。默认只读：只查询 MySQL、Mongo 和本地 JSONL 事件，不修改业务数据，不重放工具，不写入 trace。

## 快速流程

1. 先确认用户给的是 `trace_id`、`request_id`、`conversation_id`、`session_id`、`turn_id`，还是一段报错日志。短 ID（如 `0744f155`）只对兼容的旧 request_id 使用前缀查询。
2. 在项目根目录运行脚本。旧版 archive/backend 链路仍使用：

```bash
agri_backend_v2/.venv/bin/python .codex/skills/trace-chain-debugger/scripts/analyze_trace_chain.py --project . --request-id 0744f155
```

v2 Agent 使用字符串 `turn_id`，并把 trace 存在 MongoDB 的 `traceRecords`；使用 v2 兼容模式：

```bash
python .codex/skills/trace-chain-debugger/scripts/analyze_trace_chain.py \
  --project . --agri_backend_v2 --turn-id a93fdbf47d7a
```

脚本会先通过 v2 `/traces` 列表把 `turn_id` 解析为对应的 `trace_id`（当前兼容响应可能仍叫 `request_id`），再读取 trace 节点和会话消息。
不要把 v2 的 `turn_id` 当成旧版 MySQL `agent_turns.id`。

3. 如果项目有多个开发环境，必须让脚本使用与后端进程一致的配置环境。优先确认 `FARM_MANAGER_ENV` 或 `APP_ENV` 是 `dev` 还是 `prod`；必要时用 `DATABASE__URL`、`MONGODB__URI`、`MONGODB__DATABASE` 等环境变量临时覆盖，但不要把密码或完整连接串输出给用户。
4. 需要看 trace 输入输出摘要时加 `--include-payload`。需要会话最近多轮时用 `--session-id <id> --limit 10`。
5. 报告里优先看：`解析范围`、`错误节点`、`耗时热点`、`证据状态`、`排查建议`。Mongo 不可用时保留 MySQL/JSONL 结论，并说明降级。

### v2 自动鉴权

v2 查询会自动按以下顺序获取用户 Bearer Token，令牌只保存在当前进程内存中，不写文件、不打印：

1. 复用 `V2_AGENT_AUTHORIZATION`、`AGENT_AUTHORIZATION`、`V2_AGENT_TOKEN` 或 `AGENT_TOKEN`；
2. 如果设置 `V2_AGENT_PHONE` 与 `V2_AGENT_PASSWORD`，调用 `POST /api/v2/auth/login` 自动登录；
3. 如果目标是本机 Agent 且没有登录凭据，调用开发专用 `/api/v2/dev-users`；只有匹配到唯一用户时才自动选择。多用户环境请设置 `V2_AGENT_USER_PHONE`。

示例：

```bash
export V2_AGENT_PHONE="13800138000"
read -r -s V2_AGENT_PASSWORD
export V2_AGENT_PASSWORD

python .codex/skills/trace-chain-debugger/scripts/analyze_trace_chain.py \
  --project . --agri_backend_v2 --trace-id <trace_id> --include-events
```

`V2_AGENT_AUTO_AUTH=0` 可以关闭自动鉴权。生产或非本机地址不会调用 `/dev-users`；应通过环境变量提供显式 Authorization 或登录凭据。鉴权失败会保留 `401/403`、登录失败和开发用户歧义等状态，不会伪装成空 Trace。

## v2 调试召回模式

v2 的正式链路主键和召回边界见 `references/v2-trace-recall-design.md` 以及
`../../../agri_backend_v2/docs/spec/2026-08-18-agent-trace-observability-and-recall-design.md`。

### 单轮 Turn

目标是还原一轮从接入、排队、Worker、LLM、Tool、审批、业务提交、最终答复到 `done` 的完整证据链。

优先级：`trace_id` > `turn_id` > 精确 `request_id` > 短 `request_id` 前缀。

目标接口顺序：

```text
GET /api/v2/traces?turn_id=<turn_id>
GET /api/v2/traces/{trace_id}/summary
GET /api/v2/traces/{trace_id}/timeline
GET /api/v2/conversations/{conversation_id}
```

单轮报告必须检查：

- `queued/accepted/started/meta` 是否存在；
- SSE `seq` 是否连续、`event_id` 是否重复；
- `approval_required -> approval_result` 是否闭合；
- `tool_started -> tool_finished -> observation` 是否闭合；
- `operation_committed` 是否有真实业务结果；
- `final_answer` 和 assistant 消息是否存在；
- `done` 是否唯一且状态正确；
- 第一个 error 节点及其上游输入。

### 整段会话

目标是还原 `conversation_id` 内多轮消息、Turn、Trace、工具结果和状态演进：

```text
GET /api/v2/conversations/{conversation_id}  # 分页读取消息
GET /api/v2/traces?conversation_id=<conversation_id>  # 分页读取每轮摘要
GET /api/v2/traces/{trace_id}/timeline  # 逐轮读取合并时间线
```

合并键固定为：

```text
conversation_id -> turn_id -> trace_id -> event_id/seq -> span_id
```

会话报告必须识别：上一轮工具结果是否进入下一轮上下文、是否出现重复 Turn/幂等重放、业务写入但没有最终答复、以及只有自然语言成功声明而无业务提交证据的情况。

### v2 接口命名

正式命名使用 `trace_id`：

```text
GET /api/v2/traces
GET /api/v2/traces/{trace_id}
GET /api/v2/traces/{trace_id}/summary
GET /api/v2/traces/{trace_id}/nodes
GET /api/v2/traces/{trace_id}/events
GET /api/v2/traces/{trace_id}/timeline
```

当前已存在的 `/api/v2/traces/{request_id}` 和 `.../summary` 是兼容入口。文档和报告统一输出 `trace_id`，不能把 v2 字符串 `turn_id` 当作旧版数字 `agent_turns.id`。

### CLI 参数

当前可执行的 v2 单轮命令：

```bash
python .codex/skills/trace-chain-debugger/scripts/analyze_trace_chain.py \
  --project . --agri_backend_v2 --turn-id <turn_id>
```

当前支持参数：`--trace-id`、`--conversation-id`、`--include-events`、`--include-payload`、`--json`。`traceEvents` 集合未创建或不可用时必须报告 `not_available(v2_api)`/`unavailable`，不能静默转为空事件。

### 报告口径

固定输出：`目标`、`解析范围`、`证据状态`、`会话/Turn 概览`、`SSE 时间线`、`Trace 时间线`、`业务结果`、`错误节点`、`证据缺口`、`排查建议`。

证据状态必须区分：`confirmed`、`inferred`、`missing`、`unavailable`、`not_implemented`。数据源不可用不等于没有数据；没有 assistant 消息也不能仅凭最终自然语言回复推断执行成功。

## 多环境配置

- `backend/config.dev.yaml` 和 `backend/config.prod.yaml` 由 `FARM_MANAGER_ENV=dev|prod` 或 `APP_ENV=dev|prod` 选择；未设置时可能回退到 `backend/config.yaml` 或默认值。
- 分析请求链路时，不要假设当前 shell、后台服务和用户指定环境连接的是同一套 MySQL/Mongo。先确认后端进程的工作目录和环境，再运行脚本。
- 如果用户说“开发环境不同 MySQL/Mongo 不同”，不要改业务配置代码；把差异作为运行上下文处理。示例：

```bash
FARM_MANAGER_ENV=dev backend/.venv/bin/python .codex/skills/trace-chain-debugger/scripts/analyze_trace_chain.py --project . --request-id 0744f155
FARM_MANAGER_ENV=prod backend/.venv/bin/python .codex/skills/trace-chain-debugger/scripts/analyze_trace_chain.py --project . --session-id <id> --limit 10
```

- 如果需要临时指定连接信息，用环境变量覆盖 YAML，并在汇报中只说明“使用 dev/prod/环境变量覆盖”，不要泄露真实 URL、密码、token 或账号。
- 如果同一个 `request_id` 在 JSONL 能找到，但 MySQL/Mongo 查不到，先排查配置环境不一致、事件目录不一致、`storage.trace` 和 `storage.conversation_messages` 后端差异。

## 参数选择

- 单次请求：`--request-id <完整或前缀>`。
- 会话链路：`--session-id <session_id> --limit 5`。
- 精确 turn：`--turn-id <agent_turns.id 或 v2 字符串 turn_id>`。
- 输出机器可读结果：加 `--json`。
- v2 服务地址：加 `--v2-base-url <url>`，默认 `http://127.0.0.1:8000`。
- 只想快速定位候选：短 request_id 前缀即可，脚本会列出匹配候选。

## 调试判断

- `agent_turns` 有记录但 trace 为空：检查 TraceDAO flush、trace_context、storage.trace。
- MySQL `trace_records` 缺表但 Mongo 有 `traceRecords`：这是 trace 存储切到 Mongo 或 MySQL 文档表清理后的常见状态，不要把整个链路判为丢失。
- MySQL 有 trace、Mongo 为空且 Mongo 状态 ok：检查 dual-write、补偿队列、`traceRecords` collection。
- Mongo 有 trace、MySQL 为空：检查 `storage.trace=mongo`、MySQL 表是否被清理或缺失。
- `conversationMessages.traceId`、`conversationMessages.turnId` 是消息到 Trace 的正式回链；旧数据的 `meta.trace_request_id` 只作为兼容证据。`meta.event_file` 和 `meta.event_seq_range` 是 JSONL 事件回链。
- 多环境开发时，MySQL/Mongo 未命中不等于证据丢失；先确认脚本和后端是否使用同一个 `FARM_MANAGER_ENV`、`APP_ENV`、`database.url`、`mongodb.uri`、`mongodb.database`。
- 第一个 error 节点通常是根因入口，沿时间线向前看输入、上下文和上一轮工具结果。
- 慢节点超过 5 秒时，优先排查外部网络、LLM provider、Mongo server selection 或 MySQL 慢查询。

## 参考资料

需要确认项目表、collection 和字段映射时读取 `references/farm-manager-trace-map.md`。
需要确认 v2 Trace 接口、SSE 事件和整段/单轮召回方式时读取 `references/v2-trace-recall-design.md`。
