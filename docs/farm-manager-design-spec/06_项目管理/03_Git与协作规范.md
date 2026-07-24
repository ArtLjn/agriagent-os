# 03 — Git 与协作规范

> 状态：草稿 | 维护：BlockShip | 关联：[04_相关规范/06_防污染与文档同步规范](../04_相关规范/06_防污染与文档同步规范.md)

---

## 1. 分支模型

采用 trunk-based + 短期 feature branch。

```
main (保护分支，永远可发布)
 ├── feature/<scope>-<short-desc>  (#123)
 ├── fix/<scope>-<short-desc>
 ├── refactor/<scope>-<short-desc>
 ├── docs/<short-desc>
 ├── chore/<short-desc>
 └── hotfix/<short-desc>  (从 main 拉，合并回 main + tag)
```

**规则**：
- `main` 永远可发布，禁止直接 push。
- 所有改动通过 PR 合并，至少 1 个 reviewer approve。
- feature branch 生命周期 ≤ 1 sprint（> 2 周必须拆分或合并）。
- hotfix 完成后必须打 tag（`v1.2.10-hotfix.1`）。

## 2. 分支命名

| 类型 | 格式 | 示例 |
| --- | --- | --- |
| 功能 | `feature/<scope>-<desc>` | `feature/skill-create-debt` |
| 修复 | `fix/<scope>-<desc>` | `fix/billing-summary-unit` |
| 重构 | `refactor/<scope>-<desc>` | `refactor/runtime-graph` |
| 文档 | `docs/<desc>` | `docs/spec-system-testing` |
| 杂项 | `chore/<desc>` | `chore/upgrade-ruff` |
| 性能 | `perf/<scope>-<desc>` | `perf/cost-list-index` |
| 热修 | `hotfix/<desc>` | `hotfix/jwt-refresh-bug` |

`<scope>` 优先用模块名：`agent` / `skill` / `cost` / `cycle` / `weather` / `context` / `memory` / `prompt` / `flywheel` / `admin` / `mobile` / `deploy`。

## 3. Commit 规范

### 3.1 格式

参考 [04_相关规范/06_防污染与文档同步规范](../04_相关规范/06_防污染与文档同步规范.md) 第 3 节。

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 3.2 type

| type | 用途 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `refactor` | 重构（不改外部行为） |
| `docs` | 文档 |
| `test` | 测试 |
| `chore` | 杂项（依赖、CI、配置） |
| `perf` | 性能优化 |
| `style` | 格式（不改逻辑） |
| `ci` | CI/CD |
| `build` | 构建 |

### 3.3 scope

| scope | 范围 |
| --- | --- |
| `agent` | Agent runtime / router / executor / reflector |
| `skill` | Skill 实现 / 契约 |
| `cost` | 成本 / 收入 / 账单 |
| `cycle` | 茬口 |
| `crop` | 作物模板 |
| `weather` | 天气 / 预警 |
| `context` | Context 工程 |
| `memory` | Memory 工程 |
| `prompt` | Prompt 工程 |
| `flywheel` | DataFlywheel |
| `admin` | Admin Web |
| `mobile` | 移动端 |
| `api` | API 端点 |
| `db` | 数据库 / 迁移 |
| `auth` | 认证 / 授权 |
| `deploy` | 部署 / 运维 |
| `trace` | 观测 / trace |
| `ci` | CI 流水线 |

### 3.4 示例

```
feat(skill): add create-cost-record skill with pending confirmation

- 实现 create_cost_record Skill 写操作
- 通过 PendingAction 二次确认
- 添加 5 个单元测试 + 2 个集成测试

Closes #123
```

```
fix(cost): correct billing summary amount unit (yuan → cents)

- 修复汇总时单位混淆导致金额显示 ×100
- 添加 unit test 覆盖分/元转换
- 回归 2026-06 的所有 billing 相关 trace

Fixes #145
```

### 3.5 规则

- subject ≤ 70 字符，动词开头，结尾不加句号。
- 中文 subject 允许，type / scope 用英文。
- 一个 commit 一个逻辑变更。
- body 解释 **为什么**（what 看代码即可）。
- 大改拆多 commit，每个独立可编译。
- 同天多个相关 commit 可在合并前 squash 成一个。

## 4. PR 规范

### 4.1 标题

同 commit subject 格式（PR squash 合并时直接复用）。

### 4.2 描述模板

```markdown
## 背景
为什么做这个改动（链接 issue / spec 章节 / 用户反馈）。

## 改动
- 改动 1
- 改动 2

## 测试
- [x] 单元测试通过
- [x] 集成测试通过
- [x] 手工验证场景 <描述>

## 文档
- 更新 xxx.md
- 更新本 Spec xxx 章节

## 关联
- Closes #123
- Depends on #124
```

### 4.3 Review 标准

| 维度 | 检查 |
| --- | --- |
| 功能 | 是否解决问题，无回归 |
| 架构 | 是否符合 [01_正式设计/01_Agent平台架构] 边界 |
| 代码质量 | [04_相关规范/05_Python编码规范] / [04_相关规范/04_前端编码规范] |
| 测试 | 覆盖正常 + 异常 + 边界 |
| 安全 | [04_相关规范/02_安全与权限规范] 全部满足 |
| 文档 | 按 [04_相关规范/06_防污染与文档同步规范] 第 2.1 节同步 |
| 性能 | 是否引入 N+1 / 死循环 / 大对象 |

### 4.4 合并方式

| 场景 | 方式 |
| --- | --- |
| 单 commit PR | Squash merge |
| 多 commit 拆分清晰（如重构 + 测试） | Rebase merge |
| 大 feature 多人协作 | Merge commit（保留分支历史） |

默认 squash merge。

## 5. 版本号

参考 SemVer。

```
v<MAJOR>.<MINOR>.<PATCH>
```

| 变更 | 升级 |
| --- | --- |
| 数据库不兼容 / API 破坏性变更 | MAJOR |
| 新增功能（向后兼容） | MINOR |
| Bug 修复 | PATCH |

预发布：`v1.3.0-rc.1`。
热修：`v1.2.10-hotfix.1`。

**当前版本**：`v1.2.9`（参考 `git log`）。

## 6. Tag 与发布

```bash
# 发布流程
git checkout main && git pull
git tag -a v1.3.0 -m "release: v1.3.0"
git push origin v1.3.0

# CI 自动触发
# 1. 跑全集测试 + 仿真 + 评测
# 2. 构建产物
# 3. 部署 staging → 灰度 → prod
# 4. 通知发布渠道
```

详见部署文档 [../../../docs/architecture/overview.md](../../../docs/architecture/overview.md)。

## 7. Code Owner

`CODEOWNERS` 文件示例：

```
*                           @BlockShip
/backend/app/agent/         @BlockShip
/backend/app/skills/        @BlockShip
/backend/app/domains/users/ @BlockShip
/backend/app/domains/planting/ @BlockShip
/admin-web/                 @BlockShip
/mobile-app/                @BlockShip
/docs/farm-manager-design-spec/  @BlockShip
/docs/                      @BlockShip
/.claude/rules/             @BlockShip
```

后续若团队扩大，按模块分配 owner。

## 8. 冲突解决

- PR 合并前必须 rebase 到最新 `main`。
- 冲突优先 rebase 解决，不用 merge commit。
- 大冲突（如重构同名模块）必须线下同步讨论。

## 9. 敏感操作（必须人工确认）

| 操作 | 确认方 |
| --- | --- |
| `git push --force` 到 main / release 分支 | 禁止 |
| `git push --force` 到 feature 分支（多人协作） | 通知协作者 |
| 删除分支 | PR 合并后由 GitHub 自动删 |
| `git reset --hard` 已 push 的 commit | 禁止 |
| 修改历史 commit message | 仅未 push 时 |

参考 [CLAUDE.md](../../CLAUDE.md) 全局规则：不跳 hooks、不做破坏性 git 操作。

## 10. CI 流水线

`.github/workflows/ci.yml`：

| Stage | 触发 | 动作 |
| --- | --- | --- |
| Lint | 所有 PR | ruff / eslint |
| Unit Test | 所有 PR | pytest / vitest / flutter_test |
| Layer Deps | 所有 PR | check-layer-deps.sh |
| Skill Contract | 所有 PR | test_skill_docs.py |
| Integration | PR to main | pytest tests/api tests/agent |
| Simulation Smoke | PR to main | pytest tests/simulation -q 或后端启动后调用 `/simulation/run` |
| Build | merge to main | 构建镜像 + 推 registry |
| Deploy Staging | merge to main | 自动部署 staging |
| Deploy Prod | tag v* | 人工 approve 后部署 |

## 11. 协作工具

| 用途 | 工具 |
| --- | --- |
| 代码托管 | GitHub |
| 任务管理 | GitHub Project / Issue |
| 文档 | 本 Spec + docs/ |
| 沟通 | 微信 / Slack |
| 决策 | ADR `docs/adr/` |
| 紧急响应 | 电话 + oncall 轮值 |

## 12. 相关文档

- [01_里程碑与路线图.md](./01_里程碑与路线图.md)
- [02_工作拆解.md](./02_工作拆解.md)
- [04_相关规范/06_防污染与文档同步规范](../04_相关规范/06_防污染与文档同步规范.md)
- [../../CLAUDE.md](../../CLAUDE.md)
