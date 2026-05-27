import { useEffect, useMemo, useState } from 'react';
import { Card, Segmented, Statistic, Table, Progress, Row, Col } from 'antd';
import { Line, Bar } from '@ant-design/charts';
import {
  getTokenSummary,
  getDailyTokenStats,
  type TokenSummary,
  type DailyTokenItem,
} from '../../api/admin';

const BG = '#0d1117';
const CARD_BG = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';

const QUOTA_LIMIT = 10000;

export default function TokenDashboard() {
  const [days, setDays] = useState<number>(7);
  const [summary, setSummary] = useState<TokenSummary | null>(null);
  const [dailyItems, setDailyItems] = useState<DailyTokenItem[]>([]);
  const [loading, setLoading] = useState(false);

  const todayStr = useMemo(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([getTokenSummary(days), getDailyTokenStats(todayStr)])
      .then(([sum, daily]) => {
        if (cancelled) return;
        setSummary(sum);
        setDailyItems(daily.items);
      })
      .finally(() => setLoading(false));
    return () => { cancelled = true; };
  }, [days, todayStr]);

  const todayUsage = useMemo(
    () => dailyItems.reduce((sum, i) => sum + i.total_tokens, 0),
    [dailyItems]
  );

  const quotaPercent = useMemo(
    () => Math.min(100, Math.round((todayUsage / QUOTA_LIMIT) * 100)),
    [todayUsage]
  );

  const quotaStatus = useMemo(() => {
    if (quotaPercent >= 100) return 'exception';
    if (quotaPercent >= 80) return 'warning';
    return 'success';
  }, [quotaPercent]);

  const lineData = useMemo(() => {
    if (!summary) return [];
    return Object.values(summary.by_model).map((m) => ({
      model: m.model,
      tokens: m.total_tokens,
    }));
  }, [summary]);

  const barData = useMemo(() => {
    if (!summary) return [];
    const out: { model: string; type: string; value: number }[] = [];
    Object.values(summary.by_model).forEach((m) => {
      out.push({ model: m.model, type: 'Prompt', value: m.prompt_tokens });
      out.push({ model: m.model, type: 'Completion', value: m.completion_tokens });
    });
    return out;
  }, [summary]);

  const lineConfig = {
    data: lineData,
    xField: 'model',
    yField: 'tokens',
    smooth: true,
    color: '#58a6ff',
    height: 240,
    theme: 'dark',
  };

  const barConfig = {
    data: barData,
    xField: 'model',
    yField: 'value',
    seriesField: 'type',
    group: true,
    height: 240,
    theme: 'dark',
    color: ['#58a6ff', '#238636'],
  };

  const columns = [
    { title: '模型', dataIndex: 'model', key: 'model' },
    { title: '调用类型', dataIndex: 'call_type', key: 'call_type' },
    { title: 'Prompt Tokens', dataIndex: 'prompt_tokens', key: 'prompt_tokens' },
    { title: 'Completion Tokens', dataIndex: 'completion_tokens', key: 'completion_tokens' },
    { title: 'Total Tokens', dataIndex: 'total_tokens', key: 'total_tokens' },
    { title: '请求数', dataIndex: 'request_count', key: 'request_count' },
    {
      title: '预估费用(CNY)',
      dataIndex: 'estimated_cost_cny',
      key: 'estimated_cost_cny',
      render: (v?: number) => (v !== undefined ? `¥${v.toFixed(4)}` : '-'),
    },
  ];

  return (
    <div style={{ padding: 24, background: BG, minHeight: '100vh' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ color: TEXT, margin: 0 }}>Token 用量看板</h2>
        <Segmented
          options={[
            { label: '近 7 天', value: 7 },
            { label: '近 30 天', value: 30 },
          ]}
          value={days}
          onChange={(v) => setDays(v as number)}
          style={{ background: CARD_BG }}
        />
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ background: CARD_BG, borderColor: BORDER }} loading={loading}>
            <Statistic
              title={<span style={{ color: TEXT_DIM }}>总 Tokens</span>}
              value={summary?.total_tokens ?? 0}
              valueStyle={{ color: TEXT }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ background: CARD_BG, borderColor: BORDER }} loading={loading}>
            <Statistic
              title={<span style={{ color: TEXT_DIM }}>总请求数</span>}
              value={summary?.total_requests ?? 0}
              valueStyle={{ color: TEXT }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ background: CARD_BG, borderColor: BORDER }} loading={loading}>
            <Statistic
              title={<span style={{ color: TEXT_DIM }}>今日用量</span>}
              value={todayUsage}
              valueStyle={{ color: TEXT }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ background: CARD_BG, borderColor: BORDER }} loading={loading}>
            <div style={{ color: TEXT_DIM, fontSize: 14, marginBottom: 8 }}>配额使用</div>
            <Progress percent={quotaPercent} status={quotaStatus as any} />
            <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 4 }}>
              {todayUsage} / {QUOTA_LIMIT}
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <Card
            title={<span style={{ color: TEXT }}>按模型用量趋势</span>}
            style={{ background: CARD_BG, borderColor: BORDER }}
            bodyStyle={{ padding: 12 }}
          >
            <Line {...lineConfig} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            title={<span style={{ color: TEXT }}>Prompt / Completion 分布</span>}
            style={{ background: CARD_BG, borderColor: BORDER }}
            bodyStyle={{ padding: 12 }}
          >
            <Bar {...barConfig} />
          </Card>
        </Col>
      </Row>

      <Card
        title={<span style={{ color: TEXT }}>今日明细</span>}
        style={{ background: CARD_BG, borderColor: BORDER }}
      >
        <Table
          dataSource={dailyItems}
          columns={columns}
          rowKey={(record, index) => `${record.model}-${record.call_type}-${index}`}
          pagination={false}
          loading={loading}
          style={{ background: CARD_BG }}
        />
      </Card>
    </div>
  );
}
