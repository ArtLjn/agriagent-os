# admin-web Playground 体验优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提升 admin-web Trace Monitor 和 Chat Playground 的调试体验：Skill 输出格式化展示、一键复制耗时分析、Playground 用户身份模拟。

**Architecture:** 纯前端增强为主，后端仅增加可选 `simulate_user_id` 参数支持 Playground 用户模拟。Skill 格式化采用「提取+折叠」组件化方案，耗时分析基于已加载 timeline 数据前端实时计算。

**Tech Stack:** React 18 + TypeScript + Ant Design, FastAPI + SQLAlchemy

---

## 文件结构

### 新增文件

| 文件 | 职责 |
|------|------|
| `admin-web/src/components/SkillOutputFormatter/index.tsx` | Skill 输出 JSON 的结构化渲染：提取 reply_preview 高亮展示，其余字段折叠 |

### 修改文件

| 文件 | 职责 |
|------|------|
| `backend/app/schemas/agent.py` | `ChatRequest` 增加 `simulate_user_id` 可选字段 |
| `backend/app/api/agent.py` | `agent_chat_stream` 支持 `simulate_user_id` 参数，管理员可模拟其他用户 |
| `admin-web/src/api/admin.ts` | 增加 `listUsers` 接口定义和类型 |
| `admin-web/src/pages/TraceMonitor/index.tsx` | 集成 SkillOutputFormatter + 复制耗时按钮 |
| `admin-web/src/pages/Playground/index.tsx` | 集成 SkillOutputFormatter + 用户选择器 |

---

## Task 1: 后端 — ChatRequest 增加 simulate_user_id 字段

**Files:**
- Modify: `backend/app/schemas/agent.py:8-14`

- [ ] **Step 1: 修改 ChatRequest schema**

```python
class ChatRequest(BaseModel):
    """Agent 对话请求。"""

    cycle_id: int | None = None
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(None, max_length=64)
    simulate_user_id: str | None = Field(None, description="管理员模拟用户ID")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/agent.py
git commit -m "feat(schema): ChatRequest 增加 simulate_user_id 字段"
```

---

## Task 2: 后端 — agent_chat_stream 支持用户模拟

**Files:**
- Modify: `backend/app/api/agent.py:99-127`

**设计**: 当 `chat_request.simulate_user_id` 存在时，检查当前用户是否为管理员，然后查询目标用户及其农场，替换为模拟身份。

- [ ] **Step 1: 修改 agent_chat_stream 参数和逻辑**

将第 99-127 行的函数签名和逻辑替换为：

```python
@router.post("/chat/stream")
@limiter.limit("10/minute")
async def agent_chat_stream(
    request: Request,
    response: Response,
    chat_request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """流式与农事顾问 Agent 对话（SSE）。支持管理员模拟其他用户身份。"""
    # 确定实际用户和农场
    user = current_user
    if chat_request.simulate_user_id:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限才能模拟用户")
        simulated = db.query(User).filter(User.id == chat_request.simulate_user_id).first()
        if not simulated:
            raise HTTPException(status_code=404, detail="模拟用户不存在")
        user = simulated

    farm = db.query(Farm).filter(Farm.user_id == user.id).first()
    if farm is None:
        raise HTTPException(status_code=404, detail="未找到关联农场")

    rid = _new_request_id()
    logger.info(
        "[%s] POST /agent/chat/stream | message=%s simulate_user=%s",
        rid, chat_request.message[:80], chat_request.simulate_user_id
    )

    async def event_generator():
        full_reply = ""
        start = time.perf_counter()
        try:
            async for chunk in stream_chat_with_agent(
                chat_request.message,
                farm_id=farm.id,
                cycle_id=chat_request.cycle_id,
                db=db,
                session_id=chat_request.session_id,
                user_id=user.id,
                request_id=rid,
            ):
                full_reply += chunk
                data = json.dumps({"content": chunk}, ensure_ascii=False)
                yield f"data: {data}\n\n"

            # flush trace 队列确保 skill_call 记录已落盘
            from app.infra.trace_collector import get_trace_dao
            dao = get_trace_dao()
            if dao and dao.queue_size > 0:
                await dao.flush_now()

            # 查询本次对话调用的 skill 列表
            skills = (
                db.query(TraceRecord.node_name)
                .filter(TraceRecord.request_id == rid)
                .filter(TraceRecord.node_type == "skill_call")
                .distinct()
                .all()
            )
            skill_names = [s[0] for s in skills if s[0]]

            # 保存 AI 回复到 conversation_messages + AgentRecord
            conversation = None
            if chat_request.session_id:
                conversation = (
                    db.query(Conversation)
                    .filter(Conversation.session_id == chat_request.session_id)
                    .first()
                )
                if conversation:
                    meta = json.dumps({"skills": skill_names}, ensure_ascii=False) if skill_names else None
                    save_message(db, conversation.id, "assistant", full_reply, meta=meta)

            record = AgentRecord(
                cycle_id=chat_request.cycle_id,
                record_type="chat",
                content=full_reply,
                farm_id=farm.id,
                user_id=user.id,
                conversation_id=conversation.id if conversation else None,
            )
            db.add(record)
            db.commit()

            if skill_names:
                yield f"data: {json.dumps({'skills': skill_names}, ensure_ascii=False)}\n\n"

            pending = get_pending(farm.id)
            if pending:
                pa_event = json.dumps({'pending_action': {'action_id': pending.action_id, 'skill_name': pending.skill_name, 'params': pending.params}}, ensure_ascii=False)
                logger.info("[%s] 发送 pending_action SSE 事件 | skill=%s", rid, pending.skill_name)
                yield f"data: {pa_event}\n\n"

            logger.info(
                "[%s] /chat/stream 完成 | 耗时 %.2fs | reply %d 字符 | skills=%s",
                rid,
                time.perf_counter() - start,
                len(full_reply),
                skill_names,
            )
        except LlmNotConfiguredError as exc:
            logger.error("[%s] /chat/stream 失败: %s", rid, exc)
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

注意：移除了函数签名中的 `farm: Farm = Depends(get_current_farm)` 注入，改为函数内部手动查询，以支持模拟用户时的农场切换。

- [ ] **Step 2: 移除未使用的 Farm import（如果 IDE 提示）**

检查第 20 行的 `from app.models.farm import Farm` 是否仍需要——仍然需要，因为函数内手动查询 farm 时用到。

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/agent.py
git commit -m "feat(api): agent_chat_stream 支持管理员模拟用户身份"
```

---

## Task 3: 前端 API 层 — 增加 listUsers 接口

**Files:**
- Modify: `admin-web/src/api/admin.ts`

- [ ] **Step 1: 在 admin.ts 末尾（deleteTracesBefore 之后）添加用户相关类型和函数**

在 `admin.ts` 第 93 行之后插入：

```typescript
// ─── Users API ───────────────────────────────────────────────────────────────

export interface AdminUserListItem {
  id: string;
  phone: string;
  nickname: string | null;
  avatar_url: string | null;
  role: string;
  status: string;
  created_at: string;
  farm_name: string | null;
}

export interface AdminUserListResponse {
  items: AdminUserListItem[];
  total: number;
}

export async function listUsers(params?: { page?: number; size?: number; status?: string }): Promise<AdminUserListResponse> {
  const res = await apiClient.get<AdminUserListResponse>('/admin/users', { params });
  return res.data;
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/api/admin.ts
git commit -m "feat(api): admin-web 增加 listUsers 接口"
```

---

## Task 4: 创建 SkillOutputFormatter 组件

**Files:**
- Create: `admin-web/src/components/SkillOutputFormatter/index.tsx`

- [ ] **Step 1: 创建组件文件**

```tsx
import { Button, Space, message } from 'antd';
import { CopyOutlined } from '@ant/icons';

const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const BORDER = '#30363d';
const BG = '#161b22';

interface SkillOutputFormatterProps {
  outputData: string | null;
}

interface ParsedSkillOutput {
  reply_preview?: string;
  status?: string;
  [key: string]: unknown;
}

export default function SkillOutputFormatter({ outputData }: SkillOutputFormatterProps) {
  if (!outputData) return null;

  let parsed: ParsedSkillOutput | null = null;
  try {
    parsed = JSON.parse(outputData) as ParsedSkillOutput;
  } catch {
    // 解析失败，回退到原始展示
  }

  // 解析失败或不含 reply_preview —— 回退到原始 JSON
  if (!parsed || typeof parsed !== 'object' || !parsed.reply_preview) {
    return (
      <pre style={{
        backgroundColor: BG,
        padding: 12,
        borderRadius: 6,
        border: `1px solid ${BORDER}`,
        fontSize: 12,
        margin: 0,
        maxHeight: 300,
        overflow: 'auto',
        whiteSpace: 'pre-wrap',
        color: TEXT,
      }}>
        {outputData}
      </pre>
    );
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(parsed!.reply_preview || '');
      message.success('已复制到剪贴板');
    } catch {
      message.error('复制失败');
    }
  };

  // 分离 reply_preview 和其余字段
  const { reply_preview, ...restFields } = parsed;
  const hasRest = Object.keys(restFields).length > 0;

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {/* reply_preview 高亮展示 */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ color: TEXT_DIM, fontSize: 12 }}>执行结果</span>
          <Button
            size="small"
            icon={<CopyOutlined />}
            onClick={handleCopy}
            style={{ background: BG, borderColor: BORDER, color: TEXT_DIM }}
          >
            复制结果
          </Button>
        </div>
        <div style={{
          backgroundColor: '#1a2332',
          padding: 12,
          borderRadius: 6,
          border: `1px solid ${BORDER}`,
          color: TEXT,
          fontSize: 13,
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
        }}>
          {reply_preview}
        </div>
      </div>

      {/* 其余字段折叠 */}
      {hasRest && (
        <details style={{ cursor: 'pointer' }}>
          <summary style={{ color: TEXT_DIM, fontSize: 12, userSelect: 'none' }}>
            查看完整输出 ({Object.keys(restFields).length} 个字段)
          </summary>
          <pre style={{
            backgroundColor: BG,
            padding: 12,
            borderRadius: 6,
            border: `1px solid ${BORDER}`,
            fontSize: 12,
            margin: '8px 0 0 0',
            maxHeight: 300,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
            color: TEXT,
          }}>
            {JSON.stringify(restFields, null, 2)}
          </pre>
        </details>
      )}
    </Space>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/components/SkillOutputFormatter/index.tsx
git commit -m "feat(ui): 创建 SkillOutputFormatter 组件"
```

---

## Task 5: TraceMonitor — 集成 SkillOutputFormatter

**Files:**
- Modify: `admin-web/src/pages/TraceMonitor/index.tsx`

- [ ] **Step 1: 导入 SkillOutputFormatter**

在第 26 行 `import { getNodeLabel } from '../../constants/trace';` 之后添加：

```typescript
import SkillOutputFormatter from '../../components/SkillOutputFormatter';
```

- [ ] **Step 2: 替换 output_data 展示区域**

找到第 464-481 行（output_data 展示块），替换为：

```tsx
{nodeDetail.output_data && (
  <div>
    <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>输出数据</div>
    {nodeDetail.node_type === 'skill_call' ? (
      <SkillOutputFormatter outputData={nodeDetail.output_data} />
    ) : (
      <pre style={{
        backgroundColor: '#161b22',
        padding: 12,
        borderRadius: 6,
        border: '1px solid #30363d',
        fontSize: 12,
        margin: 0,
        maxHeight: 300,
        overflow: 'auto',
        whiteSpace: 'pre-wrap',
      }}>
        {formatJson(nodeDetail.output_data)}
      </pre>
    )}
  </div>
)}
```

- [ ] **Step 3: Commit**

```bash
git add admin-web/src/pages/TraceMonitor/index.tsx
git commit -m "feat(trace): TraceMonitor Skill 输出使用格式化组件"
```

---

## Task 6: Playground — 集成 SkillOutputFormatter

**Files:**
- Modify: `admin-web/src/pages/Playground/index.tsx`

- [ ] **Step 1: 导入 SkillOutputFormatter**

在第 10 行 `import { getNodeLabel } from '../../constants/trace';` 之后添加：

```typescript
import SkillOutputFormatter from '../../components/SkillOutputFormatter';
```

- [ ] **Step 2: 替换 output_data 展示区域**

找到 Playground 中 Drawer 的 output_data 展示块（约第 596-607 行），替换为与 TraceMonitor 相同的逻辑：

```tsx
{nodeDetail.output_data && (
  <div>
    <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>输出数据</div>
    {nodeDetail.node_type === 'skill_call' ? (
      <SkillOutputFormatter outputData={nodeDetail.output_data} />
    ) : (
      <pre style={{
        backgroundColor: '#161b22',
        padding: 12,
        borderRadius: 6,
        border: '1px solid #30363d',
        fontSize: 12,
        margin: 0,
        maxHeight: 300,
        overflow: 'auto',
        whiteSpace: 'pre-wrap',
      }}>
        {formatJson(nodeDetail.output_data)}
      </pre>
    )}
  </div>
)}
```

- [ ] **Step 3: Commit**

```bash
git add admin-web/src/pages/Playground/index.tsx
git commit -m "feat(playground): Playground Skill 输出使用格式化组件"
```

---

## Task 7: TraceMonitor — 添加复制耗时按钮

**Files:**
- Modify: `admin-web/src/pages/TraceMonitor/index.tsx`

- [ ] **Step 1: 导入 CopyOutlined 图标**

在第 14 行，将导入语句从：
```typescript
import { SearchOutlined, ClearOutlined } from '@ant-design/icons';
```
改为：
```typescript
import { SearchOutlined, ClearOutlined, CopyOutlined } from '@ant-design/icons';
```

- [ ] **Step 2: 添加耗时计算和复制函数**

在 `formatJson` 函数（第 160-167 行）之后添加：

```typescript
function computeTimingReport(timeline: TraceTimeline): string {
  const typeStats = new Map<string, { duration: number; count: number }>();
  let totalDuration = 0;

  for (const round of timeline.rounds) {
    for (const node of round.nodes) {
      if (node.duration_ms && node.duration_ms > 0) {
        const existing = typeStats.get(node.node_type) || { duration: 0, count: 0 };
        existing.duration += node.duration_ms;
        existing.count += 1;
        typeStats.set(node.node_type, existing);
        totalDuration += node.duration_ms;
      }
    }
  }

  const NODE_TYPE_LABELS: Record<string, string> = {
    routing: '路由决策',
    prompt_render: 'Prompt 渲染',
    llm_call: 'LLM 调用',
    skill_call: 'Skill 执行',
    error: '错误',
  };

  let md = '### Trace 耗时分析\n\n';
  md += '| 节点类型 | 累计耗时(ms) | 占比 | 节点数 |\n';
  md += '|----------|-------------|------|--------|\n';

  for (const [type, stats] of typeStats) {
    const label = NODE_TYPE_LABELS[type] || type;
    const pct = totalDuration > 0 ? ((stats.duration / totalDuration) * 100).toFixed(1) : '0.0';
    md += `| ${label} | ${stats.duration} | ${pct}% | ${stats.count} |\n`;
  }

  md += `| **总计** | **${totalDuration}** | **100%** | **${Array.from(typeStats.values()).reduce((s, v) => s + v.count, 0)}** |\n`;

  return md;
}

async function copyTimingReport(timeline: TraceTimeline) {
  try {
    const report = computeTimingReport(timeline);
    await navigator.clipboard.writeText(report);
    message.success('耗时分析已复制到剪贴板');
  } catch {
    message.error('复制失败');
  }
}
```

- [ ] **Step 3: 在列表头部添加复制耗时按钮**

找到第 295-300 行（trace 头部信息行，包含展开/收起按钮），在展开状态下添加复制耗时按钮。

具体修改：在第 287-300 行（日期和展开/收起区域）之前，插入复制耗时按钮。

找到这段代码（约第 269-301 行）：
```tsx
<span style={{ marginLeft: 'auto', color: TEXT_DIM, fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
  <span>{new Date(item.created_at).toLocaleString('zh-CN')}</span>
  <span style={{ color: ACCENT }}>
    {expandedCards.has(item.request_id) ? '收起 ▲' : '展开 ▼'}
  </span>
</span>
```

将其替换为：
```tsx
<span style={{ marginLeft: 'auto', color: TEXT_DIM, fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
  {expandedCards.has(item.request_id) && item.timeline && (
    <Button
      size="small"
      icon={<CopyOutlined />}
      onClick={(e) => { e.stopPropagation(); copyTimingReport(item.timeline!); }}
      style={{ background: 'transparent', borderColor: BORDER, color: TEXT_DIM, fontSize: 12 }}
    >
      复制耗时
    </Button>
  )}
  <span>{new Date(item.created_at).toLocaleString('zh-CN')}</span>
  <span style={{ color: ACCENT }}>
    {expandedCards.has(item.request_id) ? '收起 ▲' : '展开 ▼'}
  </span>
</span>
```

- [ ] **Step 4: Commit**

```bash
git add admin-web/src/pages/TraceMonitor/index.tsx
git commit -m "feat(trace): Trace 列表增加复制耗时分析按钮"
```

---

## Task 8: Playground — 添加用户选择器

**Files:**
- Modify: `admin-web/src/pages/Playground/index.tsx`

- [ ] **Step 1: 导入 listUsers 和 Select 组件**

在第 2 行，将 Ant Design 导入从：
```typescript
import { Input, Button, Space, Collapse, Typography, Drawer, Tag, Tooltip, message } from 'antd';
```
改为：
```typescript
import { Input, Button, Space, Collapse, Typography, Drawer, Tag, Tooltip, message, Select } from 'antd';
```

在第 6 行，添加 `listUsers` 导入：
```typescript
import { listTraces, getTimeline, type TraceTimeline, type TraceNodeDetail, listUsers, type AdminUserListItem } from '../../api/admin';
```

- [ ] **Step 2: 在 Playground state 中添加用户相关状态**

在第 158 行 `const [conversations, setConversations] = useState<ConversationItem[]>([]);` 之后添加：

```typescript
const [users, setUsers] = useState<AdminUserListItem[]>([]);
const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
```

- [ ] **Step 3: 添加加载用户列表逻辑**

在 `loadConversations` 函数（第 163-169 行）之后添加：

```typescript
const loadUsers = useCallback(async () => {
  try {
    const res = await listUsers({ size: 100 });
    setUsers(res.items);
  } catch {
    // 静默失败
  }
}, []);
```

在现有的 `useEffect`（第 172-174 行）中同步加载用户：

将：
```typescript
useEffect(() => {
  loadConversations();
}, [loadConversations]);
```

改为：
```typescript
useEffect(() => {
  loadConversations();
  loadUsers();
}, [loadConversations, loadUsers]);
```

- [ ] **Step 4: 修改 streamPlaygroundChat 支持 simulateUserId**

将 `streamPlaygroundChat` 函数（第 89-125 行）从：
```typescript
async function* streamPlaygroundChat(message: string, sessionId: string): AsyncGenerator<StreamChunk> {
```

改为：
```typescript
async function* streamPlaygroundChat(message: string, sessionId: string, simulateUserId?: string | null): AsyncGenerator<StreamChunk> {
```

将 body 从：
```typescript
body: JSON.stringify({ message, session_id: sessionId }),
```
改为：
```typescript
body: JSON.stringify({ message, session_id: sessionId, simulate_user_id: simulateUserId }),
```

- [ ] **Step 5: 修改 handleSend 传递 selectedUserId**

找到 `handleSend` 中调用 `streamPlaygroundChat` 的地方（约第 245 行），从：
```typescript
for await (const chunk of streamPlaygroundChat(userMsg, sessionId)) {
```
改为：
```typescript
for await (const chunk of streamPlaygroundChat(userMsg, sessionId, selectedUserId)) {
```

- [ ] **Step 6: 在配置栏添加用户选择下拉框**

找到配置栏区域（约第 423-440 行），将：
```tsx
{/* 配置栏 */}
<div style={{
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  background: CARD, border: `1px solid ${BORDER}`, borderRadius: 8,
  padding: '12px 16px', marginBottom: 16,
}}>
  <div style={{ color: TEXT_DIM, fontSize: 13 }}>
    Session ID: <span style={{ color: TEXT, fontFamily: 'monospace' }}>{sessionId}</span>
  </div>
  <Button
    size="small"
    icon={<DeleteOutlined />}
    onClick={handleClear}
    style={{ background: CARD, borderColor: BORDER, color: TEXT_DIM }}
  >
    清空对话
  </Button>
</div>
```

改为：
```tsx
{/* 配置栏 */}
<div style={{
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  background: CARD, border: `1px solid ${BORDER}`, borderRadius: 8,
  padding: '12px 16px', marginBottom: 16,
}}>
  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
    <div style={{ color: TEXT_DIM, fontSize: 13 }}>
      Session ID: <span style={{ color: TEXT, fontFamily: 'monospace' }}>{sessionId}</span>
    </div>
    <Select
      placeholder="选择用户"
      value={selectedUserId}
      onChange={(value) => {
        setSelectedUserId(value);
        setMessages([]);
        setTimeline(null);
      }}
      style={{ width: 180 }}
      dropdownStyle={{ background: CARD }}
      options={[
        { value: null, label: '匿名用户' },
        ...users.map((u) => ({
          value: u.id,
          label: u.nickname || u.phone,
        })),
      ]}
    />
  </div>
  <Button
    size="small"
    icon={<DeleteOutlined />}
    onClick={handleClear}
    style={{ background: CARD, borderColor: BORDER, color: TEXT_DIM }}
  >
    清空对话
  </Button>
</div>
```

- [ ] **Step 7: Commit**

```bash
git add admin-web/src/pages/Playground/index.tsx
git commit -m "feat(playground): Playground 增加用户选择器支持模拟用户身份"
```

---

## Task 9: 验证与测试

- [ ] **Step 1: 后端类型检查**

```bash
cd backend && poetry run python -m py_compile app/schemas/agent.py app/api/agent.py
```

- [ ] **Step 2: 前端类型检查**

```bash
cd admin-web && npx tsc --noEmit
```

- [ ] **Step 3: 启动后端并测试 API**

```bash
cd backend && poetry run uvicorn app.main:app --reload
```

在另一个终端测试：
```bash
curl -X POST http://localhost:8000/api/agent/chat/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"message":"你好","simulate_user_id":"<target_user_id>"}'
```

- [ ] **Step 4: 启动前端并手动验证三个功能**

```bash
cd admin-web && pnpm dev
```

验证清单：
1. Trace Monitor → 展开 trace → 点击 skill_call 节点 → 确认 reply_preview 高亮展示 + 折叠区域 + 复制按钮
2. Trace Monitor → 展开 trace → 确认「复制耗时」按钮出现 → 点击后粘贴到编辑器确认 Markdown 表格格式正确
3. Playground → 确认用户下拉框加载 → 选择不同用户发送消息 → 确认回复基于选中用户的农场上下文

- [ ] **Step 5: 最终 Commit（如有修复）**

```bash
git add -A
git commit -m "fix: 验证修复"
```

---

## Self-Review Checklist

### 1. Spec 覆盖

| Spec 需求 | 对应 Task |
|-----------|----------|
| Skill 输出结构化渲染 | Task 4 + Task 5 + Task 6 |
| 格式化失败回退 | Task 4 (try/catch + 原始 JSON) |
| 一键复制格式化内容 | Task 4 (复制按钮) |
| Trace 列表显示分类耗时 | Task 7 (按钮可见性) |
| 一键复制耗时分析 | Task 7 (computeTimingReport + copy) |
| 耗时按钮状态管理 | Task 7 (条件渲染: expanded && timeline) |
| Playground 用户选择器 | Task 8 (Select + loadUsers) |
| 匿名模式兼容 | Task 8 (value: null 选项 + 不传 simulate_user_id) |
| 用户上下文生效 | Task 2 (后端模拟用户) + Task 8 (传递 simulate_user_id) |

✅ 全覆盖，无遗漏。

### 2. Placeholder 扫描

- [x] 无 "TBD", "TODO", "implement later"
- [x] 无 "Add appropriate error handling" 类模糊描述
- [x] 无 "Similar to Task N" 类引用
- [x] 每个代码步骤包含完整代码

### 3. 类型一致性

- [x] `simulate_user_id` 在 schema (str | None)、API 参数、前端请求体中类型一致
- [x] `AdminUserListItem` 类型在前端 API 层和组件中一致
- [x] `StreamChunk` 类型未变更，与现有代码兼容
