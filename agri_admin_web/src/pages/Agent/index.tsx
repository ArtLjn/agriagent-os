import { useState, useEffect, useRef } from 'react';
import { Tabs, Input, Button, Select, Space, Switch, message, Typography } from 'antd';
import { SendOutlined, BulbOutlined, FileTextOutlined, HistoryOutlined } from '@ant-design/icons';
import { approveTurn, streamChat, type PendingAction } from '../../api/agent';
import { personalizationApi, type PersonalizationSettings } from '../../api/personalization';
import { listCycles, type CropCycleListItem } from '../../api/cycles';
import { PageShell } from '../../components/PageShell';
import { MarkdownContent } from '../../components/MarkdownContent';
import { palette } from '../../styles/theme';

const BG = palette.bg;
const CARD = palette.bgElevated;
const BORDER = palette.border;
const TEXT = palette.text;
const TEXT_DIM = palette.textMuted;
const USER_BG = palette.accentFill;
const AI_BG = palette.bgSoftStrong;

function generateSessionId(): string {
  return `agent-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export default function Agent() {
  const [cycles, setCycles] = useState<CropCycleListItem[]>([]);
  const [selectedCycle, setSelectedCycle] = useState<number | undefined>();

  useEffect(() => {
    listCycles().then((res) => setCycles(res.items)).catch(() => {});
  }, []);

  return (
    <PageShell title="AI 助手" description="围绕种植、农事和经营数据，与田掌柜协作。">
      <Tabs
        style={{ flex: 1 }}
        items={[
          { key: 'chat', label: <span><SendOutlined /> 对话</span>, children: <ChatTab cycles={cycles} selectedCycle={selectedCycle} setSelectedCycle={setSelectedCycle} /> },
          { key: 'advice', label: <span><BulbOutlined /> 每日建议</span>, children: <AdviceTab cycleId={selectedCycle} /> },
          { key: 'report', label: <span><FileTextOutlined /> 报告</span>, children: <ReportTab cycles={cycles} selectedCycle={selectedCycle} setSelectedCycle={setSelectedCycle} /> },
          { key: 'history', label: <span><HistoryOutlined /> 历史</span>, children: <HistoryTab cycleId={selectedCycle} /> },
        ]}
      />
    </PageShell>
  );
}

/* ── 聊天气泡组件 ── */
function ChatBubble({ role, content, pendingAction, onAction }: { role: string; content: string; pendingAction?: PendingAction | null; onAction?: (action: string) => void }) {
  const isUser = role === 'user';
  return (
    <div style={{ marginBottom: 16, display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
      {!isUser && (
        <div style={{
          width: 32, height: 32, borderRadius: '50%', background: palette.accentFill,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontSize: 14, fontWeight: 700, marginRight: 10, flexShrink: 0,
        }}>AI</div>
      )}
      <div style={{
        background: isUser ? USER_BG : AI_BG,
        color: isUser ? '#ffffff' : TEXT,
        padding: '10px 16px',
        borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
        maxWidth: '70%',
        wordBreak: 'break-word',
      }}>
        {isUser ? content : <MarkdownContent content={content} style={{ color: TEXT, lineHeight: 1.7, fontSize: 14 }} />}
        {!isUser && pendingAction?.context && (
          <div style={{ marginTop: 8, padding: '8px 10px', background: palette.bgSoft, borderRadius: 8, fontSize: 13, color: palette.textMuted }}>
            {pendingAction.context.original_input && (
              <div style={{ marginBottom: 4 }}>📝 理解：您说的是「{pendingAction.context.original_input}」</div>
            )}
            {pendingAction.context.notes?.map((note, i) => (
              <div key={i} style={{ marginBottom: i < pendingAction.context!.notes.length - 1 ? 4 : 0 }}>{note}</div>
            ))}
          </div>
        )}
        {!isUser && pendingAction && onAction && (
          <div style={{ display: 'flex', gap: 8, marginTop: 10, justifyContent: 'flex-end' }}>
            <Button size="small" type="primary" onClick={() => onAction('确认')}>确认</Button>
            <Button size="small" onClick={() => onAction('取消')}>取消</Button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── 对话 Tab ── */
function ChatTab({ cycles, selectedCycle, setSelectedCycle }: { cycles: CropCycleListItem[]; selectedCycle?: number; setSelectedCycle: (v?: number) => void }) {
  const [sessionId, setSessionId] = useState<string>(generateSessionId);
  const [temporary, setTemporary] = useState(() => new URLSearchParams(window.location.search).get('temporary') === '1');
  const [preferences, setPreferences] = useState<PersonalizationSettings | null>(null);
  useEffect(() => { if (!temporary) void personalizationApi.getSettings().then(setPreferences).catch(() => setPreferences(null)); }, [temporary]);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<{ role: string; content: string; pendingAction?: PendingAction | null }[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    setTimeout(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }), 50);
  };

  const handleSend = async (overrideInput?: string) => {
    const userMsg = overrideInput ?? input;
    if (!userMsg.trim()) return;
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);
    setLoading(true);
    setProgress([]);
    scrollToBottom();
    try {
      let idx = -1;
      setMessages((prev) => { idx = prev.length - 1; return prev; });
      for await (const chunk of streamChat(userMsg, sessionId, undefined, { temporary })) {
        if (chunk.type === 'progress' && chunk.data.message) {
          setProgress((items) => [...items.slice(-19), chunk.data.message!]);
        } else if (chunk.type === 'tool_started') {
          setProgress((items) => [...items.slice(-19), `正在执行：${chunk.data.tool_name}`]);
        } else if (chunk.type === 'tool_finished') {
          setProgress((items) => [...items.slice(-19), chunk.data.error ? '操作未完成，请查看回复' : '操作已完成']);
        } else if (chunk.type === 'content') {
          setMessages((prev) => {
            const next = [...prev];
            next[idx] = { ...next[idx], content: next[idx].content + chunk.data };
            return next;
          });
        } else if (chunk.type === 'pending_action') {
          setMessages((prev) => {
            const next = [...prev];
            next[idx] = { ...next[idx], pendingAction: chunk.data };
            return next;
          });
        }
        scrollToBottom();
      }
    } catch {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { role: 'assistant', content: '对话失败，请重试' };
        return next;
      });
    } finally {
      setLoading(false);
    }
  };

  const handleApproval = async (messageIndex: number, action: string) => {
    const pendingAction = messages[messageIndex]?.pendingAction;
    if (!pendingAction?.action_id) {
      message.error('当前审批上下文已失效，请重新发起请求');
      return;
    }
    try {
      await approveTurn(pendingAction.action_id, action === '确认', action === '确认' ? '用户确认' : '用户取消');
    } catch {
      message.error('审批提交失败，请重试');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'clamp(360px, calc(100dvh - 260px), 760px)' }}>
      <div style={{ marginBottom: 12 }}>
        <Space style={{ marginRight: 16 }}><Switch aria-label="临时对话" checked={temporary} disabled={loading} onChange={(value) => { setTemporary(value); setSessionId(generateSessionId()); setMessages([]); }} />临时对话</Space>
        <Select placeholder="关联茬口（可选）" allowClear style={{ width: 220 }}
          value={selectedCycle} onChange={setSelectedCycle}
          options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
      </div>

      {/* 消息区域 */}
      <div ref={scrollRef} style={{
        flex: 1, overflow: 'auto', background: BG, borderRadius: 12,
        border: `1px solid ${BORDER}`, padding: 20, marginBottom: 12,
      }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: TEXT_DIM, padding: '60px 0' }}>
            <div style={{ fontSize: 40, marginBottom: 16 }}>🌾</div>
            <div style={{ fontSize: 16, marginBottom: 8 }}>{temporary ? "临时对话" : `你好，我是${preferences?.assistant_name || "农业技术顾问"}`}</div>
            <div style={{ fontSize: 13 }}>可以问我天气、种植周期、农事记录、成本收支等问题</div>
          </div>
        )}
        {messages.map((m, i) => (
          <ChatBubble
            key={i}
            role={m.role}
            content={m.content}
            pendingAction={m.pendingAction}
            onAction={(action) => { void handleApproval(i, action); }}
          />
        ))}
        {!temporary && preferences?.execution_detail_level === 'detailed' && progress.length > 0 && <details open={loading} style={{ color: TEXT_DIM, marginBottom: 12 }}><summary>执行过程</summary>{progress.map((item, index) => <div key={index}>{item}</div>)}</details>}
        {loading && messages[messages.length - 1]?.content === '' && (
          <div style={{ display: 'flex', alignItems: 'center', color: TEXT_DIM, padding: '0 42px' }}>
            <span className="ant-spin-dot" style={{ marginRight: 8 }} />
            {(temporary || preferences?.loading_greeting_enabled !== false) ? "正在为你整理，请稍候…" : "处理中…"}
          </div>
        )}
      </div>

      {/* 输入区域 */}
      <Space.Compact style={{ width: '100%' }}>
        <Input size="large" value={input} onChange={(e) => setInput(e.target.value)}
          onPressEnter={() => handleSend()} placeholder="输入你的问题..."
          style={{ background: CARD, borderColor: BORDER, color: TEXT }} />
        <Button size="large" type="primary" icon={<SendOutlined />} onClick={() => handleSend()}
          loading={loading} style={{ height: 40 }}>发送</Button>
      </Space.Compact>
    </div>
  );
}

/* agri_backend_v2 当前只提供 Agent 对话和审批流；每日建议、报告、历史接口尚未纳入 agri_backend_v2。 */
function V2Unavailable({ title }: { title: string }) {
  return (
    <div style={{ minHeight: 320, display: 'grid', placeItems: 'center', color: TEXT_DIM }}>
      <Typography.Text style={{ color: TEXT_DIM }}>{title}暂未接入 v2 Agent 接口</Typography.Text>
    </div>
  );
}

export function AdviceTab(props: { cycleId?: number }) {
  void props;
  return <V2Unavailable title="每日建议" />;
}

function ReportTab(props: { cycles: CropCycleListItem[]; selectedCycle?: number; setSelectedCycle: (v?: number) => void }) {
  void props;
  return <V2Unavailable title="报告" />;
}

function HistoryTab(props: { cycleId?: number }) {
  void props;
  return <V2Unavailable title="历史记录" />;
}
