# AGENTS.md — 项目地图

> Agent 入口文件。控制在 80 行以内，详细内容放 rules/ 和 docs/。

## 项目简介
farm-manager，FastAPI 后端 + React+TS 前端

## 快速导航
| 你想做什么 | 去哪里看 |
|-----------|---------|
| 了解系统架构 | docs/architecture/overview.md |
| 了解系统演进路线图 | docs/architecture/evolution-roadmap.md |
| 了解 Agent 平台目标架构 | docs/architecture/overview.md#agent-平台边界 |
| 了解模块边界和依赖规则 | docs/architecture/boundaries.md |
| 了解兼容入口保留理由 | docs/architecture/compatibility-entries.md |
| 了解 Python 编码规范 | .Codex/rules/python-style.md |
| 了解前端编码规范 | .Codex/rules/frontend-style.md |
| 了解安全规范 | .Codex/rules/security.md |
| 了解文档同步规则 | .Codex/rules/docs-sync.md |
| 了解 Skill 书写规范 | .Codex/rules/skill-writing.md |
| 了解当前迭代任务 | docs/plans/current-sprint.md |
| 了解设计文档模板 | docs/design/TEMPLATE.md |

<!-- Guide+Sensor 配对说明：以下每条规则都应对应 scripts/ 中的检查脚本。
     运行 bash scripts/check-guide-sensor-pairing.sh 验证配对完整性。 -->
## 硬性规则（CI 会验证）
1. 依赖方向：后端以 api → application/modules/platform → shared/core/models/infra 为目标，兼容期旧分层由 check-layer-deps.sh 检查；前端 api → components → layouts → pages
2. 横切关注点（auth/log/telemetry）只通过依赖注入
3. 单文件 ≤ 500 行，单方法 ≤ 50 行
4. 新增代码必须有对应测试
5. 使用结构化日志，禁止 console.log / print 调试
6. 错误信息必须含 code 字段和上下文
7. 修改代码后必须运行复杂度预算检查；新增抽象、生成物入库、大文件和工作区污染由 check-complexity-budget.sh 拦截

## 可测试性分级
开发新功能前，先判断需求类型再选验证策略：
| 需求类型 | 验证方式 | 人工审查 |
|---------|---------|---------|
| 需求明确+可测试 | CI 七道门 | 不需要 |
| 需求明确+不可测试 | Agent 结构检查 + 关键节点人工审查 | 需要 |
| 需求模糊+不可测试 | 人主导，Agent 辅助 | 必须 |

## 常用命令
| 操作 | 命令 |
|------|------|
| Lint | ``ruff check . && ruff format .`` |
| 架构约束 | `bash scripts/check-layer-deps.sh` |
| 复杂度预算 | `bash scripts/check-complexity-budget.sh` |
| Guide+Sensor 配对 | `bash scripts/check-guide-sensor-pairing.sh` |
| Lint 规则过期追踪 | `bash scripts/check-lint-expiry.sh` |
| Harness 全量检查 | `bash scripts/harness-check.sh` |
| 后端启动 | `poetry run uvicorn app.main:app --reload` |
| 后端测试 | `poetry run pytest -v` |
| 前端启动 | `pnpm dev` |
| 前端测试 | `pnpm test` |

## 提交规范
- feat: 新功能 | fix: 修复 | refactor: 重构 | docs: 文档 | test: 测试 | chore: 杂项
- 禁止提交 .env、密钥、大文件
- 同天多个 commit 合并为一个（squash）
