import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type {
  ChatMessage,
  DailyAdvice,
  ReportResponse,
  ReportListItem,
  PendingAction,
} from '../api/types';
import { agentApi, weatherApi } from '../api/client';

interface AgentState {
  messages: ChatMessage[];
  dailyAdvice: DailyAdvice | null;
  report: ReportResponse | null;
  weather: any | null;
  loading: boolean;
  error: string | null;
  cityName: string;
  cityLat: number | undefined;
  cityLon: number | undefined;
  reports: ReportListItem[];
  pendingAction: PendingAction | null;
  sessionId: string;
  sendMessage: (message: string, cycleId?: number) => void;
  fetchDailyAdvice: (cycleId?: number) => Promise<void>;
  refreshDailyAdvice: (cycleId?: number) => Promise<void>;
  generateReport: (reportType: string, cycleId?: number) => Promise<void>;
  fetchWeather: (days?: number) => Promise<void>;
  fetchReports: () => Promise<void>;
  loadCachedWeather: () => Promise<void>;
  setCity: (name: string, lat?: number, lon?: number) => Promise<void>;
  clearChat: () => void;
  clearError: () => void;
}

export const useAgentStore = create<AgentState, [['zustand/persist', unknown]]>(
  persist(
    (set) => ({
      messages: [],
      dailyAdvice: null,
      report: null,
      weather: null,
      loading: false,
      error: null,
      cityName: '苏州',
      cityLat: 31.3,
      cityLon: 120.62,
      reports: [],
      pendingAction: null,
      sessionId: `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,

      sendMessage: (message, cycleId) => {
        set((state) => ({
          messages: [...state.messages, { role: 'user', content: message }],
          loading: true,
          error: null,
          pendingAction: null,
        }));
        const sid = useAgentStore.getState().sessionId;
        agentApi.streamChat(
          { message, cycle_id: cycleId, session_id: sid },
          (chunk) => {
            set((state) => {
              const msgs = [...state.messages];
              const last = msgs[msgs.length - 1];
              if (last?.role === 'agent') {
                msgs[msgs.length - 1] = {
                  ...last,
                  content: last.content + chunk,
                };
              } else {
                msgs.push({ role: 'agent', content: chunk });
              }
              return { messages: msgs };
            });
          },
          () => set({ loading: false }),
          (err) => {
            set((state) => ({
              messages: [
                ...state.messages.filter(
                  (m) => m.role !== 'agent' || m.content
                ),
                { role: 'agent', content: `抱歉，出错了：${err}` },
              ],
              loading: false,
            }));
          },
          (action) => {
            set((state) => {
              const msgs = [...state.messages];
              const last = msgs[msgs.length - 1];
              if (last?.role === 'agent') {
                msgs[msgs.length - 1] = { ...last, pending_action: action };
              }
              return { messages: msgs, pendingAction: action };
            });
          }
        );
      },

      fetchDailyAdvice: async (cycleId) => {
        set({ loading: true, error: null });
        try {
          const res = await agentApi.getDailyAdvice(cycleId);
          set({ dailyAdvice: res.data, loading: false });
        } catch (err: any) {
          set({ error: err.message, loading: false });
        }
      },

      refreshDailyAdvice: async (cycleId) => {
        set({ loading: true, error: null });
        try {
          const res = await agentApi.refreshAdvice(cycleId);
          set({ dailyAdvice: res.data, loading: false });
        } catch (err: any) {
          set({ error: err.message, loading: false });
        }
      },

      fetchReports: async () => {
        try {
          const res = await agentApi.getReportHistory();
          set({ reports: res.data.items });
        } catch (_e) {
          // 报告列表加载失败不阻塞主流程
        }
      },

      generateReport: async (reportType, cycleId) => {
        set({ loading: true, error: null });
        try {
          const res = await agentApi.generateReport({
            report_type: reportType,
            cycle_id: cycleId,
          });
          set({ report: res.data, loading: false });
        } catch (err: any) {
          set({ error: err.message, loading: false });
        }
      },

      fetchWeather: async (days?: number) => {
        const currentWeather = useAgentStore.getState().weather;
        if (!currentWeather) {
          set({ loading: true, error: null });
        }
        try {
          const state = useAgentStore.getState();
          const res = await weatherApi.getForecast(
            days ?? 3,
            state.cityLat,
            state.cityLon,
            state.cityName
          );
          const cacheKey = `weather_cache_${state.cityName}`;
          await AsyncStorage.setItem(cacheKey, JSON.stringify(res.data));
          set({ weather: res.data, loading: false });
        } catch (err: any) {
          set({ error: err.message, loading: false });
        }
      },

      loadCachedWeather: async () => {
        try {
          const cityName = useAgentStore.getState().cityName;
          const cacheKey = `weather_cache_${cityName}`;
          const cached = await AsyncStorage.getItem(cacheKey);
          if (cached) {
            set({ weather: JSON.parse(cached) });
          }
        } catch (_e) {
          // 缓存读取失败不影响主流程
        }
      },

      setCity: async (name, lat, lon) => {
        set({ cityName: name, cityLat: lat, cityLon: lon });
        await useAgentStore.getState().loadCachedWeather();
        useAgentStore.getState().fetchWeather();
      },

      clearChat: () => set({
        messages: [],
        sessionId: `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      }),
      clearError: () => set({ error: null }),
    }),
    {
      name: 'agent-store',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({
        cityName: state.cityName,
        cityLat: state.cityLat,
        cityLon: state.cityLon,
      }),
    }
  )
);
