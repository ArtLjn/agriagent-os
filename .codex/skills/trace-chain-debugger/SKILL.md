---
name: trace-chain-debugger
description: Use when debugging farm-manager Agent request chains, trace evidence, request_id/session_id/turn_id investigations, MySQL trace_records, Mongo traceRecords, conversationMessages, JSONL agent-events, tool-call failures, missing context evidence, slow LLM/tool nodes, or Mongo/MySQL consistency gaps during Codex development work.
---

# Trace Chain Debugger

## 核心边界

用于 Codex 开发调试，不是项目运行时 Agent Skill。默认只读：只查询 MySQL、Mongo 和本地 JSONL 事件，不修改业务数据，不重放工具，不写入 trace。

## 快速流程

1. 先确认用户给的是 `request_id`、`session_id`、`turn_id`，还是一段报错日志。短 ID（如 `0744f155`）先按 request_id 前缀查。
2. 在项目根目录运行脚本：

```bash
backend/.venv/bin/python .codex/skills/trace-chain-debugger/scripts/analyze_trace_chain.py --project . --request-id 0744f155
```

3. 如果项目有多个开发环境，必须让脚本使用与后端进程一致的配置环境。优先确认 `FARM_MANAGER_ENV` 或 `APP_ENV` 是 `dev` 还是 `prod`；必要时用 `DATABASE__URL`、`MONGODB__URI`、`MONGODB__DATABASE` 等环境变量临时覆盖，但不要把密码或完整连接串输出给用户。
4. 需要看 trace 输入输出摘要时加 `--include-payload`。需要会话最近多轮时用 `--session-id <id> --limit 10`。
5. 报告里优先看：`解析范围`、`错误节点`、`耗时热点`、`证据状态`、`排查建议`。Mongo 不可用时保留 MySQL/JSONL 结论，并说明降级。

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
- 精确 turn：`--turn-id <agent_turns.id>`。
- 输出机器可读结果：加 `--json`。
- 只想快速定位候选：短 request_id 前缀即可，脚本会列出匹配候选。

## 调试判断

- `agent_turns` 有记录但 trace 为空：检查 TraceDAO flush、trace_context、storage.trace。
- MySQL `trace_records` 缺表但 Mongo 有 `traceRecords`：这是 trace 存储切到 Mongo 或 MySQL 文档表清理后的常见状态，不要把整个链路判为丢失。
- MySQL 有 trace、Mongo 为空且 Mongo 状态 ok：检查 dual-write、补偿队列、`traceRecords` collection。
- Mongo 有 trace、MySQL 为空：检查 `storage.trace=mongo`、MySQL 表是否被清理或缺失。
- `conversationMessages.meta.trace_request_id` 是消息到 trace 的关键回链；`meta.event_file` 和 `meta.event_seq_range` 是 JSONL 事件回链。
- 多环境开发时，MySQL/Mongo 未命中不等于证据丢失；先确认脚本和后端是否使用同一个 `FARM_MANAGER_ENV`、`APP_ENV`、`database.url`、`mongodb.uri`、`mongodb.database`。
- 第一个 error 节点通常是根因入口，沿时间线向前看输入、上下文和上一轮工具结果。
- 慢节点超过 5 秒时，优先排查外部网络、LLM provider、Mongo server selection 或 MySQL 慢查询。

## 参考资料

需要确认项目表、collection 和字段映射时读取 `references/farm-manager-trace-map.md`。
