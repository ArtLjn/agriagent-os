import { useState, useRef, useCallback, useEffect } from 'react';
import { Input, Button, Space, Drawer, Tag, Tooltip, message, Select } from 'antd';
import { SendOutlined, DeleteOutlined, CopyOutlined, PlusOutlined, MenuFoldOutlined, MenuUnfoldOutlined, LoadingOutlined, LinkOutlined, ProfileOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { listTraces, getTimeline, type TraceNodeDetail, type TraceTimeline, listUsers, type AdminUserListItem } from '../../api/admin';
import { getSessionDebugExport, listConversations, getConversationMessages, type ConversationItem, type ConversationMessage } from '../../api/agent';
import type { PendingAction } from '../../api/agent';
import type { PendingPlan } from '../../api/agent';
import { getNodeLabel } from '../../constants/trace';
import SkillOutputFormatter from '../../components/SkillOutputFormatter';
import { formatTracePayload, hasTracePayload } from '../../utils/tracePayload';
import { authStore } from '../../stores/authStore';
import { palette } from '../../styles/theme';
import { buildConversationRows } from './conversationRows';
import { usersApi, type CurrentUser } from '../../api/users';
import { chooseDefaultUserId } from './currentUser';
import { buildSessionDebugExport, type DebugExportMessage } from './sessionDebugExport';
import { canConfirmAssistantMessage } from './pendingPlanControls';
import {
  buildPlaygroundTraceMetrics,
  extractLatestLlmContextSnapshot,
  hasAutomaticCompression,
} from './traceMetrics';
import { copyAsyncText } from './clipboard';
import { buildTraceMonitorUrl, selectLatestTraceRequestId } from './traceLinks';
import { LlmContextInspector } from './LlmContextInspector';

const CARD = palette.bgElevated;
const BORDER = palette.border;
const TEXT = palette.text;
const TEXT_DIM = palette.textMuted;
const ACCENT = palette.accent;
const USER_BG = palette.accentStrong;
const AI_BG = palette.bgPanel;
const SIDEBAR_BG = palette.bgElevated;
const SIDEBAR_BORDER = palette.borderSoft;
const ROW_HOVER = 'rgba(139, 148, 158, 0.08)';
const ROW_ACTIVE = 'rgba(88, 166, 255, 0.12)';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  skills?: string[];
  pendingAction?: PendingAction | null;
  pendingPlan?: PendingPlan | null;
}

interface ChatSessionState {
  messages: Message[];
  loading: boolean;
  traceLoading: boolean;
  timeline: TraceTimeline | null;
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
    timeline: null,
  };
}

/* ── Markdown 渲染容器 ── */
function MarkdownContent({ content }: { content: string }) {
  return (
    <div style={{ color: TEXT, lineHeight: 1.7, fontSize: 14 }}>
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}

/* ── 执行状态标签 ── */
function ExecutionStatus({ skills, pendingAction, pendingPlan }: { skills?: string[]; pendingAction?: PendingAction | null; pendingPlan?: boolean }) {
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
function ChatBubble({ role, content, skills, pendingAction, pendingPlan, onAction }: { role: 'user' | 'assistant'; content: string; skills?: string[]; pendingAction?: PendingAction | null; pendingPlan?: PendingPlan | null; onAction?: (action: string) => void }) {
  const isUser = role === 'user';
  const canConfirm = canConfirmAssistantMessage({ role, content, pendingAction, pendingPlan });
  return (
    <div style={{ marginBottom: 16, display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
      {!isUser && (
        <div style={{
          width: 32, height: 32, borderRadius: '50%', background: '#238636',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontSize: 14, fontWeight: 700, marginRight: 10, flexShrink: 0,
        }}>AI</div>
      )}
      <div style={{
        background: isUser ? USER_BG : AI_BG,
        color: TEXT,
        padding: '10px 16px',
        borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
        maxWidth: '78%',
        wordBreak: 'break-word',
      }}>
        {isUser ? content : <MarkdownContent content={content} />}
        {!isUser && (
          <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <ExecutionStatus
              skills={skills}
              pendingAction={pendingAction}
              pendingPlan={canConfirm && !pendingAction}
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
        {!isUser && canConfirm && onAction && (
          <div style={{ display: 'flex', gap: 8, marginTop: 10, justifyContent: 'flex-end' }}>
            <button onClick={() => onAction('确认')} style={{ background: '#238636', color: '#fff', border: 'none', borderRadius: 6, padding: '4px 16px', cursor: 'pointer', fontSize: 13 }}>确认</button>
            <button onClick={() => onAction('取消')} style={{ background: '#30363d', color: '#8b949e', border: 'none', borderRadius: 6, padding: '4px 16px', cursor: 'pointer', fontSize: 13 }}>取消</button>
          </div>
        )}
      </div>
    </div>
  );
}

type StreamChunk =
  | { type: 'content'; data: string }
  | { type: 'skills'; data: string[] }
  | { type: 'pending_action'; data: PendingAction }
  | { type: 'pending_plan'; data: PendingPlan };

/* ── SSE 流式对话 ── */
async function* streamPlaygroundChat(message: string, sessionId: string, simulateUserId?: string | null): AsyncGenerator<StreamChunk> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = authStore.getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const resp = await fetch('/api/agent/chat/stream', {
    method: 'POST',
    headers,
    body: JSON.stringify({ message, session_id: sessionId, simulate_user_id: simulateUserId }),
  });
  if (!resp.ok || !resp.body) throw new Error(`stream error: ${resp.status}`);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop() ?? '';
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data: ')) continue;
      const payload = trimmed.slice(6);
      if (payload === '[DONE]') return;
      try {
        const obj = JSON.parse(payload);
        if (obj.error) throw new Error(obj.error);
        if (obj.content) yield { type: 'content', data: obj.content };
        if (obj.skills) yield { type: 'skills', data: obj.skills };
        if (obj.pending_action) yield { type: 'pending_action', data: obj.pending_action };
        if (obj.pending_plan) yield { type: 'pending_plan', data: obj.pending_plan };
      } catch (e) {
        if (e instanceof SyntaxError) continue;
        throw e;
      }
    }
  }
}

/* ── Trace 查询 ── */
async function fetchSessionTimeline(sid: string): Promise<TraceTimeline | null> {
  try {
    const listRes = await listTraces({ session_id: sid, limit: 1 });
    if (!listRes.items || listRes.items.length === 0) return null;
    const requestId = listRes.items[0].request_id;
    const timelineRes = await getTimeline(requestId);
    return timelineRes;
  } catch {
    return null;
  }
}

export default function Playground() {
  const [sessionId, setSessionId] = useState<string>(generateSessionId);
  const [sessions, setSessions] = useState<Record<string, ChatSessionState>>(() => ({
    [sessionId]: emptySessionState(),
  }));
  const [input, setInput] = useState('');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [nodeDetail] = useState<TraceNodeDetail | null>(null);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [llmContextOpen, setLlmContextOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeSession = sessions[sessionId] ?? emptySessionState();
  const messages = activeSession.messages;
  const loading = activeSession.loading;
  const traceLoading = activeSession.traceLoading;
  const timeline = activeSession.timeline;
  const traceMetrics = buildPlaygroundTraceMetrics(timeline);
  const llmContextSnapshot = extractLatestLlmContextSnapshot(timeline);
  const compressed = hasAutomaticCompression(traceMetrics);
  const conversationRows = buildConversationRows(sessions, conversations);

  const updateSession = useCallback((sid: string, updater: (state: ChatSessionState) => ChatSessionState) => {
    setSessions((prev) => {
      const current = prev[sid] ?? emptySessionState();
      return { ...prev, [sid]: updater(current) };
    });
  }, []);

  const ensureSession = useCallback((sid: string) => {
    setSessions((prev) => (prev[sid] ? prev : { ...prev, [sid]: emptySessionState() }));
  }, []);

  /* ── 加载会话列表 ── */
  const loadConversations = useCallback(async () => {
    try {
      const list = await listConversations(50, selectedUserId);
      setConversations(list);
    } catch {
      // 静默失败
    }
  }, [selectedUserId]);

  /* ── 加载用户列表 ── */
  const loadUsers = useCallback(async () => {
    try {
      const [currentRes, res] = await Promise.all([
        usersApi.getCurrent(),
        listUsers({ size: 100 }),
      ]);
      setUsers(res.items);
      setCurrentUser(currentRes.data);
      const defaultUserId = chooseDefaultUserId(currentRes.data, res.items);
      setSelectedUserId((prev) => prev ?? defaultUserId);
      if (defaultUserId) {
        const list = await listConversations(50, defaultUserId);
        setConversations(list);
      }
    } catch {
      // 静默失败
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => {
      loadUsers();
    });
  }, [loadUsers]);

  useEffect(() => {
    setLlmContextOpen(false);
  }, [sessionId]);

  /* ── 切换会话 ── */
  const switchConversation = useCallback(async (sid: string) => {
    setSessionId(sid);
    updateSession(sid, () => ({ ...emptySessionState(), loading: true }));
    try {
      const msgs = await getConversationMessages(sid, selectedUserId);
      updateSession(sid, (state) => ({
        ...state,
        loading: false,
        messages: msgs.map((m: ConversationMessage) => ({
          id: `history-${m.id}`,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          skills: m.skills,
          pendingAction: m.pending_action,
          pendingPlan: m.pending_plan,
        })),
        timeline: null,
      }));
    } catch {
      updateSession(sid, (state) => ({ ...state, loading: false }));
      message.error('加载会话失败');
    }
  }, [selectedUserId, updateSession]);

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
      const persistedMessages = await getConversationMessages(sid, selectedUserId);
      if (persistedMessages.length > 0) {
        sourceMessages = persistedMessages.map((m) => ({
          role: m.role,
          content: m.content,
          skills: m.skills,
          pendingAction: m.pending_action,
          pendingPlan: m.pending_plan,
        }));
      }
    } catch {
      // 历史消息读取失败时，使用当前本地状态继续导出。
    }
    const timeline = state.timeline ?? await fetchSessionTimeline(sid);
    const debugExport = buildSessionDebugExport({
      sessionId: sid,
      simulateUserId: selectedUserId,
      copiedAt: new Date().toISOString(),
      messages: sourceMessages,
      timeline,
    });
    return JSON.stringify(debugExport, null, 2);
  }, [selectedUserId, sessions]);

  const copySessionJson = useCallback(async (sid: string) => {
    const ok = await copyAsyncText({
      placeholder: `正在准备调试 JSON...\nsession_id: ${sid}`,
      loadText: async () => {
        try {
          const debugExport = await getSessionDebugExport(sid, selectedUserId);
          return JSON.stringify(debugExport, null, 2);
        } catch {
          return buildFallbackSessionDebugJson(sid);
        }
      },
    });
    if (ok) {
      message.success('已复制调试 JSON 到剪贴板');
    } else {
      message.error('复制失败');
    }
  }, [buildFallbackSessionDebugJson, selectedUserId]);

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
    const requestIdFromTimeline = state?.timeline?.request_id;
    if (requestIdFromTimeline) {
      window.open(buildTraceMonitorUrl({ sessionId: sid, requestId: requestIdFromTimeline }), '_blank');
      return;
    }
    try {
      const listRes = await listTraces({ session_id: sid, limit: 1 });
      const requestId = selectLatestTraceRequestId(listRes.items);
      window.open(buildTraceMonitorUrl({ sessionId: sid, requestId }), '_blank');
    } catch {
      window.open(buildTraceMonitorUrl({ sessionId: sid }), '_blank');
    }
  }, [sessions]);

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

  const handleSend = useCallback(async (overrideMsg?: string) => {
    const userMsg = overrideMsg ?? input.trim();
    if (!userMsg) return;
    const targetSessionId = sessionId;
    const targetSession = sessions[targetSessionId] ?? emptySessionState();
    if (targetSession.loading) {
      message.warning('当前会话正在生成中，请先切换到其他会话并行发送');
      return;
    }
    const userMessage = createMessage('user', userMsg);
    const assistantMessage = createMessage('assistant', '');
    setInput('');
    updateSession(targetSessionId, (state) => ({
      ...state,
      messages: [...state.messages, userMessage, assistantMessage],
      loading: true,
      traceLoading: false,
      timeline: null,
    }));
    scrollToBottom();

    try {
      for await (const chunk of streamPlaygroundChat(userMsg, targetSessionId, selectedUserId)) {
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

      updateSession(targetSessionId, (state) => ({ ...state, traceLoading: true }));
      const latestTimeline = await fetchSessionTimeline(targetSessionId);
      updateSession(targetSessionId, (state) => ({
        ...state,
        timeline: latestTimeline,
        traceLoading: false,
      }));

      await loadConversations();
    } catch {
      updateSession(targetSessionId, (state) => {
        const next = state.messages.map((item) => (
          item.id === assistantMessage.id
            ? { ...item, content: '对话失败，请重试' }
            : item
        ));
        return { ...state, messages: next };
      });
    } finally {
      updateSession(targetSessionId, (state) => ({
        ...state,
        loading: false,
        traceLoading: false,
      }));
    }
  }, [input, scrollToBottom, sessionId, sessions, updateSession, loadConversations, selectedUserId]);

  const isThinking = loading && messages.length > 0 && messages[messages.length - 1].content === '';

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
            padding: sidebarCollapsed ? '0 8px' : '0 16px',
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

        {/* 新建会话按钮 */}
        {!sidebarCollapsed && (
          <div style={{ padding: '12px 12px 8px', flexShrink: 0 }}>
            <Button
              block
              type="primary"
              icon={<PlusOutlined />}
              onClick={createNewSession}
              style={{
                background: ACCENT,
                borderColor: ACCENT,
                height: 36,
                borderRadius: 8,
                fontWeight: 500,
              }}
            >
              新建会话
            </Button>
          </div>
        )}

        {/* 会话列表 */}
        <div className="surface-scroll" style={{ flex: 1, overflow: 'auto', padding: sidebarCollapsed ? '8px 6px' : '6px 8px' }}>
          {conversationRows.map((conv) => {
            const isActive = conv.session_id === sessionId;
            const sessionState = sessions[conv.session_id];
            const isRunning = Boolean(sessionState?.loading);
            return (
              <div
                key={conv.session_id}
                onClick={() => switchConversation(conv.session_id)}
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
                  <Tooltip title={conv.session_id} placement="right">
                    <div style={{
                      width: 28, height: 28, borderRadius: 8,
                      background: isActive ? ACCENT : 'rgba(139,148,158,0.12)',
                      color: isActive ? '#fff' : TEXT_DIM,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 12, fontWeight: 600,
                    }}>
                      {conv.session_id.slice(-2)}
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
                        {conv.session_id}
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
                        {new Date(conv.created_at).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </div>
                      <Space size={0} style={{ opacity: isActive ? 1 : 0.6, flexShrink: 0 }}>
                        <Tooltip title="复制 Session ID">
                          <Button
                            type="text"
                            size="small"
                            icon={<CopyOutlined />}
                            onClick={(e) => { e.stopPropagation(); void copySessionId(conv.session_id); }}
                            style={{ color: isActive ? ACCENT : TEXT_DIM, padding: '0 4px', minWidth: 24, height: 24 }}
                          />
                        </Tooltip>
                        <Tooltip title="跳转链路追踪">
                          <Button
                            type="text"
                            size="small"
                            icon={<LinkOutlined />}
                            onClick={(e) => { e.stopPropagation(); openTraceMonitor(conv.session_id); }}
                            style={{ color: TEXT_DIM, padding: '0 4px', minWidth: 24, height: 24 }}
                          />
                        </Tooltip>
                        <Tooltip title="复制调试 JSON">
                          <Button
                            type="text"
                            size="small"
                            icon={<ProfileOutlined />}
                            onClick={(e) => { e.stopPropagation(); copySessionJson(conv.session_id); }}
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
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden', padding: '16px 20px 16px' }}>
        {/* 配置栏 - 极简单行 */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '0 4px 12px',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Select
              placeholder="选择用户"
              value={selectedUserId}
              onChange={(value) => {
                setSelectedUserId(value);
                const sid = generateSessionId();
                setSessionId(sid);
                setSessions({ [sid]: emptySessionState() });
                setConversations([]);
                void listConversations(50, value).then(setConversations).catch(() => {
                  message.error('加载会话列表失败');
                });
              }}
              style={{ width: 200 }}
              styles={{ popup: { root: { background: CARD } } }}
              options={[
                ...users.map((u) => ({
                  value: u.id,
                  label: u.id === currentUser?.id
                    ? `${u.nickname || u.phone}（当前登录）`
                    : u.nickname || u.phone,
                })),
              ]}
            />
            <Tooltip title={`${sessionId}（点击复制）`}>
              <span
                onClick={() => void copySessionId(sessionId)}
                style={{
                  color: TEXT_DIM,
                  fontSize: 12,
                  fontFamily: 'monospace',
                  maxWidth: 360,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  cursor: 'pointer',
                  padding: '2px 6px',
                  borderRadius: 4,
                  transition: 'background 120ms ease, color 120ms ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = ROW_HOVER;
                  e.currentTarget.style.color = TEXT;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = TEXT_DIM;
                }}
              >
                {sessionId}
              </span>
            </Tooltip>
            <Tooltip title="复制 Session ID">
              <Button
                type="text"
                size="small"
                icon={<CopyOutlined />}
                onClick={() => void copySessionId(sessionId)}
                style={{ color: TEXT_DIM, padding: '0 6px', minWidth: 24, height: 24 }}
              />
            </Tooltip>
          </div>
          <Button
            size="small"
            type="text"
            icon={<DeleteOutlined />}
            onClick={handleClear}
            style={{ color: TEXT_DIM }}
          >
            清空
          </Button>
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
            }}>
              <div style={{ fontSize: 56, marginBottom: 20, opacity: 0.6 }}>🧪</div>
              <div style={{ fontSize: 18, marginBottom: 8, color: TEXT, fontWeight: 500 }}>Playground — 开发者调试</div>
              <div style={{ fontSize: 13, maxWidth: 360, lineHeight: 1.6 }}>
                直接输入消息与 AI 对话，或从左侧切换历史会话
              </div>
            </div>
          )}
          {messages.map((m) => (
            <ChatBubble
              key={m.id}
              role={m.role}
              content={m.content}
              skills={m.skills}
              pendingAction={m.pendingAction}
              pendingPlan={m.pendingPlan}
              onAction={loading ? undefined : (action) => handleSend(action)}
            />
          ))}
          {isThinking && (
            <div style={{ display: 'flex', alignItems: 'center', color: TEXT_DIM, padding: '0 42px' }}>
              <span className="ant-spin-dot" style={{ marginRight: 8 }} />
              AI 正在思考中...
            </div>
          )}
        </div>

        {llmContextSnapshot && (
          <LlmContextInspector
            snapshot={llmContextSnapshot}
            open={llmContextOpen}
            onToggle={() => setLlmContextOpen((value) => !value)}
          />
        )}

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
                window.open(buildTraceMonitorUrl({ sessionId, requestId: timeline?.request_id }), '_blank');
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
            onPressEnter={() => handleSend()}
            placeholder={loading ? '当前会话生成中，可切换或新建会话并行聊天' : '输入你的问题...'}
            disabled={loading}
            style={{ background: CARD, borderColor: BORDER, color: TEXT, height: 48, fontSize: 14 }}
          />
          <Button
            size="large"
            type="primary"
            icon={<SendOutlined />}
            onClick={() => handleSend()}
            loading={loading}
            style={{ height: 48, paddingInline: 24, fontSize: 14 }}
          >
            发送
          </Button>
        </Space.Compact>
      </div>

      {/* ── 右侧节点详情浮窗 ── */}
      <Drawer
        title="节点详情"
        placement="right"
        width={480}
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        styles={{
          body: { background: '#0d1117', padding: 0 },
          header: { background: '#161b22', borderBottom: '1px solid #30363d', color: '#e6edf3' },
          mask: { background: 'rgba(0,0,0,0.6)' },
        }}
      >
        {nodeDetail ? (
          <div style={{ padding: 16, color: TEXT }}>
            {/* 头部信息 */}
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16 }}>
              <Tag color={nodeDetail.status === 'success' ? 'success' : 'error'}>
                {nodeDetail.status}
              </Tag>
              <Tag color="processing">{getNodeLabel(nodeDetail.node_type)}</Tag>
              <span style={{ color: TEXT_DIM, fontSize: 13 }}>
                {nodeDetail.duration_ms?.toLocaleString() ?? '-'} ms
              </span>
            </div>

            {/* 节点名称 */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 4 }}>节点名称</div>
              <div style={{ fontSize: 16, fontWeight: 600, color: ACCENT }}>{nodeDetail.node_name}</div>
            </div>

            {/* 开始时间 */}
            {nodeDetail.start_time && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 4 }}>开始时间</div>
                <div style={{ fontSize: 13 }}>{new Date(nodeDetail.start_time).toLocaleString('zh-CN')}</div>
              </div>
            )}

            {/* 错误信息 */}
            {nodeDetail.error_message && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ color: '#ff4d4f', fontSize: 12, marginBottom: 4 }}>错误信息</div>
                <pre style={{
                  backgroundColor: '#2a1215', padding: 12, borderRadius: 6,
                  border: '1px solid #58181c', color: '#ff4d4f', fontSize: 12,
                  margin: 0, whiteSpace: 'pre-wrap',
                }}>
                  {nodeDetail.error_message}
                </pre>
              </div>
            )}

            {/* 输入数据 */}
            {hasTracePayload(nodeDetail.input_data) && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 4 }}>输入数据</div>
                <pre style={{
                  backgroundColor: '#161b22', padding: 12, borderRadius: 6,
                  border: '1px solid #30363d', fontSize: 12, margin: 0,
                  maxHeight: 300, overflow: 'auto', whiteSpace: 'pre-wrap',
                  color: TEXT,
                }}>
                  {formatTracePayload(nodeDetail.input_data)}
                </pre>
              </div>
            )}

            {/* 输出数据 */}
            {hasTracePayload(nodeDetail.output_data) && (
              <div>
                <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 4 }}>输出数据</div>
                {nodeDetail.node_type === 'skill_call' ? (
                  <SkillOutputFormatter outputData={nodeDetail.output_data} />
                ) : (
                  <pre style={{
                    backgroundColor: '#161b22', padding: 12, borderRadius: 6,
                    border: '1px solid #30363d', fontSize: 12, margin: 0,
                    maxHeight: 500, overflow: 'auto', whiteSpace: 'pre-wrap',
                    color: TEXT,
                  }}>
                    {formatTracePayload(nodeDetail.output_data)}
                  </pre>
                )}
              </div>
            )}
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
