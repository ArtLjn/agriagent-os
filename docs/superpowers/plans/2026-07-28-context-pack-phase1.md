# Context Pack Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize running summary by aligning its prompt contract with overwrite semantics and adding a `summarized_until_message_id` cursor in `conversations.meta_json`.

**Architecture:** Keep the change narrow inside MemoryService. `conversationMessages` remains the complete message source; `conversations.summary` remains the only persisted session summary; `conversations.meta_json.context_cursor` records the summary boundary so future compaction only sees new messages.

**Tech Stack:** FastAPI backend, SQLAlchemy ORM, pytest, existing conversation repository abstraction.

---

## Scope

This plan implements only Phase 1 and Phase 2 from `docs/specs/2026-07-28-agent-context-pack-design.md`.

Included:

- Change `backend/app/memory/prompts/summary.md` so the LLM returns a full replacement summary.
- Add helpers in `backend/app/memory/service.py` for reading and writing `meta_json.context_cursor`.
- Change `maybe_summarize()` to load messages after `summarized_until_message_id`.
- Update and add tests in `backend/tests/memory/test_maybe_summarize.py`.

Excluded:

- New `ContextPackService`.
- Advisor history migration.
- Closing duplicate `ConversationSelector` / `short_term_recent` injection.
- Admin-web context observability.

## Files

- Modify: `backend/app/memory/prompts/summary.md`
- Modify: `backend/app/memory/service.py`
- Modify: `backend/tests/memory/test_maybe_summarize.py`

## Task 1: Summary Prompt Contract

**Files:**
- Modify: `backend/app/memory/prompts/summary.md`
- Modify: `backend/tests/memory/test_maybe_summarize.py`

- [ ] **Step 1: Write failing test for full replacement summary prompt**

Add a test that renders the summary prompt and asserts it tells the model to output a complete replacement summary, not an append-only paragraph.

```python
def test_render_summary_prompt_要求输出完整新版摘要():
    from app.memory.summarizer import render_summary_prompt

    prompt = render_summary_prompt(
        current_summary="旧摘要：西棚预算 250 元。",
        recent_messages=[
            ConversationMessage(role="user", content="不对，预算是 200 元。")
        ],
        persona=None,
    )

    assert "生成一份完整新版会话摘要" in prompt
    assert "不要只输出追加段落" in prompt
    assert "以新增消息中的最后一次更正为准" in prompt
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd backend
pytest tests/memory/test_maybe_summarize.py::test_render_summary_prompt_要求输出完整新版摘要 -v
```

Expected: FAIL because the current prompt still says “只输出要追加的新摘要段落”.

- [ ] **Step 3: Update prompt text**

Replace the first sentence and output format rules in `backend/app/memory/prompts/summary.md` with:

```markdown
你是会话 running summary 生成器。请基于现有摘要和新增消息，生成一份完整新版会话摘要，用于直接替换当前摘要。
```

The output rules must include:

```markdown
- 输出完整新版摘要，不要只输出追加段落。
- 允许基于新增消息修正当前摘要中的过时或错误信息。
- 用户明确更正时，以新增消息中的最后一次更正为准。
- 若新增消息没有长期价值且当前摘要已有可用内容，可以原样输出当前摘要。
- 若当前摘要为空且新增消息没有长期价值，输出“无新增摘要”。
```

- [ ] **Step 4: Run test and verify it passes**

Run:

```bash
cd backend
pytest tests/memory/test_maybe_summarize.py::test_render_summary_prompt_要求输出完整新版摘要 -v
```

Expected: PASS.

## Task 2: Compaction Cursor Helpers

**Files:**
- Modify: `backend/app/memory/service.py`
- Modify: `backend/tests/memory/test_maybe_summarize.py`

- [ ] **Step 1: Write failing test for cursor write on successful summary**

Extend `test_maybe_summarize_正常生成后写入数据库并同步短时缓存` or add a new test:

```python
@pytest.mark.asyncio
async def test_maybe_summarize_成功后写入摘要边界(db_session, monkeypatch):
    from app.memory import service as service_module

    conversation = _新建会话(db_session, summary="旧摘要")
    _补充消息(db_session, conversation, 12)
    _配置摘要(monkeypatch, service_module)
    monkeypatch.setattr(service_module, "get_llm", lambda role: object())
    monkeypatch.setattr(
        service_module,
        "generate_summary",
        AsyncMock(return_value="【当前目标】\n- 用户关注西棚黄瓜预算 200 元。"),
    )

    service = InMemoryMemoryService()
    await service.maybe_summarize(db_session, conversation.id, 1, "summary-session", [])

    db_session.refresh(conversation)
    cursor = conversation.meta_json["context_cursor"]
    last_message = (
        db_session.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.id.desc())
        .first()
    )
    assert cursor["summary_version"] == 1
    assert cursor["summarized_until_message_id"] == last_message.id
    assert cursor["summary_hash"].startswith("sha256:")
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd backend
pytest tests/memory/test_maybe_summarize.py::test_maybe_summarize_成功后写入摘要边界 -v
```

Expected: FAIL because `context_cursor` is not written.

- [ ] **Step 3: Implement cursor helpers**

Add helpers in `backend/app/memory/service.py`:

```python
import hashlib
```

```python
CONTEXT_CURSOR_KEY = "context_cursor"
```

```python
def _summary_hash(summary: str) -> str:
    return "sha256:" + hashlib.sha256(summary.encode("utf-8")).hexdigest()
```

```python
def _conversation_meta(conversation: Conversation) -> dict[str, Any]:
    return dict(conversation.meta_json or {})
```

```python
def _summary_cursor(conversation: Conversation) -> dict[str, Any]:
    meta = _conversation_meta(conversation)
    cursor = meta.get(CONTEXT_CURSOR_KEY)
    return dict(cursor) if isinstance(cursor, dict) else {}
```

```python
def _cursor_message_id(conversation: Conversation) -> int | None:
    value = _summary_cursor(conversation).get("summarized_until_message_id")
    return int(value) if value is not None else None
```

```python
def _build_next_cursor(
    *,
    previous_cursor: dict[str, Any],
    latest_message: Any | None,
    summary: str,
) -> dict[str, Any]:
    previous_version = int(previous_cursor.get("summary_version") or 0)
    return {
        "summary_version": previous_version + 1,
        "summarized_until_message_id": getattr(latest_message, "id", None),
        "summarized_until_created_at": _iso_datetime(
            getattr(latest_message, "created_at", None)
        ),
        "summary_hash": _summary_hash(summary),
        "updated_at": datetime.now(UTC).isoformat(),
    }
```

```python
def _iso_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_aware_utc(value).isoformat()
    return str(value)
```

- [ ] **Step 4: Write cursor in summary update**

Change `_update_summary_if_version_matches()` to accept `cursor` and update `meta_json.context_cursor` in the same optimistic update:

```python
def _update_summary_if_version_matches(
    *,
    db,
    conversation_id: int,
    previous_updated_at: datetime | None,
    summary: str,
    cursor: dict[str, Any],
) -> bool:
```

Fetch current conversation metadata before executing the update:

```python
conversation = db.get(Conversation, conversation_id)
if conversation is None:
    return False
meta = _conversation_meta(conversation)
meta[CONTEXT_CURSOR_KEY] = cursor
```

Then include `meta_json=meta` in `stmt.values(...)`.

- [ ] **Step 5: Run test and verify it passes**

Run:

```bash
cd backend
pytest tests/memory/test_maybe_summarize.py::test_maybe_summarize_成功后写入摘要边界 -v
```

Expected: PASS.

## Task 3: Incremental Summary Input

**Files:**
- Modify: `backend/app/memory/service.py`
- Modify: `backend/tests/memory/test_maybe_summarize.py`

- [ ] **Step 1: Write failing test for loading only messages after cursor**

Add:

```python
@pytest.mark.asyncio
async def test_maybe_summarize_只总结摘要边界后的新增消息(db_session, monkeypatch):
    from app.memory import service as service_module

    conversation = _新建会话(
        db_session,
        summary="【当前目标】\n- 用户关注西棚黄瓜预算。",
    )
    _补充消息(db_session, conversation, 12)
    boundary = (
        db_session.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.id.asc())
        .all()[7]
    )
    conversation.meta_json = {
        "context_cursor": {
            "summary_version": 1,
            "summarized_until_message_id": boundary.id,
            "summary_hash": "sha256:old",
        }
    }
    db_session.commit()
    _配置摘要(monkeypatch, service_module, threshold=4, debounce=30)
    monkeypatch.setattr(service_module, "get_llm", lambda role: object())
    generate_summary = AsyncMock(return_value="【最近话题】\n- 用户继续补充黄瓜预算。")
    monkeypatch.setattr(service_module, "generate_summary", generate_summary)

    service = InMemoryMemoryService()
    await service.maybe_summarize(db_session, conversation.id, 1, "summary-session", [])

    summarized_messages = generate_summary.await_args.kwargs["old_messages"]
    assert [message.id for message in summarized_messages] == [
        message.id
        for message in db_session.query(ConversationMessage)
        .filter(
            ConversationMessage.conversation_id == conversation.id,
            ConversationMessage.id > boundary.id,
        )
        .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        .all()
    ]
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd backend
pytest tests/memory/test_maybe_summarize.py::test_maybe_summarize_只总结摘要边界后的新增消息 -v
```

Expected: FAIL because all session messages are passed.

- [ ] **Step 3: Load summary messages after cursor**

Change `_load_summary_messages()` signature:

```python
async def _load_summary_messages(
    *,
    db,
    farm_id: int,
    session_id: str,
    after_message_id: int | None,
    fallback_messages: list[Any] | None,
) -> list[Any]:
```

Load `list_by_session()` as today, then filter in memory:

```python
stored_messages = await resolve_maybe_awaitable(...)
if stored_messages and after_message_id is not None:
    stored_messages = [
        message
        for message in stored_messages
        if getattr(message, "id", None) is not None
        and int(getattr(message, "id")) > after_message_id
    ]
return stored_messages or list(fallback_messages or [])
```

Rationale: repository already abstracts MySQL/Mongo; filtering here avoids changing repository contracts in Phase 1.

- [ ] **Step 4: Use cursor in maybe_summarize**

Inside `maybe_summarize()` after loading `conversation`:

```python
summary_cursor = _summary_cursor(conversation)
after_message_id = _cursor_message_id(conversation)
```

Pass `after_message_id` to `_load_summary_messages()`.

Build next cursor before `_update_summary_if_version_matches()`:

```python
next_cursor = _build_next_cursor(
    previous_cursor=summary_cursor,
    latest_message=summary_messages[-1] if summary_messages else None,
    summary=summary,
)
```

Pass `cursor=next_cursor`.

- [ ] **Step 5: Run incremental test**

Run:

```bash
cd backend
pytest tests/memory/test_maybe_summarize.py::test_maybe_summarize_只总结摘要边界后的新增消息 -v
```

Expected: PASS.

## Task 4: Regression and Guardrails

**Files:**
- Modify: `backend/tests/memory/test_maybe_summarize.py`
- Modify: `backend/app/memory/service.py`

- [ ] **Step 1: Update existing success test expectations**

In `test_maybe_summarize_正常生成后写入数据库并同步短时缓存`, change generated summary to a complete structured summary:

```python
generate_summary = AsyncMock(
    return_value="【当前目标】\n- 用户关注西棚黄瓜预算 200 元。"
)
```

Keep assertions that `conversation.summary` equals the generated full summary.

- [ ] **Step 2: Ensure conflict tests keep cursor unchanged**

In optimistic lock conflict tests, assert `conversation.meta_json` does not receive a new `context_cursor` from the stale writer.

- [ ] **Step 3: Run full memory summary tests**

Run:

```bash
cd backend
pytest tests/memory/test_maybe_summarize.py -v
```

Expected: PASS.

- [ ] **Step 4: Run formatting and complexity checks for touched backend files**

Run:

```bash
cd backend
ruff check app/memory/service.py tests/memory/test_maybe_summarize.py
```

Expected: PASS.

Run:

```bash
bash scripts/check-complexity-budget.sh
```

Expected: PASS.

## Review Notes

- This plan intentionally uses `conversations.meta_json.context_cursor` instead of a new table to avoid migration conflicts during parallel sessions.
- This plan does not touch `backend/app/application/advice/advisor.py`, `backend/app/agent/runtime/loop.py`, or admin-web files, because the current main workspace has unrelated dirty changes in those areas.
- If another session modifies `backend/app/memory/service.py` before merge, rebase and resolve by preserving the cursor helper semantics and the existing optimistic update guard.
