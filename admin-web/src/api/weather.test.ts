import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import { getForecast } from './weather';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('weather api', () => {
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
});
