import apiClient from './client';

export interface DayWeather {
  date: string;
  max_temp: number;
  min_temp: number;
  precipitation: number;
  weather_code: number;
  wind_speed: number;
}

export interface ForecastResponse {
  days: DayWeather[];
}

export async function getForecast(days: number = 7): Promise<ForecastResponse> {
  const res = await apiClient.get<ForecastResponse>(`/weather/forecast`, { params: { days } });
  return res.data;
}
