import { useState, useEffect } from 'react';
import { Tabs, Input, Button, Card, List, Select, Space, Spin, message } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { chat, getDailyAdvice, generateReport, getAdviceHistory, getReportHistory } from '../../api/agent';
import { listCycles, type CropCycleListItem } from '../../api/cycles';

export default function Agent() {
  const [cycles, setCycles] = useState<CropCycleListItem[]>([]);
  const [selectedCycle, setSelectedCycle] = useState<number | undefined>();

  useEffect(() => {
    listCycles().then((res) => setCycles(res.data)).catch(() => {});
  }, []);

  return (
    <Tabs items={[
      { key: 'chat', label: '对话', children: <ChatTab cycles={cycles} selectedCycle={selectedCycle} setSelectedCycle={setSelectedCycle} /> },
      { key: 'advice', label: '每日建议', children: <AdviceTab cycleId={selectedCycle} /> },
      { key: 'report', label: '报告生成', children: <ReportTab cycles={cycles} selectedCycle={selectedCycle} setSelectedCycle={setSelectedCycle} /> },
      { key: 'history', label: '历史记录', children: <HistoryTab cycleId={selectedCycle} /> },
    ]} />
  );
}

function ChatTab({ cycles, selectedCycle, setSelectedCycle }: { cycles: CropCycleListItem[]; selectedCycle?: number; setSelectedCycle: (v?: number) => void }) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { role: 'user', content: input }]);
    setLoading(true);
    try {
      const res = await chat(input, selectedCycle);
      setMessages((prev) => [...prev, { role: 'assistant', content: res.data.reply }]);
      setInput('');
    } catch {
      message.error('对话失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Select placeholder="关联茬口" allowClear style={{ width: 200, marginBottom: 12 }} value={selectedCycle}
        onChange={setSelectedCycle} options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
      <Card style={{ height: 400, overflow: 'auto', marginBottom: 12 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 8, textAlign: m.role === 'user' ? 'right' : 'left' }}>
            <span style={{ background: m.role === 'user' ? '#e6f7ff' : '#f0f0f0', padding: '4px 12px', borderRadius: 8, display: 'inline-block' }}>
              {m.content}
            </span>
          </div>
        ))}
        {loading && <Spin />}
      </Card>
      <Space.Compact style={{ width: '100%' }}>
        <Input value={input} onChange={(e) => setInput(e.target.value)} onPressEnter={handleSend} placeholder="输入消息..." />
        <Button type="primary" icon={<SendOutlined />} onClick={handleSend} loading={loading}>发送</Button>
      </Space.Compact>
    </div>
  );
}

function AdviceTab({ cycleId }: { cycleId?: number }) {
  const [advice, setAdvice] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchAdvice = async () => {
    setLoading(true);
    try {
      const res = await getDailyAdvice(cycleId);
      setAdvice(res.data.advice);
    } catch {
      message.error('获取建议失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Button onClick={fetchAdvice} loading={loading} style={{ marginBottom: 12 }}>获取今日建议</Button>
      <Card>{advice || '点击按钮获取建议'}</Card>
    </div>
  );
}

function ReportTab({ cycles, selectedCycle, setSelectedCycle }: { cycles: CropCycleListItem[]; selectedCycle?: number; setSelectedCycle: (v?: number) => void }) {
  const [report, setReport] = useState('');
  const [loading, setLoading] = useState(false);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const res = await generateReport('weekly', selectedCycle);
      setReport(res.data.content);
    } catch {
      message.error('生成报告失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Select placeholder="关联茬口" allowClear style={{ width: 200 }} value={selectedCycle}
          onChange={setSelectedCycle} options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
        <Button type="primary" onClick={handleGenerate} loading={loading}>生成周报</Button>
      </Space>
      <Card><pre style={{ whiteSpace: 'pre-wrap' }}>{report || '点击按钮生成报告'}</pre></Card>
    </div>
  );
}

function HistoryTab({ cycleId }: { cycleId?: number }) {
  const [adviceHistory, setAdviceHistory] = useState<any[]>([]);
  const [reportHistory, setReportHistory] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      getAdviceHistory({ cycle_id: cycleId, limit: 10 }).catch(() => ({ data: [] })),
      getReportHistory({ cycle_id: cycleId, limit: 10 }).catch(() => ({ data: [] })),
    ]).then(([a, r]) => {
      setAdviceHistory(a.data);
      setReportHistory(r.data);
    });
  }, [cycleId]);

  return (
    <div>
      <h4>建议历史</h4>
      <List size="small" dataSource={adviceHistory} renderItem={(item) => (
        <List.Item><List.Item.Meta title={`${item.advice_type} - ${item.created_at}`} description={item.content?.slice(0, 100)} /></List.Item>
      )} />
      <h4 style={{ marginTop: 16 }}>报告历史</h4>
      <List size="small" dataSource={reportHistory} renderItem={(item) => (
        <List.Item><List.Item.Meta title={`${item.report_type} - ${item.created_at}`} description={item.content?.slice(0, 100)} /></List.Item>
      )} />
    </div>
  );
}
