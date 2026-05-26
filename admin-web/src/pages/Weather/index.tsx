import { useEffect, useState } from 'react';
import { Card, Row, Col, InputNumber, Button, Spin } from 'antd';
import { getForecast } from '../../api/weather';

interface DayWeather {
  date: string;
  temp_max: number;
  temp_min: number;
  precipitation: number;
  wind_max: number;
}

export default function Weather() {
  const [days, setDays] = useState(7);
  const [weather, setWeather] = useState<DayWeather[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchWeather = async () => {
    setLoading(true);
    try {
      const res = await getForecast(days);
      const items: DayWeather[] = res.days.map((day) => ({
        date: day.date,
        temp_max: day.max_temp,
        temp_min: day.min_temp,
        precipitation: day.precipitation,
        wind_max: day.wind_speed,
      }));
      setWeather(items);
    } catch {
      setWeather([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchWeather(); }, []);

  return (
    <div>
      <Row gutter={8} style={{ marginBottom: 16 }}>
        <Col><InputNumber min={1} max={16} value={days} onChange={(v) => setDays(v ?? 7)} /></Col>
        <Col><Button type="primary" onClick={fetchWeather} loading={loading}>查询</Button></Col>
      </Row>
      {loading ? <Spin /> : (
        <Row gutter={[16, 16]}>
          {weather.map((d) => (
            <Col span={Math.max(4, 24 / Math.min(days, 6))} key={d.date}>
              <Card size="small" title={d.date}>
                <p>{d.temp_min}°C ~ {d.temp_max}°C</p>
                <p>降水: {d.precipitation}mm</p>
                <p>风速: {d.wind_max}m/s</p>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </div>
  );
}
