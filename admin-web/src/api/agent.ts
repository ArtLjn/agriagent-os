import apiClient from './client';

export const chat = (message: string, cycleId?: number) =>
  apiClient.post('/agent/chat', { message, cycle_id: cycleId });

export async function* streamChat(message: string, cycleId?: number): AsyncGenerator<string> {
  const resp = await fetch('/api/agent/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, cycle_id: cycleId }),
  });
  if (!resp.ok || !resp.body) throw new Error(`stream error: ${resp.status}`);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop() ?? '';
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data: ')) continue;
      const payload = trimmed.slice(6);
      if (payload === '[DONE]') return;
      try {
        const obj = JSON.parse(payload);
        if (obj.error) throw new Error(obj.error);
        if (obj.content) yield obj.content;
      } catch (e) {
        if (e instanceof SyntaxError) continue;
        throw e;
      }
    }
  }
}

export const getDailyAdvice = (cycleId?: number) =>
  apiClient.get('/agent/daily', { params: { cycle_id: cycleId } });
export const generateReport = (reportType: string = 'weekly', cycleId?: number) =>
  apiClient.post('/agent/report', { report_type: reportType, cycle_id: cycleId });
export const getAdviceHistory = (params?: { cycle_id?: number; limit?: number }) =>
  apiClient.get('/agent/advice-history', { params });
export const getReportHistory = (params?: { cycle_id?: number; limit?: number }) =>
  apiClient.get('/agent/report-history', { params });
