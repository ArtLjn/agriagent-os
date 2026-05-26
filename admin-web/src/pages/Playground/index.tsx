import { useState, useRef, useCallback } from 'react';
import { Input, Button, Space, Collapse, Typography } from 'antd';
import { SendOutlined, DeleteOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { listTraces, getTimeline, type TraceTimeline } from '../../api/admin';
import GanttTimeline from '../../components/GanttTimeline';

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
function ChatBubble({ role, content }: { role: 'user' | 'assistant'; content: string }) {
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
      </div>
    </div>
  );
}

/* ── SSE 流式对话 ── */
async function* streamPlaygroundChat(message: string): AsyncGenerator<string> {
  const resp = await fetch('/api/agent/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
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
        if (obj.content) yield obj.content;
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
        const timeline = timelineRes;
    return timeline;
  } catch {
    return null;
  }
}

export default function Playground() {
  const [sessionId, setSessionId] = useState<string>(generateSessionId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [timeline, setTimeline] = useState<TraceTimeline | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

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

  const handleSend = useCallback(async () => {
    if (!input.trim()) return;
    const userMsg = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }]);
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);
    setLoading(true);
    setTimeline(null);
    scrollToBottom();

    let assistantIdx = -1;
    setMessages((prev) => { assistantIdx = prev.length - 1; return prev; });

    try {
      for await (const chunk of streamPlaygroundChat(userMsg)) {
        setMessages((prev) => {
          const next = [...prev];
          if (assistantIdx >= 0 && assistantIdx < next.length) {
            next[assistantIdx] = { ...next[assistantIdx], content: next[assistantIdx].content + chunk };
          }
          return next;
        });
        scrollToBottom();
      }

      // 对话完成后查询最新 trace
      setTraceLoading(true);
      const latestTimeline = await fetchLatestTimeline();
      setTimeline(latestTimeline);
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
  }, [input, scrollToBottom]);

  const isThinking = loading && messages.length > 0 && messages[messages.length - 1].content === '';

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: 24 }}>
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

      {/* 消息区域 */}
      <div ref={scrollRef} style={{
        flex: 1, overflow: 'auto', background: BG, borderRadius: 12,
        border: `1px solid ${BORDER}`, padding: 20, marginBottom: 16,
      }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: TEXT_DIM, padding: '80px 0' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>🧪</div>
            <div style={{ fontSize: 16, marginBottom: 8 }}>Playground — 开发者调试</div>
            <div style={{ fontSize: 13 }}>直接输入消息与 AI 对话，右侧显示执行链路</div>
          </div>
        )}
        {messages.map((m, i) => (
          <ChatBubble key={i} role={m.role} content={m.content} />
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
                        })),
                      }))}
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
          onPressEnter={handleSend}
          placeholder="输入你的问题..."
          disabled={loading}
          style={{ background: CARD, borderColor: BORDER, color: TEXT }}
        />
        <Button
          size="large"
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={loading}
          style={{ height: 40 }}
        >
          发送
        </Button>
      </Space.Compact>
    </div>
  );
}
