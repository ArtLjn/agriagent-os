import { useEffect, useMemo, useState } from 'react';
import { Button, Card, Progress, Row, Col, Select, Segmented, Space, Statistic, Tag } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import {
  getDailyTokenStats,
  getHourlyTokenStats,
  getTokenSummary,
  type DailyTokenItem,
  type HourlyTokenItem,
  type TokenSummary,
} from '../../api/admin';
import { usersApi, type UserListItem, type UserQuotaStatus } from '../../api/users';
import {
  ChartCard,
  HeatmapSection,
  LegendItem,
  ModelUsageRows,
  PerformanceTrendChart,
  TokenTrendChart,
} from './dashboard-ui';
import {
  AMBER,
  BG,
  BLUE,
  GREEN,
  HOURS_24,
  PURPLE,
  TEXT,
  TEXT_DIM,
  compactCardStyle,
  fieldLabelStyle,
  formatCompactNumber,
  panelStyle,
  toNumber,
  type HeatmapRow,
  type NormalizedModelStats,
  type TrendPoint,
} from './dashboard-shared';

const formatTime = (value: Date | null) => {
  if (!value) return '-';
  return value.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
};

const normalizeHeatmapRows = (rows: Map<string, HeatmapRow>) => (
  Array.from(rows.values())
    .map((row) => ({
      ...row,
      avg_tokens: row.request_count > 0 ? Math.round(row.total_tokens / row.request_count) : 0,
    }))
    .sort((a, b) => b.total_tokens - a.total_tokens)
);

type RangeMode = 'day' | 'week' | 'month';

const formatDateKey = (date: Date) => (
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
);

const addDays = (date: Date, offset: number) => {
  const next = new Date(date);
  next.setDate(next.getDate() + offset);
  return next;
};

export default function TokenDashboard() {
  const [rangeMode, setRangeMode] = useState<RangeMode>('week');
  const [selectedUserId, setSelectedUserId] = useState<string | undefined>();
  const [selectedModel, setSelectedModel] = useState<string | undefined>();
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [userQuota, setUserQuota] = useState<UserQuotaStatus | null>(null);
  const [summary, setSummary] = useState<TokenSummary | null>(null);
  const [dailyItems, setDailyItems] = useState<DailyTokenItem[]>([]);
  const [hourlyItems, setHourlyItems] = useState<HourlyTokenItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [quotaLoading, setQuotaLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastLoadedAt, setLastLoadedAt] = useState<Date | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);

  const todayStr = useMemo(() => {
    return formatDateKey(new Date());
  }, []);

  const range = useMemo(() => {
    const today = new Date();
    const start = rangeMode === 'day'
      ? today
      : rangeMode === 'week'
        ? addDays(today, -6)
        : new Date(today.getFullYear(), today.getMonth(), 1);
    const days = Math.max(1, Math.floor((today.getTime() - start.getTime()) / 86_400_000) + 1);
    return {
      mode: rangeMode,
      days,
      startDate: formatDateKey(start),
      endDate: formatDateKey(today),
      label: rangeMode === 'day' ? '当日' : rangeMode === 'week' ? '近 7 天' : '本月',
    };
  }, [rangeMode]);

  useEffect(() => {
    let cancelled = false;
    usersApi.list({ page: 1, size: 100 })
      .then((res) => {
        if (!cancelled) setUsers(res.data.items);
      })
      .catch(() => {
        if (!cancelled) setUsers([]);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const params = { days: range.days, user_id: selectedUserId };
    const hourlyParams = {
      user_id: selectedUserId,
      model: selectedModel,
      start_date: range.startDate,
      end_date: range.endDate,
    };
    void Promise.resolve().then(() => {
      setLoading(true);
      setLoadFailed(false);
      return Promise.allSettled([
        getTokenSummary(params),
        getDailyTokenStats(todayStr, { user_id: selectedUserId }),
        getHourlyTokenStats(hourlyParams),
      ])
        .then(([summaryResult, dailyResult, hourlyResult]) => {
          if (cancelled) return;
          const results = [summaryResult, dailyResult, hourlyResult];
          const hasSuccess = results.some((result) => result.status === 'fulfilled');
          setLoadFailed(results.some((result) => result.status === 'rejected'));
          setSummary(summaryResult.status === 'fulfilled' ? summaryResult.value : null);
          setDailyItems(dailyResult.status === 'fulfilled' ? dailyResult.value.items : []);
          setHourlyItems(hourlyResult.status === 'fulfilled' ? hourlyResult.value.items : []);
          if (hasSuccess) setLastLoadedAt(new Date());
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    });
    return () => { cancelled = true; };
  }, [range, selectedUserId, selectedModel, todayStr, refreshKey]);

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
          if (!cancelled) setUserQuota(res.data);
        })
        .catch(() => {
          if (!cancelled) setUserQuota(null);
        })
        .finally(() => setQuotaLoading(false));
    });

    return () => { cancelled = true; };
  }, [selectedUserId]);

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId),
    [users, selectedUserId]
  );

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

  const todayUsage = useMemo(
    () => dailyItems
      .filter((item) => !selectedModel || item.model === selectedModel)
      .reduce((sum, item) => sum + toNumber(item.total_tokens), 0),
    [dailyItems, selectedModel]
  );

  const hourlyTrend = useMemo<TrendPoint[]>(() => {
    const rows = new Map<string, TrendPoint>();
    if (range.mode === 'day') {
      HOURS_24.forEach((hour) => {
        rows.set(`${range.startDate}-${hour}`, {
          key: `${range.startDate}-${hour}`,
          label: `${range.startDate} ${hour}:00`,
          shortLabel: `${hour}:00`,
          date: range.startDate,
          hour,
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: 0,
          request_count: 0,
        });
      });
    }
    hourlyItems.forEach((item) => {
      const date = item.date || range.startDate;
      const key = `${date}-${item.hour}`;
      const row = rows.get(key) ?? {
        key,
        label: `${date} ${item.hour}:00`,
        shortLabel: range.mode === 'day' ? `${item.hour}:00` : `${date.slice(5)} ${item.hour}:00`,
        date,
        hour: item.hour,
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
        request_count: 0,
      };
      const promptTokens = toNumber(item.prompt_tokens);
      const completionTokens = toNumber(item.completion_tokens);
      row.prompt_tokens += promptTokens;
      row.completion_tokens += completionTokens;
      row.total_tokens += promptTokens + completionTokens;
      row.request_count += toNumber(item.request_count);
      rows.set(key, row);
    });
    return Array.from(rows.values()).sort((a, b) => a.key.localeCompare(b.key));
  }, [hourlyItems, range]);

  const allHeatmapRows = useMemo<HeatmapRow[]>(() => {
    if (hourlyItems.length === 0) return [];
    const row: HeatmapRow = {
      id: 'all',
      label: selectedUser ? selectedUser.nickname || selectedUser.phone : '全部用户',
      tokensByHour: {},
      total_tokens: 0,
      request_count: 0,
      avg_tokens: 0,
    };
    hourlyItems.forEach((item) => {
      const tokens = toNumber(item.total_tokens);
      row.tokensByHour[item.hour] = (row.tokensByHour[item.hour] ?? 0) + tokens;
      row.total_tokens += tokens;
      row.request_count += toNumber(item.request_count);
    });
    row.avg_tokens = row.request_count > 0 ? Math.round(row.total_tokens / row.request_count) : 0;
    return [row];
  }, [hourlyItems, selectedUser]);

  const userHeatmapRows = useMemo<HeatmapRow[]>(() => {
    const rows = new Map<string, HeatmapRow>();
    hourlyItems.forEach((item) => {
      const id = item.user_id || `farm-${item.farm_id}`;
      const user = users.find((candidate) => candidate.id === item.user_id);
      const row = rows.get(id) ?? {
        id,
        label: user ? user.nickname || user.phone : id,
        tokensByHour: {},
        total_tokens: 0,
        request_count: 0,
        avg_tokens: 0,
      };
      const tokens = toNumber(item.total_tokens);
      row.tokensByHour[item.hour] = (row.tokensByHour[item.hour] ?? 0) + tokens;
      row.total_tokens += tokens;
      row.request_count += toNumber(item.request_count);
      rows.set(id, row);
    });
    return normalizeHeatmapRows(rows);
  }, [hourlyItems, users]);

  const dayHeatmapRows = useMemo<HeatmapRow[]>(() => {
    const rows = new Map<string, HeatmapRow>();
    hourlyItems.forEach((item) => {
      const date = item.date || todayStr;
      const weekday = new Date(`${date}T00:00:00`).toLocaleDateString('zh-CN', { weekday: 'short' });
      const row = rows.get(date) ?? {
        id: date,
        label: `${date} ${weekday}`,
        tokensByHour: {},
        total_tokens: 0,
        request_count: 0,
        avg_tokens: 0,
      };
      const tokens = toNumber(item.total_tokens);
      row.tokensByHour[item.hour] = (row.tokensByHour[item.hour] ?? 0) + tokens;
      row.total_tokens += tokens;
      row.request_count += toNumber(item.request_count);
      rows.set(date, row);
    });
    return normalizeHeatmapRows(rows).sort((a, b) => a.id.localeCompare(b.id));
  }, [hourlyItems, todayStr]);

  const modelHeatmapRows = useMemo<HeatmapRow[]>(() => {
    const rows = new Map<string, HeatmapRow>();
    hourlyItems.forEach((item) => {
      const row = rows.get(item.model) ?? {
        id: item.model,
        label: item.model,
        tokensByHour: {},
        total_tokens: 0,
        request_count: 0,
        avg_tokens: 0,
      };
      const tokens = toNumber(item.total_tokens);
      row.tokensByHour[item.hour] = (row.tokensByHour[item.hour] ?? 0) + tokens;
      row.total_tokens += tokens;
      row.request_count += toNumber(item.request_count);
      rows.set(item.model, row);
    });
    return normalizeHeatmapRows(rows);
  }, [hourlyItems]);

  const displayTotalTokens = modelStats.reduce((sum, item) => sum + item.total_tokens, 0);
  const displayTotalRequests = modelStats.reduce((sum, item) => sum + item.request_count, 0);
  const maxModelTokens = Math.max(1, ...modelStats.map((item) => item.total_tokens));
  const maxHeatmapTokens = Math.max(1, ...hourlyItems.map((item) => toNumber(item.total_tokens)));
  const maxTrendTokens = Math.max(1, ...hourlyTrend.map((item) => item.total_tokens));
  const maxTrendRequests = Math.max(1, ...hourlyTrend.map((item) => item.request_count));
  const monthlyPercent = getQuotaPercent(userQuota?.monthly_usage, userQuota?.monthly_limit);
  const weeklyPercent = getQuotaPercent(userQuota?.weekly_usage, userQuota?.weekly_limit);
  const loadedText = loadFailed ? '加载失败' : loading ? '加载中' : '已加载';
  const quotaEmptyText = selectedUserId ? '该用户暂无配额数据' : '请选择用户查看个人配额';

  const refresh = () => setRefreshKey((key) => key + 1);

  return (
    <div style={{ padding: '14px 20px 64px', background: BG, minHeight: '100vh' }}>
      <div style={{ marginBottom: 12 }}>
        <Space align="center" size={12} wrap>
          <h2 style={{ color: TEXT, margin: 0 }}>Token 监控看板</h2>
          <Tag color={loadFailed ? 'error' : 'success'}>{loadedText}</Tag>
          <span style={{ color: TEXT_DIM, fontSize: 13 }}>最后刷新：{formatTime(lastLoadedAt)}</span>
        </Space>
        <div style={{ color: TEXT_DIM, fontSize: 13, marginTop: 8 }}>
          provider usage 入账 · {range.label} · {range.startDate} 至 {range.endDate}
          {selectedUser ? `，当前用户：${selectedUser.nickname || selectedUser.phone}` : '，当前范围：全部用户'}
          {selectedModel ? `，模型：${selectedModel}` : ''}
        </div>
      </div>

      <Card style={{ ...panelStyle, marginBottom: 12 }} bodyStyle={{ padding: 12 }}>
        <Row gutter={[14, 14]} align="bottom">
          <Col xs={24} sm={12} xl={6}>
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
          <Col xs={24} sm={12} xl={6}>
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
          <Col xs={24} md={10} xl={6}>
            <div style={fieldLabelStyle}>汇总范围</div>
            <Segmented
              block
              options={[
                { label: '当日', value: 'day' },
                { label: '近 7 天', value: 'week' },
                { label: '本月', value: 'month' },
              ]}
              value={rangeMode}
              onChange={(v) => setRangeMode(v as RangeMode)}
              style={{ background: BG }}
            />
          </Col>
          <Col xs={24} md={6} xl={4}>
            <Button block type="primary" icon={<ReloadOutlined />} loading={loading} onClick={refresh}>刷新</Button>
          </Col>
        </Row>
      </Card>

      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col xs={24} sm={12} xl={5}>
          <Card style={compactCardStyle} loading={loading} bodyStyle={{ padding: 14 }}>
            <Statistic title={<span style={{ color: TEXT_DIM }}>Token</span>} value={displayTotalTokens} formatter={(value) => formatCompactNumber(Number(value))} valueStyle={{ color: TEXT }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={5}>
          <Card style={compactCardStyle} loading={loading} bodyStyle={{ padding: 14 }}>
            <Statistic title={<span style={{ color: TEXT_DIM }}>请求</span>} value={displayTotalRequests} valueStyle={{ color: TEXT }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={5}>
          <Card style={compactCardStyle} loading={loading || quotaLoading} bodyStyle={{ padding: 14 }}>
            <Statistic title={<span style={{ color: TEXT_DIM }}>今日</span>} value={todayUsage} formatter={(value) => formatCompactNumber(Number(value))} valueStyle={{ color: TEXT }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={5}>
          <Card style={compactCardStyle} loading={quotaLoading} bodyStyle={{ padding: 14 }}>
            <div style={{ color: TEXT_DIM, fontSize: 13, marginBottom: 4 }}>月配额</div>
            {selectedUserId && userQuota ? (
              <>
                <Progress percent={monthlyPercent} status={getQuotaStatus(monthlyPercent)} />
                <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 2 }}>
                  {formatCompactNumber(userQuota.monthly_usage)} / {formatCompactNumber(userQuota.monthly_limit)}
                </div>
              </>
            ) : (
              <div style={{ color: TEXT_DIM, fontSize: 13 }}>{quotaEmptyText}</div>
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={4}>
          <Card style={compactCardStyle} loading={quotaLoading} bodyStyle={{ padding: 14 }}>
            <div style={{ color: TEXT_DIM, fontSize: 13, marginBottom: 4 }}>周配额</div>
            {selectedUserId && userQuota ? (
              <>
                <Progress percent={weeklyPercent} status={getQuotaStatus(weeklyPercent)} />
                <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 2 }}>
                  {formatCompactNumber(userQuota.weekly_usage)} / {formatCompactNumber(userQuota.weekly_limit)}
                </div>
              </>
            ) : (
              <div style={{ color: TEXT_DIM, fontSize: 13 }}>{quotaEmptyText}</div>
            )}
          </Card>
        </Col>
      </Row>

      <ChartCard title="自然时间轴" legend={[
        ['Prompt', BLUE, 'square'],
        ['Completion', GREEN, 'square'],
        ['请求数', AMBER, 'dot'],
      ]}>
        <TokenTrendChart hourlyTrend={hourlyTrend} maxTrendTokens={maxTrendTokens} maxTrendRequests={maxTrendRequests} />
      </ChartCard>

      <ChartCard title="性能走势" legend={[
        ['平均 Token/请求', '#56d695', 'dot'],
        ['请求数', PURPLE, 'dot'],
      ]}>
        <PerformanceTrendChart hourlyTrend={hourlyTrend} />
      </ChartCard>

      <HeatmapSection title="部门 × 小时分布" rows={allHeatmapRows} hint="当前接口暂无部门维度，按当前范围汇总" maxHeatmapTokens={maxHeatmapTokens} />
      <HeatmapSection title="用户 × 小时分布" rows={userHeatmapRows} hint="看不同用户的使用时段" maxHeatmapTokens={maxHeatmapTokens} />
      <HeatmapSection title="工作日 × 小时" rows={dayHeatmapRows} hint="按自然日展示小时分布" maxHeatmapTokens={maxHeatmapTokens} />
      <HeatmapSection title="模型 × 小时" rows={modelHeatmapRows} hint="看不同模型的使用时段" maxHeatmapTokens={maxHeatmapTokens} />

      <Card title={<span style={{ color: TEXT }}>模型用量</span>} extra={<span style={{ color: TEXT_DIM, fontSize: 12 }}>按模型聚合</span>} style={panelStyle} bodyStyle={{ padding: 20 }}>
        <Space size={16} style={{ marginBottom: 18 }}>
          <LegendItem color={BLUE} label="Prompt" shape="square" />
          <LegendItem color={GREEN} label="Completion" shape="square" />
        </Space>
        <ModelUsageRows modelStats={modelStats} maxModelTokens={maxModelTokens} />
      </Card>
    </div>
  );
}

function getQuotaPercent(usage?: number, limit?: number) {
  if (!usage || !limit) return 0;
  return Math.min(100, Math.round((usage / limit) * 100));
}

function getQuotaStatus(percent: number) {
  if (percent >= 80) return 'exception';
  return percent >= 60 ? 'active' : 'success';
}
