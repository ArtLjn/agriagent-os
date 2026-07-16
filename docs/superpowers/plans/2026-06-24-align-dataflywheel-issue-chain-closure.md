# DataFlywheel IssueChain Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 DataFlywheel 的最终人工判断、回归草稿和修复包出口收口到 ReviewIssueChain 主流程，并把高级搜索降级为查证入口。

**Architecture:** 后端先补齐固定标签、证据 checklist 和 chain 资产出口契约；前端再让 Daily Review 调用 chain API，同时移除高级搜索中的正式标注/导出入口。旧 sample API 保留为兼容调试路径，但产品 UI 不再走它生成正式资产。

**Tech Stack:** FastAPI、SQLAlchemy、pytest、React 19、TypeScript、Ant Design、Vitest、OpenSpec。

---

## 文件结构

- 修改：`backend/app/modules/data_flywheel/service.py`
  - 负责 DataFlywheel 标签枚举、sample row、source/evidence 基础序列化。
- 修改：`backend/app/modules/data_flywheel/review_issue_chain_helpers.py`
  - 负责 ReviewIssueChain timeline turn、evidence checklist、evidence status。
- 修改：`backend/app/modules/data_flywheel/review_issue_chain_repository.py`
  - 负责 chain review 保存校验，复用 `ALLOWED_LABELS`。
- 修改：`backend/app/modules/data_flywheel/repair_pack_repository.py`
  - 给 sample 级 repair pack 响应加 compatibility/debug 标识。
- 修改：`backend/app/modules/data_flywheel/review_issue_chain_case.py`
  - 确认 chain draft metadata 完整；必要时加 status guard。
- 修改：`backend/tests/api/test_admin_data_flywheel.py`
  - 覆盖标签枚举、evidence checklist、sample 兼容路径。
- 修改：`backend/tests/api/test_admin_data_flywheel_review_issue_chain_closure.py`
  - 覆盖 chain final label、chain draft/repair pack 出口阻断。
- 修改：`backend/tests/api/test_admin_data_flywheel_repair_packs.py`
  - 覆盖 sample repair pack compatibility/debug 标识。
- 修改：`admin-web/src/api/dataFlywheel.ts`
  - 补齐标签类型、chain draft/repair pack API 方法、repair pack case 字段。
- 修改：`admin-web/src/api/dataFlywheel.test.ts`
  - 覆盖新增 API endpoint 编码和 payload。
- 修改：`admin-web/src/pages/DataFlywheel/components/IssueChainReviewPanel.tsx`
  - 补齐标签集合和 chain 闭环按钮。
- 修改：`admin-web/src/pages/DataFlywheel/components/DailyReviewWorkbench.tsx`
  - 承接 chain draft/repair pack 回调和预览状态。
- 修改：`admin-web/src/pages/DataFlywheel/index.tsx`
  - 移除高级搜索详情栏中的正式标注/回归/修复包入口，保留 debug/证据能力。
- 修改：`admin-web/src/pages/DataFlywheel/index.test.tsx`
  - 覆盖每日质检 chain 出口和高级搜索边界。
- 修改：`admin-web/src/pages/DataFlywheel/layout.test.tsx`
  - 覆盖默认入口和高级搜索结构不回退。
- 修改：`docs/farm-manager-design-spec/01_正式设计/06_数据飞轮与评测.md`
  - 更新当前状态和旧入口边界说明。

## Task 1: 固定标签集合对齐

**Files:**
- Modify: `backend/app/modules/data_flywheel/service.py`
- Modify: `backend/tests/api/test_admin_data_flywheel_review_issue_chain_closure.py`
- Modify: `admin-web/src/api/dataFlywheel.ts`
- Modify: `admin-web/src/pages/DataFlywheel/index.tsx`
- Modify: `admin-web/src/pages/DataFlywheel/components/IssueChainReviewPanel.tsx`
- Test: `backend/tests/api/test_admin_data_flywheel_review_issue_chain_closure.py`
- Test: `admin-web/src/api/dataFlywheel.test.ts`

- [ ] **Step 1: 写后端失败测试，证明 `tool_parameter_mismatch` 可保存为 final label**

在 `backend/tests/api/test_admin_data_flywheel_review_issue_chain_closure.py` 末尾追加：

```python
def test_review_issue_chain_accepts_tool_parameter_mismatch_label(
    db_session, tmp_path
) -> None:
    _, trigger, _ = _seed_reviewed_chain(db_session, tmp_path)

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}/review",
            json={
                "status": "accepted",
                "context_turn_ids": [],
                "result_turn_ids": [],
                "final_labels": ["tool_parameter_mismatch", "needs_regression"],
                "root_cause": "批量结算作用域被收窄为单个工人",
                "expected_behavior": "应保留所有待结算工人并逐一生成确认步骤。",
            },
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    human_review = resp.json()["chain"]["human_review"]
    assert "tool_parameter_mismatch" in human_review["quality_labels"]
    assert human_review["expected_behavior"] == (
        "应保留所有待结算工人并逐一生成确认步骤。"
    )
```

- [ ] **Step 2: 运行后端测试确认失败**

Run:

```bash
cd backend && pytest tests/api/test_admin_data_flywheel_review_issue_chain_closure.py::test_review_issue_chain_accepts_tool_parameter_mismatch_label -q
```

Expected: FAIL，错误包含 `INVALID_LABEL` 或 HTTP 400。

- [ ] **Step 3: 后端加入标签枚举**

在 `backend/app/modules/data_flywheel/service.py` 的 `ALLOWED_LABELS` 中加入：

```python
    "tool_parameter_mismatch",
```

最终集合应包含：

```python
ALLOWED_LABELS = {
    "good_reply",
    "bad_reply",
    "wrong_tool_selection",
    "tool_parameter_mismatch",
    "pending_missed",
    "hallucinated_execution",
    "tool_error_ignored",
    "missing_wage",
    "disabled_worker_used",
    "needs_regression",
    "off_topic",
    "sensitive_info_leak",
    "unclear_intent",
    "not_actionable",
}
```

- [ ] **Step 4: 前端类型和筛选标签加入 `tool_parameter_mismatch`**

在 `admin-web/src/api/dataFlywheel.ts` 的 `DataFlywheelLabel` union 中加入：

```ts
  | 'tool_parameter_mismatch'
```

在 `admin-web/src/pages/DataFlywheel/index.tsx` 的 `labelOptions` 加入：

```ts
  { label: '工具参数错配', value: 'tool_parameter_mismatch' },
```

- [ ] **Step 5: IssueChain 审核面板使用完整标签集合**

把 `admin-web/src/pages/DataFlywheel/components/IssueChainReviewPanel.tsx` 中的 `labelOptions` 替换为：

```ts
const labelOptions = [
  { label: 'good_reply', value: 'good_reply' },
  { label: 'bad_reply', value: 'bad_reply' },
  { label: 'wrong_tool_selection', value: 'wrong_tool_selection' },
  { label: 'tool_parameter_mismatch', value: 'tool_parameter_mismatch' },
  { label: 'pending_missed', value: 'pending_missed' },
  { label: 'hallucinated_execution', value: 'hallucinated_execution' },
  { label: 'tool_error_ignored', value: 'tool_error_ignored' },
  { label: 'off_topic', value: 'off_topic' },
  { label: 'sensitive_info_leak', value: 'sensitive_info_leak' },
  { label: 'missing_wage', value: 'missing_wage' },
  { label: 'disabled_worker_used', value: 'disabled_worker_used' },
  { label: 'unclear_intent', value: 'unclear_intent' },
  { label: 'not_actionable', value: 'not_actionable' },
  { label: 'needs_regression', value: 'needs_regression' },
];
```

- [ ] **Step 6: 运行标签相关测试**

Run:

```bash
cd backend && pytest tests/api/test_admin_data_flywheel_review_issue_chain_closure.py::test_review_issue_chain_accepts_tool_parameter_mismatch_label -q
cd admin-web && pnpm test src/api/dataFlywheel.test.ts
```

Expected: 两个命令 PASS。

- [ ] **Step 7: 提交**

```bash
git add backend/app/modules/data_flywheel/service.py \
  backend/tests/api/test_admin_data_flywheel_review_issue_chain_closure.py \
  admin-web/src/api/dataFlywheel.ts \
  admin-web/src/pages/DataFlywheel/index.tsx \
  admin-web/src/pages/DataFlywheel/components/IssueChainReviewPanel.tsx
git commit -m "fix: 对齐数据飞轮固定标签集合"
```

## Task 2: ReviewIssueChain 证据 checklist 增强

**Files:**
- Modify: `backend/app/modules/data_flywheel/service.py`
- Modify: `backend/app/modules/data_flywheel/review_issue_chain_helpers.py`
- Modify: `backend/tests/api/test_admin_data_flywheel.py`
- Test: `backend/tests/api/test_admin_data_flywheel.py`

- [ ] **Step 1: 写缺 trace、db diff、backfilled 的失败测试**

在 `backend/tests/api/test_admin_data_flywheel.py` 末尾追加：

```python
def test_review_issue_chain_evidence_checklist_exposes_trace_db_diff_and_backfill(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.91
    turn.risk_severity = "P0"
    turn.risk_dominant_signal = "rule"
    db_session.commit()

    events = admin_data_flywheel_api.read_event_segment(
        turn.event_file,
        turn.event_seq_start,
        turn.event_seq_end,
    )
    for event in events:
        if event["event_type"] == "message.user":
            event["payload"]["backfilled"] = True
    with open(turn.event_file, "w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    checklist = {
        item["key"]: item["status"]
        for item in resp.json()["evidence_checklist"]
    }
    assert checklist["event_log"] == "present"
    assert checklist["chat_messages"] == "present"
    assert checklist["router_decision"] == "present"
    assert checklist["tool_result"] == "present"
    assert checklist["pending_lifecycle"] == "present"
    assert checklist["trace"] == "missing"
    assert checklist["db_diff"] == "needs_human"
    assert checklist["backfilled_event"] == "present"
```

如果 `admin_data_flywheel_api.read_event_segment` 不存在于该模块导入上下文，改为在测试顶部加入：

```python
from app.infra.agent_events import read_event_segment
```

并把测试中的调用改成：

```python
events = read_event_segment(
    turn.event_file,
    turn.event_seq_start,
    turn.event_seq_end,
)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && pytest tests/api/test_admin_data_flywheel.py::test_review_issue_chain_evidence_checklist_exposes_trace_db_diff_and_backfill -q
```

Expected: FAIL，缺少 `trace`、`db_diff` 或 `backfilled_event` key。

- [ ] **Step 3: 在 helper 中实现证据判断函数**

在 `backend/app/modules/data_flywheel/review_issue_chain_helpers.py` 中加入 import：

```python
from app.models.trace import TraceRecord
```

添加辅助函数：

```python
def _has_trace(db: Session, turn: AgentTurn) -> bool:
    if not turn.request_id:
        return False
    return (
        db.query(TraceRecord.id)
        .filter(TraceRecord.request_id == turn.request_id)
        .first()
        is not None
    )


def _has_backfilled_event(events: list[dict[str, Any]]) -> bool:
    for event in events:
        payload = event.get("payload") or {}
        if isinstance(payload, dict) and payload.get("backfilled") is True:
            return True
    return False
```

- [ ] **Step 4: 替换 evidence_checklist 签名和内容**

把 `evidence_checklist(trigger: AgentTurn, events: list[dict[str, Any]])` 改为：

```python
def evidence_checklist(
    db: Session, trigger: AgentTurn, events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    source = _source_to_dict(trigger)
    event_status = source["event_log_status"]
    tool_events = _tool_events(events)
    pending_events = _pending_lifecycle(events)
    return [
        {
            "key": "event_log",
            "status": "present" if event_status == "available" else "missing",
            "turn_id": trigger.id,
        },
        {"key": "chat_messages", "status": "present", "turn_id": trigger.id},
        {
            "key": "router_decision",
            "status": "present" if _router_decision(events) else "missing",
            "turn_id": trigger.id,
        },
        {
            "key": "tool_result",
            "status": "present" if tool_events else "needs_human",
            "turn_id": trigger.id,
        },
        {
            "key": "pending_lifecycle",
            "status": "present" if pending_events else "needs_human",
            "turn_id": trigger.id,
        },
        {
            "key": "trace",
            "status": "present" if _has_trace(db, trigger) else "missing",
            "turn_id": trigger.id,
        },
        {
            "key": "db_diff",
            "status": "needs_human",
            "turn_id": trigger.id,
        },
        {
            "key": "backfilled_event",
            "status": "present" if _has_backfilled_event(events) else "missing",
            "turn_id": trigger.id,
        },
    ]
```

- [ ] **Step 5: 更新调用点**

在 `backend/app/modules/data_flywheel/review_issue_chain_service.py` 的 `_chain_for_turn()` 中，把：

```python
evidence = evidence_checklist(trigger, events)
```

改为：

```python
evidence = evidence_checklist(db, trigger, events)
```

- [ ] **Step 6: 运行证据测试**

Run:

```bash
cd backend && pytest tests/api/test_admin_data_flywheel.py::test_review_issue_chain_evidence_checklist_exposes_trace_db_diff_and_backfill -q
```

Expected: PASS。

- [ ] **Step 7: 运行现有 chain closure 测试确认未破坏 repair warnings**

Run:

```bash
cd backend && pytest tests/api/test_admin_data_flywheel_review_issue_chain_closure.py -q
```

Expected: PASS；如果 repair pack warnings 因 `db_diff=needs_human` 变化导致断言失败，将该测试的 `manifest["warnings"] == []` 改为检查 warnings 包含 `db_diff` 且 repair pack 仍可导出 only when chain accepted。

- [ ] **Step 8: 提交**

```bash
git add backend/app/modules/data_flywheel/review_issue_chain_helpers.py \
  backend/app/modules/data_flywheel/review_issue_chain_service.py \
  backend/tests/api/test_admin_data_flywheel.py \
  backend/tests/api/test_admin_data_flywheel_review_issue_chain_closure.py
git commit -m "fix: 增强问题链证据状态"
```

## Task 3: 前端 API 增加 chain draft 和 chain repair pack 方法

**Files:**
- Modify: `admin-web/src/api/dataFlywheel.ts`
- Modify: `admin-web/src/api/dataFlywheel.test.ts`
- Test: `admin-web/src/api/dataFlywheel.test.ts`

- [ ] **Step 1: 写 API 失败测试**

在 `admin-web/src/api/dataFlywheel.test.ts` 的 imports 中加入：

```ts
  createReviewIssueChainCaseDraft,
  createReviewIssueChainRepairPack,
```

在 describe 内追加：

```ts
  it('从问题链生成 regression draft', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 9,
        draft_id: 'draft-chain-1',
        source_sample_id: 'turn:1:s:1',
        target_type: 'evaluation_replay',
        status: 'draft',
        case_json: { metadata: { chain_id: 'chain:1:s:1' } },
        created_by: 'admin',
      },
    });

    const result = await createReviewIssueChainCaseDraft(
      'chain:1:playground:s:1:12',
      'evaluation_replay'
    );

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/review-issue-chains/chain%3A1%3Aplayground%3As%3A1%3A12/case-draft',
      { target_type: 'evaluation_replay' }
    );
    expect(result.case_json.metadata).toEqual({ chain_id: 'chain:1:s:1' });
  });

  it('从问题链导出 repair pack', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 10,
        pack_id: 'repair-router-abc',
        fix_target: 'router',
        labels: ['tool_parameter_mismatch'],
        source_sample_ids: ['turn:1:s:1'],
        source_label_ids: [],
        status: 'exported',
        export_path: 'data/repair-packs/repair-router-abc',
        manifest: { source_chain_ids: ['chain:1:s:1'] },
      },
    });

    const result = await createReviewIssueChainRepairPack('chain:1:playground:s:1:12');

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/review-issue-chains/chain%3A1%3Aplayground%3As%3A1%3A12/repair-pack'
    );
    expect(result.manifest.source_chain_ids).toEqual(['chain:1:s:1']);
  });
```

- [ ] **Step 2: 运行 API 测试确认失败**

Run:

```bash
cd admin-web && pnpm test src/api/dataFlywheel.test.ts
```

Expected: FAIL，提示导入的函数不存在。

- [ ] **Step 3: 实现前端 API 方法**

在 `admin-web/src/api/dataFlywheel.ts` 的 `saveReviewIssueChainReview()` 后加入：

```ts
export async function createReviewIssueChainCaseDraft(
  chainId: string,
  targetType: CaseDraftTargetType
): Promise<CaseDraft> {
  const response = await apiClient.post<CaseDraft>(
    `/admin/data-flywheel/review-issue-chains/${encodeURIComponent(chainId)}/case-draft`,
    { target_type: targetType }
  );
  return response.data;
}

export async function createReviewIssueChainRepairPack(
  chainId: string
): Promise<DataFlywheelRepairPack> {
  const response = await apiClient.post<DataFlywheelRepairPack>(
    `/admin/data-flywheel/review-issue-chains/${encodeURIComponent(chainId)}/repair-pack`
  );
  return response.data;
}
```

在 `RepairPackCase` 中补充 chain 字段：

```ts
  chain_id?: string | null;
  trigger_turn_id?: number | null;
  context_turn_ids?: number[];
  result_turn_ids?: number[];
  root_cause?: string | null;
```

- [ ] **Step 4: 运行 API 测试确认通过**

Run:

```bash
cd admin-web && pnpm test src/api/dataFlywheel.test.ts
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add admin-web/src/api/dataFlywheel.ts admin-web/src/api/dataFlywheel.test.ts
git commit -m "feat: 增加问题链闭环 API"
```

## Task 4: Daily Review 审核面板接入 chain 闭环按钮

**Files:**
- Modify: `admin-web/src/pages/DataFlywheel/components/IssueChainReviewPanel.tsx`
- Modify: `admin-web/src/pages/DataFlywheel/components/DailyReviewWorkbench.tsx`
- Modify: `admin-web/src/pages/DataFlywheel/index.tsx`
- Modify: `admin-web/src/pages/DataFlywheel/index.test.tsx`
- Test: `admin-web/src/pages/DataFlywheel/index.test.tsx`

- [ ] **Step 1: 写前端失败测试，确认每日质检可生成 chain draft 和 repair pack**

在 `admin-web/src/pages/DataFlywheel/index.test.tsx` 的 mock imports 中加入：

```ts
  createReviewIssueChainCaseDraft,
  createReviewIssueChainRepairPack,
```

在 `vi.mock('../../api/dataFlywheel', () => ({ ... }))` 中加入：

```ts
  createReviewIssueChainCaseDraft: vi.fn(),
  createReviewIssueChainRepairPack: vi.fn(),
```

在 mocked constants 附近加入：

```ts
const mockedCreateChainDraft = vi.mocked(createReviewIssueChainCaseDraft);
const mockedCreateChainRepairPack = vi.mocked(createReviewIssueChainRepairPack);
```

追加测试：

```tsx
  it('每日质检从问题链生成回归草稿和修复包', async () => {
    mockedCreateChainDraft.mockResolvedValueOnce({
      id: 9,
      draft_id: 'draft-chain',
      source_sample_id: 'turn:1:session-a:3',
      target_type: 'evaluation_replay',
      status: 'draft',
      case_json: {
        metadata: {
          chain_id: 'chain:1:session-a:3',
          related_turn_ids: [1, 3, 4],
        },
      },
      created_by: 'admin',
    });
    mockedCreateChainRepairPack.mockResolvedValueOnce({
      id: 11,
      pack_id: 'repair-router-chain',
      fix_target: 'router',
      labels: ['tool_parameter_mismatch'],
      source_sample_ids: ['turn:1:session-a:3'],
      source_label_ids: [],
      status: 'exported',
      export_path: 'data/repair-packs/repair-router-chain',
      manifest: { source_chain_ids: ['chain:1:session-a:3'] },
      cases: [],
    });

    render(<DataFlywheel />);

    expect(await screen.findByRole('tab', { name: /每日质检/ })).toHaveAttribute('aria-selected', 'true');
    await screen.findByText('chain:1:session-a:3');

    await userEvent.click(screen.getByRole('button', { name: /生成回归/ }));
    expect(mockedCreateChainDraft).toHaveBeenCalledWith('chain:1:session-a:3', 'evaluation_replay');
    expect(await screen.findByText(/draft-chain/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /导出修复包/ }));
    expect(mockedCreateChainRepairPack).toHaveBeenCalledWith('chain:1:session-a:3');
    expect(await screen.findByText(/repair-router-chain/)).toBeInTheDocument();
  });
```

如果 fixture 中 `reviewChainDetail.chain.status` 不是 `accepted` 或缺 expected behavior，先在该测试内复制 fixture：

```ts
mockedReviewChain.mockResolvedValueOnce({
  ...reviewChainDetail,
  chain: {
    ...reviewChainDetail.chain,
    status: 'accepted',
    human_review: {
      ...reviewChainDetail.chain.human_review,
      expected_behavior: '应保留所有待结算工人。',
      root_cause: '批量作用域丢失',
      quality_labels: ['tool_parameter_mismatch', 'needs_regression'],
    },
  },
});
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd admin-web && pnpm test src/pages/DataFlywheel/index.test.tsx -t "每日质检从问题链生成回归草稿和修复包"
```

Expected: FAIL，按钮或 API 方法未接入。

- [ ] **Step 3: 给 IssueChainReviewPanel 增加 props**

在 `IssueChainReviewPanelProps` 中加入：

```ts
  acting?: boolean;
  onCreateRegressionDraft?: () => Promise<void>;
  onCreateRepairPack?: () => Promise<void>;
```

组件参数加入：

```ts
  acting = false,
  onCreateRegressionDraft,
  onCreateRepairPack,
```

添加阻断函数：

```ts
function closureBlockedReason(detail: ReviewIssueChainDetail): string | null {
  if (detail.chain.status === 'needs_evidence') return '缺少证据';
  if (detail.chain.status !== 'accepted') return '需要先采纳问题链';
  if (!detail.chain.human_review.expected_behavior) return '缺少 expected behavior';
  return null;
}
```

- [ ] **Step 4: 渲染闭环按钮**

在 `闭环出口` section 中替换原文本区为：

```tsx
          <section style={sectionStyle}>
            <Typography.Text strong style={{ color: palette.text }}>闭环出口</Typography.Text>
            <Space direction="vertical" size={8} style={{ width: '100%', marginTop: 8 }}>
              {closureBlockedReason(detail) && (
                <Typography.Text style={{ color: palette.textMuted }}>
                  阻断原因：{closureBlockedReason(detail)}
                </Typography.Text>
              )}
              <Button
                block
                disabled={Boolean(closureBlockedReason(detail)) || !onCreateRegressionDraft}
                loading={acting}
                onClick={onCreateRegressionDraft}
              >
                生成回归
              </Button>
              <Button
                block
                disabled={Boolean(closureBlockedReason(detail)) || !onCreateRepairPack}
                loading={acting}
                onClick={onCreateRepairPack}
              >
                导出修复包
              </Button>
            </Space>
          </section>
```

- [ ] **Step 5: DailyReviewWorkbench 调用 API 并把结果抛给父组件**

在 `DailyReviewWorkbench.tsx` imports 中加入：

```ts
  createReviewIssueChainCaseDraft,
  createReviewIssueChainRepairPack,
  type CaseDraft,
  type DataFlywheelRepairPack,
```

扩展 props：

```ts
interface DailyReviewWorkbenchProps {
  onCaseDraftCreated?: (draft: CaseDraft) => void;
  onRepairPackCreated?: (pack: DataFlywheelRepairPack) => void;
}
```

把函数签名改为：

```ts
export default function DailyReviewWorkbench({
  onCaseDraftCreated,
  onRepairPackCreated,
}: DailyReviewWorkbenchProps) {
```

新增状态：

```ts
  const [actingClosure, setActingClosure] = useState(false);
```

新增 handler：

```ts
  const handleCreateRegressionDraft = async () => {
    if (!selectedChainId) return;
    setActingClosure(true);
    try {
      const draft = await createReviewIssueChainCaseDraft(selectedChainId, 'evaluation_replay');
      message.success('已生成问题链回归草稿');
      onCaseDraftCreated?.(draft);
    } catch {
      message.error('生成问题链回归草稿失败');
    } finally {
      setActingClosure(false);
    }
  };

  const handleCreateRepairPack = async () => {
    if (!selectedChainId) return;
    setActingClosure(true);
    try {
      const pack = await createReviewIssueChainRepairPack(selectedChainId);
      message.success('已导出问题链修复包');
      onRepairPackCreated?.(pack);
    } catch {
      message.error('导出问题链修复包失败');
    } finally {
      setActingClosure(false);
    }
  };
```

把 `IssueChainReviewPanel` 调用改为：

```tsx
        <IssueChainReviewPanel
          detail={detail}
          contextTurnIds={contextTurnIds}
          resultTurnIds={resultTurnIds}
          saving={saving}
          acting={actingClosure}
          onSave={handleSave}
          onCreateRegressionDraft={handleCreateRegressionDraft}
          onCreateRepairPack={handleCreateRepairPack}
        />
```

- [ ] **Step 6: DataFlywheel 父组件接收预览**

在 `admin-web/src/pages/DataFlywheel/index.tsx` 的 Daily Review tab 改为：

```tsx
children: (
  <DailyReviewWorkbench
    onCaseDraftCreated={(nextDraft) => {
      setDraft(nextDraft);
      setDraftOpen(true);
    }}
    onRepairPackCreated={(nextPack) => {
      setRepairPack(nextPack);
      setRepairPackOpen(true);
    }}
  />
),
```

- [ ] **Step 7: 运行每日质检前端测试**

Run:

```bash
cd admin-web && pnpm test src/pages/DataFlywheel/index.test.tsx -t "每日质检从问题链生成回归草稿和修复包"
```

Expected: PASS。

- [ ] **Step 8: 运行 DataFlywheel 前端相关测试**

Run:

```bash
cd admin-web && pnpm test src/api/dataFlywheel.test.ts src/pages/DataFlywheel/index.test.tsx src/pages/DataFlywheel/layout.test.tsx
```

Expected: PASS。

- [ ] **Step 9: 提交**

```bash
git add admin-web/src/api/dataFlywheel.ts \
  admin-web/src/api/dataFlywheel.test.ts \
  admin-web/src/pages/DataFlywheel/components/IssueChainReviewPanel.tsx \
  admin-web/src/pages/DataFlywheel/components/DailyReviewWorkbench.tsx \
  admin-web/src/pages/DataFlywheel/index.tsx \
  admin-web/src/pages/DataFlywheel/index.test.tsx
git commit -m "feat: 接入问题链闭环出口"
```

## Task 5: 高级搜索边界收口

**Files:**
- Modify: `admin-web/src/pages/DataFlywheel/index.tsx`
- Modify: `admin-web/src/pages/DataFlywheel/index.test.tsx`
- Test: `admin-web/src/pages/DataFlywheel/index.test.tsx`

- [ ] **Step 1: 写失败测试，确认高级搜索没有正式标注和资产按钮**

在 `admin-web/src/pages/DataFlywheel/index.test.tsx` 追加：

```tsx
  it('高级搜索只保留查证入口，不暴露最终标注和正式资产按钮', async () => {
    render(<DataFlywheel />);

    fireEvent.click(screen.getByRole('tab', { name: /高级搜索/ }));
    expect(await screen.findByText(/样本队列/)).toBeInTheDocument();

    await userEvent.click(await screen.findByTestId(`sample-row-${sample.sample_id}`));

    expect(screen.queryByRole('button', { name: /保存标注/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /标记 bad case/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /生成 regression case/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /生成修复包/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /复制 debug JSON/ })).toBeInTheDocument();
  });
```

如果按钮文案不同，以 `AnnotationPanel` 当前实际按钮文本为准，但断言目标保持：高级搜索中不出现保存最终标注、bad case、regression、repair pack。

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd admin-web && pnpm test src/pages/DataFlywheel/index.test.tsx -t "高级搜索只保留查证入口"
```

Expected: FAIL，因为当前高级搜索仍渲染 `AnnotationPanel` 的保存/导出按钮。

- [ ] **Step 3: 给 AnnotationPanel 增加只读模式**

在 `admin-web/src/pages/DataFlywheel/components/AnnotationPanel.tsx` 的 props 中加入：

```ts
  mode?: 'review' | 'evidence';
```

默认值：

```ts
  mode = 'review',
```

在渲染保存、删除、resolve、AI 采纳、标记 bad case、生成 regression、生成 repair pack 的按钮外层加：

```tsx
{mode === 'review' && (
  // existing review-only controls
)}
```

保留复制 debug JSON、导出 JSONL / Evidence Pack、trace 证据查看按钮。

- [ ] **Step 4: 高级搜索详情传 evidence 模式**

在 `admin-web/src/pages/DataFlywheel/index.tsx` 构造 `detailContent` 时，把 `AnnotationPanel` 调用加入：

```tsx
mode={activeTab === 'advanced-search' ? 'evidence' : 'review'}
```

如果 `AnnotationPanel` 在每日质检已不再使用，仍保留该 prop 以兼容旧 view。

- [ ] **Step 5: 批量导出修复包按钮仅在 repair-packs 或已确认问题归档中展示**

在 `filterBar` 中把批量导出按钮包裹为：

```tsx
{activeTab !== 'advanced-search' && (
  <Button
    aria-label="批量导出修复包"
    icon={<CloudDownloadOutlined />}
    loading={acting}
    disabled={selectedRepairSampleIds.length === 0}
    onClick={handleCreateBatchRepairPack}
  >
    {selectedRepairSampleIds.length > 0
      ? `批量导出修复包 ${selectedRepairSampleIds.length}`
      : '批量导出修复包'}
  </Button>
)}
```

如果产品仍需要批量兼容导出，把按钮移到 `repair-packs` tab，并改文案为“兼容导出 sample 修复包”。

- [ ] **Step 6: 运行高级搜索边界测试**

Run:

```bash
cd admin-web && pnpm test src/pages/DataFlywheel/index.test.tsx -t "高级搜索只保留查证入口"
```

Expected: PASS。

- [ ] **Step 7: 运行 DataFlywheel 前端全量测试**

Run:

```bash
cd admin-web && pnpm test src/pages/DataFlywheel/index.test.tsx src/pages/DataFlywheel/layout.test.tsx
```

Expected: PASS。需要同步更新旧测试名“高级搜索中保留旧样本检索入口”，让它只断言检索和证据查看，不再断言保存/导出按钮。

- [ ] **Step 8: 提交**

```bash
git add admin-web/src/pages/DataFlywheel/index.tsx \
  admin-web/src/pages/DataFlywheel/index.test.tsx \
  admin-web/src/pages/DataFlywheel/components/AnnotationPanel.tsx
git commit -m "fix: 收口高级搜索审核边界"
```

## Task 6: Sample 级兼容路径标识

**Files:**
- Modify: `backend/app/modules/data_flywheel/service.py`
- Modify: `backend/app/modules/data_flywheel/repair_pack_repository.py`
- Modify: `backend/tests/api/test_admin_data_flywheel.py`
- Modify: `backend/tests/api/test_admin_data_flywheel_repair_packs.py`
- Test: `backend/tests/api/test_admin_data_flywheel.py`
- Test: `backend/tests/api/test_admin_data_flywheel_repair_packs.py`

- [ ] **Step 1: 写 sample case draft compatibility 测试**

在 `backend/tests/api/test_admin_data_flywheel.py` 中找到 sample case draft 测试附近，追加：

```python
def test_sample_case_draft_marks_compatibility_debug_path(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/case-draft",
            json={"target_type": "evaluation_replay"},
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["case_json"]["metadata"]["source"] == "data_flywheel"
    assert data["case_json"]["metadata"]["asset_path"] == "compatibility_debug"
    assert data["case_json"]["metadata"]["formal_review_required"] is True
```

- [ ] **Step 2: 写 sample repair pack compatibility 测试**

在 `backend/tests/api/test_admin_data_flywheel_repair_packs.py` 追加：

```python
def test_sample_repair_pack_marks_compatibility_debug_path(
    db_session, tmp_path, monkeypatch
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)

    import app.api.admin_data_flywheel_repair_packs as repair_api

    monkeypatch.setattr(repair_api, "REPAIR_PACK_BASE_DIR", tmp_path / "repair-packs")

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            "/admin/data-flywheel/repair-packs",
            json={"sample_ids": [sample_id], "limit": 1},
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["manifest"]["asset_path"] == "compatibility_debug"
    assert data["manifest"]["formal_review_required"] is True
```

如果该测试文件中 seed helper 名称不是 `_seed_turn` / `_sample_id`，复用文件已有 helper 名称，不新建重复 seed。

- [ ] **Step 3: 运行兼容路径测试确认失败**

Run:

```bash
cd backend && pytest \
  tests/api/test_admin_data_flywheel.py::test_sample_case_draft_marks_compatibility_debug_path \
  tests/api/test_admin_data_flywheel_repair_packs.py::test_sample_repair_pack_marks_compatibility_debug_path -q
```

Expected: FAIL，metadata/manifest 缺少 compatibility 字段。

- [ ] **Step 4: sample case draft 加 metadata**

在 `backend/app/modules/data_flywheel/service.py` 的 `build_case_draft()` 中，`case_json = build_case_json(...)` 后加入：

```python
    case_json.setdefault("metadata", {})
    case_json["metadata"]["asset_path"] = "compatibility_debug"
    case_json["metadata"]["formal_review_required"] = True
```

- [ ] **Step 5: sample repair pack manifest 加 metadata**

在 `backend/app/modules/data_flywheel/repair_pack_repository.py` 的 `create_repair_pack()` 中，`manifest = payload["manifest"]` 后加入：

```python
    manifest["asset_path"] = "compatibility_debug"
    manifest["formal_review_required"] = True
```

在 `rebuild_repair_pack_files()` 中生成 manifest 后也加入同样两行，避免重建丢失标识。

- [ ] **Step 6: 运行兼容路径测试**

Run:

```bash
cd backend && pytest \
  tests/api/test_admin_data_flywheel.py::test_sample_case_draft_marks_compatibility_debug_path \
  tests/api/test_admin_data_flywheel_repair_packs.py::test_sample_repair_pack_marks_compatibility_debug_path -q
```

Expected: PASS。

- [ ] **Step 7: 运行 repair pack 和 data flywheel API 测试**

Run:

```bash
cd backend && pytest tests/api/test_admin_data_flywheel.py tests/api/test_admin_data_flywheel_repair_packs.py -q
```

Expected: PASS。

- [ ] **Step 8: 提交**

```bash
git add backend/app/modules/data_flywheel/service.py \
  backend/app/modules/data_flywheel/repair_pack_repository.py \
  backend/tests/api/test_admin_data_flywheel.py \
  backend/tests/api/test_admin_data_flywheel_repair_packs.py
git commit -m "fix: 标记 sample 级飞轮资产为兼容路径"
```

## Task 7: 文档和最终验证

**Files:**
- Modify: `docs/farm-manager-design-spec/01_正式设计/06_数据飞轮与评测.md`
- Test: backend DataFlywheel pytest
- Test: admin-web Vitest
- Test: OpenSpec strict validation

- [ ] **Step 1: 更新设计文档当前状态**

在 `docs/farm-manager-design-spec/01_正式设计/06_数据飞轮与评测.md` 的 `## 14. 当前状态` 中，确保以下条目存在或被更新：

```markdown
- ✅ DataFlywheel 页面边界收口：每日质检是最终人工审核入口，高级搜索只用于查证、抽检和候选链补充
- ✅ 固定标签体系补齐 `tool_parameter_mismatch`
- ✅ ReviewIssueChain → regression draft / repair pack 为正式闭环出口
- ⚠️ sample 级 regression draft / repair pack 仅保留为兼容调试路径，不作为正式标注闭环
- 🚧 Dataset 版本管理（待落地）
- 🚧 Simulation 失败 → DataFlywheel 回流（待打通）
```

- [ ] **Step 2: 运行后端 DataFlywheel 相关测试**

Run:

```bash
cd backend && pytest \
  tests/api/test_admin_data_flywheel.py \
  tests/api/test_admin_data_flywheel_repair_packs.py \
  tests/api/test_admin_data_flywheel_review_issue_chain_closure.py \
  tests/services/test_data_flywheel_issue_detector.py \
  tests/services/test_data_flywheel_repair_pack_repository.py \
  tests/services/test_data_flywheel_repair_pack_service.py -q
```

Expected: PASS。

- [ ] **Step 3: 运行前端 DataFlywheel 相关测试**

Run:

```bash
cd admin-web && pnpm test \
  src/api/dataFlywheel.test.ts \
  src/pages/DataFlywheel/index.test.tsx \
  src/pages/DataFlywheel/layout.test.tsx \
  src/pages/DataFlywheel/components/RepairPackListPanel.test.tsx
```

Expected: PASS。

- [ ] **Step 4: 运行 lint/格式检查**

Run:

```bash
cd backend && ruff check . && ruff format --check .
cd admin-web && pnpm lint
```

Expected: PASS。若项目当前存在无关 lint 失败，记录失败文件，不在本 change 中修复无关代码。

- [ ] **Step 5: 运行 OpenSpec 校验**

Run:

```bash
openspec validate align-dataflywheel-issue-chain-closure --type change --strict
```

Expected:

```text
Change 'align-dataflywheel-issue-chain-closure' is valid
```

- [ ] **Step 6: 运行复杂度预算检查**

Run:

```bash
bash scripts/check-complexity-budget.sh
```

Expected: PASS。

- [ ] **Step 7: 手工验收批量作用域错配链路**

在 admin-web 打开 DataFlywheel，使用一个包含“所有员工工资结了 / 只结算单个工人”的 session，验收：

```text
每日质检 -> 选择风险 session -> trigger/context/result 高亮
-> final_labels 选择 tool_parameter_mismatch + needs_regression
-> 填写 root cause 和 expected behavior
-> 保存 accepted
-> 生成回归
-> 导出修复包
```

Expected:

```text
回归草稿 metadata 包含 chain_id、context_turn_ids、result_turn_ids、expected_behavior
修复包 manifest 包含 source_chain_ids、root_cause、expected_behavior
高级搜索中不能直接保存 final label，也不能直接导出正式 repair pack
```

- [ ] **Step 8: 最终提交**

```bash
git add docs/farm-manager-design-spec/01_正式设计/06_数据飞轮与评测.md
git commit -m "docs: 更新数据飞轮收口状态"
```

## 自检

**Spec coverage:**

- `dataflywheel-issue-chain-closure`：
  - 每日质检最终审核入口：Task 4、Task 5。
  - 高级搜索只查证：Task 5。
  - 固定标签集合：Task 1。
  - 证据状态完整展示：Task 2。
  - 问题链闭环出口：Task 3、Task 4。
- `failure-repair-pack-export`：
  - 正式修复包从 accepted ReviewIssueChain 导出：Task 4。
  - sample 级导出标记兼容调试：Task 6。
- `agent-evaluation-foundation`：
  - chain-derived regression draft：Task 3、Task 4。
  - 高级搜索不能直接创建正式回归资产：Task 5。

**Placeholder scan:**

- 本计划不包含 `TBD`、`TODO`、`implement later`。
- 每个代码改动步骤都给出目标文件、具体代码片段或明确替换内容。

**Type consistency:**

- 前端新增 API 使用 `createReviewIssueChainCaseDraft(chainId, targetType)` 和 `createReviewIssueChainRepairPack(chainId)`。
- 后端标签名统一为 `tool_parameter_mismatch`。
- Repair pack chain 字段统一为 `chain_id`、`trigger_turn_id`、`context_turn_ids`、`result_turn_ids`。
