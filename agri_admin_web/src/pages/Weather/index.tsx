import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Col, InputNumber, Row, Select, message } from 'antd';
import {
  CloudOutlined,
  DashboardOutlined,
  EnvironmentOutlined,
  FieldTimeOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { getForecast, searchLocations, type LocationOption } from '../../api/weather';
import { PageShell, StateBlock, Toolbar } from '../../components/PageShell';
import { palette } from '../../styles/theme';
import { buildWeatherSummary, buildWeatherView, type WeatherViewDay } from './weatherModel';

export default function Weather() {
  const [days, setDays] = useState(7);
  const [queryDays, setQueryDays] = useState(7);
  const [weather, setWeather] = useState<WeatherViewDay[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [summary, setSummary] = useState('暂无天气数据');
  const [selectedLocation, setSelectedLocation] = useState<LocationOption | null>(null);
  const [locationOptions, setLocationOptions] = useState<LocationOption[]>([]);
  const [locationSearching, setLocationSearching] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetchWeather = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getForecast({
        days: queryDays,
        location: selectedLocation?.display_name,
        lat: selectedLocation?.lat,
        lon: selectedLocation?.lon,
      });
      const viewDays = buildWeatherView(res.days);
      setWeather(viewDays);
      setWarnings(res.warnings ?? []);
      setSummary(buildWeatherSummary(res.days));
    } catch {
      setWeather([]);
      setWarnings([]);
      setSummary('天气数据加载失败');
      message.error('天气数据加载失败');
    } finally {
      setLoading(false);
    }
  }, [queryDays, selectedLocation]);

  useEffect(() => { fetchWeather(); }, [fetchWeather]);

  const handleQuery = () => {
    if (days === queryDays) {
      fetchWeather();
      return;
    }
    setQueryDays(days);
  };

  const handleSearchLocation = async (query: string) => {
    const keyword = query.trim();
    if (!keyword) {
      setLocationOptions([]);
      return;
    }
    setLocationSearching(true);
    try {
      setLocationOptions(await searchLocations(keyword));
    } catch {
      setLocationOptions([]);
    } finally {
      setLocationSearching(false);
    }
  };

  const handleSelectLocation = (value?: string) => {
    if (!value) {
      setSelectedLocation(null);
      return;
    }
    const option = locationOptions.find((item) => item.display_name === value);
    if (option) setSelectedLocation(option);
  };

  const hotDays = weather.filter((day) => day.riskText === '高温').length;
  const rainyDays = weather.filter((day) => day.riskText === '有雨' || day.riskText === '强降水').length;
  const warningDays = weather.filter((day) => day.riskLevel === 'warning').length;

  const heroTemp = useMemo(() => {
    const today = weather[0];
    if (!today) return null;
    return today.temperatureRange;
  }, [weather]);

  const heroLabel = useMemo(() => weather[0]?.label ?? null, [weather]);

  return (
    <PageShell
      title="天气预报"
      description="把未来天气转成灌溉、排水、防风和高温作业提醒。"
    >
      <Toolbar
        left={(
          <>
            <span className="weather-toolbar__label">预报天数</span>
            <InputNumber min={1} max={16} value={days} onChange={(v) => setDays(v ?? 7)} />
            <Select
              allowClear
              showSearch
              filterOption={false}
              loading={locationSearching}
              placeholder="搜索地点"
              value={selectedLocation?.display_name}
              style={{ width: 240 }}
              suffixIcon={<EnvironmentOutlined style={{ color: palette.textMuted }} />}
              onSearch={handleSearchLocation}
              onChange={handleSelectLocation}
              options={locationOptions.map((item) => ({
                value: item.display_name,
                label: item.display_name,
              }))}
            />
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

      <Row gutter={[16, 16]} className="weather-hero-row" align="top">
        <Col xs={24} lg={12}>
          <section className="weather-hero">
            <header className="weather-hero__head">
              <span className="weather-hero__eyebrow">
                <CloudOutlined style={{ color: palette.accent, fontSize: 16 }} />
                农事天气摘要
              </span>
              {heroTemp && (
                <div className="weather-hero__temp">
                  <span className="weather-hero__temp-value">{heroTemp}</span>
                  {heroLabel && <span className="weather-hero__temp-label">{heroLabel}</span>}
                </div>
              )}
            </header>
            <p className="weather-hero__summary">{summary}</p>
          </section>
        </Col>
        <Col xs={24} lg={12}>
          <Row gutter={[12, 12]} className="weather-metric-row">
            <Col xs={24} sm={8}>
              <WeatherMetric
                icon={<WarningOutlined />}
                accent={warningDays > 0 ? palette.danger : palette.success}
                label="风险天数"
                value={warningDays}
                hint={warningDays > 0 ? '需调整作业' : '总体平稳'}
              />
            </Col>
            <Col xs={24} sm={8}>
              <WeatherMetric
                icon={<ThunderboltOutlined />}
                accent={palette.warning}
                label="高温关注"
                value={hotDays}
                hint={hotDays > 0 ? '注意防暑' : '无需特别防护'}
              />
            </Col>
            <Col xs={24} sm={8}>
              <WeatherMetric
                icon={<DashboardOutlined />}
                accent={palette.accent}
                label="降水窗口"
                value={rainyDays}
                hint={rainyDays > 0 ? '关注排水' : '灌溉正常'}
              />
            </Col>
          </Row>
        </Col>
      </Row>

      <div className="weather-warnings-section">
        <OfficialWarnings warnings={warnings} />
      </div>

      {warningDays > 0 && (
        <Alert
          type="warning"
          showIcon
          className="weather-alert"
          message="存在影响作业安排的天气风险"
          description="建议优先检查排水、棚膜、支架和灌溉计划，把采收、施肥、喷药安排到风险较低的时段。"
        />
      )}

      <StateBlock loading={loading} empty={weather.length === 0} emptyText="暂无天气数据">
        <Row gutter={[16, 16]} className="weather-day-grid">
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

interface WeatherMetricProps {
  icon: React.ReactNode;
  accent: string;
  label: string;
  value: number;
  hint: string;
}

function WeatherMetric({ icon, accent, label, value, hint }: WeatherMetricProps) {
  return (
    <div
      className="weather-metric"
      style={{ '--weather-metric-accent': accent } as React.CSSProperties}
    >
      <div className="weather-metric__icon" style={{ color: accent, background: `${accent}1f` }}>
        {icon}
      </div>
      <div className="weather-metric__body">
        <div className="weather-metric__label">{label}</div>
        <div className="weather-metric__value">
          {value}
          <span className="weather-metric__unit">天</span>
        </div>
        <div className="weather-metric__hint">{hint}</div>
      </div>
    </div>
  );
}

function OfficialWarnings({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) {
    return (
      <div className="weather-warnings weather-warnings--empty">
        <span className="weather-warnings__title">官方天气预警</span>
        <span className="weather-warnings__pill">
          <span className="weather-warnings__dot" />
          无官方预警
        </span>
      </div>
    );
  }

  return (
    <div className="weather-warnings" aria-label="官方天气预警">
      <header className="weather-warnings__head">
        <span className="weather-warnings__title">官方天气预警</span>
        <span className="weather-warnings__count">{warnings.length} 条 · 横向滑动查看</span>
      </header>
      <div className="weather-warnings__track">
        {warnings.map((item) => (
          <div key={item} className="weather-warnings__item" title={item}>
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function WeatherCard({ day }: { day: WeatherViewDay }) {
  const riskColor = day.riskLevel === 'warning'
    ? palette.danger
    : day.riskLevel === 'notice'
      ? palette.warning
      : palette.success;

  return (
    <article
      className="weather-card"
      style={{ '--weather-card-accent': riskColor } as React.CSSProperties}
    >
      <header className="weather-card__head">
        <div className="weather-card__date">
          <span className="weather-card__short">{day.shortDate}</span>{' '}
          <span className="weather-card__label">
            <CloudOutlined style={{ color: palette.accent, fontSize: 14 }} />
            {day.label}
          </span>
        </div>
        <span
          className="weather-card__risk"
          style={{ color: riskColor, background: `${riskColor}1f`, borderColor: `${riskColor}55` }}
        >
          {day.riskText}
        </span>
      </header>

      <div className="weather-card__temp">{day.temperatureRange}</div>

      <Row gutter={8} className="weather-card__metrics">
        <Col span={12}>
          <SmallMetric icon={<DashboardOutlined />} label="降水" value={day.precipitationText} />
        </Col>
        <Col span={12}>
          <SmallMetric icon={<ThunderboltOutlined />} label="风速" value={day.windText} />
        </Col>
      </Row>

      <div className="weather-card__advice">
        <FieldTimeOutlined style={{ marginRight: 6, color: palette.accent }} />
        {day.advice}
      </div>
    </article>
  );
}

function SmallMetric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="weather-small-metric">
      <div className="weather-small-metric__label">
        {icon}
        {label}
      </div>
      <div className="weather-small-metric__value">{value}</div>
    </div>
  );
}
