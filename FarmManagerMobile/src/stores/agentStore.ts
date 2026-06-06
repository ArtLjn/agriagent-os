import AsyncStorage from "@react-native-async-storage/async-storage";
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type {
  ChatMessage,
  DailyAdvice,
  ReportResponse,
  ReportListItem,
  PendingAction,
  ConversationListItem,
  ConversationMessageItem,
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

const isEmptyDraftSession = (session: ChatSession) =>
  session.messages.length === 0;

const normalizeBackendRole = (
  role: ConversationMessageItem["role"]
): ChatMessage["role"] => (role === "assistant" ? "agent" : role);

const mapBackendMessage = (message: ConversationMessageItem): ChatMessage => ({
  role: normalizeBackendRole(message.role),
  content: message.content,
});

const mapBackendConversation = (
  conversation: ConversationListItem,
  existing?: ChatSession
): ChatSession => {
  const updatedAt = new Date(conversation.last_active_at).getTime();
  const createdAt = new Date(conversation.created_at).getTime();
  return {
    id: conversation.session_id,
    title: conversation.title || existing?.title || "历史对话",
    preview:
      conversation.preview || existing?.preview || "点击查看这轮农事对话",
    category: conversation.category || existing?.category || "对话",
    createdAt: Number.isFinite(createdAt) ? createdAt : Date.now(),
    updatedAt: Number.isFinite(updatedAt) ? updatedAt : Date.now(),
    messages: existing?.messages || [],
  };
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

const updateSessionMessages = (
  state: AgentState,
  targetSessionId: string,
  updater: (messages: ChatMessage[]) => ChatMessage[],
  extraState?: Partial<Pick<AgentState, "loading" | "pendingAction">>
) => {
  const targetSession = state.sessions.find(
    (session) => session.id === targetSessionId
  );
  if (!targetSession) {
    return {};
  }
  const nextMessages = updater(targetSession.messages);
  const isActiveSession = state.sessionId === targetSessionId;
  const nextSessions = state.sessions.map((session) =>
    session.id === targetSessionId
      ? { ...session, messages: nextMessages, updatedAt: Date.now() }
      : session
  );
  return {
    sessions: nextSessions,
    ...(isActiveSession ? { messages: nextMessages } : {}),
    ...(extraState && isActiveSession ? extraState : {}),
    ...(extraState?.loading !== undefined
      ? { loading: extraState.loading }
      : {}),
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
  switchChatSession: (sessionId: string) => Promise<void>;
  fetchChatSessions: () => Promise<void>;
  loadChatSessionMessages: (sessionId: string) => Promise<void>;
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
              set((state) =>
                updateSessionMessages(state, sid, (messages) => {
                  const msgs = [...messages];
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
                  return msgs;
                })
              );
            },
            () => {
              set((state) =>
                updateSessionMessages(
                  state,
                  sid,
                  (messages) => {
                    const msgs = [...messages];
                    const last = msgs[msgs.length - 1];
                    if (last?.role === "agent") {
                      msgs[msgs.length - 1] = { ...last, is_streaming: false };
                    }
                    return msgs;
                  },
                  { loading: false }
                )
              );
            },
            (err) => {
              set((state) =>
                updateSessionMessages(
                  state,
                  sid,
                  (messages) => [
                    ...messages.filter((m, index) => {
                      const isLast = index === messages.length - 1;
                      return !(isLast && m.role === "agent" && m.is_streaming);
                    }),
                    { role: "agent", content: `抱歉，出错了：${err}` },
                  ],
                  { loading: false }
                )
              );
            },
            (action) => {
              set((state) =>
                updateSessionMessages(
                  state,
                  sid,
                  (messages) => {
                    const msgs = [...messages];
                    const last = msgs[msgs.length - 1];
                    if (last?.role === "agent") {
                      msgs[msgs.length - 1] = {
                        ...last,
                        pending_action: action,
                        is_streaming: false,
                      };
                    }
                    return msgs;
                  },
                  { pendingAction: action }
                )
              );
            }
          );
        },

        startNewChatSession: () => {
          const newSession = createEmptySession();
          set((state) => ({
            sessions: [
              newSession,
              ...state.sessions.filter(
                (session) => !isEmptyDraftSession(session)
              ),
            ],
            sessionId: newSession.id,
            messages: [],
            pendingAction: null,
            error: null,
          }));
        },

        switchChatSession: async (nextSessionId) => {
          set((state) => {
            const session = state.sessions.find(
              ({ id }) => id === nextSessionId
            );
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
          await useAgentStore.getState().loadChatSessionMessages(nextSessionId);
        },

        fetchChatSessions: async () => {
          try {
            const res = await agentApi.getConversations();
            set((state) => {
              const localById = new Map(
                state.sessions.map((session) => [session.id, session])
              );
              const remoteSessions = res.data.map((conversation) =>
                mapBackendConversation(
                  conversation,
                  localById.get(conversation.session_id)
                )
              );
              const remoteIds = new Set(
                remoteSessions.map((session) => session.id)
              );
              const localOnlySessions = state.sessions.filter(
                (session) =>
                  !remoteIds.has(session.id) && !isEmptyDraftSession(session)
              );
              const sessions = [...remoteSessions, ...localOnlySessions].sort(
                (a, b) => b.updatedAt - a.updatedAt
              );
              const activeSession =
                sessions.find((session) => session.id === state.sessionId) ||
                sessions[0];
              return {
                sessions,
                sessionId: activeSession?.id || state.sessionId,
                messages: activeSession?.messages || state.messages,
              };
            });
          } catch (_e) {
            // 会话历史加载失败时保留本地会话，避免影响聊天主流程
          }
        },

        loadChatSessionMessages: async (targetSessionId) => {
          try {
            const res = await agentApi.getConversationMessages(targetSessionId);
            const messages = res.data.map(mapBackendMessage);
            set((state) => {
              const nextSessions = state.sessions.map((session) =>
                session.id === targetSessionId
                  ? {
                      ...session,
                      messages,
                      title: messages[0]?.content
                        ? createSessionTitle(messages[0].content)
                        : session.title,
                      preview:
                        messages[messages.length - 1]?.content ||
                        session.preview,
                      category: messages[0]?.content
                        ? inferSessionCategory(messages[0].content)
                        : session.category,
                    }
                  : session
              );
              return {
                sessions: nextSessions,
                ...(state.sessionId === targetSessionId ? { messages } : {}),
              };
            });
          } catch (_e) {
            // 单个会话消息加载失败时保留已有缓存
          }
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
              sessions: [
                newSession,
                ...state.sessions.filter(
                  (session) => !isEmptyDraftSession(session)
                ),
              ],
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
        messages: state.messages,
        sessions: state.sessions,
      }),
    }
  )
);
