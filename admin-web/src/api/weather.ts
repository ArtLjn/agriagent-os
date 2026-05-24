import apiClient from './client';

export const getForecast = (days: number = 7) =>
  apiClient.get('/weather/forecast', { params: { days } });
