import apiClient from './client';
import { authStore } from '../stores/authStore';

// ── SSE 事件类型 ──
export interface SseEvent {
  type: string;
  data: Record<string, unknown>;
}

// ── 对话相关类型 ──
export interface ConversationItem {
  conversation_id: string;
  last_message: string;
  last_role: string;
  last_at: string;
  message_count: number;
}

export interface ConversationMessage {
  role: string;
  content: string;
  created_at?: string;
}

// ── Pending Action / Plan（保留给 Playground 组件用）──
export interface PendingActionContext {
  original_input: string;
  extracted_params: Record<string, unknown>;
  notes: string[];
}

export interface PendingAction {
  action_id: string;
  skill_name: string;
  params: Record<string, unknown>;
  context?: PendingActionContext | null;
  /** 原始 SSE approval_required 事件的完整 data，用于 UI 展示风险等级/计划等 */
  raw?: Record<string, unknown> | null;
}

export interface PendingPlan {
  plan_id?: string;
  status?: string;
  steps?: unknown[];
  goal?: string;
  step_count?: number;
}

/** 单步 plan（plan_created 事件） */
export interface PlanStep {
  skill?: string;
  description?: string;
  [key: string]: unknown;
}

/** observation 事件：工具调用结果 */
export interface Observation {
  tool_name: string;
  result?: unknown;
  error?: string | null;
}

/** operation_committed 事件：HITL 确认后业务写入结果 */
export interface OperationCommitted {
  result?: unknown;
  [key: string]: unknown;
}

/** approval_result 事件：HITL 决策结果 */
export interface ApprovalResult {
  decision: 'approved' | 'rejected';
  reason?: string;
  [key: string]: unknown;
}

/** done 事件：整轮结束 */
export interface DoneEvent {
  status: 'completed' | 'failed' | string;
  [key: string]: unknown;
}

// ── Stream Chunk（Playground 消费）──
// 对齐 v2/agent/static/index.html 的 appendEvent 覆盖的事件类型。
export type StreamChunk =
  | { type: 'content'; data: string }
  | { type: 'final_content'; data: string }
  | { type: 'final_answer_start'; data: null }
  | { type: 'skills'; data: string[] }
  | { type: 'thought'; data: string }
  | { type: 'plan'; data: { steps: string[] } }
  | { type: 'plan_created'; data: { goal: string; step_count: number; steps: PlanStep[] } }
  | { type: 'plan_step_done'; data: { step_index: number; skill: string; status: string } }
  | { type: 'action'; data: { tool_name: string; arguments: Record<string, unknown>; rationale?: string } }
  | { type: 'observation'; data: Observation }
  | { type: 'pending_action'; data: PendingAction }
  | { type: 'pending_plan'; data: PendingPlan }
  | { type: 'approval_result'; data: ApprovalResult }
  | { type: 'operation_committed'; data: OperationCommitted }
  | { type: 'context_usage'; data: { percent: number; level: string; used: number; total: number; step?: number } }
  | { type: 'context_compressing'; data: { trigger: string; before_percent: number } }
  | { type: 'context_compressed'; data: { after_percent: number; summary_preview?: string } }
  | { type: 'doom_loop_warning'; data: { message: string } }
  | { type: 'verification_warning'; data: { issues: string[] } }
  | { type: 'write_committed_reply_failed'; data: { code: string; message: string } }
  | { type: 'retrying'; data: { code: string; attempt: number; delay_ms: number } }
  | { type: 'meta'; data: { turn_id: string; conversation_id: string; request_id?: string } }
  | { type: 'done'; data: DoneEvent }
  | { type: 'error'; data: { code: string; message: string } };

// ── SSE 解析器：标准 event:/data: 格式 ──
export async function* parseSseStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<SseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // SSE 事件以 \n\n 分隔
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() ?? '';
    for (const block of blocks) {
      const lines = block.split('\n');
      let eventType = 'message';
      let dataStr = '';
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          dataStr += line.slice(6);
        }
      }
      if (!dataStr) continue;
      try {
        const data = JSON.parse(dataStr);
        yield { type: eventType, data };
      } catch {
        // 非 JSON data，跳过
      }
    }
  }
}

// ── 将 SSE 事件映射为 StreamChunk ──
// 参考 v2/agent/static/index.html 的 appendEvent 实现，覆盖所有事件类型，
// 让 Playground 能像 index.html 一样实时展示 thought/plan/action/observation 等。
export function mapSseToChunk(event: SseEvent): StreamChunk | null {
  const { type, data } = event;
  switch (type) {
    case 'meta':
      return {
        type: 'meta',
        data: {
          turn_id: String(data.turn_id ?? ''),
          conversation_id: String(data.conversation_id ?? ''),
          request_id: data.request_id ? String(data.request_id) : undefined,
        },
      };
    case 'final_answer_start':
      return { type: 'final_answer_start', data: null };
    case 'final_answer_delta':
      return { type: 'content', data: String(data.delta ?? '') };
    case 'assistant_delta':
      return { type: 'content', data: String(data.delta ?? '') };
    case 'final_answer':
      return { type: 'final_content', data: String(data.text ?? '') };
    case 'thought':
      return { type: 'thought', data: String(data.content ?? '') };
    case 'plan':
      return {
        type: 'plan',
        data: { steps: Array.isArray(data.steps) ? data.steps.map((s) => String(s)) : [] },
      };
    case 'plan_created': {
      const steps = Array.isArray(data.steps) ? data.steps : [];
      return {
        type: 'plan_created',
        data: {
          goal: String(data.goal ?? ''),
          step_count: Number(data.step_count ?? steps.length),
          steps: steps as PlanStep[],
        },
      };
    }
    case 'plan_step_done':
      return {
        type: 'plan_step_done',
        data: {
          step_index: Number(data.step_index ?? 0),
          skill: String(data.skill ?? ''),
          status: String(data.status ?? 'done'),
        },
      };
    case 'action':
      return {
        type: 'action',
        data: {
          tool_name: String(data.tool_name ?? ''),
          arguments: (data.arguments as Record<string, unknown>) ?? {},
          rationale: typeof data.rationale === 'string' ? data.rationale : undefined,
        },
      };
    case 'observation':
      return {
        type: 'observation',
        data: {
          tool_name: String(data.tool_name ?? ''),
          result: data.result,
          error: typeof data.error === 'string' ? data.error : null,
        },
      };
    case 'approval_required':
      return {
        type: 'pending_action',
        data: {
          action_id: String(data.turn_id ?? ''),
          skill_name: String(data.tool_name ?? ''),
          params: (data.arguments as Record<string, unknown>) ?? {},
          context: null,
          raw: data,
        },
      };
    case 'approval_result':
      return {
        type: 'approval_result',
        data: {
          decision: data.decision === 'approved' ? 'approved' : 'rejected',
          reason: typeof data.reason === 'string' ? data.reason : undefined,
          ...data as Record<string, unknown>,
        },
      };
    case 'operation_committed':
      return {
        type: 'operation_committed',
        data: { result: data.result, ...data as Record<string, unknown> },
      };
    case 'context_usage':
      return {
        type: 'context_usage',
        data: {
          percent: Number(data.percent ?? 0),
          level: String(data.level ?? 'green'),
          used: Number(data.used ?? 0),
          total: Number(data.total ?? 0),
          step: typeof data.step === 'number' ? data.step : undefined,
        },
      };
    case 'context_compressing':
      return {
        type: 'context_compressing',
        data: {
          trigger: String(data.trigger ?? ''),
          before_percent: Number(data.before_percent ?? 0),
        },
      };
    case 'context_compressed':
      return {
        type: 'context_compressed',
        data: {
          after_percent: Number(data.after_percent ?? 0),
          summary_preview: typeof data.summary_preview === 'string' ? data.summary_preview : undefined,
        },
      };
    case 'doom_loop_warning':
      return {
        type: 'doom_loop_warning',
        data: { message: String(data.message ?? '') },
      };
    case 'verification_warning':
      return {
        type: 'verification_warning',
        data: { issues: Array.isArray(data.issues) ? data.issues.map((i) => String(i)) : [] },
      };
    case 'write_committed_reply_failed':
      return {
        type: 'write_committed_reply_failed',
        data: {
          code: String(data.code ?? 'error'),
          message: String(data.message ?? ''),
        },
      };
    case 'retrying':
      return {
        type: 'retrying',
        data: {
          code: String(data.code ?? 'retrying'),
          attempt: Number(data.attempt ?? 0),
          delay_ms: Number(data.delay_ms ?? 0),
        },
      };
    case 'done':
      return {
        type: 'done',
        data: { status: String(data.status ?? 'completed'), ...data as Record<string, unknown> },
      };
    case 'error':
      return {
        type: 'error',
        data: {
          code: String(data.code ?? 'error'),
          message: String(data.message ?? '未知错误'),
        },
      };
    default:
      return null;
  }
}

// ── 聊天（SSE 流式）──
// userToken 可选：传入则用 dev-user token 覆盖 Authorization 头（用于 admin 模拟用户）
export async function* streamChat(
  message: string,
  conversationId?: string,
  userToken?: string | null,
): AsyncGenerator<StreamChunk> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = userToken || authStore.getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const resp = await fetch('/api/agent/chat', {
    method: 'POST',
    headers,
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (!resp.ok || !resp.body) throw new Error(`stream error: ${resp.status}`);
  for await (const event of parseSseStream(resp.body)) {
    const chunk = mapSseToChunk(event);
    if (chunk) yield chunk;
    // done 事件 yield 后再退出，让前端能感知整轮结束并刷新 trace
    if (event.type === 'done') return;
  }
}

// ── 对话列表 ──
export async function listConversations(limit = 50): Promise<ConversationItem[]> {
  const res = await apiClient.get<{ items: ConversationItem[] }>('/agent/conversations', {
    params: { limit },
  });
  return res.data.items ?? [];
}

// ── 对话消息 ──
export async function getConversationMessages(
  conversationId: string,
): Promise<ConversationMessage[]> {
  const res = await apiClient.get<{ items: ConversationMessage[] }>(
    `/agent/conversations/${encodeURIComponent(conversationId)}`,
    { params: { limit: 100 } },
  );
  return res.data.items ?? [];
}

// ── HITL 审批 ──
export async function approveTurn(
  turnId: string,
  decision: boolean,
  reason = '',
): Promise<void> {
  await apiClient.post('/agent/approve', {
    turn_id: turnId,
    decision,
    reason,
  });
}

// ── 重置对话 ──
export async function resetConversation(conversationId: string): Promise<void> {
  await apiClient.post('/agent/reset', { conversation_id: conversationId });
}

// ── 开发用户列表 ──
export interface DevUser {
  user_id: string;
  nickname: string;
  phone: string;
  role: string;
  farm_id: number;
  token: string;
}

export async function listDevUsers(): Promise<DevUser[]> {
  const res = await apiClient.get<{ users: DevUser[] }>('/agent/dev-users');
  return res.data.users ?? [];
}

/**
 * 兼容 Operations 旧页面的技能列表入口。
 * v2 Agent 当前通过本地 skill loader 组装工具，尚未提供该 REST 端点。
 */
export interface AppSkillItem {
  key: string;
  title: string;
  description: string;
  category: string;
  icon?: string;
  icon_color?: string;
  recommended?: boolean;
  enabled?: boolean;
}

export interface AppSkillListResponse {
  items: AppSkillItem[];
  total: number;
}

export async function listAppSkills(): Promise<AppSkillListResponse> {
  const res = await apiClient.get<AppSkillListResponse>('/agent/skills');
  return res.data;
}

// ── 会话调试导出（v2 后端未提供独立端点，调用会 404，前端走 fallback 构建）──
export interface SessionDebugExport {
  format: string;
  session_id: string;
  simulate_user_id: string | null;
  copied_at: string;
  messages: unknown[];
  used_skills: string[];
  pending_actions: unknown[];
  trace_request_id: string | null;
  skill_calls: unknown[];
  router_diagnostics: unknown[];
  pending_plans: unknown[];
}

export async function getSessionDebugExport(
  _sessionId: string,
  _simulateUserId?: string | null,
): Promise<SessionDebugExport> {
  void _sessionId;
  void _simulateUserId;
  // v2 后端无此端点，直接抛错让 Playground 走本地 fallback
  throw new Error('session debug export endpoint not available on v2 agent');
}

// ── 兼容旧接口的 stub（后端尚未实现，调用会 404 但不影响编译）──
export interface ChatResponse { reply: string }
export async function chat(message: string): Promise<ChatResponse> {
  const res = await apiClient.post<ChatResponse>('/agent/chat', { message });
  return res.data;
}
