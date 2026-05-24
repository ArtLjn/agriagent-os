import {create} from 'zustand';
import type {ChatMessage, DailyAdvice, ReportResponse} from '../api/types';
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
  sendMessage: (message: string, cycleId?: number) => Promise<void>;
  fetchDailyAdvice: (cycleId?: number) => Promise<void>;
  generateReport: (reportType: string, cycleId?: number) => Promise<void>;
  fetchWeather: () => Promise<void>;
  setCity: (name: string, lat?: number, lon?: number) => void;
  clearChat: () => void;
  clearError: () => void;
}

export const useAgentStore = create<AgentState>(set => ({
  messages: [],
  dailyAdvice: null,
  report: null,
  weather: null,
  loading: false,
  error: null,
  cityName: '苏州',
  cityLat: undefined,
  cityLon: undefined,

  sendMessage: async (message, cycleId) => {
    set(state => ({
      messages: [...state.messages, {role: 'user', content: message}],
      loading: true,
      error: null,
    }));
    try {
      const res = await agentApi.chat({message, cycle_id: cycleId});
      set(state => ({
        messages: [
          ...state.messages,
          {role: 'agent', content: res.data.reply},
        ],
        loading: false,
      }));
    } catch (err: any) {
      set(state => ({
        messages: [
          ...state.messages,
          {role: 'agent', content: `抱歉，出错了：${err.message}`},
        ],
        loading: false,
      }));
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
}));
