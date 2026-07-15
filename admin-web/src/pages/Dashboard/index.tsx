import { useEffect, useState } from 'react';
import { Alert, Button, Card, Col, Empty, Modal, Row, Spin, Statistic, Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  FileTextOutlined,
  HomeOutlined,
  ReloadOutlined,
  TeamOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import * as dashboardApi from '../../api/dashboard';
import { MetricCard, PageShell } from '../../components/PageShell';
import { cardStyle, palette } from '../../styles/theme';

const TREND_BAR_HEIGHT = 160;

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [summary, setSummary] = useState<dashboardApi.DashboardSummary | null>(null);
  const [trend, setTrend] = useState<dashboardApi.DashboardTrendItem[]>([]);
  const [error, setError] = useState('');

  const [activeModalOpen, setActiveModalOpen] = useState(false);
  const [activeUsers, setActiveUsers] = useState<dashboardApi.DashboardActiveUser[]>([]);
  const [activeUsersLoading, setActiveUsersLoading] = useState(false);

  const loadData = async (force = false) => {
    if (!force) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    setError('');
    try {
      const [s, t] = await Promise.all([
        dashboardApi.getSummary(),
        dashboardApi.getTrend(7),
      ]);
      setSummary(s);
      setTrend(t.days);
    } catch {
      setError('后端连接失败');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const openActiveModal = async () => {
    setActiveModalOpen(true);
    setActiveUsersLoading(true);
    try {
      const res = await dashboardApi.getActiveUsers();
      setActiveUsers(res.items);
    } catch {
      setActiveUsers([]);
    } finally {
      setActiveUsersLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }
  if (error) {
    return <Alert type="error" message={error} />;
  }

  const maxCount = Math.max(1, ...trend.map((d) => d.count));
  const totalRecords = trend.reduce((acc, d) => acc + d.count, 0);

  const activeUserColumns: ColumnsType<dashboardApi.DashboardActiveUser> = [
    { title: '用户', dataIndex: 'nickname', key: 'nickname' },
    { title: '手机号', dataIndex: 'phone_masked', key: 'phone_masked' },
    { title: '农场', dataIndex: 'farm_name', key: 'farm_name', render: (v) => v || '—' },
    {
      title: '最后活跃',
      dataIndex: 'last_active_at',
      key: 'last_active_at',
      render: (v: string | null) => (v ? new Date(v).toLocaleString('zh-CN') : '—'),
    },
  ];

  return (
    <PageShell
      title="仪表盘"
      description="平台运营概览：规模、活跃、业务产出。"
      actions={
        <Button
          icon={<ReloadOutlined />}
          loading={refreshing}
          onClick={() => loadData(true)}
        >
          刷新
        </Button>
      }
    >
      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <MetricCard>
            <Statistic
              title="在管农场"
              value={summary?.farm_count ?? '--'}
              prefix={<HomeOutlined />}
            />
          </MetricCard>
        </Col>
        <Col xs={12} md={6}>
          <MetricCard accent={palette.success}>
            <Statistic
              title="注册用户"
              value={summary?.user_count ?? '--'}
              prefix={<TeamOutlined />}
            />
          </MetricCard>
        </Col>
        <Col xs={12} md={6}>
          <div
            onClick={() => {
              if ((summary?.dau_today ?? 0) > 0) openActiveModal();
            }}
            title={(summary?.dau_today ?? 0) > 0 ? '点击查看活跃用户列表' : ''}
            style={{
              cursor: (summary?.dau_today ?? 0) > 0 ? 'pointer' : 'default',
              transition: 'opacity 0.2s',
            }}
            onMouseEnter={(e) => {
              if ((summary?.dau_today ?? 0) > 0) e.currentTarget.style.opacity = '0.85';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.opacity = '1';
            }}
          >
            <MetricCard accent={palette.purple}>
              <Statistic
                title="今日活跃用户"
                value={summary?.dau_today ?? '--'}
                prefix={<ThunderboltOutlined />}
              />
            </MetricCard>
          </div>
        </Col>
        <Col xs={12} md={6}>
          <MetricCard accent={palette.warning}>
            <Statistic
              title="今日业务记录"
              value={summary?.records_today ?? '--'}
              prefix={<FileTextOutlined />}
            />
          </MetricCard>
        </Col>
      </Row>

      <Card style={{ ...cardStyle, marginTop: 16 }}>
        <Typography.Text style={{ color: palette.textMuted }}>
          近 7 天业务记录数（农事日志 + 成本记账）
        </Typography.Text>
        {totalRecords === 0 ? (
          <div style={{ padding: '40px 0' }}>
            <Empty description="近 7 天暂无业务记录" />
          </div>
        ) : (
          <div
            style={{
              display: 'flex',
              gap: 12,
              marginTop: 16,
              alignItems: 'flex-end',
              height: TREND_BAR_HEIGHT + 48,
            }}
          >
            {trend.map((d) => {
              const heightPx = Math.max(
                2,
                Math.round((d.count / maxCount) * TREND_BAR_HEIGHT),
              );
              const isToday = d.date === new Date().toISOString().slice(0, 10);
              return (
                <div key={d.date} style={{ flex: 1, textAlign: 'center' }}>
                  <div style={{ color: palette.text, fontSize: 12, marginBottom: 4 }}>
                    {d.count || ''}
                  </div>
                  <div
                    style={{
                      height: heightPx,
                      background: isToday ? palette.accent : palette.accentStrong,
                      opacity: d.count === 0 ? 0.3 : 1,
                      borderRadius: 4,
                    }}
                  />
                  <div style={{ color: palette.textMuted, fontSize: 12, marginTop: 6 }}>
                    {d.date.slice(5)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Modal
        title="今日活跃用户"
        open={activeModalOpen}
        onCancel={() => setActiveModalOpen(false)}
        footer={null}
        width={680}
      >
        <Table
          rowKey="user_id"
          columns={activeUserColumns}
          dataSource={activeUsers}
          loading={activeUsersLoading}
          pagination={false}
          size="small"
          locale={{ emptyText: '今日暂无活跃用户' }}
        />
      </Modal>
    </PageShell>
  );
}
