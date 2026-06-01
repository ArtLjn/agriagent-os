import { useState, useRef, useCallback, useEffect } from 'react';
import { Input, Button, Space, Collapse, Typography, Drawer, Tag, Tooltip, message, Select } from 'antd';
import { SendOutlined, DeleteOutlined, CopyOutlined, PlusOutlined, MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { listTraces, getTimeline, type TraceTimeline, type TraceNodeDetail, listUsers, type AdminUserListItem } from '../../api/admin';
import { listConversations, getConversationMessages, type ConversationItem, type ConversationMessage } from '../../api/agent';
import type { PendingAction } from '../../api/agent';
import GanttTimeline from '../../components/GanttTimeline';
import type { GanttNode } from '../../components/GanttTimeline/types';
import { getNodeLabel } from '../../constants/trace';
import SkillOutputFormatter from '../../components/SkillOutputFormatter';
import { authStore } from '../../stores/authStore';

const BG = '#0d1117';
const CARD = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const ACCENT = '#58a6ff';
const USER_BG = '#1f6feb';
const AI_BG = '#21262d';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  skills?: string[];
  pendingAction?: PendingAction | null;
}

function generateSessionId(): string {
  return `playground-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/* ── Markdown 渲染容器 ── */
function MarkdownContent({ content }: { content: string }) {
  return (
    <div style={{ color: TEXT, lineHeight: 1.7, fontSize: 14 }}>
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}

/* ── 聊天气泡组件 ── */
function ChatBubble({ role, content, skills, pendingAction, onAction }: { role: 'user' | 'assistant'; content: string; skills?: string[]; pendingAction?: PendingAction | null; onAction?: (action: string) => void }) {
  const isUser = role === 'user';
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
        maxWidth: '70%',
        wordBreak: 'break-word',
      }}>
        {isUser ? content : <MarkdownContent content={content} />}
        {!isUser && skills && skills.length > 0 && (
          <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {skills.map((s) => (
              <span key={s} style={{
                fontSize: 11, color: ACCENT, background: 'rgba(88,166,255,0.12)',
                padding: '2px 8px', borderRadius: 4, border: `1px solid ${ACCENT}`,
              }}>
                ⚡ {s}
              </span>
            ))}
          </div>
        )}
        {!isUser && pendingAction && onAction && (
          <div style={{ display: 'flex', gap: 8, marginTop: 10, justifyContent: 'flex-end' }}>
            <button onClick={() => onAction('确认')} style={{ background: '#238636', color: '#fff', border: 'none', borderRadius: 6, padding: '4px 16px', cursor: 'pointer', fontSize: 13 }}>确认</button>
            <button onClick={() => onAction('取消')} style={{ background: '#30363d', color: '#8b949e', border: 'none', borderRadius: 6, padding: '4px 16px', cursor: 'pointer', fontSize: 13 }}>取消</button>
          </div>
        )}
      </div>
    </div>
  );
}

type StreamChunk = { type: 'content'; data: string } | { type: 'skills'; data: string[] } | { type: 'pending_action'; data: PendingAction };

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
      } catch (e) {
        if (e instanceof SyntaxError) continue;
        throw e;
      }
    }
  }
}

/* ── Trace 查询 ── */
async function fetchLatestTimeline(): Promise<TraceTimeline | null> {
  try {
    const listRes = await listTraces({ limit: 1 });
    if (!listRes.items || listRes.items.length === 0) return null;
    const requestId = listRes.items[0].request_id;
    const timelineRes = await getTimeline(requestId);
    return timelineRes;
  } catch {
    return null;
  }
}

function formatJson(raw: string | null): string {
  if (!raw) return '';
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw.replace(/\\n/g, '\n').replace(/\\t/g, '\t').replace(/\\"/g, '"');
  }
}

export default function Playground() {
  const [sessionId, setSessionId] = useState<string>(generateSessionId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [timeline, setTimeline] = useState<TraceTimeline | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [nodeDetail, setNodeDetail] = useState<TraceNodeDetail | null>(null);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  /* ── 加载会话列表 ── */
  const loadConversations = useCallback(async () => {
    try {
      const list = await listConversations(50);
      setConversations(list);
    } catch {
      // 静默失败
    }
  }, []);

  /* ── 加载用户列表 ── */
  const loadUsers = useCallback(async () => {
    try {
      const res = await listUsers({ size: 100 });
      setUsers(res.items);
    } catch {
      // 静默失败
    }
  }, []);

  useEffect(() => {
    loadConversations();
    loadUsers();
  }, [loadConversations, loadUsers]);

  /* ── 切换会话 ── */
  const switchConversation = useCallback(async (sid: string) => {
    setSessionId(sid);
    setMessages([]);
    setTimeline(null);
    try {
      const msgs = await getConversationMessages(sid);
      setMessages(
        msgs.map((m: ConversationMessage) => ({
          role: m.role as 'user' | 'assistant',
          content: m.content,
          skills: m.skills,
        }))
      );
    } catch {
      message.error('加载会话失败');
    }
  }, []);

  /* ── 新建会话 ── */
  const createNewSession = useCallback(() => {
    const sid = generateSessionId();
    setSessionId(sid);
    setMessages([]);
    setTimeline(null);
  }, []);

  /* ── 复制会话 JSON ── */
  const copyConversationJson = useCallback(async () => {
    try {
      const msgs = messages.map((m) => ({
        role: m.role,
        content: m.content,
        skills: m.skills,
      }));
      const json = JSON.stringify(msgs, null, 2);
      await navigator.clipboard.writeText(json);
      message.success('已复制到剪贴板');
    } catch {
      message.error('复制失败');
    }
  }, [messages]);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }, 50);
  }, []);

  const handleClear = useCallback(() => {
    setMessages([]);
    setTimeline(null);
    setSessionId(generateSessionId());
  }, []);

  const handleSend = useCallback(async (overrideMsg?: string) => {
    const userMsg = overrideMsg ?? input.trim();
    if (!userMsg) return;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }]);
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);
    setLoading(true);
    setTimeline(null);
    scrollToBottom();

    let assistantIdx = -1;
    setMessages((prev) => { assistantIdx = prev.length - 1; return prev; });

    try {
      for await (const chunk of streamPlaygroundChat(userMsg, sessionId, selectedUserId)) {
        if (chunk.type === 'content') {
          setMessages((prev) => {
            const next = [...prev];
            if (assistantIdx >= 0 && assistantIdx < next.length) {
              next[assistantIdx] = { ...next[assistantIdx], content: next[assistantIdx].content + chunk.data };
            }
            return next;
          });
          scrollToBottom();
        } else if (chunk.type === 'skills') {
          setMessages((prev) => {
            const next = [...prev];
            if (assistantIdx >= 0 && assistantIdx < next.length) {
              next[assistantIdx] = { ...next[assistantIdx], skills: chunk.data };
            }
            return next;
          });
        } else if (chunk.type === 'pending_action') {
          setMessages((prev) => {
            const next = [...prev];
            if (assistantIdx >= 0 && assistantIdx < next.length) {
              next[assistantIdx] = { ...next[assistantIdx], pendingAction: chunk.data };
            }
            return next;
          });
        }
      }

      setTraceLoading(true);
      const latestTimeline = await fetchLatestTimeline();
      setTimeline(latestTimeline);

      await loadConversations();
    } catch {
      setMessages((prev) => {
        const next = [...prev];
        if (assistantIdx >= 0 && assistantIdx < next.length) {
          next[assistantIdx] = { role: 'assistant', content: '对话失败，请重试' };
        }
        return next;
      });
    } finally {
      setLoading(false);
      setTraceLoading(false);
    }
  }, [input, scrollToBottom, sessionId, loadConversations, selectedUserId]);

  const isThinking = loading && messages.length > 0 && messages[messages.length - 1].content === '';

  const handleNodeClick = (
    _roundIndex: number,
    _nodeIndex: number,
    nodeData: GanttNode
  ) => {
    const detail: TraceNodeDetail = {
      id: 0,
      request_id: '',
      round_index: _roundIndex,
      node_type: nodeData.node_type,
      node_name: nodeData.node_name,
      input_data: nodeData.input_data ?? null,
      output_data: nodeData.output_data ?? null,
      duration_ms: nodeData.duration_ms,
      token_usage: null,
      status: nodeData.status,
      error_message: nodeData.error_message ?? null,
      start_time: nodeData.start_time,
      end_time: null,
    };
    setNodeDetail(detail);
    setDrawerOpen(true);
  };

  return (
    <div style={{ height: '100%', display: 'flex' }}>
      {/* ── 会话列表侧边栏 ── */}
      <div
        style={{
          width: sidebarCollapsed ? 48 : 240,
          background: CARD,
          borderRight: `1px solid ${BORDER}`,
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
          transition: 'width 0.2s',
          overflow: 'hidden',
        }}
      >
        {/* 侧边栏头部 */}
        <div
          style={{
            height: 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 12px',
            borderBottom: `1px solid ${BORDER}`,
            flexShrink: 0,
          }}
        >
          {!sidebarCollapsed && (
            <span style={{ color: TEXT, fontSize: 14, fontWeight: 600 }}>会话列表</span>
          )}
          <Button
            type="text"
            icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            style={{ color: TEXT_DIM, padding: 0 }}
          />
        </div>

        {/* 新建会话按钮 */}
        {!sidebarCollapsed && (
          <div style={{ padding: '8px 12px', borderBottom: `1px solid ${BORDER}` }}>
            <Button
              block
              type="primary"
              icon={<PlusOutlined />}
              onClick={createNewSession}
              style={{ background: ACCENT }}
            >
              新会话
            </Button>
          </div>
        )}

        {/* 会话列表 */}
        <div style={{ flex: 1, overflow: 'auto', padding: sidebarCollapsed ? '8px 0' : '8px' }}>
          {conversations.map((conv) => {
            const isActive = conv.session_id === sessionId;
            return (
              <div
                key={conv.id}
                onClick={() => switchConversation(conv.session_id)}
                style={{
                  padding: '8px 10px',
                  borderRadius: 6,
                  marginBottom: 4,
                  cursor: 'pointer',
                  background: isActive ? 'rgba(88,166,255,0.15)' : 'transparent',
                  borderLeft: isActive ? `3px solid ${ACCENT}` : '3px solid transparent',
                  position: 'relative',
                  display: sidebarCollapsed ? 'none' : 'block',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ overflow: 'hidden' }}>
                    <div style={{ color: TEXT, fontSize: 13, fontWeight: isActive ? 600 : 400, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {conv.session_id.slice(0, 10)}...
                    </div>
                    <div style={{ color: TEXT_DIM, fontSize: 11, marginTop: 2 }}>
                      {new Date(conv.created_at).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                  <Tooltip title="复制 JSON">
                    <Button
                      type="text"
                      size="small"
                      icon={<CopyOutlined />}
                      onClick={(e) => { e.stopPropagation(); copyConversationJson(); }}
                      style={{ color: TEXT_DIM, padding: '0 4px', minWidth: 24 }}
                    />
                  </Tooltip>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── 主聊天区域 ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 24, overflow: 'hidden' }}>
        {/* 页面标题 */}
        <Typography.Title level={3} style={{ color: TEXT, margin: '0 0 16px 0' }}>
          Chat Playground
        </Typography.Title>

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

        {/* 消息区域 */}
        <div ref={scrollRef} style={{
          flex: 1, overflow: 'auto', background: BG, borderRadius: 12,
          border: `1px solid ${BORDER}`, padding: 20, marginBottom: 16,
        }}>
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', color: TEXT_DIM, padding: '80px 0' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🧪</div>
              <div style={{ fontSize: 16, marginBottom: 8 }}>Playground — 开发者调试</div>
              <div style={{ fontSize: 13 }}>直接输入消息与 AI 对话，或从左侧切换历史会话</div>
            </div>
          )}
          {messages.map((m, i) => (
            <ChatBubble
              key={i}
              role={m.role}
              content={m.content}
              skills={m.skills}
              pendingAction={m.pendingAction}
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

        {/* Trace Overlay */}
        {(timeline !== null || traceLoading) && (
          <div style={{ marginBottom: 16 }}>
            <Collapse
              bordered={false}
              style={{ background: CARD, border: `1px solid ${BORDER}`, borderRadius: 8 }}
              items={[
                {
                  key: 'trace',
                  label: (
                    <span style={{ color: ACCENT, fontSize: 14, fontWeight: 500 }}>
                      执行链路 {traceLoading && '(加载中...)'}
                    </span>
                  ),
                  children: timeline ? (
                    timeline.rounds && timeline.rounds.length > 0 ? (
                      <GanttTimeline
                        rounds={timeline.rounds.map((r) => ({
                          round_index: r.round_index,
                          nodes: r.nodes.map((n) => ({
                            node_type: n.node_type,
                            node_name: n.node_name,
                            duration_ms: n.duration_ms,
                            status: n.status,
                            start_time: n.start_time,
                            input_data: n.input_data,
                            output_data: n.output_data,
                            error_message: n.error_message,
                          })),
                        }))}
                        onNodeClick={handleNodeClick}
                      />
                    ) : (
                      <div style={{ color: TEXT_DIM, textAlign: 'center', padding: '24px 0' }}>
                        暂无执行链路数据
                      </div>
                    )
                  ) : (
                    <div style={{ color: TEXT_DIM, textAlign: 'center', padding: '24px 0' }}>
                      暂无执行链路数据
                    </div>
                  ),
                },
              ]}
            />
          </div>
        )}

        {/* 输入区域 */}
        <Space.Compact style={{ width: '100%' }}>
          <Input
            size="large"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={() => handleSend()}
            placeholder="输入你的问题..."
            disabled={loading}
            style={{ background: CARD, borderColor: BORDER, color: TEXT }}
          />
          <Button
            size="large"
            type="primary"
            icon={<SendOutlined />}
            onClick={() => handleSend()}
            loading={loading}
            style={{ height: 40 }}
          >
            发送
          </Button>
        </Space.Compact>

        {/* 节点详情 Drawer */}
        <Drawer
          title="节点详情"
          placement="right"
          width={640}
          onClose={() => setDrawerOpen(false)}
          open={drawerOpen}
        >
          {nodeDetail ? (
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <Tag color={nodeDetail.status === 'success' ? 'success' : 'error'}>
                  {nodeDetail.status}
                </Tag>
                <Tag color="processing">{getNodeLabel(nodeDetail.node_type)}</Tag>
                <span style={{ color: TEXT_DIM }}>
                  {nodeDetail.duration_ms?.toLocaleString() ?? '-'} ms
                </span>
              </div>
              <div>
                <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>节点名称</div>
                <div style={{ fontSize: 15, fontWeight: 500 }}>{nodeDetail.node_name}</div>
              </div>
              {nodeDetail.start_time && (
                <div>
                  <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>开始时间</div>
                  <div>{new Date(nodeDetail.start_time).toLocaleString('zh-CN')}</div>
                </div>
              )}
              {nodeDetail.error_message && (
                <div>
                  <div style={{ color: '#ff4d4f', marginBottom: 4, fontSize: 12 }}>错误信息</div>
                  <pre style={{
                    backgroundColor: '#2a1215', padding: 12, borderRadius: 6,
                    border: '1px solid #58181c', color: '#ff4d4f', fontSize: 12,
                    margin: 0, whiteSpace: 'pre-wrap',
                  }}>
                    {nodeDetail.error_message}
                  </pre>
                </div>
              )}
              {nodeDetail.input_data && (
                <div>
                  <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>输入数据</div>
                  <pre style={{
                    backgroundColor: '#161b22', padding: 12, borderRadius: 6,
                    border: '1px solid #30363d', fontSize: 12, margin: 0,
                    maxHeight: 300, overflow: 'auto', whiteSpace: 'pre-wrap',
                  }}>
                    {formatJson(nodeDetail.input_data)}
                  </pre>
                </div>
              )}
              {nodeDetail.output_data && (
                <div>
                  <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>输出数据</div>
                  {nodeDetail.node_type === 'skill_call' ? (
                    <SkillOutputFormatter outputData={nodeDetail.output_data} />
                  ) : (
                    <pre style={{
                      backgroundColor: '#161b22', padding: 12, borderRadius: 6,
                      border: '1px solid #30363d', fontSize: 12, margin: 0,
                      maxHeight: 500, overflow: 'auto', whiteSpace: 'pre-wrap',
                    }}>
                      {formatJson(nodeDetail.output_data)}
                    </pre>
                  )}
                </div>
              )}
            </Space>
          ) : null}
        </Drawer>
      </div>
    </div>
  );
}
