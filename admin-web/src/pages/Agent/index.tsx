import { useState, useEffect, useRef } from 'react';
import { Tabs, Input, Button, Select, Space, message, Typography } from 'antd';
import { SendOutlined, BulbOutlined, FileTextOutlined, HistoryOutlined, ReloadOutlined } from '@ant-design/icons';
import {
  streamChat,
  getDailyAdvice,
  refreshDailyAdvice,
  generateReport,
  getAdviceHistory,
  getReportHistory,
  type AdviceHistoryItem,
  type PendingAction,
  type ReportHistoryItem,
} from '../../api/agent';
import { listCycles, type CropCycleListItem } from '../../api/cycles';
import { MarkdownContent } from '../../components/MarkdownContent';

const BG = '#0d1117';
const CARD = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const ACCENT = '#58a6ff';
const USER_BG = '#1f6feb';
const AI_BG = '#21262d';

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
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Tabs
        style={{ flex: 1 }}
        items={[
          { key: 'chat', label: <span><SendOutlined /> 对话</span>, children: <ChatTab cycles={cycles} selectedCycle={selectedCycle} setSelectedCycle={setSelectedCycle} /> },
          { key: 'advice', label: <span><BulbOutlined /> 每日建议</span>, children: <AdviceTab cycleId={selectedCycle} /> },
          { key: 'report', label: <span><FileTextOutlined /> 报告</span>, children: <ReportTab cycles={cycles} selectedCycle={selectedCycle} setSelectedCycle={setSelectedCycle} /> },
          { key: 'history', label: <span><HistoryOutlined /> 历史</span>, children: <HistoryTab cycleId={selectedCycle} /> },
        ]}
      />
    </div>
  );
}

/* ── 聊天气泡组件 ── */
function ChatBubble({ role, content, pendingAction, onAction }: { role: string; content: string; pendingAction?: PendingAction | null; onAction?: (action: string) => void }) {
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
        {isUser ? content : <MarkdownContent content={content} style={{ color: TEXT, lineHeight: 1.7, fontSize: 14 }} />}
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
  const [sessionId] = useState<string>(generateSessionId);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<{ role: string; content: string; pendingAction?: PendingAction | null }[]>([]);
  const [loading, setLoading] = useState(false);
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
    scrollToBottom();
    try {
      let idx = -1;
      setMessages((prev) => { idx = prev.length - 1; return prev; });
      for await (const chunk of streamChat(userMsg, selectedCycle, sessionId)) {
        if (chunk.type === 'content') {
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 180px)' }}>
      <div style={{ marginBottom: 12 }}>
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
            <div style={{ fontSize: 16, marginBottom: 8 }}>你好，我是农业技术顾问</div>
            <div style={{ fontSize: 13 }}>可以问我天气、种植周期、农事记录、成本收支等问题</div>
          </div>
        )}
        {messages.map((m, i) => (
          <ChatBubble
            key={i}
            role={m.role}
            content={m.content}
            pendingAction={m.pendingAction}
            onAction={loading ? undefined : (action) => handleSend(action)}
          />
        ))}
        {loading && messages[messages.length - 1]?.content === '' && (
          <div style={{ display: 'flex', alignItems: 'center', color: TEXT_DIM, padding: '0 42px' }}>
            <span className="ant-spin-dot" style={{ marginRight: 8 }} />
            AI 正在思考中...
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

/* ── 每日建议 Tab ── */
export function AdviceTab({ cycleId }: { cycleId?: number }) {
  const [advice, setAdvice] = useState('');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [fetched, setFetched] = useState(false);

  const fetchAdvice = async () => {
    setLoading(true);
    setFetched(true);
    try {
      const res = await getDailyAdvice(cycleId);
      setAdvice(res.advice);
    } catch {
      message.error('获取建议失败，请确认后端服务正常运行');
      setFetched(false);
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshAdvice = async () => {
    setRefreshing(true);
    setFetched(true);
    try {
      const res = await refreshDailyAdvice(cycleId);
      setAdvice(res.advice);
      message.success('已重新获取今日建议');
    } catch {
      message.error('重新获取建议失败，请确认后端服务正常运行');
    } finally {
      setRefreshing(false);
    }
  };

  const busy = loading || refreshing;
  const handlePrimaryAdviceClick = fetched ? handleRefreshAdvice : fetchAdvice;

  return (
    <div style={{ height: 'calc(100vh - 220px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
        <Button type="primary" icon={<BulbOutlined />} onClick={handlePrimaryAdviceClick} loading={busy} size="large">
          {fetched ? '刷新建议' : '获取今日建议'}
        </Button>
        {busy && <span style={{ color: TEXT_DIM }}>AI 正在分析天气和种植数据，请稍候...</span>}
      </div>

      <div style={{
        flex: 1, overflow: 'auto', background: CARD, borderRadius: 12,
        border: `1px solid ${BORDER}`, padding: 24,
      }}>
        {!fetched && !loading ? (
          <div style={{ textAlign: 'center', color: TEXT_DIM, padding: '80px 0' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>☀️</div>
            <div style={{ fontSize: 16, marginBottom: 8 }}>点击上方按钮获取今日农事建议</div>
            <div style={{ fontSize: 13 }}>AI 将结合天气预报和种植周期给出具体建议</div>
          </div>
        ) : advice ? (
          <MarkdownContent content={advice} style={{ color: TEXT, lineHeight: 1.7, fontSize: 14 }} />
        ) : null}
      </div>
    </div>
  );
}

/* ── 报告生成 Tab ── */
function ReportTab({ cycles, selectedCycle, setSelectedCycle }: { cycles: CropCycleListItem[]; selectedCycle?: number; setSelectedCycle: (v?: number) => void }) {
  const [report, setReport] = useState('');
  const [loading, setLoading] = useState(false);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const res = await generateReport('weekly', selectedCycle);
      setReport(res.content);
    } catch {
      message.error('生成报告失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ height: 'calc(100vh - 220px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
        <Select placeholder="关联茬口（可选）" allowClear style={{ width: 220 }}
          value={selectedCycle} onChange={setSelectedCycle}
          options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
        <Button type="primary" icon={<FileTextOutlined />} onClick={handleGenerate} loading={loading}>
          生成周报
        </Button>
        {loading && <span style={{ color: TEXT_DIM }}>AI 正在生成报告...</span>}
      </div>

      <div style={{
        flex: 1, overflow: 'auto', background: CARD, borderRadius: 12,
        border: `1px solid ${BORDER}`, padding: 24,
      }}>
        {report ? <MarkdownContent content={report} style={{ color: TEXT, lineHeight: 1.7, fontSize: 14 }} /> : (
          <div style={{ textAlign: 'center', color: TEXT_DIM, padding: '80px 0' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>📊</div>
            <div style={{ fontSize: 16, marginBottom: 8 }}>选择茬口后点击生成周报</div>
            <div style={{ fontSize: 13 }}>AI 将汇总种植周期数据生成分析报告</div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── 历史记录条目（可展开） ── */
function HistoryItem({
  item,
  icon,
}: {
  item: AdviceHistoryItem | ReportHistoryItem;
  icon: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const itemType =
    'advice_type' in item
      ? item.advice_type === 'daily'
        ? '每日建议'
        : item.advice_type === 'chat'
          ? '对话'
          : item.advice_type
      : item.report_type === 'weekly'
        ? '周报'
        : '月报';

  return (
    <div style={{
      background: CARD, borderRadius: 8, border: `1px solid ${BORDER}`,
      marginBottom: 8, overflow: 'hidden',
    }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: '12px 16px', cursor: 'pointer', display: 'flex',
          justifyContent: 'space-between', alignItems: 'center',
        }}
      >
        <span style={{ color: TEXT }}>
          {icon} {itemType}
          {' · '}
          <span style={{ color: TEXT_DIM }}>{new Date(item.created_at).toLocaleString('zh-CN')}</span>
        </span>
        <span style={{ color: TEXT_DIM, fontSize: 12 }}>{expanded ? '收起 ▲' : '展开 ▼'}</span>
      </div>
      {expanded && (
        <div style={{
          padding: '0 16px 16px', borderTop: `1px solid ${BORDER}`,
          maxHeight: 400, overflow: 'auto',
        }}>
          <MarkdownContent content={item.content} style={{ color: TEXT, lineHeight: 1.7, fontSize: 14 }} />
        </div>
      )}
    </div>
  );
}

/* ── 历史记录 Tab ── */
function HistoryTab({ cycleId }: { cycleId?: number }) {
  const [adviceHistory, setAdviceHistory] = useState<AdviceHistoryItem[]>([]);
  const [reportHistory, setReportHistory] = useState<ReportHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [a, r] = await Promise.all([
        getAdviceHistory({ cycle_id: cycleId, limit: 10 }).catch(() => ([])),
        getReportHistory({ cycle_id: cycleId, limit: 10 }).catch(() => ({ items: [], total: 0 })),
      ]);
      setAdviceHistory(a);
      setReportHistory(r.items);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [cycleId]);

  return (
    <div style={{
      height: 'calc(100vh - 220px)', display: 'flex', flexDirection: 'column', color: TEXT,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ color: TEXT, margin: 0 }}>
          <HistoryOutlined style={{ marginRight: 8 }} />历史记录
        </Typography.Title>
        <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading} size="small">刷新</Button>
      </div>

      <div style={{ flex: 1, overflow: 'auto', paddingRight: 4 }}>
        <Typography.Title level={5} style={{ color: ACCENT }}>
          <BulbOutlined style={{ marginRight: 8 }} />建议记录 ({adviceHistory.length})
        </Typography.Title>
        {adviceHistory.length === 0 ? (
          <div style={{ color: TEXT_DIM, padding: '20px 0', textAlign: 'center' }}>暂无建议记录</div>
        ) : adviceHistory.map((item) => <HistoryItem key={item.id} item={item} icon="💡" />)}

        <Typography.Title level={5} style={{ color: ACCENT, marginTop: 24 }}>
          <FileTextOutlined style={{ marginRight: 8 }} />报告记录 ({reportHistory.length})
        </Typography.Title>
        {reportHistory.length === 0 ? (
          <div style={{ color: TEXT_DIM, padding: '20px 0', textAlign: 'center' }}>暂无报告记录</div>
        ) : reportHistory.map((item) => <HistoryItem key={item.id} item={item} icon="📊" />)}
      </div>
    </div>
  );
}
