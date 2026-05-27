import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Typography, Alert, Spin, Button, Space } from 'antd';
import { CheckCircleOutlined, DollarOutlined, CloudOutlined, RobotOutlined, ReloadOutlined } from '@ant-design/icons';
import * as cyclesApi from '../../api/cycles';
import * as costsApi from '../../api/costs';
import * as weatherApi from '../../api/weather';
import * as agentApi from '../../api/agent';

const CACHE_TTL_MS = 30 * 60 * 1000; // 30 分钟

interface CacheEntry<T> {
  data: T;
  ts: number;
}

function getCache<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const entry: CacheEntry<T> = JSON.parse(raw);
    if (Date.now() - entry.ts > CACHE_TTL_MS) {
      localStorage.removeItem(key);
      return null;
    }
    return entry.data;
  } catch {
    return null;
  }
}

function setCache<T>(key: string, data: T) {
  localStorage.setItem(key, JSON.stringify({ data, ts: Date.now() }));
}

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [cycleCount, setCycleCount] = useState(0);
  const [weather, setWeather] = useState('');
  const [advice, setAdvice] = useState('');
  const [summary, setSummary] = useState<{ total_cost: string; total_income: string; net_profit: string } | null>(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async (force = false) => {
    if (!force) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }

    const year = new Date().getFullYear();

    // 1. 周期和成本：每次请求（业务数据变化频繁）
    const cyclesPromise = cyclesApi.listCycles();
    const costsPromise = costsApi.getYearlySummary(year);

    // 2. 天气：有缓存用缓存
    const cachedWeather = !force ? getCache<string>('dash_weather') : null;
    const weatherPromise = cachedWeather
      ? Promise.resolve({ days: [] })
      : weatherApi.getForecast(1);

    // 3. AI 建议：有缓存用缓存
    const cachedAdvice = !force ? getCache<string>('dash_advice') : null;
    const advicePromise = cachedAdvice
      ? Promise.resolve({ advice: '' })
      : agentApi.getDailyAdvice();

    const [cyclesRes, costsRes, weatherRes, adviceRes] = await Promise.allSettled([
      cyclesPromise,
      costsPromise,
      weatherPromise,
      advicePromise,
    ]);

    if (cyclesRes.status === 'fulfilled') {
      setCycleCount(cyclesRes.value.items.length);
    }
    if (costsRes.status === 'fulfilled') {
      setSummary(costsRes.value);
    }

    if (cachedWeather) {
      setWeather(cachedWeather);
    } else if (weatherRes.status === 'fulfilled') {
      const d = weatherRes.value.days?.[0];
      const w = d ? `${d.max_temp}°C` : '';
      setWeather(w);
      if (w) setCache('dash_weather', w);
    }

    if (cachedAdvice) {
      setAdvice(cachedAdvice);
    } else if (adviceRes.status === 'fulfilled') {
      const a = adviceRes.value;
      const text = a?.advice ? a.advice.slice(0, 100) + '...' : '暂无建议';
      setAdvice(text);
      if (text) setCache('dash_advice', text);
    }

    if (cyclesRes.status === 'rejected') {
      setError('后端连接失败');
    }

    setLoading(false);
    setRefreshing(false);
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (error) return <Alert type="error" message={error} />;

  return (
    <div>
      <Space style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>仪表盘</Typography.Title>
        <Button icon={<ReloadOutlined />} loading={refreshing} onClick={() => loadData(true)}>
          刷新
        </Button>
      </Space>
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
