import { describe, expect, it } from 'vitest';

import { buildWeatherSummary, buildWeatherView, getWeatherLabel } from './weatherModel';

describe('weatherModel', () => {
  it('根据天气代码、降水和温度生成农事视图', () => {
    const view = buildWeatherView([
      {
        date: '2026-06-08',
        max_temp: 36,
        min_temp: 28,
        precipitation: 0,
        weather_code: 0,
        wind_speed: 3,
      },
    ]);

    expect(view[0]).toMatchObject({
      label: '晴',
      shortDate: '6/8',
      riskLevel: 'warning',
      riskText: '高温',
    });
    expect(view[0].advice).toContain('早晚补水');
  });

  it('优先使用后端天气文本', () => {
    expect(getWeatherLabel({
      date: '2026-06-08',
      max_temp: 26,
      min_temp: 20,
      precipitation: 0,
      weather_text: '小到中雨',
      wind_speed: 4,
    })).toBe('小到中雨');
  });

  it('生成仪表盘摘要并优先展示预警', () => {
    const summary = buildWeatherSummary([
      {
        date: '2026-06-08',
        max_temp: 30,
        min_temp: 23,
        precipitation: 0,
        wind_speed: 2,
      },
    ], ['2026-06-08 大风预警：最大风速 18m/s']);

    expect(summary).toBe('2026-06-08 大风预警：最大风速 18m/s');
  });
});
