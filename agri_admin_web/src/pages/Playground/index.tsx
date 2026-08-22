import { useState, useRef, useCallback, useEffect } from 'react';
import { Input, Button, Space, Tag, Tooltip, message, Select } from 'antd';
import { SendOutlined, DeleteOutlined, CopyOutlined, PlusOutlined, MenuFoldOutlined, MenuUnfoldOutlined, LoadingOutlined, LinkOutlined, ProfileOutlined } from '@ant-design/icons';
import { listTraces, getTimeline, type TraceTimeline } from '../../api/admin';
import {
  streamChat,
  approveTurn,
  listDevUsers,
  listConversations,
  getConversationMessages,
  type ConversationItem,
  type ConversationMessage,
  type DevUser,
  type PendingAction,
  type PendingPlan,
  type StreamTraceContext,
} from '../../api/agent';
import { MarkdownContent } from '../../components/MarkdownContent';
import { palette } from '../../styles/theme';
import { buildConversationRows } from './conversationRows';
import { buildSessionDebugExport, type DebugExportMessage } from './sessionDebugExport';
import { applyHistoricalPendingResolution, canConfirmAssistantMessage, hasPendingConfirmationControls, type PendingResolution } from './pendingPlanControls';
import {
  buildPlaygroundTraceMetrics,
  extractLatestLlmContextSnapshot,
  hasAutomaticCompression,
} from './traceMetrics';
import { copyAsyncText } from './clipboard';
import { buildTraceMonitorUrl, selectLatestTraceId } from './traceLinks';
import { LlmContextInspector, LlmContextTriggerButton } from './LlmContextInspector';
import { QuickPrompts } from './QuickPrompts';
import { ExecutionTimeline } from './ExecutionTimeline';
import { appendExecutionEvent, executionEventFromChunk, type ExecutionEvent } from './executionEvents';
import { authStore } from '../../stores/authStore';

const CARD = palette.bgElevated;
const BORDER = palette.border;
const TEXT = palette.text;
const TEXT_DIM = palette.textMuted;
const ACCENT = palette.accent;
const USER_BG = palette.accentStrong;
const SIDEBAR_BG = palette.bgElevated;
const SIDEBAR_BORDER = palette.borderSoft;
const ROW_HOVER = 'rgba(139, 148, 158, 0.08)';
const ROW_ACTIVE = 'rgba(88, 166, 255, 0.12)';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  events?: ExecutionEvent[];
  skills?: string[];
  pendingAction?: PendingAction | null;
  pendingPlan?: PendingPlan | null;
  pendingResolution?: PendingResolution | null;
}

interface ChatSessionState {
  messages: Message[];
  loading: boolean;
  traceLoading: boolean;
  trace?: StreamTraceContext | null;
  timeline: TraceTimeline | null;
  llmContextTimeline: TraceTimeline | null;
}

function generateSessionId(): string {
  return `playground-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function createMessage(role: Message['role'], content: string): Message {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    content,
  };
}

function emptySessionState(): ChatSessionState {
  return {
    messages: [],
    loading: false,
    traceLoading: false,
    trace: null,
    timeline: null,
    llmContextTimeline: null,
  };
}

/* ── 执行状态标签 ── */
function ExecutionStatus({ skills, pendingAction, pendingPlan, pendingResolution }: { skills?: string[]; pendingAction?: PendingAction | null; pendingPlan?: boolean; pendingResolution?: PendingResolution | null }) {
  if (pendingResolution) {
    const canceled = pendingResolution === 'canceled';
    return (
      <span style={{
        fontSize: 11, color: canceled ? '#8b949e' : '#52c41a', background: canceled ? 'rgba(139,148,158,0.12)' : 'rgba(82,196,26,0.12)',
        padding: '2px 8px', borderRadius: 4, border: `1px solid ${canceled ? '#8b949e' : '#52c41a'}`,
      }}>
        {canceled ? '🚫 已取消执行' : '✅ 已确认执行'}
      </span>
    );
  }
  if (pendingAction || pendingPlan) {
    return (
      <span style={{
        fontSize: 11, color: '#faad14', background: 'rgba(250,173,20,0.12)',
        padding: '2px 8px', borderRadius: 4, border: '1px solid #faad14',
      }}>
        ⏳ 待确认执行
      </span>
    );
  }
  if (skills && skills.length > 0) {
    return (
      <span style={{
        fontSize: 11, color: '#52c41a', background: 'rgba(82,196,26,0.12)',
        padding: '2px 8px', borderRadius: 4, border: '1px solid #52c41a',
      }} title={skills.join(', ')}>
        ✅ 真实执行了 {skills.length} 个函数
      </span>
    );
  }
  return (
    <span style={{
      fontSize: 11, color: TEXT_DIM, background: 'rgba(139,148,158,0.12)',
      padding: '2px 8px', borderRadius: 4, border: `1px solid ${TEXT_DIM}`,
    }}>
      💬 纯文本生成
    </span>
  );
}

function formatMetricNumber(value: number | null): string {
  if (value === null) return '-';
  return value.toLocaleString('zh-CN');
}

function TraceMetricPill({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <span style={{
      color: TEXT_DIM,
      fontSize: 12,
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
    }}>
      {label}: <span style={{ color: accent ?? TEXT, fontFamily: 'monospace' }}>{value}</span>
    </span>
  );
}

/* ── 聊天气泡组件 ── */
function ChatBubble({
  role, content, events, skills, loading, pendingAction, pendingPlan, pendingResolution, onAction,
}: {
  role: 'user' | 'assistant';
  content: string;
  events?: ExecutionEvent[];
  skills?: string[];
  loading: boolean;
  pendingAction?: PendingAction | null;
  pendingPlan?: PendingPlan | null;
  pendingResolution?: PendingResolution | null;
  onAction?: (action: string) => void;
}) {
  const isUser = role === 'user';
  const hasConfirmationControls = hasPendingConfirmationControls({ role, content, pendingAction, pendingPlan, pendingResolution });
  const canConfirm = canConfirmAssistantMessage({ role, content, pendingAction, pendingPlan, pendingResolution });
  const confirmationDisabled = !canConfirm || !onAction;
  return (
    <div style={{ marginBottom: isUser ? 16 : 28, display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start', minWidth: 0 }}>
      {!isUser && (
        <div style={{
          width: 32, height: 32, borderRadius: 10, background: '#238636',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontSize: 14, fontWeight: 700, marginRight: 10, flexShrink: 0,
        }}>AI</div>
      )}
      <div style={{
        background: isUser ? USER_BG : 'transparent',
        color: TEXT,
        padding: isUser ? '10px 16px' : 0,
        borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
        maxWidth: isUser ? '78%' : 'min(100%, 1240px)',
        width: isUser ? 'auto' : '100%',
        minWidth: 0,
        wordBreak: 'break-word',
      }}>
        {isUser ? content : (
          <>
            <ExecutionTimeline events={events} loading={loading} />
            {content && <MarkdownContent content={content} style={{ color: TEXT, lineHeight: 1.75, fontSize: 15 }} />}
          </>
        )}
        {/* ── 执行状态 + 技能标签 ── */}
        {!isUser && (
          <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <ExecutionStatus
              skills={skills}
              pendingAction={canConfirm ? pendingAction : null}
              pendingPlan={canConfirm && !pendingAction}
              pendingResolution={pendingResolution}
            />
            {skills && skills.length > 0 && skills.map((s) => (
              <span key={s} style={{
                fontSize: 11, color: ACCENT, background: 'rgba(88,166,255,0.12)',
                padding: '2px 8px', borderRadius: 4, border: `1px solid ${ACCENT}`,
              }}>
                ⚡ {s}
              </span>
            ))}
          </div>
        )}
        {!isUser && pendingAction?.context && (
          <div style={{ marginTop: 8, padding: '8px 10px', background: 'rgba(139,148,158,0.08)', borderRadius: 8, fontSize: 13, color: '#8b949e' }}>
            {pendingAction.context.original_input && (
              <div style={{ marginBottom: 4 }}>📝 理解：您说的是「{pendingAction.context.original_input}」</div>
            )}
            {pendingAction.context.notes?.map((note, i) => (
              <div key={i} style={{ marginBottom: i < pendingAction.context!.notes.length - 1 ? 4 : 0 }}>{note}</div>
            ))}
          </div>
        )}
        {!isUser && hasConfirmationControls && (
          <div style={{ display: 'flex', gap: 8, marginTop: 10, justifyContent: 'flex-end' }}>
            <button
              disabled={confirmationDisabled}
              onClick={() => {
                if (!confirmationDisabled) onAction?.('确认');
              }}
              style={{
                background: confirmationDisabled ? '#2d333b' : '#238636',
                color: confirmationDisabled ? '#8b949e' : '#fff',
                border: 'none',
                borderRadius: 6,
                padding: '4px 16px',
                cursor: confirmationDisabled ? 'not-allowed' : 'pointer',
                fontSize: 13,
                opacity: confirmationDisabled ? 0.72 : 1,
              }}
            >
              确认
            </button>
            <button
              disabled={confirmationDisabled}
              onClick={() => {
                if (!confirmationDisabled) onAction?.('取消');
              }}
              style={{
                background: '#30363d',
                color: '#8b949e',
                border: 'none',
                borderRadius: 6,
                padding: '4px 16px',
                cursor: confirmationDisabled ? 'not-allowed' : 'pointer',
                fontSize: 13,
                opacity: confirmationDisabled ? 0.72 : 1,
              }}
            >
              取消
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Trace 查询 ── */
async function fetchSessionTimeline(
  convId: string,
  traceId?: string | null,
): Promise<TraceTimeline | null> {
  try {
    if (traceId) return await getTimeline(traceId, { include_payload: true });
    const listRes = await listTraces({ conversation_id: convId, limit: 1 });
    if (!listRes.items || listRes.items.length === 0) return null;
    const latestTraceId = listRes.items[0].trace_id ?? listRes.items[0].request_id;
    return await getTimeline(latestTraceId, { include_payload: true });
  } catch {
    return null;
  }
}

async function fetchSessionLlmContextTimeline(
  convId: string,
  latestTimeline: TraceTimeline | null,
): Promise<TraceTimeline | null> {
  if (extractLatestLlmContextSnapshot(latestTimeline)) return latestTimeline;
  try {
    const listRes = await listTraces({ conversation_id: convId, limit: 12 });
    for (const item of listRes.items ?? []) {
      if (!item.trace_id) continue;
      const candidate = item.trace_id === latestTimeline?.trace_id
        ? latestTimeline
        : await getTimeline(item.trace_id, { include_payload: true });
      if (extractLatestLlmContextSnapshot(candidate)) return candidate;
    }
  } catch {
    // LLM Context 是调试增强能力，查询失败时保留当前 request timeline。
  }
  return null;
}

export default function Playground() {
  const [sessionId, setSessionId] = useState<string>(generateSessionId);
  const [sessions, setSessions] = useState<Record<string, ChatSessionState>>(() => ({
    [sessionId]: emptySessionState(),
  }));
  const [input, setInput] = useState('');
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [devUsers, setDevUsers] = useState<DevUser[]>([]);
  const [selectedDevUser, setSelectedDevUser] = useState<DevUser | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [llmContextOpen, setLlmContextOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeSession = sessions[sessionId] ?? emptySessionState();
  const messages = activeSession.messages;
  const loading = activeSession.loading;
  const traceLoading = activeSession.traceLoading;
  const timeline = activeSession.timeline;
  const llmContextTimeline = activeSession.llmContextTimeline ?? timeline;
  const traceMetrics = buildPlaygroundTraceMetrics(timeline);
  const llmContextSnapshot = extractLatestLlmContextSnapshot(llmContextTimeline);
  const compressed = hasAutomaticCompression(traceMetrics);
  const conversationRows = buildConversationRows(sessions, conversations);
  const timelineNodeCount = timeline?.rounds.reduce((sum, round) => sum + round.nodes.length, 0) ?? 0;
  const currentRequestId = timeline?.trace_id;
  const llmContextRequestId = llmContextTimeline?.trace_id;
  // dev user token：模拟用户时注入到 streamChat 的 Authorization 头
  const activeUserToken = selectedDevUser?.token ?? null;
  const viewerToken = authStore.getToken();

  const updateSession = useCallback((sid: string, updater: (state: ChatSessionState) => ChatSessionState) => {
    setSessions((prev) => {
      const current = prev[sid] ?? emptySessionState();
      return { ...prev, [sid]: updater(current) };
    });
  }, []);

  const ensureSession = useCallback((sid: string) => {
    setSessions((prev) => (prev[sid] ? prev : { ...prev, [sid]: emptySessionState() }));
  }, []);

  const markPendingResolution = useCallback((
    sid: string,
    messageId: string,
    resolution: PendingResolution | null,
  ) => {
    updateSession(sid, (state) => ({
      ...state,
      messages: state.messages.map((item) => (
        item.id === messageId ? { ...item, pendingResolution: resolution } : item
      )),
    }));
  }, [updateSession]);

  /* ── 加载会话列表 ── */
  const loadConversations = useCallback(async () => {
    try {
      const list = await listConversations(50);
      setConversations(list);
    } catch {
      // 静默失败
    }
  }, []);

  /* ── 加载 dev 用户列表（agri_backend_v2 agent /api/v2/dev-users）── */
  const loadDevUsers = useCallback(async () => {
    try {
      const users = await listDevUsers();
      setDevUsers(users);
      // 默认不选中任何 dev user，使用 admin 自身 token
    } catch {
      // 静默失败
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => {
      loadDevUsers();
      loadConversations();
    });
  }, [loadDevUsers, loadConversations]);

  useEffect(() => {
    setLlmContextOpen(false);
  }, [sessionId]);

  /* ── 切换会话 ── */
  const switchConversation = useCallback(async (sid: string) => {
    setSessionId(sid);
    updateSession(sid, () => ({ ...emptySessionState(), loading: true }));
    try {
      const msgs = await getConversationMessages(sid);
      // agri_backend_v2 agent 只返回 role/content/created_at；skills/pendingAction 仅来自 SSE 流，历史消息无此字段
      const loaded: Message[] = msgs.map((m: ConversationMessage, idx: number) => ({
        id: `history-${idx}-${m.role}`,
        role: m.role as 'user' | 'assistant',
        content: m.content,
      }));
      const resolved = applyHistoricalPendingResolution(loaded);
      updateSession(sid, (state) => ({
        ...state,
        loading: false,
        trace: null,
        messages: resolved,
        timeline: null,
        llmContextTimeline: null,
      }));
    } catch {
      updateSession(sid, (state) => ({ ...state, loading: false }));
      message.error('加载会话失败');
    }
  }, [updateSession]);

  /* ── 新建会话 ── */
  const createNewSession = useCallback(() => {
    const sid = generateSessionId();
    setSessionId(sid);
    ensureSession(sid);
  }, [ensureSession]);

  const buildFallbackSessionDebugJson = useCallback(async (sid: string) => {
    const state = sessions[sid] ?? emptySessionState();
    let sourceMessages: DebugExportMessage[] = state.messages.map((m) => ({
      role: m.role,
      content: m.content,
      skills: m.skills,
      pendingAction: m.pendingAction,
      pendingPlan: m.pendingPlan,
    }));
    try {
      const persistedMessages = await getConversationMessages(sid);
      if (persistedMessages.length > 0) {
        // agri_backend_v2 agent 历史消息只有 role/content，skills/pendingAction 仅存在于当前会话 SSE 流中
        sourceMessages = persistedMessages.map((m) => ({
          role: m.role,
          content: m.content,
        }));
      }
    } catch {
      // 历史消息读取失败时，使用当前本地状态继续导出。
    }
    const timeline = state.timeline ?? await fetchSessionTimeline(sid, state.trace?.trace_id);
    const debugExport = buildSessionDebugExport({
      sessionId: sid,
      simulateUserId: selectedDevUser?.user_id ?? null,
      copiedAt: new Date().toISOString(),
      messages: sourceMessages,
      timeline,
    });
    return JSON.stringify(debugExport, null, 2);
  }, [selectedDevUser, sessions]);

  const copySessionJson = useCallback(async (sid: string) => {
    const ok = await copyAsyncText({
      placeholder: `正在准备调试 JSON...\nconversation_id: ${sid}`,
      loadText: async () => {
        // agri_backend_v2 agent 无独立 debug export 端点，始终走本地 fallback 构建
        return buildFallbackSessionDebugJson(sid);
      },
    });
    if (ok) {
      message.success('已复制调试 JSON 到剪贴板');
    } else {
      message.error('复制失败');
    }
  }, [buildFallbackSessionDebugJson]);

  const copySessionId = useCallback(async (sid: string) => {
    try {
      if (!navigator.clipboard) {
        message.error('剪贴板不可用');
        return false;
      }
      await navigator.clipboard.writeText(sid);
      message.success('已复制 Session ID');
      return true;
    } catch {
      message.error('复制失败');
      return false;
    }
  }, []);

  const openTraceMonitor = useCallback(async (sid: string) => {
    const state = sessions[sid];
    const traceId = state?.timeline?.trace_id ?? state?.trace?.trace_id;
    if (traceId) {
      window.open(buildTraceMonitorUrl({ conversationId: sid, traceId }), '_blank');
      return;
    }
    try {
      const listRes = await listTraces({ conversation_id: sid, limit: 1 });
      const latestTraceId = selectLatestTraceId(listRes.items);
      window.open(buildTraceMonitorUrl({ conversationId: sid, traceId: latestTraceId }), '_blank');
    } catch {
      window.open(buildTraceMonitorUrl({ conversationId: sid }), '_blank');
    }
  }, [sessions]);

  const refreshSessionTimeline = useCallback(async (sid: string, traceId?: string | null) => {
    updateSession(sid, (state) => ({ ...state, traceLoading: true }));
    const latestTimeline = await fetchSessionTimeline(sid, traceId);
    const latestLlmContextTimeline = await fetchSessionLlmContextTimeline(sid, latestTimeline);
    updateSession(sid, (state) => ({
      ...state,
      timeline: latestTimeline,
      llmContextTimeline: latestLlmContextTimeline,
      traceLoading: false,
    }));
    return latestTimeline;
  }, [updateSession]);

  const openLlmContextInspector = useCallback(() => {
    if (selectedDevUser) return;
    setLlmContextOpen(true);
    void refreshSessionTimeline(sessionId);
  }, [refreshSessionTimeline, sessionId, selectedDevUser]);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }, 50);
  }, []);

  const handleClear = useCallback(() => {
    const sid = generateSessionId();
    setSessionId(sid);
    setSessions((prev) => ({ ...prev, [sid]: emptySessionState() }));
  }, []);

  const handleSend = useCallback(async (overrideMsg?: string): Promise<boolean> => {
    const userMsg = overrideMsg ?? input.trim();
    if (!userMsg) return false;
    const targetSessionId = sessionId;
    const targetSession = sessions[targetSessionId] ?? emptySessionState();
    if (targetSession.loading) {
      message.warning('当前会话正在生成中，请先切换到其他会话并行发送');
      return false;
    }
    const userMessage = createMessage('user', userMsg);
    const assistantMessage = createMessage('assistant', '');
    setInput('');
    updateSession(targetSessionId, (state) => ({
      ...state,
      messages: [...state.messages, userMessage, assistantMessage],
      loading: true,
      traceLoading: false,
      trace: null,
      timeline: null,
      llmContextTimeline: null,
    }));
    scrollToBottom();

    try {
      const clientRequestId = `${targetSessionId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      let streamedTrace: StreamTraceContext | null = null;
      for await (const chunk of streamChat(userMsg, targetSessionId, activeUserToken, {
        client_request_id: clientRequestId,
        viewerToken,
        presentationProfile: selectedDevUser ? 'user' : 'admin_debug',
      })) {
        if (chunk.type === 'meta') {
          streamedTrace = chunk.data;
          updateSession(targetSessionId, (state) => ({ ...state, trace: chunk.data }));
        }
        const executionEvent = executionEventFromChunk(chunk);
        if (executionEvent) {
          updateSession(targetSessionId, (state) => ({
            ...state,
            messages: state.messages.map((item) => (
              item.id === assistantMessage.id
                ? { ...item, events: appendExecutionEvent(item.events ?? [], executionEvent) }
                : item
            )),
          }));
        }
        if (chunk.type === 'content') {
          updateSession(targetSessionId, (state) => {
            const next = state.messages.map((item) => (
              item.id === assistantMessage.id
                ? { ...item, content: item.content + chunk.data }
                : item
            ));
            return { ...state, messages: next };
          });
          if (targetSessionId === sessionId) scrollToBottom();
        } else if (chunk.type === 'final_content') {
          updateSession(targetSessionId, (state) => ({
            ...state,
            messages: state.messages.map((item) => (
              item.id === assistantMessage.id ? { ...item, content: chunk.data } : item
            )),
          }));
        } else if (chunk.type === 'skills') {
          updateSession(targetSessionId, (state) => {
            const next = state.messages.map((item) => (
              item.id === assistantMessage.id ? { ...item, skills: chunk.data } : item
            ));
            return { ...state, messages: next };
          });
        } else if (chunk.type === 'pending_action') {
          updateSession(targetSessionId, (state) => {
            const next = state.messages.map((item) => (
              item.id === assistantMessage.id ? { ...item, pendingAction: chunk.data } : item
            ));
            return { ...state, messages: next };
          });
        } else if (chunk.type === 'pending_plan') {
          updateSession(targetSessionId, (state) => {
            const next = state.messages.map((item) => (
              item.id === assistantMessage.id ? { ...item, pendingPlan: chunk.data } : item
            ));
            return { ...state, messages: next };
          });
        }
      }

      if (!selectedDevUser) {
        await refreshSessionTimeline(targetSessionId, streamedTrace?.trace_id);
      }

      await loadConversations();
      return true;
    } catch {
      updateSession(targetSessionId, (state) => {
        const next = state.messages.map((item) => (
          item.id === assistantMessage.id
            ? { ...item, content: '对话失败，请重试' }
            : item
        ));
        return { ...state, messages: next };
      });
      return false;
    } finally {
      updateSession(targetSessionId, (state) => ({
        ...state,
        loading: false,
        traceLoading: false,
      }));
    }
  }, [activeUserToken, input, scrollToBottom, sessionId, sessions, updateSession, loadConversations, refreshSessionTimeline, selectedDevUser, viewerToken]);

  const handlePendingAction = useCallback(async (messageId: string, action: string) => {
    const targetSessionId = sessionId;
    const resolution: PendingResolution = action === '取消' ? 'canceled' : 'confirmed';
    const pendingAction = sessions[targetSessionId]?.messages.find((item) => item.id === messageId)?.pendingAction;
    if (!pendingAction?.action_id) {
      message.error('当前审批上下文已失效，请重新发起请求');
      return;
    }
    markPendingResolution(targetSessionId, messageId, resolution);
    try {
      await approveTurn(pendingAction.action_id, resolution === 'confirmed', resolution === 'confirmed' ? '用户确认' : '用户取消');
    } catch {
      markPendingResolution(targetSessionId, messageId, null);
      message.error('审批提交失败，请重试');
    }
  }, [markPendingResolution, sessionId, sessions]);

  const lastMessage = messages[messages.length - 1];
  const isThinking = loading && Boolean(lastMessage) && lastMessage.content === '' && !lastMessage.events?.length;

  return (
    <div style={{ height: '100%', display: 'flex', background: palette.bg }}>
      {/* ── 会话列表侧边栏 ── */}
      <div
        style={{
          width: sidebarCollapsed ? 56 : 260,
          background: SIDEBAR_BG,
          borderRight: `1px solid ${SIDEBAR_BORDER}`,
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
          transition: 'width 200ms cubic-bezier(0.25, 1, 0.5, 1)',
          overflow: 'hidden',
        }}
      >
        {/* 侧边栏头部 - 与 admin sider 高度对齐 */}
        <div
          style={{
            height: 58,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: sidebarCollapsed ? '0 8px' : '0 12px 0 16px',
            borderBottom: `1px solid ${SIDEBAR_BORDER}`,
            flexShrink: 0,
          }}
        >
          {!sidebarCollapsed && (
            <span style={{ color: TEXT, fontSize: 13, fontWeight: 600, letterSpacing: 0.2 }}>
              会话
              <span style={{ color: TEXT_DIM, fontWeight: 400, marginLeft: 8, fontSize: 12 }}>
                {conversationRows.length}
              </span>
            </span>
          )}
          <Tooltip title={sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'} placement="right">
            <Button
              type="text"
              aria-label={sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'}
              icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              style={{ color: TEXT_DIM, width: 32, height: 32 }}
            />
          </Tooltip>
        </div>

        {/* 会话列表 */}
        <div className="surface-scroll" style={{ flex: 1, overflow: 'auto', padding: sidebarCollapsed ? '8px 6px' : '8px 8px' }}>
          {conversationRows.map((conv) => {
            const conversationId = conv.conversation_id;
            const isActive = conversationId === sessionId;
            const sessionState = sessions[conversationId];
            const isRunning = Boolean(sessionState?.loading);
            return (
              <div
                key={conversationId}
                onClick={() => switchConversation(conversationId)}
                style={{
                  padding: sidebarCollapsed ? '8px 0' : '8px 10px',
                  borderRadius: 8,
                  marginBottom: 2,
                  cursor: 'pointer',
                  background: isActive ? ROW_ACTIVE : 'transparent',
                  borderLeft: isActive ? `3px solid ${ACCENT}` : '3px solid transparent',
                  transition: 'background 120ms ease',
                  display: sidebarCollapsed ? 'flex' : 'block',
                  justifyContent: sidebarCollapsed ? 'center' : undefined,
                  alignItems: sidebarCollapsed ? 'center' : undefined,
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.background = ROW_HOVER;
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.background = 'transparent';
                }}
              >
                {sidebarCollapsed ? (
                  <Tooltip title={conversationId} placement="right">
                    <div style={{
                      width: 28, height: 28, borderRadius: 8,
                      background: isActive ? ACCENT : 'rgba(139,148,158,0.12)',
                      color: isActive ? '#fff' : TEXT_DIM,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 12, fontWeight: 600,
                    }}>
                      {conversationId.slice(-2)}
                    </div>
                  </Tooltip>
                ) : (
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                      {isRunning && <LoadingOutlined style={{ color: ACCENT, fontSize: 11, flexShrink: 0 }} />}
                      <div style={{
                        color: TEXT,
                        fontSize: 12,
                        fontWeight: isActive ? 600 : 500,
                        fontFamily: 'monospace',
                        lineHeight: 1.4,
                        wordBreak: 'break-all',
                        flex: 1,
                        minWidth: 0,
                      }}>
                        {conversationId}
                      </div>
                    </div>
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 4,
                      marginTop: 4,
                    }}>
                      <div style={{ color: TEXT_DIM, fontSize: 11, flexShrink: 0 }}>
                        {new Date(conv.last_at).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </div>
                      <Space size={0} style={{ opacity: isActive ? 1 : 0.6, flexShrink: 0 }}>
                        <Tooltip title="复制 Session ID">
                          <Button
                            type="text"
                            size="small"
                            icon={<CopyOutlined />}
                            onClick={(e) => { e.stopPropagation(); void copySessionId(conversationId); }}
                            style={{ color: isActive ? ACCENT : TEXT_DIM, padding: '0 4px', minWidth: 24, height: 24 }}
                          />
                        </Tooltip>
                        <Tooltip title="跳转链路追踪">
                          <Button
                            type="text"
                            size="small"
                            icon={<LinkOutlined />}
                            onClick={(e) => { e.stopPropagation(); openTraceMonitor(conversationId); }}
                            style={{ color: TEXT_DIM, padding: '0 4px', minWidth: 24, height: 24 }}
                          />
                        </Tooltip>
                        <Tooltip title="复制调试 JSON">
                          <Button
                            type="text"
                            size="small"
                            icon={<ProfileOutlined />}
                            onClick={(e) => { e.stopPropagation(); copySessionJson(conversationId); }}
                            style={{ color: TEXT_DIM, padding: '0 4px', minWidth: 24, height: 24 }}
                          />
                        </Tooltip>
                      </Space>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          {conversationRows.length === 0 && !sidebarCollapsed && (
            <div style={{ textAlign: 'center', color: TEXT_DIM, fontSize: 12, padding: '24px 12px' }}>
              暂无历史会话
            </div>
          )}
        </div>
      </div>

      {/* ── 主聊天区域 ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden', padding: '16px 20px 16px', position: 'relative' }}>
        {/* 子 header - Playground 配置 */}
        <div className="playground-toolbar" style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          gap: 12,
          padding: '8px 16px',
          marginBottom: 16,
          background: CARD,
          border: `1px solid ${BORDER}`,
          borderRadius: 10,
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
            <Select
              placeholder="选择用户"
              value={selectedDevUser?.user_id ?? ''}
              onChange={(value) => {
                const user = devUsers.find((u) => u.user_id === value) ?? null;
                setSelectedDevUser(user);
                setLlmContextOpen(false);
                // 切换用户后开启新会话，避免历史会话身份混淆
                const sid = generateSessionId();
                setSessionId(sid);
                setSessions({ [sid]: emptySessionState() });
                setConversations([]);
                // agri_backend_v2 agent 通过 token 识别用户身份，listConversations 不需要 user_id 参数
                void listConversations(50).then(setConversations).catch(() => {
                  message.error('加载会话列表失败');
                });
              }}
              style={{ width: 220, flexShrink: 0 }}
              styles={{ popup: { root: { background: CARD } } }}
              options={[
                { value: '', label: '默认用户（admin 自身）' },
                ...devUsers.map((u) => ({
                  value: u.user_id,
                  label: `${u.nickname || u.phone} (farm:${u.farm_id}, ${u.role})`,
                })),
              ]}
            />
            <Tag color={selectedDevUser ? 'blue' : 'purple'} style={{ margin: 0, whiteSpace: 'nowrap' }}>
              viewer: admin · acting_as: {selectedDevUser?.user_id ?? 'admin'} · presentation: {selectedDevUser ? 'user' : 'debug'}
            </Tag>
            <span style={{ width: 1, height: 20, background: BORDER, flexShrink: 0 }} />
            <Tooltip title="点击复制 Session ID">
              <span
                onClick={() => void copySessionId(sessionId)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  color: TEXT_DIM,
                  fontSize: 12,
                  fontFamily: 'monospace',
                  maxWidth: 260,
                  padding: '4px 10px',
                  borderRadius: 6,
                  background: 'rgba(139, 148, 158, 0.06)',
                  border: `1px solid ${palette.borderSoft}`,
                  cursor: 'pointer',
                  transition: 'all 150ms ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(139, 148, 158, 0.12)';
                  e.currentTarget.style.color = TEXT;
                  e.currentTarget.style.borderColor = BORDER;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'rgba(139, 148, 158, 0.06)';
                  e.currentTarget.style.color = TEXT_DIM;
                  e.currentTarget.style.borderColor = palette.borderSoft;
                }}
              >
                <span style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: 200,
                }}>
                  {sessionId}
                </span>
                <CopyOutlined style={{ fontSize: 11, flexShrink: 0, opacity: 0.5 }} />
              </span>
            </Tooltip>
          </div>
          <Space size={4} style={{ flexShrink: 0 }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={createNewSession}
              style={{
                borderRadius: 6,
                fontWeight: 500,
                fontSize: 13,
                height: 32,
                paddingInline: 14,
                boxShadow: '0 1px 3px rgba(31, 111, 235, 0.3)',
              }}
            >
              新建会话
            </Button>
            <Button
              type="default"
              icon={<DeleteOutlined />}
              onClick={handleClear}
              className="playground-toolbar__ghost"
              style={{
                color: TEXT_DIM,
                height: 32,
                paddingInline: 12,
                borderRadius: 6,
                fontSize: 13,
                borderColor: 'transparent',
                background: 'transparent',
              }}
            >
              清空
            </Button>
            <span style={{ width: 1, height: 16, background: BORDER, margin: '0 4px', flexShrink: 0 }} />
            <LlmContextTriggerButton
              hasSnapshot={Boolean(llmContextSnapshot)}
              loading={loading || traceLoading}
              onClick={() => {
                if (llmContextOpen) return;
                openLlmContextInspector();
              }}
              disabled={Boolean(selectedDevUser)}
            />
          </Space>
        </div>

        {/* 消息区域 */}
        <div ref={scrollRef} style={{
          flex: 1, minHeight: 0, overflow: 'auto',
          padding: '4px 8px 12px',
          marginBottom: 10,
        }}>
          {messages.length === 0 && (
            <div style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: TEXT_DIM,
              textAlign: 'center',
              padding: '16px 24px',
            }}>
              <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.7 }}>🧪</div>
              <div style={{ fontSize: 18, marginBottom: 6, color: TEXT, fontWeight: 500 }}>Playground — 开发者调试</div>
              <div style={{ fontSize: 13, maxWidth: 420, lineHeight: 1.6 }}>
                点击下方快捷提示词直接发起对话，或在输入框中输入你的问题
              </div>
              <QuickPrompts
                onSelect={(prompt) => { void handleSend(prompt); }}
                disabled={loading}
              />
            </div>
          )}
          {messages.map((m) => (
            <ChatBubble
              key={m.id}
              role={m.role}
              content={m.content}
              events={m.events}
              skills={m.skills}
              loading={loading && m.id === messages[messages.length - 1]?.id}
              pendingAction={m.pendingAction}
              pendingPlan={m.pendingPlan}
              pendingResolution={m.pendingResolution}
              onAction={(action) => { void handlePendingAction(m.id, action); }}
            />
          ))}
          {isThinking && (
            <div style={{ display: 'flex', alignItems: 'center', color: TEXT_DIM, padding: '0 42px' }}>
              <span className="ant-spin-dot" style={{ marginRight: 8 }} />
              AI 正在思考中...
            </div>
          )}
        </div>

        <LlmContextInspector
          snapshot={llmContextSnapshot}
          open={llmContextOpen}
          onOpenChange={(open) => {
            if (open) {
              openLlmContextInspector();
            } else {
              setLlmContextOpen(false);
            }
          }}
          loading={loading || traceLoading}
          hasTimeline={timeline !== null}
          requestId={currentRequestId}
          snapshotRequestId={llmContextRequestId}
          nodeCount={timelineNodeCount}
          onRefresh={() => refreshSessionTimeline(sessionId)}
        />

        {/* 执行摘要 - 紧凑单行 */}
        {(timeline !== null || traceLoading) && (
          <div style={{
            marginBottom: 10,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            padding: '6px 4px',
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
              <span style={{ color: ACCENT, fontSize: 12, fontWeight: 500 }}>执行摘要</span>
              {traceLoading ? (
                <span style={{ color: TEXT_DIM, fontSize: 12 }}>加载中...</span>
              ) : timeline && timeline.rounds ? (
                <>
                  <TraceMetricPill
                    label="节点"
                    value={formatMetricNumber(timeline.rounds.reduce((s, r) => s + r.nodes.length, 0))}
                  />
                  <TraceMetricPill label="轮次" value={formatMetricNumber(timeline.rounds.length)} />
                  <TraceMetricPill
                    label="耗时"
                    value={`${formatMetricNumber(timeline.rounds.reduce((s, r) => s + r.nodes.reduce((ns, n) => ns + (n.duration_ms || 0), 0), 0))}ms`}
                  />
                  <TraceMetricPill
                    label="上下文"
                    value={`${formatMetricNumber(traceMetrics.contextTokens)} / ${formatMetricNumber(traceMetrics.contextBudget)}`}
                  />
                  <TraceMetricPill
                    label="最终 Prompt"
                    value={`${formatMetricNumber(traceMetrics.promptTokens)} / ${formatMetricNumber(traceMetrics.promptMaxTokens)}`}
                  />
                  <TraceMetricPill
                    label="模型 Token"
                    value={formatMetricNumber(traceMetrics.llmTotalTokens)}
                  />
                  <TraceMetricPill
                    label="压缩/丢弃"
                    value={`${traceMetrics.contextCompressedCount} / ${traceMetrics.contextDroppedCount}`}
                    accent={compressed ? '#faad14' : TEXT}
                  />
                  {compressed && (
                    <Tooltip title={traceMetrics.promptActions.length > 0 ? `最终 Prompt 动作：${traceMetrics.promptActions.join(', ')}` : '上下文预算触发了压缩或丢弃'}>
                      <Tag color="warning" style={{ fontSize: 11, margin: 0 }}>
                        自动压缩已触发
                      </Tag>
                    </Tooltip>
                  )}
                  {/* Skill 标签 */}
                  <div style={{ display: 'flex', gap: 6 }}>
                    {(() => {
                      const skillNodes = timeline.rounds.flatMap(r => r.nodes).filter(n => n.node_type === 'skill_call');
                      return skillNodes.slice(0, 3).map((n, i) => (
                        <Tag key={i} color="success" style={{ fontSize: 11, margin: 0 }}>{n.node_name}</Tag>
                      ));
                    })()}
                  </div>
                </>
              ) : (
                <span style={{ color: TEXT_DIM, fontSize: 12 }}>暂无数据</span>
              )}
            </div>
            <Button
              size="small"
              type="link"
              onClick={() => {
                window.open(buildTraceMonitorUrl({ conversationId: sessionId, traceId: timeline?.trace_id }), '_blank');
              }}
              style={{ color: ACCENT, padding: 0, flexShrink: 0 }}
            >
              链路详情 →
            </Button>
          </div>
        )}

        {/* 输入区域 */}
        <Space.Compact style={{ width: '100%' }}>
          <Input
            size="large"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={() => {
              void handleSend();
            }}
            placeholder={loading ? '当前会话生成中，可切换或新建会话并行聊天' : '输入你的问题...'}
            disabled={loading}
            style={{ background: CARD, borderColor: BORDER, color: TEXT, height: 48, fontSize: 14 }}
          />
          <Button
            size="large"
            type="primary"
            icon={<SendOutlined />}
            onClick={() => {
              void handleSend();
            }}
            loading={loading}
            style={{ height: 48, paddingInline: 24, fontSize: 14 }}
          >
            发送
          </Button>
        </Space.Compact>
      </div>
    </div>
  );
}
