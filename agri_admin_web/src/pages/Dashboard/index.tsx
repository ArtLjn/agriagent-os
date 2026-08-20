import { useEffect, useState } from 'react';
import { Alert, Button, Card, Col, Empty, Row, Spin, Statistic, Typography } from 'antd';
import {
  CloudOutlined,
  DollarOutlined,
  FieldTimeOutlined,
  FileTextOutlined,
  HomeOutlined,
  ReloadOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import * as dashboardApi from '../../api/dashboard';
import { MetricCard, PageShell } from '../../components/PageShell';
import { cardStyle, palette } from '../../styles/theme';

const currencyFormatter = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  maximumFractionDigits: 2,
});

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [summary, setSummary] = useState<dashboardApi.DashboardSummary | null>(null);
  const [error, setError] = useState('');

  const loadData = async (force = false) => {
    if (force) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError('');
    try {
      setSummary(await dashboardApi.getSummary());
    } catch {
      setError('后端连接失败');
    } finally {
      setLoading(false);
      setRefreshing(false);
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
  if (!summary) {
    return <Empty description="暂无农场概览数据" />;
  }

  const weather = summary.weather_today;
  const workers = summary.workers_summary;
  const costs = summary.cost_summary;

  return (
    <PageShell
      title="农场仪表板"
      description={`${summary.name}${summary.location ? ` · ${summary.location}` : ''}`}
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
              title="当前农场"
              value={summary.name}
              prefix={<HomeOutlined />}
            />
          </MetricCard>
        </Col>
        <Col xs={12} md={6}>
          <MetricCard accent={palette.success}>
            <Statistic
              title="进行中周期"
              value={summary.active_cycles.length}
              prefix={<FieldTimeOutlined />}
            />
          </MetricCard>
        </Col>
        <Col xs={12} md={6}>
          <MetricCard accent={palette.warning}>
            <Statistic
              title="近期农事日志"
              value={summary.recent_logs_count}
              prefix={<FileTextOutlined />}
            />
          </MetricCard>
        </Col>
        <Col xs={12} md={6}>
          <MetricCard accent={palette.purple}>
            <Statistic
              title="本月成本"
              value={currencyFormatter.format(costs.month_cost)}
              prefix={<DollarOutlined />}
            />
          </MetricCard>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card style={cardStyle}>
            <Typography.Title level={5} style={{ color: palette.text, marginTop: 0 }}>
              农场经营概览
            </Typography.Title>
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <Statistic title="年度利润" value={currencyFormatter.format(costs.year_profit)} />
              </Col>
              <Col span={12}>
                <Statistic title="本月收入" value={currencyFormatter.format(costs.month_income)} />
              </Col>
              <Col span={12}>
                <Statistic title="活跃工人" value={workers.active} prefix={<TeamOutlined />} />
              </Col>
              <Col span={12}>
                <Statistic title="工人总数" value={workers.total} />
              </Col>
            </Row>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card style={cardStyle}>
            <Typography.Title level={5} style={{ color: palette.text, marginTop: 0 }}>
              今日天气
            </Typography.Title>
            {weather ? (
              <Row gutter={[16, 16]}>
                <Col span={12}>
                  <Statistic title="天气" value={weather.desc} prefix={<CloudOutlined />} />
                </Col>
                <Col span={12}>
                  <Statistic title="温度" value={`${weather.min_c}°C - ${weather.max_c}°C`} />
                </Col>
                <Col span={12}>
                  <Statistic title="降水" value={`${weather.precip_mm} mm`} />
                </Col>
                <Col span={12}>
                  <Statistic title="风速" value={`${weather.wind_mps} m/s`} />
                </Col>
              </Row>
            ) : (
              <Empty description="暂无天气数据" />
            )}
          </Card>
        </Col>
      </Row>
    </PageShell>
  );
}
