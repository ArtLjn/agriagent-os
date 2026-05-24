import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Typography, Alert, Spin } from 'antd';
import { CheckCircleOutlined, DollarOutlined, CloudOutlined, RobotOutlined } from '@ant-design/icons';
import * as cyclesApi from '../../api/cycles';
import * as costsApi from '../../api/costs';
import * as weatherApi from '../../api/weather';
import * as agentApi from '../../api/agent';

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [cycleCount, setCycleCount] = useState(0);
  const [weather, setWeather] = useState('');
  const [advice, setAdvice] = useState('');
  const [summary, setSummary] = useState<{ total_cost: string; total_income: string; net_profit: string } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const year = new Date().getFullYear();
    Promise.allSettled([
      cyclesApi.listCycles(),
      costsApi.getYearlySummary(year),
      weatherApi.getForecast(1),
      agentApi.getDailyAdvice(),
    ]).then(([cyclesRes, costsRes, weatherRes, adviceRes]) => {
      if (cyclesRes.status === 'fulfilled') setCycleCount(cyclesRes.value.data.length);
      if (costsRes.status === 'fulfilled') setSummary(costsRes.value.data);
      if (weatherRes.status === 'fulfilled') {
        const d = weatherRes.value.data?.daily;
        if (d?.temperature_2m_max?.[0]) setWeather(`${d.temperature_2m_max[0]}°C`);
      }
      if (adviceRes.status === 'fulfilled') {
        const a = adviceRes.value.data;
        setAdvice(a?.advice ? a.advice.slice(0, 100) + '...' : '暂无建议');
      }
      if (cyclesRes.status === 'rejected') setError('后端连接失败');
      setLoading(false);
    });
  }, []);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (error) return <Alert type="error" message={error} />;

  return (
    <div>
      <Typography.Title level={3}>仪表盘</Typography.Title>
      <Row gutter={16}>
        <Col span={6}>
          <Card><Statistic title="种植周期" value={cycleCount} prefix={<CheckCircleOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="今日天气" value={weather || '--'} prefix={<CloudOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="年度净利润" value={summary?.net_profit ?? '--'} prefix={<DollarOutlined />}
              valueStyle={{ color: summary && Number(summary.net_profit) >= 0 ? '#3f8600' : '#cf1322' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="AI 建议" value={advice || '--'} prefix={<RobotOutlined />} valueStyle={{ fontSize: 14 }} />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
