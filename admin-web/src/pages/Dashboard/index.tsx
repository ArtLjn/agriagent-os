import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Typography, Alert, Spin, Button, Space, Tag } from 'antd';
import {
  CheckCircleOutlined,
  DollarOutlined,
  CloudOutlined,
  RobotOutlined,
  ReloadOutlined,
  FieldTimeOutlined,
} from '@ant-design/icons';
import * as cyclesApi from '../../api/cycles';
import * as costsApi from '../../api/costs';
import * as weatherApi from '../../api/weather';
import * as agentApi from '../../api/agent';
import { MetricCard, PageShell } from '../../components/PageShell';
import { cardStyle, palette } from '../../styles/theme';
import { buildWeatherSummary, buildWeatherView, type WeatherViewDay } from '../Weather/weatherModel';

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

function isForecastCache(data: unknown): data is weatherApi.ForecastResponse {
  return typeof data === 'object' && data !== null && Array.isArray((data as weatherApi.ForecastResponse).days);
}

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [cycleCount, setCycleCount] = useState(0);
  const [weatherSummary, setWeatherSummary] = useState('暂无天气数据');
  const [todayWeather, setTodayWeather] = useState<WeatherViewDay | null>(null);
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
    const cachedWeather = !force ? getCache<unknown>('dash_weather') : null;
    const cachedForecast = isForecastCache(cachedWeather) ? cachedWeather : null;
    const weatherPromise = cachedForecast
      ? Promise.resolve(cachedForecast)
      : weatherApi.getForecast(7);

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

    if (cachedForecast) {
      const viewDays = buildWeatherView(cachedForecast.days);
      setTodayWeather(viewDays[0] ?? null);
      setWeatherSummary(buildWeatherSummary(cachedForecast.days, cachedForecast.warnings));
    } else if (weatherRes.status === 'fulfilled') {
      const viewDays = buildWeatherView(weatherRes.value.days);
      setTodayWeather(viewDays[0] ?? null);
      setWeatherSummary(buildWeatherSummary(weatherRes.value.days, weatherRes.value.warnings));
      if (weatherRes.value.days.length > 0) setCache('dash_weather', weatherRes.value);
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
    <PageShell
      title="仪表盘"
      description="聚合种植、天气、成本和 AI 建议，快速判断今日运营重点。"
      actions={(
        <Button icon={<ReloadOutlined />} loading={refreshing} onClick={() => loadData(true)}>
          刷新
        </Button>
      )}
    >
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12} xl={6}>
          <MetricCard>
            <Statistic title="种植周期" value={cycleCount} prefix={<CheckCircleOutlined />} />
          </MetricCard>
        </Col>

        <Col xs={24} md={12} xl={6}>
          <Card style={{ ...cardStyle, height: '100%', borderTop: `2px solid ${palette.accent}` }}>
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                <Typography.Text style={{ color: palette.textMuted }}>今日天气</Typography.Text>
                {todayWeather && (
                  <Tag color={todayWeather.riskLevel === 'warning' ? 'red' : todayWeather.riskLevel === 'notice' ? 'gold' : 'green'}>
                    {todayWeather.riskText}
                  </Tag>
                )}
              </Space>
              <Space align="center">
                <CloudOutlined style={{ color: palette.accent, fontSize: 24 }} />
                <Typography.Title level={3} style={{ color: palette.text, margin: 0 }}>
                  {todayWeather ? todayWeather.temperatureRange : '--'}
                </Typography.Title>
              </Space>
              <Typography.Text style={{ color: palette.textMuted }}>
                {todayWeather ? todayWeather.label : weatherSummary}
              </Typography.Text>
            </Space>
          </Card>
        </Col>

        <Col xs={24} md={12} xl={6}>
          <MetricCard accent={summary && Number(summary.net_profit) >= 0 ? palette.success : palette.danger}>
            <Statistic
              title="年度净利润"
              value={summary?.net_profit ?? '--'}
              prefix={<DollarOutlined />}
              valueStyle={{ color: summary && Number(summary.net_profit) >= 0 ? palette.success : palette.danger }}
            />
          </MetricCard>
        </Col>

        <Col xs={24} md={12} xl={6}>
          <Card style={{ ...cardStyle, height: '100%', borderTop: `2px solid ${palette.purple}` }}>
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <Space>
                <RobotOutlined style={{ color: palette.purple, fontSize: 18 }} />
                <Typography.Text style={{ color: palette.textMuted }}>AI 建议</Typography.Text>
              </Space>
              <Typography.Paragraph
                style={{ color: palette.text, margin: 0, lineHeight: 1.6 }}
                ellipsis={{ rows: 3, tooltip: advice || '暂无建议' }}
              >
                {advice || '暂无建议'}
              </Typography.Paragraph>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card style={{ ...cardStyle, marginTop: 16 }}>
        <Space direction="vertical" size={8}>
          <Space>
            <FieldTimeOutlined style={{ color: palette.accent }} />
            <Typography.Text style={{ color: palette.textMuted }}>天气作业提醒</Typography.Text>
          </Space>
          <Typography.Text style={{ color: palette.text, fontSize: 15 }}>
            {weatherSummary}
          </Typography.Text>
        </Space>
      </Card>
    </PageShell>
  );
}
