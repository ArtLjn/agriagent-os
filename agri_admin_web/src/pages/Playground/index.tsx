import { useState, useRef, useCallback, useEffect } from 'react';
import { isAxiosError } from 'axios';
import { Input, Button, Space, Tooltip, message, Select } from 'antd';
import type { TextAreaRef } from 'antd/es/input/TextArea';
import { SendOutlined, DeleteOutlined, CopyOutlined, PlusOutlined, MenuFoldOutlined, MenuUnfoldOutlined, LoadingOutlined, LinkOutlined, ProfileOutlined, ExperimentOutlined } from '@ant-design/icons';
import { listTraces, getTimeline, type TraceTimeline } from '../../api/admin';
import {
  streamChat,
  approveTurn,
  listDevUsers,
  listConversations,
  getConversationMessages,
  getConversationMessagesPage,
  getConversationTurnDetail,
  getConversationTurns,
  type ConversationItem,
  type ConversationMessage,
  type ConversationTurnDetail,
  type ConversationTurnSummary,
  type DevUser,
  type PendingAction,
  type PendingPlan,
  type StreamTraceContext,
} from '../../api/agent';
import { palette } from '../../styles/theme';
import { buildConversationRows } from './conversationRows';
import { buildSessionDebugExport, type DebugExportMessage } from './sessionDebugExport';
import { applyHistoricalPendingResolution, type PendingResolution } from './pendingPlanControls';
import {
  buildPlaygroundTraceMetrics,
  extractLatestLlmContextSnapshot,
  hasAutomaticCompression,
} from './traceMetrics';
import { copyAsyncText } from './clipboard';
import { buildTraceMonitorUrl, selectLatestTraceId } from './traceLinks';
import { LlmContextInspector, LlmContextTriggerButton } from './LlmContextInspector';
import { QuickPrompts } from './QuickPrompts';
import { ChatBubble } from './ChatBubble';
import './playground.css';
import { appendExecutionEvent, executionEventFromChunk, memoryEventsFromTimeline, type ExecutionEvent } from './executionEvents';
import { formatDuration } from './executionTimelineModel';
import { authStore } from '../../stores/authStore';
import { getSsePresentationProfile, roleLabel, USER_ROLES } from '../../constants/roles';

const CARD = palette.bgElevated;
const TEXT = palette.text;
const TEXT_DIM = palette.textMuted;
const ACCENT = palette.accent;
const SIDEBAR_BG = palette.bgElevated;
const SIDEBAR_BORDER = palette.borderSoft;

interface Message {
  id: string;
  message_id?: string | null;
  turn_id?: string | null;
  trace_id?: string | null;
  role: 'user' | 'assistant';
  content: string;
  message_kind?: string | null;
  meta?: Record<string, unknown>;
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
  historyCursor: string | null;
  historyHasMore: boolean;
  historyLoading: boolean;
  historyRevision: number;
  turnDetail: ConversationTurnDetail | null;
  turnDetailLoading: boolean;
  turns: ConversationTurnSummary[];
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
    historyCursor: null,
    historyHasMore: false,
    historyLoading: false,
    historyRevision: 0,
    turnDetail: null,
    turnDetailLoading: false,
    turns: [],
  };
}

function mapHistoricalMessage(message: ConversationMessage, index: number): Message {
  return {
    id: message.message_id ?? `history-${message.created_at ?? 'unknown'}-${index}-${message.role}`,
    message_id: message.message_id,
    turn_id: message.turn_id,
    trace_id: message.trace_id,
    role: message.role as 'user' | 'assistant',
    content: message.content,
    message_kind: message.message_kind,
    meta: message.meta,
  };
}

function formatMetricNumber(value: number | null): string {
  if (value === null) return '-';
  return value.toLocaleString('zh-CN');
}

function TraceMetricPill({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <span className="pg-stat">
      {label}
      <span className="pg-stat__value" style={accent ? { color: accent } : undefined}>{value}</span>
    </span>
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
  const composerRef = useRef<TextAreaRef>(null);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [devUsers, setDevUsers] = useState<DevUser[]>([]);
  const [selectedDevUser, setSelectedDevUser] = useState<DevUser | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [llmContextOpen, setLlmContextOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  // 只有用户仍在底部时才自动跟随流式输出，避免把正在向上翻看的用户拽回底部。
  const stickToBottomRef = useRef(true);
  // 递增令牌用于作废尚未执行的自动滚动，避免用户上翻后被旧的滚动任务拽回底部。
  const autoScrollTokenRef = useRef(0);
  const activeSession = sessions[sessionId] ?? emptySessionState();
  const messages = activeSession.messages;
  const loading = activeSession.loading;
  const traceLoading = activeSession.traceLoading;
  const timeline = activeSession.timeline;
  const llmContextTimeline = activeSession.llmContextTimeline ?? timeline;
  const turnDetail = activeSession.turnDetail;
  const turnDetailLoading = activeSession.turnDetailLoading;
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
  const executionRole = selectedDevUser?.role ?? USER_ROLES.ADMIN;
  const presentationProfile = getSsePresentationProfile(executionRole);

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
  const loadConversations = useCallback(async (userToken = activeUserToken) => {
    try {
      const list = await listConversations(50, userToken);
      setConversations(list);
    } catch {
      // 静默失败
    }
  }, [activeUserToken]);

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
    stickToBottomRef.current = true;
    updateSession(sid, () => ({ ...emptySessionState(), loading: true }));
    try {
      const [page, turnPage] = await Promise.all([
        getConversationMessagesPage(sid, { userToken: activeUserToken }),
        getConversationTurns(sid, { userToken: activeUserToken }).catch(() => null),
      ]);
      const loaded: Message[] = page.items.map(mapHistoricalMessage);
      const resolved = applyHistoricalPendingResolution(loaded);
      updateSession(sid, (state) => ({
        ...state,
        loading: false,
        trace: null,
        messages: resolved,
        timeline: null,
        llmContextTimeline: null,
        historyCursor: page.next_cursor ?? null,
        historyHasMore: page.has_more,
        historyLoading: false,
        historyRevision: page.conversation_revision ?? 0,
        turnDetail: null,
        turnDetailLoading: false,
        turns: turnPage?.items ?? [],
      }));
    } catch {
      updateSession(sid, (state) => ({ ...state, loading: false }));
      message.error('加载会话失败');
    }
  }, [activeUserToken, updateSession]);

  const loadOlderMessages = useCallback(async () => {
    const sid = sessionId;
    const current = sessions[sid] ?? emptySessionState();
    if (current.historyLoading || !current.historyHasMore || !current.historyCursor) return;

    const container = scrollRef.current;
    const previousHeight = container?.scrollHeight ?? 0;
    const previousTop = container?.scrollTop ?? 0;
    updateSession(sid, (state) => ({ ...state, historyLoading: true }));
    try {
      const page = await getConversationMessagesPage(sid, {
        userToken: activeUserToken,
        cursor: current.historyCursor,
      });
      const older = page.items.map(mapHistoricalMessage);
      updateSession(sid, (state) => {
        const existingIds = new Set(state.messages.map((item) => item.id));
        const uniqueOlder = older.filter((item) => !existingIds.has(item.id));
        return {
          ...state,
          messages: [...uniqueOlder, ...state.messages],
          historyCursor: page.next_cursor ?? null,
          historyHasMore: page.has_more,
          historyRevision: page.conversation_revision ?? state.historyRevision,
          historyLoading: false,
        };
      });
      requestAnimationFrame(() => {
        const nextContainer = scrollRef.current;
        if (nextContainer) {
          nextContainer.scrollTop = previousTop + nextContainer.scrollHeight - previousHeight;
        }
      });
    } catch (error) {
      if (isAxiosError(error) && error.response?.status === 409) {
        await switchConversation(sid);
        return;
      }
      updateSession(sid, (state) => ({ ...state, historyLoading: false }));
      message.error('加载更早历史失败');
    }
  }, [activeUserToken, sessionId, sessions, switchConversation, updateSession]);

  /* ── 新建会话 ── */
  const createNewSession = useCallback(() => {
    const sid = generateSessionId();
    setSessionId(sid);
    stickToBottomRef.current = true;
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
      const persistedMessages = await getConversationMessages(sid, activeUserToken);
      if (persistedMessages.length > 0) {
        // 历史接口保留消息关联字段；skills/pendingAction 仍只存在于当前会话 SSE 流中。
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
  }, [activeUserToken, selectedDevUser, sessions]);

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

  const viewTurnDetails = useCallback(async (turnId: string) => {
    const sid = sessionId;
    updateSession(sid, (state) => ({ ...state, turnDetailLoading: true }));
    try {
      const detail = await getConversationTurnDetail(sid, turnId, {
        userToken: activeUserToken,
      });
      updateSession(sid, (state) => ({
        ...state,
        turnDetail: detail,
        turnDetailLoading: false,
      }));
      if (detail.trace_id) {
        const timeline = await refreshSessionTimeline(sid, detail.trace_id);
        const memoryEvents = memoryEventsFromTimeline(timeline);
        if (memoryEvents.length) updateSession(sid, (state) => ({
          ...state,
          messages: state.messages.map((item) => item.turn_id === turnId && item.role === 'assistant'
            ? { ...item, events: memoryEvents.reduce(appendExecutionEvent, item.events ?? []) } : item),
        }));
      }
    } catch {
      updateSession(sid, (state) => ({ ...state, turnDetailLoading: false }));
      message.error('加载执行详情失败');
    }
  }, [activeUserToken, refreshSessionTimeline, sessionId, updateSession]);

  const refreshLatestHistory = useCallback(async (sid: string) => {
    try {
      const [page, turnPage] = await Promise.all([
        getConversationMessagesPage(sid, { userToken: activeUserToken }),
        getConversationTurns(sid, { userToken: activeUserToken }).catch(() => null),
      ]);
      const persisted = page.items.map(mapHistoricalMessage);
      updateSession(sid, (state) => {
        const next = [...state.messages];
        for (const item of persisted) {
          const existingIndex = next.findIndex((candidate) => (
            candidate.id === item.id
            || (!candidate.message_id
              && candidate.role === item.role
              && candidate.content === item.content)
          ));
          if (existingIndex >= 0) {
            next[existingIndex] = {
              ...item,
              ...next[existingIndex],
              id: item.id,
              message_id: item.message_id,
              turn_id: item.turn_id,
              trace_id: item.trace_id,
              message_kind: item.message_kind,
              meta: item.meta,
            };
          } else if (!next.some((candidate) => candidate.id === item.id)) {
            next.push(item);
          }
        }
        return {
          ...state,
          messages: next,
          historyCursor: page.next_cursor ?? null,
          historyHasMore: page.has_more,
          historyRevision: page.conversation_revision ?? state.historyRevision,
          turns: turnPage?.items ?? state.turns,
        };
      });
    } catch {
      // 最新页刷新失败时保留当前 SSE 结果和历史滚动状态。
    }
  }, [activeUserToken, updateSession]);

  const openLlmContextInspector = useCallback(() => {
    if (selectedDevUser) return;
    setLlmContextOpen(true);
    void refreshSessionTimeline(sessionId);
  }, [refreshSessionTimeline, sessionId, selectedDevUser]);

  const scrollToBottom = useCallback((force = false) => {
    if (!force && !stickToBottomRef.current) return;
    const token = ++autoScrollTokenRef.current;
    setTimeout(() => {
      if (token !== autoScrollTokenRef.current) return;
      if (!force && !stickToBottomRef.current) return;
      const container = scrollRef.current;
      if (!container) return;
      // 流式输出频繁触发，使用瞬时滚动避免动画与用户滚动互相拉扯。
      container.scrollTo({ top: container.scrollHeight, behavior: 'auto' });
    }, 50);
  }, []);

  const handleClear = useCallback(() => {
    const sid = generateSessionId();
    setSessionId(sid);
    stickToBottomRef.current = true;
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
      turnDetail: null,
      turnDetailLoading: false,
    }));
    stickToBottomRef.current = true;
    scrollToBottom(true);

    try {
      const clientRequestId = `${targetSessionId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      let streamedTrace: StreamTraceContext | null = null;
      for await (const chunk of streamChat(userMsg, targetSessionId, activeUserToken, {
        client_request_id: clientRequestId,
        viewerToken,
        presentationProfile,
      })) {
        if (chunk.type === 'meta') {
          streamedTrace = chunk.data;
          // 学习可在回答流结束前启动，收到真实轮次后即可查询，不等待历史回填。
          updateSession(targetSessionId, (state) => ({
            ...state,
            trace: chunk.data,
            messages: state.messages.map((item) => (
              item.id === assistantMessage.id || item.id === userMessage.id
                ? { ...item, turn_id: chunk.data.turn_id, trace_id: chunk.data.trace_id }
                : item
            )),
          }));
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
      await refreshLatestHistory(targetSessionId);

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
  }, [activeUserToken, input, presentationProfile, refreshLatestHistory, scrollToBottom, sessionId, sessions, updateSession, loadConversations, refreshSessionTimeline, selectedDevUser, viewerToken]);

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
    <div className="playground-workspace">
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
            // 会话标题优先展示最近一条消息，机器 ID 只在 tooltip / 复制动作里出现
            const title = conv.last_message?.trim() || (conv.local ? '新会话' : conversationId);
            return (
              <div
                key={conversationId}
                onClick={() => switchConversation(conversationId)}
                className={`pg-session${isActive ? ' pg-session--active' : ''}`}
                style={{
                  padding: sidebarCollapsed ? '8px 0' : '8px 10px',
                  display: sidebarCollapsed ? 'flex' : 'block',
                  justifyContent: sidebarCollapsed ? 'center' : undefined,
                  alignItems: sidebarCollapsed ? 'center' : undefined,
                }}
              >
                {sidebarCollapsed ? (
                  <Tooltip title={`${title} · ${conversationId}`} placement="right">
                    <div className={`pg-session__dot${isActive ? ' pg-session__dot--active' : ''}`}>
                      {conversationId.slice(-2)}
                    </div>
                  </Tooltip>
                ) : (
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                      {isRunning && <LoadingOutlined style={{ color: ACCENT, fontSize: 11, flexShrink: 0 }} />}
                      <div className="pg-session__title" title={conversationId}>
                        {title}
                      </div>
                    </div>
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 4,
                      marginTop: 4,
                    }}>
                      <div className="pg-session__meta">
                        {new Date(conv.last_at).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                        {conv.message_count > 0 && ` · ${conv.message_count} 条`}
                      </div>
                      <span className="pg-session__actions">
                        <Space size={0}>
                          <Tooltip title="复制 Session ID">
                            <Button
                              type="text"
                              size="small"
                              icon={<CopyOutlined />}
                              onClick={(e) => { e.stopPropagation(); void copySessionId(conversationId); }}
                              style={{ color: TEXT_DIM, padding: '0 4px', minWidth: 24, height: 24 }}
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
                      </span>
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
      <div className="playground-chat">
        {/* 顶栏：与全局 header、会话 header 对齐 */}
        <div className="playground-toolbar">
          <div className="playground-toolbar__inner">
            <div className="playground-toolbar__main">
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
                  // 使用 dev-users 返回的 token 获取该用户自己的会话，避免展示管理员会话。
                  const nextToken = user?.token ?? null;
                  void loadConversations(nextToken).catch(() => {
                    message.error('加载会话列表失败');
                  });
                }}
                className="playground-user-select"
                styles={{ popup: { root: { background: CARD } } }}
                options={[
                  { value: '', label: '默认用户（admin 自身）' },
                  ...devUsers.map((u) => ({
                    value: u.user_id,
                    label: `${u.nickname || u.phone} (farm:${u.farm_id}, ${u.role})`,
                  })),
                ]}
              />
              <div
                className="playground-identity"
                title={`viewer: admin · acting_as: ${selectedDevUser?.user_id ?? 'admin'} · presentation: ${selectedDevUser ? 'user' : 'debug'}`}
              >
                <span className={`pg-chip ${presentationProfile === 'user' ? 'pg-chip--accent' : 'pg-chip--muted'}`}>
                  {presentationProfile === 'user' ? `${roleLabel(executionRole)}视图` : '管理员视图'}
                </span>
                {selectedDevUser && (
                  <span className="playground-identity__acting-as">
                    acting_as: {selectedDevUser.user_id}
                  </span>
                )}
              </div>
              <Tooltip title={`${sessionId}（点击复制）`}>
                <button
                  type="button"
                  className="playground-session-id"
                  onClick={() => void copySessionId(sessionId)}
                >
                  <span>{sessionId}</span>
                  <CopyOutlined />
                </button>
              </Tooltip>
            </div>
            <div className="playground-toolbar__actions">
              <LlmContextTriggerButton
                hasSnapshot={Boolean(llmContextSnapshot)}
                loading={loading || traceLoading}
                onClick={() => {
                  if (llmContextOpen) return;
                  openLlmContextInspector();
                }}
                disabled={Boolean(selectedDevUser)}
              />
              <span className="playground-toolbar__divider" />
              <Button
                type="text"
                icon={<DeleteOutlined />}
                onClick={handleClear}
                className="playground-toolbar__danger"
                style={{
                  color: TEXT_DIM,
                  height: 32,
                  paddingInline: 10,
                  borderRadius: 8,
                  fontSize: 13,
                }}
              >
                清空
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                aria-label="新建会话"
                onClick={createNewSession}
                style={{
                  borderRadius: 8,
                  fontWeight: 500,
                  fontSize: 13,
                  height: 32,
                  paddingInline: 14,
                  boxShadow: 'none',
                }}
              >
                新建会话
              </Button>
            </div>
          </div>
        </div>

        {/* 消息区域 */}
        <div
          className="playground-messages surface-scroll"
          ref={scrollRef}
          onScroll={(event) => {
            const container = event.currentTarget;
            const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
            stickToBottomRef.current = nearBottom;
            if (!nearBottom) {
              // 离开底部后停止流式自动跟随，并取消尚未执行的滚动任务。
              autoScrollTokenRef.current += 1;
            }
            if (container.scrollTop <= 48) void loadOlderMessages();
          }}
        >
          {messages.length === 0 && (
            <div className="pg-empty">
              <div className="pg-empty__badge"><ExperimentOutlined /></div>
              <div className="pg-empty__title">田掌柜 Agent Playground</div>
              <div className="pg-empty__hint">
                从感兴趣的问题开始，或直接说说你想了解什么
              </div>
              <QuickPrompts
                key={selectedDevUser?.user_id ?? 'self'}
                userToken={activeUserToken}
                onSelect={(prompt) => { setInput(prompt); composerRef.current?.focus(); }}
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
              turnId={m.turn_id}
              traceId={m.trace_id}
              learningUserToken={activeUserToken}
              watchLearning={m.id === messages[messages.length - 1]?.id}
              loading={loading && m.id === messages[messages.length - 1]?.id}
              pendingAction={m.pendingAction}
              pendingPlan={m.pendingPlan}
              pendingResolution={m.pendingResolution}
              onAction={(action) => { void handlePendingAction(m.id, action); }}
              onViewDetails={viewTurnDetails}
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

        {/* ── 底部输入区：Trace 摘要 + 输入框共用一列宽 ── */}
        <div className="playground-footer">
          {/* Trace 摘要 - 紧凑单行 */}
          {(timeline !== null || traceLoading || turnDetailLoading || turnDetail !== null) && (
            <div className="pg-summary">
              <div className="pg-summary__stats">
                <span className="pg-summary__label">Trace 摘要</span>
                {turnDetailLoading ? (
                  <span style={{ color: TEXT_DIM, fontSize: 12 }}>加载 Turn 详情...</span>
                ) : traceLoading ? (
                  <span style={{ color: TEXT_DIM, fontSize: 12 }}>加载中...</span>
                ) : timeline && timeline.rounds ? (
                  <>
                    {turnDetail && (
                      <span className={`pg-chip ${turnDetail.events_status === 'available' ? 'pg-chip--success' : 'pg-chip--warning'}`}>
                        Turn: {turnDetail.status}
                      </span>
                    )}
                    <TraceMetricPill
                      label="节点"
                      value={formatMetricNumber(timeline.rounds.reduce((s, r) => s + r.nodes.length, 0))}
                    />
                    <TraceMetricPill label="轮次" value={formatMetricNumber(timeline.rounds.length)} />
                    <TraceMetricPill
                      label="耗时"
                      value={formatDuration(timeline.rounds.reduce((s, r) => s + r.nodes.reduce((ns, n) => ns + (n.duration_ms || 0), 0), 0))}
                    />
                    {/* 缺数据的指标直接隐藏，避免 - / - 占位看起来像坏了 */}
                    {traceMetrics.contextTokens !== null && (
                      <TraceMetricPill
                        label="上下文"
                        value={`${formatMetricNumber(traceMetrics.contextTokens)} / ${formatMetricNumber(traceMetrics.contextBudget)}`}
                      />
                    )}
                    {traceMetrics.promptTokens !== null && (
                      <TraceMetricPill
                        label="最终 Prompt"
                        value={`${formatMetricNumber(traceMetrics.promptTokens)} / ${formatMetricNumber(traceMetrics.promptMaxTokens)}`}
                      />
                    )}
                    {traceMetrics.llmTotalTokens > 0 && (
                      <TraceMetricPill
                        label="模型 Token"
                        value={formatMetricNumber(traceMetrics.llmTotalTokens)}
                      />
                    )}
                    {(traceMetrics.contextCompressedCount > 0 || traceMetrics.contextDroppedCount > 0) && (
                      <TraceMetricPill
                        label="压缩/丢弃"
                        value={`${traceMetrics.contextCompressedCount} / ${traceMetrics.contextDroppedCount}`}
                        accent={compressed ? palette.warning : undefined}
                      />
                    )}
                    {compressed && (
                      <Tooltip title={traceMetrics.promptActions.length > 0 ? `最终 Prompt 动作：${traceMetrics.promptActions.join(', ')}` : '上下文预算触发了压缩或丢弃'}>
                        <span className="pg-chip pg-chip--warning">自动压缩已触发</span>
                      </Tooltip>
                    )}
                    {/* Skill 标签 */}
                    <div style={{ display: 'flex', gap: 6 }}>
                      {(() => {
                        const skillNodes = timeline.rounds.flatMap(r => r.nodes).filter(n => n.node_type === 'skill_call');
                        return skillNodes.slice(0, 3).map((n, i) => (
                          <span key={i} className="pg-chip pg-chip--success">{n.node_name}</span>
                        ));
                      })()}
                    </div>
                  </>
                ) : turnDetail ? (
                  <span className="pg-chip pg-chip--warning">执行证据不可用</span>
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
          <div className="playground-composer">
            <Input.TextArea
              ref={composerRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  void handleSend();
                }
              }}
              autoSize={{ minRows: 2, maxRows: 6 }}
              placeholder={loading ? '当前会话生成中，可切换或新建会话并行聊天' : '输入你的问题，让 Agent 帮你处理任务…'}
              disabled={loading}
              aria-label="对话输入"
            />
            <div className="playground-composer__footer">
              <span>{loading ? 'Agent 正在执行任务' : 'Enter 发送 · Shift + Enter 换行'}</span>
              <Button
                type="primary"
                aria-label="发送"
                icon={<SendOutlined />}
                onClick={() => { void handleSend(); }}
                loading={loading}
                disabled={!input.trim() && !loading}
                style={{ height: 32, borderRadius: 8, fontSize: 13, paddingInline: 16 }}
              >
                发送
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
