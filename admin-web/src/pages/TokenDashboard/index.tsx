import { useEffect, useMemo, useState } from 'react';
import { Button, Card, Empty, Progress, Row, Col, Select, Segmented, Space, Statistic, Table, Tag } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import {
  getTokenSummary,
  getDailyTokenStats,
  getHourlyTokenStats,
  type TokenSummary,
  type DailyTokenItem,
  type HourlyTokenItem,
} from '../../api/admin';
import { usersApi, type UserListItem, type UserQuotaStatus } from '../../api/users';

const BG = '#0d1117';
const CARD_BG = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const TEXT_SOFT = '#c9d1d9';
const GREEN = '#238636';
const BLUE = '#2f81f7';
const HOURS_24 = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, '0'));

type NormalizedModelStats = {
  model: string;
  call_type: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
};

type HourlyRow = {
  id: string;
  label: string;
  tokensByHour: Record<string, number>;
  total_tokens: number;
  request_count: number;
};

const toNumber = (value: unknown) => {
  const num = Number(value ?? 0);
  return Number.isFinite(num) ? num : 0;
};

const formatNumber = (value: number) => Math.round(value).toLocaleString();

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

const compactCardStyle = {
  ...panelStyle,
  minHeight: 142,
} as const;

const monoStyle = {
  color: TEXT_SOFT,
  fontVariantNumeric: 'tabular-nums',
} as const;

const truncateStyle = {
  minWidth: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
} as const;

const modelUsageColumns = 'minmax(180px, 1.2fr) minmax(220px, 2fr) minmax(240px, 2.2fr) 112px 72px';

export default function TokenDashboard() {
  const [days, setDays] = useState<number>(7);
  const [selectedUserId, setSelectedUserId] = useState<string | undefined>();
  const [selectedModel, setSelectedModel] = useState<string | undefined>();
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [userQuota, setUserQuota] = useState<UserQuotaStatus | null>(null);
  const [summary, setSummary] = useState<TokenSummary | null>(null);
  const [dailyItems, setDailyItems] = useState<DailyTokenItem[]>([]);
  const [hourlyItems, setHourlyItems] = useState<HourlyTokenItem[]>([]);
  const [hourlyHours, setHourlyHours] = useState<string[]>([]);
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
    const hourlyParams = {
      user_id: selectedUserId,
      model: selectedModel,
      start_date: todayStr,
      end_date: todayStr,
    };
    void Promise.resolve().then(() => {
      setLoading(true);
      setLoadFailed(false);
      return Promise.all([
        getTokenSummary(params),
        getDailyTokenStats(todayStr, { user_id: selectedUserId }),
        getHourlyTokenStats(hourlyParams),
      ])
        .then(([sum, daily, hourly]) => {
          if (cancelled) return;
          setSummary(sum);
          setDailyItems(daily.items);
          setHourlyItems(hourly.items);
          setHourlyHours(hourly.hours);
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
  }, [days, selectedUserId, selectedModel, todayStr, refreshKey]);

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
      .reduce((sum, i) => sum + toNumber(i.total_tokens), 0),
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

  const modelStats = useMemo<NormalizedModelStats[]>(() => {
    if (!summary) return [];
    return Object.values(summary.by_model)
      .map((m) => ({
        model: m.model,
        call_type: m.call_type,
        prompt_tokens: toNumber(m.prompt_tokens),
        completion_tokens: toNumber(m.completion_tokens),
        total_tokens: toNumber(m.total_tokens),
        request_count: toNumber(m.request_count),
      }))
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
    () => dailyItems
      .filter((item) => !selectedModel || item.model === selectedModel)
      .map((item) => ({
        ...item,
        prompt_tokens: toNumber(item.prompt_tokens),
        completion_tokens: toNumber(item.completion_tokens),
        total_tokens: toNumber(item.total_tokens),
        request_count: toNumber(item.request_count),
        estimated_cost_cny: item.estimated_cost_cny === undefined
          ? undefined
          : toNumber(item.estimated_cost_cny),
      })),
    [dailyItems, selectedModel]
  );

  const maxModelTokens = useMemo(
    () => Math.max(1, ...modelStats.map((item) => item.total_tokens)),
    [modelStats]
  );

  const visibleHours = useMemo(() => {
    return HOURS_24;
  }, []);

  const activeHoursText = useMemo(() => {
    if (hourlyHours.length === 0) return '暂无活跃小时';
    return hourlyHours.join(', ');
  }, [hourlyHours]);

  const hourlyByModel = useMemo<HourlyRow[]>(() => {
    const rows = new Map<string, HourlyRow>();
    hourlyItems.forEach((item) => {
      const row = rows.get(item.model) ?? {
        id: item.model,
        label: item.model,
        tokensByHour: {},
        total_tokens: 0,
        request_count: 0,
      };
      const tokens = toNumber(item.total_tokens);
      row.tokensByHour[item.hour] = (row.tokensByHour[item.hour] ?? 0) + tokens;
      row.total_tokens += tokens;
      row.request_count += toNumber(item.request_count);
      rows.set(item.model, row);
    });
    return Array.from(rows.values()).sort((a, b) => b.total_tokens - a.total_tokens);
  }, [hourlyItems]);

  const hourlyByUser = useMemo<HourlyRow[]>(() => {
    const rows = new Map<string, HourlyRow>();
    hourlyItems.forEach((item) => {
      const id = item.user_id || `farm-${item.farm_id}`;
      const user = users.find((candidate) => candidate.id === item.user_id);
      const label = user ? `${user.nickname || '未命名'} / ${user.phone}` : id;
      const row = rows.get(id) ?? {
        id,
        label,
        tokensByHour: {},
        total_tokens: 0,
        request_count: 0,
      };
      const tokens = toNumber(item.total_tokens);
      row.tokensByHour[item.hour] = (row.tokensByHour[item.hour] ?? 0) + tokens;
      row.total_tokens += tokens;
      row.request_count += toNumber(item.request_count);
      rows.set(id, row);
    });
    return Array.from(rows.values()).sort((a, b) => b.total_tokens - a.total_tokens);
  }, [hourlyItems, users]);

  const maxHourlyTokens = useMemo(() => {
    const values = hourlyItems.map((item) => toNumber(item.total_tokens));
    return Math.max(1, ...values);
  }, [hourlyItems]);

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId),
    [users, selectedUserId]
  );

  const loadedText = loadFailed ? '加载失败' : loading ? '加载中' : '已加载';

  const refresh = () => setRefreshKey((key) => key + 1);

  const emptyBlock = (description: string) => (
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
    {
      title: 'Prompt Tokens',
      dataIndex: 'prompt_tokens',
      key: 'prompt_tokens',
      render: (v: number) => formatNumber(toNumber(v)),
    },
    {
      title: 'Completion Tokens',
      dataIndex: 'completion_tokens',
      key: 'completion_tokens',
      render: (v: number) => formatNumber(toNumber(v)),
    },
    {
      title: 'Total Tokens',
      dataIndex: 'total_tokens',
      key: 'total_tokens',
      render: (v: number) => formatNumber(toNumber(v)),
    },
    {
      title: '请求数',
      dataIndex: 'request_count',
      key: 'request_count',
      render: (v: number) => formatNumber(toNumber(v)),
    },
    {
      title: '预估费用(CNY)',
      dataIndex: 'estimated_cost_cny',
      key: 'estimated_cost_cny',
      render: (v?: number) => (v !== undefined ? `¥${toNumber(v).toFixed(4)}` : '-'),
    },
  ];

  const renderModelUsageRows = () => {
    if (modelStats.length === 0) return emptyBlock('当前筛选下暂无模型用量');
    return (
      <div style={{ overflowX: 'auto' }}>
        <div style={{ minWidth: 920 }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: modelUsageColumns,
              gap: 16,
              alignItems: 'center',
              color: TEXT_DIM,
              fontSize: 12,
              padding: '0 0 10px',
            }}
          >
            <span>模型</span>
            <span>总量</span>
            <span>Prompt / Completion</span>
            <span style={{ textAlign: 'right' }}>Token</span>
            <span style={{ textAlign: 'right' }}>请求</span>
          </div>
          <div
            style={{
              maxHeight: 330,
              overflowY: modelStats.length > 5 ? 'auto' : 'visible',
              paddingRight: modelStats.length > 5 ? 6 : 0,
            }}
          >
            {modelStats.map((item) => {
              const totalWidth = `${Math.max(8, Math.round((item.total_tokens / maxModelTokens) * 100))}%`;
              const promptPercent = item.total_tokens > 0
                ? Math.round((item.prompt_tokens / item.total_tokens) * 100)
                : 0;
              const completionPercent = Math.max(0, 100 - promptPercent);
              return (
                <div
                  key={`${item.model}-${item.call_type}`}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: modelUsageColumns,
                    gap: 16,
                    alignItems: 'center',
                    minHeight: 62,
                    borderTop: `1px solid ${BORDER}`,
                  }}
                >
                  <div style={truncateStyle} title={`${item.model} / ${item.call_type}`}>
                    <div style={{ ...truncateStyle, color: TEXT, fontWeight: 700 }}>
                      {item.model}
                    </div>
                    <div style={{ ...truncateStyle, color: TEXT_DIM, fontSize: 12, marginTop: 3 }}>
                      {item.call_type}
                    </div>
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ height: 24, background: '#21262d', borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{ width: totalWidth, height: '100%', background: BLUE }} />
                    </div>
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: 'flex', height: 24, background: '#21262d', borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{ width: `${promptPercent}%`, background: BLUE }} />
                      <div style={{ width: `${completionPercent}%`, background: GREEN }} />
                    </div>
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
                        gap: 10,
                        color: TEXT_DIM,
                        fontSize: 12,
                        marginTop: 5,
                      }}
                    >
                      <span style={truncateStyle}>Prompt {formatNumber(item.prompt_tokens)} ({promptPercent}%)</span>
                      <span style={{ ...truncateStyle, textAlign: 'right' }}>
                        Completion {formatNumber(item.completion_tokens)} ({completionPercent}%)
                      </span>
                    </div>
                  </div>
                  <div style={{ ...monoStyle, textAlign: 'right', fontWeight: 700, overflow: 'hidden' }}>
                    {formatNumber(item.total_tokens)}
                  </div>
                  <div style={{ ...monoStyle, textAlign: 'right', overflow: 'hidden' }}>
                    {formatNumber(item.request_count)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  };

  const renderHourlyRows = (rows: HourlyRow[], emptyText: string) => {
    if (rows.length === 0) return emptyBlock(emptyText);
    return (
      <div style={{ overflowX: 'auto', paddingBottom: 2 }}>
        <div style={{ minWidth: 1280, display: 'grid', gap: 10 }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `220px repeat(${visibleHours.length}, 32px) 112px 72px`,
              gap: 6,
              alignItems: 'center',
              color: TEXT_DIM,
              fontSize: 12,
            }}
          >
            <span />
            {visibleHours.map((hour) => <span key={hour} style={{ textAlign: 'center' }}>{hour}</span>)}
            <span style={{ textAlign: 'right' }}>Token</span>
            <span style={{ textAlign: 'right' }}>请求</span>
          </div>
          {rows.map((row) => (
            <div
              key={row.id}
              style={{
                display: 'grid',
                gridTemplateColumns: `220px repeat(${visibleHours.length}, 32px) 112px 72px`,
                gap: 6,
                alignItems: 'center',
              }}
            >
              <div style={{ ...truncateStyle, color: TEXT, fontWeight: 600 }} title={row.label}>
                {row.label}
              </div>
              {visibleHours.map((hour) => {
                const value = row.tokensByHour[hour] ?? 0;
                const opacity = value > 0 ? Math.max(0.22, value / maxHourlyTokens) : 0;
                return (
                  <div
                    key={`${row.id}-${hour}`}
                    title={`${hour}:00 ${formatNumber(value)} tokens`}
                    style={{
                      height: 24,
                      borderRadius: 4,
                      background: value > 0 ? `rgba(35, 134, 54, ${opacity})` : '#21262d',
                      border: '1px solid rgba(48, 54, 61, 0.7)',
                    }}
                  />
                );
              })}
              <div style={{ ...monoStyle, textAlign: 'right' }}>{formatNumber(row.total_tokens)}</div>
              <div style={{ ...monoStyle, textAlign: 'right' }}>{formatNumber(row.request_count)}</div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div style={{ padding: '20px 24px 80px', background: BG, minHeight: '100vh' }}>
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

      <Card style={{ ...panelStyle, marginBottom: 14 }} bodyStyle={{ padding: 14 }}>
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

      <Row gutter={[14, 14]} style={{ marginBottom: 18 }}>
        <Col xs={24} sm={12} xl={5}>
          <Card style={compactCardStyle} loading={loading} bodyStyle={{ padding: 20 }}>
            <Statistic
              title={<span style={{ color: TEXT_DIM }}>近 {days} 天 Tokens</span>}
              value={displayTotalTokens}
              valueStyle={{ color: TEXT }}
            />
            <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 8 }}>按当前用户和模型筛选后统计</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={5}>
          <Card style={compactCardStyle} loading={loading} bodyStyle={{ padding: 20 }}>
            <Statistic
              title={<span style={{ color: TEXT_DIM }}>近 {days} 天请求数</span>}
              value={displayTotalRequests}
              valueStyle={{ color: TEXT }}
            />
            <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 8 }}>请求数来自 token 统计聚合</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={5}>
          <Card style={compactCardStyle} loading={loading || quotaLoading} bodyStyle={{ padding: 20 }}>
            <Statistic
              title={<span style={{ color: TEXT_DIM }}>今日 Tokens</span>}
              value={todayUsage}
              valueStyle={{ color: TEXT }}
            />
            <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 8 }}>{todayStr} 的入账记录</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={5}>
          <Card style={compactCardStyle} loading={quotaLoading} bodyStyle={{ padding: 20 }}>
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
        <Col xs={24} sm={12} xl={4}>
          <Card style={compactCardStyle} loading={quotaLoading} bodyStyle={{ padding: 20 }}>
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

      <Row gutter={[16, 16]} style={{ marginBottom: 18 }}>
        <Col xs={24}>
          <Card
            title={<span style={{ color: TEXT }}>模型用量</span>}
            extra={<span style={{ color: TEXT_DIM, fontSize: 12 }}>按模型聚合；行内展示总量和真实 token 构成</span>}
            style={panelStyle}
            bodyStyle={{ padding: 22 }}
          >
            <Space size={16} style={{ marginBottom: 18 }}>
              <Space size={6}>
                <span style={{ width: 10, height: 10, background: BLUE, borderRadius: 2, display: 'inline-block' }} />
                <span style={{ color: TEXT_DIM }}>Prompt</span>
              </Space>
              <Space size={6}>
                <span style={{ width: 10, height: 10, background: GREEN, borderRadius: 2, display: 'inline-block' }} />
                <span style={{ color: TEXT_DIM }}>Completion</span>
              </Space>
            </Space>
            {renderModelUsageRows()}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 18 }}>
        <Col xs={24}>
          <Card
            title={<span style={{ color: TEXT }}>模型 × 小时</span>}
            extra={<span style={{ color: TEXT_DIM, fontSize: 12 }}>24 小时视角；活跃小时：{activeHoursText}</span>}
            style={panelStyle}
            bodyStyle={{ padding: 20 }}
          >
            {renderHourlyRows(hourlyByModel, '今日暂无可用于小时聚合的真实 Token trace')}
          </Card>
        </Col>
        <Col xs={24}>
          <Card
            title={<span style={{ color: TEXT }}>用户 × 小时</span>}
            extra={<span style={{ color: TEXT_DIM, fontSize: 12 }}>按 farm.user_id 关联用户</span>}
            style={panelStyle}
            bodyStyle={{ padding: 20 }}
          >
            {renderHourlyRows(hourlyByUser, '今日暂无用户小时用量')}
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
