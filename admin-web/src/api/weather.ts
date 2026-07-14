import apiClient from './client';
export { searchLocations } from './locations';
export type { LocationOption } from './locations';

export interface DayWeather {
  date: string;
  max_temp: number;
  min_temp: number;
  precipitation: number;
  weather_code?: number;
  weather_text?: string;
  wind_speed: number;
}

export interface ForecastResponse {
  location?: string;
  provider?: string;
  warnings?: string[];
  current_temp?: number | null;
  days: DayWeather[];
}

export interface ForecastQuery {
  days?: number;
  location?: string;
  lat?: number;
  lon?: number;
}

interface LegacyForecastResponse {
  location?: string;
  provider?: string;
  warnings?: string[];
  current_weather?: {
    temperature?: number | null;
  };
  daily?: {
    time?: string[];
    temperature_2m_max?: number[];
    temperature_2m_min?: number[];
    precipitation_sum?: number[];
    windspeed_10m_max?: number[];
    weathercode?: number[];
    weather_text?: string[];
  };
}

function normalizeForecast(data: ForecastResponse | LegacyForecastResponse): ForecastResponse {
  if ('days' in data && Array.isArray(data.days)) {
    return data;
  }

  const legacyData = data as LegacyForecastResponse;
  const daily = legacyData.daily ?? {};
  const times: string[] = daily.time ?? [];
  const maxTemps = daily.temperature_2m_max ?? [];
  const minTemps = daily.temperature_2m_min ?? [];
  const precipitations = daily.precipitation_sum ?? [];
  const windSpeeds = daily.windspeed_10m_max ?? [];
  const weatherCodes = daily.weathercode ?? [];
  const weatherTexts = daily.weather_text ?? [];

  return {
    location: legacyData.location,
    provider: legacyData.provider,
    warnings: legacyData.warnings,
    current_temp: legacyData.current_weather?.temperature ?? null,
    days: times.map((date, index) => ({
      date,
      max_temp: Number(maxTemps[index] ?? 0),
      min_temp: Number(minTemps[index] ?? 0),
      precipitation: Number(precipitations[index] ?? 0),
      weather_code: weatherCodes[index],
      weather_text: weatherTexts[index],
      wind_speed: Number(windSpeeds[index] ?? 0),
    })),
  };
}

export async function getForecast(query: number | ForecastQuery = 7): Promise<ForecastResponse> {
  const params = typeof query === 'number' ? { days: query } : { days: query.days ?? 7, location: query.location, lat: query.lat, lon: query.lon };
  const res = await apiClient.get<ForecastResponse | LegacyForecastResponse>('/weather/forecast', { params });
  return normalizeForecast(res.data);
}
