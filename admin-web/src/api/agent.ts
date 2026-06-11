import apiClient from './client';
import { authStore } from '../stores/authStore';

export interface ChatRequest {
  cycle_id?: number;
  message: string;
}

export interface ChatResponse {
  reply: string;
}

export interface DailyAdviceResponse {
  cycle_id?: number;
  advice: string;
  created_at: string;
}

export interface ReportRequest {
  cycle_id?: number;
  report_type?: string;
}

export interface ReportResponse {
  cycle_id?: number;
  report_type: string;
  content: string;
  created_at: string;
}

export interface AdviceHistoryItem {
  id: number;
  cycle_id?: number;
  advice_type: string;
  content: string;
  created_at: string;
}

export interface ReportHistoryItem {
  id: number;
  cycle_id?: number;
  report_type: string;
  content: string;
  created_at: string;
}

export interface ReportListResponse {
  items: ReportHistoryItem[];
  total: number;
}

export interface AppSkillItem {
  key: string;
  title: string;
  description: string;
  category: string;
  icon: string;
  icon_color: string;
  recommended: boolean;
  enabled: boolean;
}

export interface AppSkillListResponse {
  items: AppSkillItem[];
  total: number;
}

export async function chat(data: ChatRequest): Promise<ChatResponse> {
  const res = await apiClient.post<ChatResponse>("/agent/chat", data);
  return res.data;
}

export interface PendingActionContext {
  original_input: string;
  extracted_params: Record<string, unknown>;
  notes: string[];
}

export interface PendingAction {
  action_id: string;
  skill_name: string;
  params: Record<string, unknown>;
  context?: PendingActionContext | null;
}

export interface PendingPlan {
  plan_id?: string;
  status?: string;
  steps?: unknown[];
}

export type StreamChunk =
  | { type: 'content'; data: string }
  | { type: 'skills'; data: string[] }
  | { type: 'pending_action'; data: PendingAction }
  | { type: 'pending_plan'; data: PendingPlan };

export async function* streamChat(message: string, cycleId?: number, sessionId?: string): AsyncGenerator<StreamChunk> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = authStore.getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const resp = await fetch('/api/agent/chat/stream', {
    method: 'POST',
    headers,
    body: JSON.stringify({ message, cycle_id: cycleId, session_id: sessionId }),
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
        if (obj.content) yield { type: 'content', data: obj.content };
        if (obj.skills) yield { type: 'skills', data: obj.skills };
        if (obj.pending_action) yield { type: 'pending_action', data: obj.pending_action };
        if (obj.pending_plan) yield { type: 'pending_plan', data: obj.pending_plan };
      } catch (e) {
        if (e instanceof SyntaxError) continue;
        throw e;
      }
    }
  }
}

export async function getDailyAdvice(cycleId?: number): Promise<DailyAdviceResponse> {
  const res = await apiClient.get<DailyAdviceResponse>("/agent/daily", { params: { cycle_id: cycleId } });
  return res.data;
}

export async function generateReport(reportType: string = 'weekly', cycleId?: number): Promise<ReportResponse> {
  const res = await apiClient.post<ReportResponse>("/agent/report", { report_type: reportType, cycle_id: cycleId });
  return res.data;
}

export async function getAdviceHistory(params?: { cycle_id?: number; limit?: number }): Promise<AdviceHistoryItem[]> {
  const res = await apiClient.get<AdviceHistoryItem[]>("/agent/advice-history", { params });
  return res.data;
}

export async function getReportHistory(params?: { cycle_id?: number; limit?: number }): Promise<ReportListResponse> {
  const res = await apiClient.get<ReportListResponse>("/agent/report-history", { params });
  return res.data;
}

export async function listAppSkills(): Promise<AppSkillListResponse> {
  const res = await apiClient.get<AppSkillListResponse>('/agent/skills');
  return res.data;
}

// ── Conversation ──
export interface ConversationItem {
  id: number;
  session_id: string;
  status: string;
  created_at: string;
  last_active_at: string;
}

export interface ConversationMessage {
  id: number;
  role: string;
  content: string;
  skills?: string[];
  pending_action?: PendingAction | null;
  pending_plan?: PendingPlan | null;
  created_at: string;
}

export async function listConversations(limit?: number, simulateUserId?: string | null): Promise<ConversationItem[]> {
  const res = await apiClient.get<ConversationItem[]>("/agent/conversations", {
    params: { limit, simulate_user_id: simulateUserId || undefined },
  });
  return res.data;
}

export async function getConversationMessages(sessionId: string, simulateUserId?: string | null): Promise<ConversationMessage[]> {
  const res = await apiClient.get<ConversationMessage[]>(`/agent/conversations/${sessionId}/messages`, {
    params: { simulate_user_id: simulateUserId || undefined },
  });
  return res.data;
}
