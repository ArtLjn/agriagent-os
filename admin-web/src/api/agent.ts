import apiClient from './client';

export const chat = (message: string, cycleId?: number) =>
  apiClient.post('/agent/chat', { message, cycle_id: cycleId });
export const getDailyAdvice = (cycleId?: number) =>
  apiClient.get('/agent/daily', { params: { cycle_id: cycleId } });
export const generateReport = (reportType: string = 'weekly', cycleId?: number) =>
  apiClient.post('/agent/report', { report_type: reportType, cycle_id: cycleId });
export const getAdviceHistory = (params?: { cycle_id?: number; limit?: number }) =>
  apiClient.get('/agent/advice-history', { params });
export const getReportHistory = (params?: { cycle_id?: number; limit?: number }) =>
  apiClient.get('/agent/report-history', { params });
