import { beforeEach, describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import { getForecast, searchLocations } from './weather';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('weather api', () => {
  beforeEach(() => {
    mockedApiClient.get.mockReset();
  });

  it('把后端 legacy daily 响应归一化为 days 列表', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        location: '当前地块',
        provider: 'open-meteo',
        daily: {
          time: ['2026-06-08'],
          temperature_2m_max: [33],
          temperature_2m_min: [25],
          precipitation_sum: [2.5],
          windspeed_10m_max: [6],
        },
        current_weather: { temperature: 29 },
        warnings: ['2026-06-08 偏热'],
      },
    });

    const result = await getForecast(7);

    expect(mockedApiClient.get).toHaveBeenCalledWith('/weather/forecast', { params: { days: 7 } });
    expect(result.days[0]).toEqual({
      date: '2026-06-08',
      max_temp: 33,
      min_temp: 25,
      precipitation: 2.5,
      weather_code: undefined,
      weather_text: undefined,
      wind_speed: 6,
    });
    expect(result.current_temp).toBe(29);
    expect(result.warnings).toEqual(['2026-06-08 偏热']);
  });

  it('查询天气时透传地点和经纬度', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: { days: [], warnings: [] },
    });

    await getForecast({
      days: 7,
      location: '苏州市虎丘区',
      lat: 31.3296,
      lon: 120.4342,
    });

    expect(mockedApiClient.get).toHaveBeenCalledWith('/weather/forecast', {
      params: {
        days: 7,
        location: '苏州市虎丘区',
        lat: 31.3296,
        lon: 120.4342,
      },
    });
  });

  it('搜索统一位置数据源', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            display_name: '苏州市虎丘区',
            lat: 31.3296,
            lon: 120.4342,
            coordinate_source: 'manual_verified',
          },
        ],
      },
    });

    const result = await searchLocations('虎丘');

    expect(mockedApiClient.get).toHaveBeenCalledWith('/locations/search', {
      params: { q: '虎丘', limit: 20 },
    });
    expect(result[0].display_name).toBe('苏州市虎丘区');
  });
});
