import AsyncStorage from "@react-native-async-storage/async-storage";
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type {
  ChatMessage,
  DailyAdvice,
  ReportResponse,
  ReportListItem,
  PendingAction,
} from "../api/types";
import { agentApi, weatherApi } from "../api/client";

export interface ChatSession {
  id: string;
  title: string;
  preview: string;
  category: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
}

const createSessionId = () =>
  `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const createEmptySession = (): ChatSession => {
  const now = Date.now();
  return {
    id: createSessionId(),
    title: "日常对话开启",
    preview: "可以直接问农事、记一笔、生成报告",
    category: "对话",
    createdAt: now,
    updatedAt: now,
    messages: [],
  };
};

const inferSessionCategory = (text: string) => {
  if (/天气|降雨|下雨|温度|打药|施药|风|雨/.test(text)) {
    return "天气";
  }
  if (/病虫害|虫|病|叶片|发黄|防治/.test(text)) {
    return "病虫害";
  }
  if (/报告|周报|月报|总结/.test(text)) {
    return "报告";
  }
  if (/记一笔|记账|成本|收入|支出|人工|费用/.test(text)) {
    return "记账";
  }
  if (/种植|浇水|施肥|采摘|播种|定植/.test(text)) {
    return "种植";
  }
  return "对话";
};

const createSessionTitle = (text: string) => {
  const cleanText = text.replace(/\s+/g, " ").trim();
  return cleanText.length > 18 ? `${cleanText.slice(0, 18)}...` : cleanText;
};

const ensureCurrentSession = (state: AgentState) => {
  const currentSession = state.sessions.find(
    (session) => session.id === state.sessionId
  );
  if (currentSession) {
    return {
      sessions: state.sessions,
      sessionId: state.sessionId,
      currentSession,
    };
  }
  const fallbackSession = createEmptySession();
  return {
    sessions: [fallbackSession, ...state.sessions],
    sessionId: fallbackSession.id,
    currentSession: fallbackSession,
  };
};

const updateCurrentSessionMessages = (
  state: AgentState,
  messages: ChatMessage[],
  patch?: Partial<Pick<ChatSession, "title" | "preview" | "category">>
) => {
  const { sessions, sessionId } = ensureCurrentSession(state);
  const now = Date.now();
  return {
    sessionId,
    messages,
    sessions: sessions.map((session) =>
      session.id === sessionId
        ? {
            ...session,
            ...patch,
            messages,
            updatedAt: now,
          }
        : session
    ),
  };
};

interface AgentState {
  messages: ChatMessage[];
  sessions: ChatSession[];
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
  startNewChatSession: () => void;
  switchChatSession: (sessionId: string) => void;
  fetchDailyAdvice: (cycleId?: number) => Promise<void>;
  refreshDailyAdvice: (cycleId?: number) => Promise<void>;
  generateReport: (reportType: string, cycleId?: number) => Promise<void>;
  fetchWeather: (days?: number) => Promise<void>;
  fetchReports: () => Promise<void>;
  deleteReports: (ids: number[]) => Promise<void>;
  loadCachedWeather: () => Promise<void>;
  setCity: (name: string, lat?: number, lon?: number) => Promise<void>;
  markPendingActionHandled: (actionId: string) => void;
  clearChat: () => void;
  clearError: () => void;
}

export const useAgentStore = create<AgentState, [["zustand/persist", unknown]]>(
  persist(
    (set) => {
      const initialSession = createEmptySession();
      return {
      messages: [],
      sessions: [initialSession],
      dailyAdvice: null,
      report: null,
      weather: null,
      loading: false,
      error: null,
      cityName: "苏州",
      cityLat: 31.3,
      cityLon: 120.62,
      reports: [],
      pendingAction: null,
      sessionId: initialSession.id,

      sendMessage: (message, cycleId) => {
        set((state) => ({
          ...updateCurrentSessionMessages(
            state,
            [
              ...state.messages,
              { role: "user", content: message },
              { role: "agent", content: "", is_streaming: true },
            ],
            {
              title: createSessionTitle(message),
              preview: createSessionTitle(message),
              category: inferSessionCategory(message),
            }
          ),
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
              if (last?.role === "agent") {
                msgs[msgs.length - 1] = {
                  ...last,
                  content: last.content + chunk,
                  is_streaming: true,
                };
              } else {
                msgs.push({
                  role: "agent",
                  content: chunk,
                  is_streaming: true,
                });
              }
              return updateCurrentSessionMessages(state, msgs);
            });
          },
          () => {
            set((state) => {
              const msgs = [...state.messages];
              const last = msgs[msgs.length - 1];
              if (last?.role === "agent") {
                msgs[msgs.length - 1] = { ...last, is_streaming: false };
              }
              return {
                ...updateCurrentSessionMessages(state, msgs),
                loading: false,
              };
            });
          },
          (err) => {
            set((state) => {
              const nextMessages = [
                ...state.messages.filter((m, index) => {
                  const isLast = index === state.messages.length - 1;
                  return !(isLast && m.role === "agent" && m.is_streaming);
                }),
                { role: "agent", content: `抱歉，出错了：${err}` },
              ];
              return {
                ...updateCurrentSessionMessages(state, nextMessages),
                loading: false,
              };
            });
          },
          (action) => {
            set((state) => {
              const msgs = [...state.messages];
              const last = msgs[msgs.length - 1];
              if (last?.role === "agent") {
                msgs[msgs.length - 1] = {
                  ...last,
                  pending_action: action,
                  is_streaming: false,
                };
              }
              return {
                ...updateCurrentSessionMessages(state, msgs),
                pendingAction: action,
              };
            });
          }
        );
      },

      startNewChatSession: () => {
        const newSession = createEmptySession();
        set((state) => ({
          sessions: [newSession, ...state.sessions],
          sessionId: newSession.id,
          messages: [],
          pendingAction: null,
          error: null,
        }));
      },

      switchChatSession: (nextSessionId) => {
        set((state) => {
          const session = state.sessions.find(({ id }) => id === nextSessionId);
          if (!session) {
            return {};
          }
          return {
            sessionId: session.id,
            messages: session.messages,
            pendingAction:
              session.messages
                .map((message) => message.pending_action)
                .filter(Boolean)
                .at(-1) ?? null,
            error: null,
          };
        });
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

      deleteReports: async (ids) => {
        set({ loading: true, error: null });
        try {
          await Promise.all(ids.map((id) => agentApi.deleteReport(id)));
          const res = await agentApi.getReportHistory();
          set({ reports: res.data.items, loading: false });
        } catch (err: any) {
          set({ error: err.message, loading: false });
          throw err;
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
          const requestCity = state.cityName;
          const requestLat = state.cityLat;
          const requestLon = state.cityLon;
          const res = await weatherApi.getForecast(
            days ?? 3,
            requestLat,
            requestLon,
            requestCity
          );
          if (useAgentStore.getState().cityName !== requestCity) {
            return;
          }
          const cacheKey = `weather_cache_${requestCity}`;
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
        await useAgentStore.getState().fetchWeather();
      },

      markPendingActionHandled: (actionId) =>
        set((state) => {
          const nextMessages = state.messages.map((message) =>
            message.pending_action?.action_id === actionId
              ? { ...message, pending_action_handled: true }
              : message
          );
          return updateCurrentSessionMessages(state, nextMessages);
        }),

      clearChat: () =>
        set((state) => {
          const newSession = createEmptySession();
          return {
            messages: [],
            sessions: [newSession, ...state.sessions],
            sessionId: newSession.id,
          };
        }),
      clearError: () => set({ error: null }),
    };
    },
    {
      name: "agent-store",
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({
        // 城市信息从 settingsStore 统一管理，agentStore 只做运行时缓存
        sessionId: state.sessionId,
        sessions: state.sessions,
      }),
    }
  )
);
