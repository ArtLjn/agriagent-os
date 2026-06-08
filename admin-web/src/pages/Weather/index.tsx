import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Col, InputNumber, Row, Space, Statistic, Tag, Typography, message } from 'antd';
import {
  CloudOutlined,
  DashboardOutlined,
  FieldTimeOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { getForecast } from '../../api/weather';
import { MetricCard, PageShell, StateBlock, Toolbar } from '../../components/PageShell';
import { cardStyle, palette } from '../../styles/theme';
import { buildWeatherSummary, buildWeatherView, type WeatherViewDay } from './weatherModel';

export default function Weather() {
  const [days, setDays] = useState(7);
  const [queryDays, setQueryDays] = useState(7);
  const [weather, setWeather] = useState<WeatherViewDay[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [summary, setSummary] = useState('暂无天气数据');
  const [loading, setLoading] = useState(false);

  const fetchWeather = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getForecast(queryDays);
      setWeather(buildWeatherView(res.days));
      setWarnings(res.warnings ?? []);
      setSummary(buildWeatherSummary(res.days, res.warnings));
    } catch {
      setWeather([]);
      setWarnings([]);
      setSummary('天气数据加载失败');
      message.error('天气数据加载失败');
    } finally {
      setLoading(false);
    }
  }, [queryDays]);

  useEffect(() => { fetchWeather(); }, [fetchWeather]);

  const handleQuery = () => {
    if (days === queryDays) {
      fetchWeather();
      return;
    }
    setQueryDays(days);
  };

  const hotDays = weather.filter((day) => day.riskText === '高温').length;
  const rainyDays = weather.filter((day) => day.riskText === '有雨' || day.riskText === '强降水').length;
  const warningDays = weather.filter((day) => day.riskLevel === 'warning').length;

  return (
    <PageShell
      title="天气预报"
      description="把未来天气转成灌溉、排水、防风和高温作业提醒。"
    >
      <Toolbar
        left={(
          <>
            <span style={{ color: palette.textMuted, fontSize: 13 }}>预报天数</span>
            <InputNumber min={1} max={16} value={days} onChange={(v) => setDays(v ?? 7)} />
            <Button
              type="primary"
              icon={<ReloadOutlined />}
              onClick={handleQuery}
              loading={loading}
            >
              查询
            </Button>
          </>
        )}
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={12}>
          <Card style={{ ...cardStyle, height: '100%' }}>
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <Space>
                <CloudOutlined style={{ color: palette.accent, fontSize: 20 }} />
                <Typography.Text style={{ color: palette.textMuted }}>农事天气摘要</Typography.Text>
              </Space>
              <Typography.Title level={4} style={{ color: palette.text, margin: 0, lineHeight: 1.45 }}>
                {summary}
              </Typography.Title>
              <Space wrap>
                {(warnings.length > 0 ? warnings : ['无官方预警']).slice(0, 3).map((item) => (
                  <Tag key={item} color={warnings.length > 0 ? 'orange' : 'green'}>{item}</Tag>
                ))}
              </Space>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={8} lg={4}>
          <MetricCard accent={warningDays > 0 ? palette.danger : palette.success}>
            <Statistic title="风险天数" value={warningDays} prefix={<WarningOutlined />} suffix="天" />
          </MetricCard>
        </Col>
        <Col xs={24} sm={8} lg={4}>
          <MetricCard accent={palette.warning}>
            <Statistic title="高温关注" value={hotDays} prefix={<ThunderboltOutlined />} suffix="天" />
          </MetricCard>
        </Col>
        <Col xs={24} sm={8} lg={4}>
          <MetricCard accent={palette.accent}>
            <Statistic title="降水窗口" value={rainyDays} prefix={<DashboardOutlined />} suffix="天" />
          </MetricCard>
        </Col>
      </Row>

      {warningDays > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="存在影响作业安排的天气风险"
          description="建议优先检查排水、棚膜、支架和灌溉计划，把采收、施肥、喷药安排到风险较低的时段。"
        />
      )}

      <StateBlock loading={loading} empty={weather.length === 0} emptyText="暂无天气数据">
        <Row gutter={[16, 16]}>
          {weather.map((day) => (
            <Col xs={24} sm={12} lg={8} xl={6} key={day.date}>
              <WeatherCard day={day} />
            </Col>
          ))}
        </Row>
      </StateBlock>
    </PageShell>
  );
}

function WeatherCard({ day }: { day: WeatherViewDay }) {
  const riskColor = day.riskLevel === 'warning' ? palette.danger : day.riskLevel === 'notice' ? palette.warning : palette.success;

  return (
    <Card
      size="small"
      style={{ ...cardStyle, height: '100%', borderTop: `2px solid ${riskColor}` }}
      title={(
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <span>{day.shortDate}</span>
          <Tag color={day.riskLevel === 'warning' ? 'red' : day.riskLevel === 'notice' ? 'gold' : 'green'}>
            {day.riskText}
          </Tag>
        </Space>
      )}
    >
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Space>
          <CloudOutlined style={{ color: palette.accent, fontSize: 18 }} />
          <Typography.Text strong>{day.label}</Typography.Text>
        </Space>

        <Row gutter={10}>
          <Col span={8}>
            <SmallMetric label="温度" value={day.temperatureRange} />
          </Col>
          <Col span={8}>
            <SmallMetric label="降水" value={day.precipitationText} />
          </Col>
          <Col span={8}>
            <SmallMetric label="风速" value={day.windText} />
          </Col>
        </Row>

        <div style={{ color: palette.textMuted, fontSize: 13, lineHeight: 1.6, minHeight: 42 }}>
          <FieldTimeOutlined style={{ marginRight: 6 }} />
          {day.advice}
        </div>
      </Space>
    </Card>
  );
}

function SmallMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ color: palette.textSubtle, fontSize: 12, marginBottom: 4 }}>{label}</div>
      <div style={{ color: palette.text, fontSize: 13, fontWeight: 650, whiteSpace: 'nowrap' }}>{value}</div>
    </div>
  );
}
