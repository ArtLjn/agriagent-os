import { useEffect, useMemo, useState } from 'react';
import { Button, Card, Empty, Progress, Row, Col, Select, Segmented, Space, Statistic, Table, Tag } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { Bar } from '@ant-design/charts';
import {
  getTokenSummary,
  getDailyTokenStats,
  type TokenSummary,
  type DailyTokenItem,
} from '../../api/admin';
import { usersApi, type UserListItem, type UserQuotaStatus } from '../../api/users';

const BG = '#0d1117';
const CARD_BG = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const TEXT_SOFT = '#c9d1d9';
const GREEN = '#238636';

const formatNumber = (value: number) => value.toLocaleString();

const formatTime = (value: Date | null) => {
  if (!value) return '-';
  return value.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

const fieldLabelStyle = {
  color: TEXT_DIM,
  fontSize: 13,
  marginBottom: 8,
} as const;

const panelStyle = {
  background: CARD_BG,
  borderColor: BORDER,
} as const;

export default function TokenDashboard() {
  const [days, setDays] = useState<number>(7);
  const [selectedUserId, setSelectedUserId] = useState<string | undefined>();
  const [selectedModel, setSelectedModel] = useState<string | undefined>();
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [userQuota, setUserQuota] = useState<UserQuotaStatus | null>(null);
  const [summary, setSummary] = useState<TokenSummary | null>(null);
  const [dailyItems, setDailyItems] = useState<DailyTokenItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [quotaLoading, setQuotaLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastLoadedAt, setLastLoadedAt] = useState<Date | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);

  const todayStr = useMemo(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }, []);

  useEffect(() => {
    let cancelled = false;
    usersApi.list({ page: 1, size: 100 })
      .then((res) => {
        if (cancelled) return;
        setUsers(res.data.items);
      })
      .catch(() => {
        if (cancelled) return;
        setUsers([]);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const params = { days, user_id: selectedUserId };
    void Promise.resolve().then(() => {
      setLoading(true);
      setLoadFailed(false);
      return Promise.all([
        getTokenSummary(params),
        getDailyTokenStats(todayStr, { user_id: selectedUserId }),
      ])
        .then(([sum, daily]) => {
          if (cancelled) return;
          setSummary(sum);
          setDailyItems(daily.items);
          setLastLoadedAt(new Date());
        })
        .catch(() => {
          if (cancelled) return;
          setLoadFailed(true);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    });
    return () => { cancelled = true; };
  }, [days, selectedUserId, todayStr, refreshKey]);

  useEffect(() => {
    let cancelled = false;
    if (!selectedUserId) {
      void Promise.resolve().then(() => setUserQuota(null));
      return () => { cancelled = true; };
    }

    void Promise.resolve().then(() => {
      setQuotaLoading(true);
      return usersApi.getQuota(selectedUserId)
        .then((res) => {
          if (cancelled) return;
          setUserQuota(res.data);
        })
        .catch(() => {
          if (cancelled) return;
          setUserQuota(null);
        })
        .finally(() => setQuotaLoading(false));
    });

    return () => { cancelled = true; };
  }, [selectedUserId]);

  const todayUsage = useMemo(
    () => dailyItems
      .filter((item) => !selectedModel || item.model === selectedModel)
      .reduce((sum, i) => sum + i.total_tokens, 0),
    [dailyItems, selectedModel]
  );

  const getQuotaPercent = (usage?: number, limit?: number) => {
    if (!usage || !limit) return 0;
    return Math.min(100, Math.round((usage / limit) * 100));
  };

  const getQuotaStatus = (percent: number) => {
    if (percent >= 100) return 'exception';
    if (percent >= 80) return 'exception';
    if (percent >= 60) return 'active';
    return 'success';
  };

  const monthlyPercent = getQuotaPercent(userQuota?.monthly_usage, userQuota?.monthly_limit);
  const weeklyPercent = getQuotaPercent(userQuota?.weekly_usage, userQuota?.weekly_limit);

  const modelStats = useMemo(() => {
    if (!summary) return [];
    return Object.values(summary.by_model)
      .filter((m) => !selectedModel || m.model === selectedModel)
      .sort((a, b) => b.total_tokens - a.total_tokens);
  }, [summary, selectedModel]);

  const modelOptions = useMemo(() => {
    if (!summary) return [];
    return Object.values(summary.by_model)
      .map((m) => m.model)
      .filter((model, index, arr) => arr.indexOf(model) === index)
      .sort()
      .map((model) => ({ label: model, value: model }));
  }, [summary]);

  const displayTotalTokens = useMemo(
    () => modelStats.reduce((sum, item) => sum + item.total_tokens, 0),
    [modelStats]
  );

  const displayTotalRequests = useMemo(
    () => modelStats.reduce((sum, item) => sum + item.request_count, 0),
    [modelStats]
  );

  const filteredDailyItems = useMemo(
    () => dailyItems.filter((item) => !selectedModel || item.model === selectedModel),
    [dailyItems, selectedModel]
  );

  const modelRankData = useMemo(
    () => modelStats.map((m) => ({
      model: m.model,
      tokens: m.total_tokens,
    })),
    [modelStats]
  );

  const barData = useMemo(() => {
    const out: { model: string; type: string; value: number }[] = [];
    modelStats.forEach((m) => {
      out.push({ model: m.model, type: 'Prompt', value: m.prompt_tokens });
      out.push({ model: m.model, type: 'Completion', value: m.completion_tokens });
    });
    return out;
  }, [modelStats]);

  const modelRankConfig = {
    data: modelRankData,
    xField: 'model',
    yField: 'tokens',
    height: 260,
    theme: 'dark',
    color: '#58a6ff',
    label: {
      text: 'tokens',
      style: { fill: TEXT_SOFT },
    },
    axis: {
      x: { labelFormatter: (value: number) => formatNumber(value) },
    },
  };

  const usageMixConfig = {
    data: barData,
    xField: 'value',
    yField: 'model',
    seriesField: 'type',
    stack: true,
    height: 260,
    theme: 'dark',
    color: ['#58a6ff', GREEN],
    axis: {
      x: { labelFormatter: (value: number) => formatNumber(value) },
    },
  };

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId),
    [users, selectedUserId]
  );

  const loadedText = loadFailed ? '加载失败' : loading ? '加载中' : '已加载';

  const refresh = () => setRefreshKey((key) => key + 1);

  const emptyChart = (description: string) => (
    <Empty
      description={<span style={{ color: TEXT_DIM }}>{description}</span>}
      image={Empty.PRESENTED_IMAGE_SIMPLE}
      style={{ margin: '48px 0' }}
    />
  );

  const quotaEmptyText = selectedUserId
    ? '该用户暂无配额数据'
    : '请选择用户查看个人配额';

  const tableLocale = {
    emptyText: (
      <Empty
        description={<span style={{ color: TEXT_DIM }}>今日暂无 Token 入账记录</span>}
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    ),
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
      <div style={{ marginBottom: 18 }}>
        <Space align="center" size={12} wrap>
          <h2 style={{ color: TEXT, margin: 0 }}>Token 监控看板</h2>
          <Tag color={loadFailed ? 'error' : 'success'}>{loadedText}</Tag>
          <span style={{ color: TEXT_DIM, fontSize: 13 }}>最后刷新：{formatTime(lastLoadedAt)}</span>
        </Space>
        <div style={{ color: TEXT_DIM, fontSize: 13, marginTop: 8 }}>
          数据来源：真实 provider usage 入账；汇总为近 {days} 天，今日明细为 {todayStr}
          {selectedUser ? `，当前用户：${selectedUser.nickname || selectedUser.phone}` : '，当前范围：全部用户'}
          {selectedModel ? `，模型：${selectedModel}` : ''}
        </div>
      </div>

      <Card style={{ ...panelStyle, marginBottom: 16 }} bodyStyle={{ padding: 16 }}>
        <Row gutter={[14, 14]} align="bottom">
          <Col xs={24} sm={12} xl={5}>
            <div style={fieldLabelStyle}>用户</div>
            <Select
              allowClear
              showSearch
              placeholder="全部用户"
              style={{ width: '100%' }}
              value={selectedUserId}
              optionFilterProp="label"
              onChange={(value) => setSelectedUserId(value)}
              options={users.map((user) => ({
                label: `${user.nickname || '未命名'} / ${user.phone}`,
                value: user.id,
              }))}
            />
          </Col>
          <Col xs={24} sm={12} xl={5}>
            <div style={fieldLabelStyle}>模型</div>
            <Select
              allowClear
              showSearch
              placeholder="全部模型"
              style={{ width: '100%' }}
              value={selectedModel}
              optionFilterProp="label"
              onChange={(value) => setSelectedModel(value)}
              options={modelOptions}
            />
          </Col>
          <Col xs={24} md={8} xl={5}>
            <div style={fieldLabelStyle}>汇总范围</div>
            <Segmented
              block
              options={[
                { label: '近 7 天', value: 7 },
                { label: '近 30 天', value: 30 },
              ]}
              value={days}
              onChange={(v) => setDays(v as number)}
              style={{ background: BG }}
            />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <Button block onClick={() => setDays(1)}>
              当日
            </Button>
          </Col>
          <Col xs={12} md={8} xl={5}>
            <Button block type="primary" icon={<ReloadOutlined />} loading={loading} onClick={refresh}>
              刷新
            </Button>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card style={panelStyle} loading={loading}>
            <Statistic
              title={<span style={{ color: TEXT_DIM }}>近 {days} 天 Tokens</span>}
              value={displayTotalTokens}
              valueStyle={{ color: TEXT }}
            />
            <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 8 }}>按当前用户和模型筛选后统计</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={panelStyle} loading={loading}>
            <Statistic
              title={<span style={{ color: TEXT_DIM }}>近 {days} 天请求数</span>}
              value={displayTotalRequests}
              valueStyle={{ color: TEXT }}
            />
            <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 8 }}>请求数来自 token 统计聚合</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={panelStyle} loading={loading || quotaLoading}>
            <Statistic
              title={<span style={{ color: TEXT_DIM }}>今日 Tokens</span>}
              value={todayUsage}
              valueStyle={{ color: TEXT }}
            />
            <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 8 }}>{todayStr} 的入账记录</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={panelStyle} loading={quotaLoading}>
            <div style={{ color: TEXT_DIM, fontSize: 14, marginBottom: 8 }}>月配额使用</div>
            {selectedUserId && userQuota ? (
              <>
                <Progress percent={monthlyPercent} status={getQuotaStatus(monthlyPercent)} />
                <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 4 }}>
                  {userQuota.monthly_usage.toLocaleString()} / {userQuota.monthly_limit.toLocaleString()}
                </div>
              </>
            ) : (
              <div style={{ color: TEXT_DIM, fontSize: 13 }}>{quotaEmptyText}</div>
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={panelStyle} loading={quotaLoading}>
            <div style={{ color: TEXT_DIM, fontSize: 14, marginBottom: 8 }}>周配额使用</div>
            {selectedUserId && userQuota ? (
              <>
                <Progress percent={weeklyPercent} status={getQuotaStatus(weeklyPercent)} />
                <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 4 }}>
                  {userQuota.weekly_usage.toLocaleString()} / {userQuota.weekly_limit.toLocaleString()}
                </div>
              </>
            ) : (
              <div style={{ color: TEXT_DIM, fontSize: 13 }}>{quotaEmptyText}</div>
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <Card
            title={<span style={{ color: TEXT }}>模型用量排行</span>}
            extra={<span style={{ color: TEXT_DIM, fontSize: 12 }}>非时间趋势，按模型聚合</span>}
            style={panelStyle}
            bodyStyle={{ padding: 12 }}
          >
            {modelRankData.length > 0 ? <Bar {...modelRankConfig} /> : emptyChart('当前筛选下暂无模型用量')}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            title={<span style={{ color: TEXT }}>Prompt / Completion 分布</span>}
            extra={<span style={{ color: TEXT_DIM, fontSize: 12 }}>堆叠展示真实 token 构成</span>}
            style={panelStyle}
            bodyStyle={{ padding: 12 }}
          >
            {barData.length > 0 ? <Bar {...usageMixConfig} /> : emptyChart('当前筛选下暂无 Prompt / Completion 数据')}
          </Card>
        </Col>
      </Row>

      <Card
        title={<span style={{ color: TEXT }}>今日明细</span>}
        extra={<span style={{ color: TEXT_DIM, fontSize: 12 }}>预估费用不是账单金额</span>}
        style={panelStyle}
      >
        <Table
          dataSource={filteredDailyItems}
          columns={columns}
          rowKey={(record, index) => `${record.model}-${record.call_type}-${index}`}
          pagination={false}
          loading={loading}
          locale={tableLocale}
          style={{ background: CARD_BG }}
        />
      </Card>
    </div>
  );
}
