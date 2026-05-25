import AsyncStorage from '@react-native-async-storage/async-storage';
import {create} from 'zustand';
import {persist, createJSONStorage} from 'zustand/middleware';
import type {ChatMessage, DailyAdvice, ReportResponse, ReportListItem} from '../api/types';
import {agentApi, weatherApi} from '../api/client';

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
  sendMessage: (message: string, cycleId?: number) => Promise<void>;
  fetchDailyAdvice: (cycleId?: number) => Promise<void>;
  refreshDailyAdvice: (cycleId?: number) => Promise<void>;
  generateReport: (reportType: string, cycleId?: number) => Promise<void>;
  fetchWeather: () => Promise<void>;
  fetchReports: () => Promise<void>;
  setCity: (name: string, lat?: number, lon?: number) => void;
  clearChat: () => void;
  clearError: () => void;
}

export const useAgentStore = create<AgentState, [['zustand/persist', unknown]]>(
  persist(
    set => ({
      messages: [],
      dailyAdvice: null,
      report: null,
      weather: null,
      loading: false,
      error: null,
      cityName: '苏州',
      cityLat: 31.30,
      cityLon: 120.62,
      reports: [],

  sendMessage: async (message, cycleId) => {
    set(state => ({
      messages: [...state.messages, {role: 'user', content: message}],
      loading: true,
      error: null,
    }));
    try {
      let reply = '';
      await agentApi.streamChat(
        {message, cycle_id: cycleId},
        chunk => {
          reply += chunk;
          set(state => {
            const msgs = [...state.messages];
            const lastIdx = msgs.length - 1;
            if (lastIdx >= 0 && msgs[lastIdx].role === 'agent') {
              msgs[lastIdx] = {role: 'agent', content: reply};
            } else {
              msgs.push({role: 'agent', content: reply});
            }
            return {messages: msgs};
          });
        },
      );
      set({loading: false});
    } catch (err: any) {
      set(state => {
        const msgs = [...state.messages];
        const lastIdx = msgs.length - 1;
        if (lastIdx >= 0 && msgs[lastIdx].role === 'agent' && !msgs[lastIdx].content) {
          msgs[lastIdx] = {role: 'agent', content: `抱歉，出错了：${err.message}`};
        } else {
          msgs.push({role: 'agent', content: `抱歉，出错了：${err.message}`});
        }
        return {messages: msgs, loading: false};
      });
    }
  },

  fetchDailyAdvice: async cycleId => {
    set({loading: true, error: null});
    try {
      const res = await agentApi.getDailyAdvice(cycleId);
      set({dailyAdvice: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  refreshDailyAdvice: async cycleId => {
    set({loading: true, error: null});
    try {
      const res = await agentApi.refreshAdvice(cycleId);
      set({dailyAdvice: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  fetchReports: async () => {
    try {
      const res = await agentApi.getReportHistory();
      set({reports: res.data.items});
    } catch (_e) {
      // 报告列表加载失败不阻塞主流程
    }
  },

  generateReport: async (reportType, cycleId) => {
    set({loading: true, error: null});
    try {
      const res = await agentApi.generateReport({
        report_type: reportType,
        cycle_id: cycleId,
      });
      set({report: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  fetchWeather: async () => {
    set({loading: true, error: null});
    try {
      const state = useAgentStore.getState();
      const res = await weatherApi.getForecast(3, state.cityLat, state.cityLon);
      set({weather: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  setCity: (name, lat, lon) => set({cityName: name, cityLat: lat, cityLon: lon}),

  clearChat: () => set({messages: []}),
  clearError: () => set({error: null}),
}),
{
  name: 'agent-store',
  storage: createJSONStorage(() => AsyncStorage),
  partialize: (state) => ({
    cityName: state.cityName,
    cityLat: state.cityLat,
    cityLon: state.cityLon,
  }),
},
));
