import AsyncStorage from "@react-native-async-storage/async-storage";
import { useAgentStore } from "../agentStore";

jest.mock("@react-native-async-storage/async-storage", () => ({
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  multiGet: jest.fn(),
  multiSet: jest.fn(),
  multiRemove: jest.fn(),
  clear: jest.fn(),
  getAllKeys: jest.fn(),
}));

jest.mock("../../api/client", () => ({
  agentApi: {
    streamChat: jest.fn(),
    getDailyAdvice: jest.fn(),
    refreshAdvice: jest.fn(),
    generateReport: jest.fn(),
    getReportHistory: jest.fn(),
    getConversations: jest.fn(),
    getConversationMessages: jest.fn(),
  },
  weatherApi: {
    getForecast: jest.fn(),
  },
}));

const { agentApi, weatherApi } = require("../../api/client");

const MOCK_WEATHER_DATA = {
  daily: {
    time: ["2026-05-27", "2026-05-28", "2026-05-29"],
    temperature_2m_max: [28, 30, 25],
    temperature_2m_min: [18, 20, 16],
    precipitation_sum: [0, 2, 8],
  },
};

beforeEach(() => {
  jest.clearAllMocks();
  useAgentStore.setState({
    messages: [],
    sessions: [],
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
  });
});

describe("loadCachedWeather", () => {
  it("有缓存时立即设置 weather state，不设 loading", async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValueOnce(
      JSON.stringify(MOCK_WEATHER_DATA)
    );

    await useAgentStore.getState().loadCachedWeather();

    expect(AsyncStorage.getItem).toHaveBeenCalledWith("weather_cache_苏州");
    expect(useAgentStore.getState().weather).toEqual(MOCK_WEATHER_DATA);
    expect(useAgentStore.getState().loading).toBe(false);
  });

  it("无缓存时不修改 weather state", async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValueOnce(null);

    await useAgentStore.getState().loadCachedWeather();

    expect(useAgentStore.getState().weather).toBeNull();
  });

  it("AsyncStorage 异常时不崩溃", async () => {
    (AsyncStorage.getItem as jest.Mock).mockRejectedValueOnce(
      new Error("读取失败")
    );

    await expect(
      useAgentStore.getState().loadCachedWeather()
    ).resolves.not.toThrow();
  });
});

describe("fetchWeather", () => {
  it("成功后将数据写入 AsyncStorage 并更新 state", async () => {
    weatherApi.getForecast.mockResolvedValueOnce({
      data: MOCK_WEATHER_DATA,
    });

    await useAgentStore.getState().fetchWeather(3);

    expect(useAgentStore.getState().weather).toEqual(MOCK_WEATHER_DATA);
    expect(AsyncStorage.setItem).toHaveBeenCalledWith(
      "weather_cache_苏州",
      JSON.stringify(MOCK_WEATHER_DATA)
    );
    expect(useAgentStore.getState().loading).toBe(false);
  });

  it("失败时不覆盖已有的 weather 数据", async () => {
    useAgentStore.setState({ weather: MOCK_WEATHER_DATA });
    weatherApi.getForecast.mockRejectedValueOnce(new Error("网络错误"));

    await useAgentStore.getState().fetchWeather(3);

    expect(useAgentStore.getState().weather).toEqual(MOCK_WEATHER_DATA);
    expect(useAgentStore.getState().error).toBe("网络错误");
  });

  it("旧城市请求慢返回时不覆盖当前城市天气", async () => {
    let resolveSuzhou: (value: unknown) => void = () => {};
    weatherApi.getForecast
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveSuzhou = resolve;
        })
      )
      .mockResolvedValueOnce({
        data: { ...MOCK_WEATHER_DATA, location: "宁德" },
      });

    const suzhouRequest = useAgentStore.getState().fetchWeather(3);
    useAgentStore.setState({
      cityName: "宁德",
      cityLat: 26.66,
      cityLon: 119.53,
    });
    await useAgentStore.getState().fetchWeather(3);
    resolveSuzhou({ data: { ...MOCK_WEATHER_DATA, location: "苏州" } });
    await suzhouRequest;

    expect(useAgentStore.getState().weather).toEqual({
      ...MOCK_WEATHER_DATA,
      location: "宁德",
    });
  });
});

describe("setCity", () => {
  it("切换城市后自动加载缓存并发起网络请求", async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValueOnce(null);
    weatherApi.getForecast.mockResolvedValueOnce({
      data: MOCK_WEATHER_DATA,
    });

    await useAgentStore.getState().setCity("宁德", 26.66, 119.53);

    expect(useAgentStore.getState().cityName).toBe("宁德");
    expect(AsyncStorage.getItem).toHaveBeenCalledWith("weather_cache_宁德");
    expect(weatherApi.getForecast).toHaveBeenCalledTimes(1);
  });

  it("切换城市后的天气请求使用新城市参数", async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValueOnce(null);
    weatherApi.getForecast.mockResolvedValueOnce({
      data: MOCK_WEATHER_DATA,
    });

    await useAgentStore.getState().setCity("宁德", 26.66, 119.53);

    expect(weatherApi.getForecast).toHaveBeenCalledWith(
      3,
      26.66,
      119.53,
      "宁德"
    );
  });
});

describe("sendMessage", () => {
  it("发送后立即创建空助手消息，并在 chunk 到达时流式追加内容", () => {
    agentApi.streamChat.mockImplementationOnce(
      (_data: unknown, onChunk: (chunk: string) => void) => {
        expect(useAgentStore.getState().messages).toEqual([
          { role: "user", content: "今天怎么管理小麦？" },
          { role: "agent", content: "", is_streaming: true },
        ]);

        onChunk("先检查墒情");
        onChunk("，再看病虫害。");
      }
    );

    useAgentStore.getState().sendMessage("今天怎么管理小麦？");

    expect(useAgentStore.getState().messages).toEqual([
      { role: "user", content: "今天怎么管理小麦？" },
      {
        role: "agent",
        content: "先检查墒情，再看病虫害。",
        is_streaming: true,
      },
    ]);
  });

  it("流式完成后关闭助手消息的生成状态", () => {
    agentApi.streamChat.mockImplementationOnce(
      (
        _data: unknown,
        onChunk: (chunk: string) => void,
        onDone: () => void
      ) => {
        onChunk("建议今天少量浇水。");
        onDone();
      }
    );

    useAgentStore.getState().sendMessage("今天要浇水吗？");

    expect(useAgentStore.getState().messages).toEqual([
      { role: "user", content: "今天要浇水吗？" },
      {
        role: "agent",
        content: "建议今天少量浇水。",
        is_streaming: false,
      },
    ]);
    expect(useAgentStore.getState().loading).toBe(false);
  });
});

describe("chat sessions", () => {
  it("新建会话后保留旧会话消息，并切换到空的新会话", () => {
    useAgentStore.getState().sendMessage("今天怎么管理小麦？");
    const firstSessionId = useAgentStore.getState().sessionId;

    useAgentStore.getState().startNewChatSession();

    expect(useAgentStore.getState().sessionId).not.toBe(firstSessionId);
    expect(useAgentStore.getState().messages).toEqual([]);

    useAgentStore.getState().switchChatSession(firstSessionId);

    expect(useAgentStore.getState().messages).toEqual([
      { role: "user", content: "今天怎么管理小麦？" },
      { role: "agent", content: "", is_streaming: true },
    ]);
  });

  it("连续新建但未发送消息时，不累计空历史会话", () => {
    useAgentStore.getState().startNewChatSession();
    useAgentStore.getState().startNewChatSession();
    useAgentStore.getState().startNewChatSession();

    expect(useAgentStore.getState().messages).toEqual([]);
    expect(useAgentStore.getState().sessions).toHaveLength(1);
    expect(useAgentStore.getState().sessions[0].messages).toEqual([]);
  });

  it("已有真实会话后新建空对话，不把空草稿计入历史列表", () => {
    useAgentStore.getState().sendMessage("今天怎么管理小麦？");

    useAgentStore.getState().startNewChatSession();
    useAgentStore.getState().startNewChatSession();

    const nonEmptySessions = useAgentStore
      .getState()
      .sessions.filter((session) => session.messages.length > 0);
    const emptySessions = useAgentStore
      .getState()
      .sessions.filter((session) => session.messages.length === 0);

    expect(nonEmptySessions).toHaveLength(1);
    expect(emptySessions).toHaveLength(1);
  });

  it("发送消息时自动更新当前会话标题和预览", () => {
    useAgentStore.getState().sendMessage("今天适不适合打药？");

    const currentSession = useAgentStore
      .getState()
      .sessions.find(
        (session) => session.id === useAgentStore.getState().sessionId
      );

    expect(currentSession).toMatchObject({
      title: "今天适不适合打药？",
      preview: "今天适不适合打药？",
      category: "天气",
    });
  });

  it("切换会话后，旧会话的流式回复仍写回原会话", () => {
    let onChunk: (chunk: string) => void = () => {};
    agentApi.streamChat.mockImplementationOnce(
      (_data: unknown, chunkHandler: (chunk: string) => void) => {
        onChunk = chunkHandler;
      }
    );

    useAgentStore.getState().sendMessage("分析番茄叶片发黄");
    const firstSessionId = useAgentStore.getState().sessionId;
    useAgentStore.getState().startNewChatSession();

    onChunk("可能是缺肥或病害。");

    const firstSession = useAgentStore
      .getState()
      .sessions.find((session) => session.id === firstSessionId);

    expect(useAgentStore.getState().messages).toEqual([]);
    expect(firstSession?.messages).toEqual([
      { role: "user", content: "分析番茄叶片发黄" },
      {
        role: "agent",
        content: "可能是缺肥或病害。",
        is_streaming: true,
      },
    ]);
  });

  it("从后端加载会话列表并保留本地会话缓存", async () => {
    agentApi.getConversations.mockResolvedValueOnce({
      data: [
        {
          id: 1,
          session_id: "remote-session-1",
          status: "active",
          title: "今天适不适合打药？",
          preview: "今天风小，可以安排傍晚打药。",
          category: "天气",
          created_at: "2026-06-04T07:00:00",
          last_active_at: "2026-06-04T07:10:00",
        },
      ],
    });

    await useAgentStore.getState().fetchChatSessions();

    expect(useAgentStore.getState().sessions[0]).toMatchObject({
      id: "remote-session-1",
      title: "今天适不适合打药？",
      preview: "今天风小，可以安排傍晚打药。",
      category: "天气",
    });
  });

  it("切换后端会话时拉取消息，并将 assistant 映射为 agent", async () => {
    useAgentStore.setState({
      sessionId: "remote-session-2",
      sessions: [
        {
          id: "remote-session-2",
          title: "历史对话",
          preview: "",
          category: "对话",
          createdAt: Date.now(),
          updatedAt: Date.now(),
          messages: [],
        },
      ],
      messages: [],
    });
    agentApi.getConversationMessages.mockResolvedValueOnce({
      data: [
        {
          id: 1,
          role: "user",
          content: "明天天气如何",
          created_at: "2026-06-04T07:00:00",
        },
        {
          id: 2,
          role: "assistant",
          content: "明天适合通风，注意午后降雨。",
          created_at: "2026-06-04T07:01:00",
        },
      ],
    });

    await useAgentStore.getState().switchChatSession("remote-session-2");

    expect(useAgentStore.getState().messages).toEqual([
      { role: "user", content: "明天天气如何" },
      { role: "agent", content: "明天适合通风，注意午后降雨。" },
    ]);
    expect(useAgentStore.getState().sessions[0]).toMatchObject({
      title: "明天天气如何",
      category: "天气",
    });
  });

  it("切换后端会话时保留待确认动作，继续展示确认按钮", async () => {
    useAgentStore.setState({
      sessionId: "remote-session-3",
      sessions: [
        {
          id: "remote-session-3",
          title: "历史对话",
          preview: "",
          category: "对话",
          createdAt: Date.now(),
          updatedAt: Date.now(),
          messages: [],
        },
      ],
      messages: [],
    });
    agentApi.getConversationMessages.mockResolvedValueOnce({
      data: [
        {
          id: 1,
          role: "assistant",
          content: "需要我帮你创建一个「橘子」茬口吗？",
          pending_action: {
            action_id: "action-orange",
            skill_name: "create_crop_cycle",
            params: { 作物: "橘子" },
          },
          created_at: "2026-06-06T10:00:00",
        },
      ],
    });

    await useAgentStore.getState().switchChatSession("remote-session-3");

    expect(useAgentStore.getState().messages[0]).toMatchObject({
      role: "agent",
      pending_action: {
        action_id: "action-orange",
        skill_name: "create_crop_cycle",
      },
    });
  });
});

describe("markPendingActionHandled", () => {
  it("按 action_id 将待确认消息标记为已处理", () => {
    useAgentStore.setState({
      messages: [
        {
          role: "agent",
          content: "确认记账吗？",
          pending_action: {
            action_id: "action-1",
            skill_name: "create-cost-record",
            params: {},
          },
        },
      ],
    });

    useAgentStore.getState().markPendingActionHandled("action-1");

    expect(useAgentStore.getState().messages[0]).toMatchObject({
      pending_action_handled: true,
    });
  });
});
