import { beforeEach, describe, expect, it, vi } from "vitest";

import apiClient from "./client";
import {
  isPersonalizationDemo,
  personalizationApi,
  resetPersonalizationDemo,
} from "./personalization";

vi.mock("./client", () => ({
  default: {
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
  parseApiError: vi.fn(() => ({ fields: [] })),
}));

const mockedApiClient = vi.mocked(apiClient, true);

const settingsPayload = {
  nickname: "农友",
  assistant_name: "田掌柜",
  reply_style: "default" as const,
  detail_level: "balanced" as const,
  display_format: "auto" as const,
  custom_instructions: "",
  loading_greeting_enabled: true,
  execution_detail_level: "concise" as const,
  auto_learn_enabled: false,
  use_saved_memories: true,
  memory_generation: 1,
  revision: 3,
  updated_at: "2026-10-20T08:00:00Z",
};

describe("personalization api", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
    resetPersonalizationDemo();
  });

  it("默认演示模式不发起请求，避免未实现接口触发 401 跳登录", async () => {
    const settings = await personalizationApi.getSettings();

    expect(mockedApiClient.get).not.toHaveBeenCalled();
    expect(settings.assistant_name).toBe("田掌柜");
    expect(isPersonalizationDemo()).toBe(true);
  });

  it("启用真实接口后使用计划书约定的路径读写个性化设置", async () => {
    vi.stubEnv("VITE_PERSONALIZATION_API_ENABLED", "true");
    mockedApiClient.get.mockResolvedValueOnce({ data: settingsPayload } as never);
    mockedApiClient.patch.mockResolvedValueOnce({
      data: { ...settingsPayload, revision: 4 },
    } as never);

    const loaded = await personalizationApi.getSettings();
    const saved = await personalizationApi.updateSettings({
      expected_revision: 3,
      nickname: "李师傅",
    });

    expect(mockedApiClient.get).toHaveBeenCalledWith("/me/personalization", { silent: true });
    expect(mockedApiClient.patch).toHaveBeenCalledWith(
      "/me/personalization",
      { expected_revision: 3, nickname: "李师傅" },
      { silent: true },
    );
    expect(loaded.revision).toBe(3);
    expect(saved.revision).toBe(4);
    expect(isPersonalizationDemo()).toBe(false);
  });

  it("按作用域和状态读取记忆列表", async () => {
    vi.stubEnv("VITE_PERSONALIZATION_API_ENABLED", "true");
    mockedApiClient.get.mockResolvedValueOnce({
      data: { items: [], total: 0, page: 1, page_size: 20 },
    } as never);

    await personalizationApi.listMemories({
      page: 1,
      page_size: 20,
      scope: "user",
      status: "active",
    });

    expect(mockedApiClient.get).toHaveBeenCalledWith("/me/memories", {
      params: { page: 1, page_size: 20, scope: "user", status: "active" },
      silent: true,
    });
  });

  it("接口未接入时降级到本地演示数据并标记演示模式", async () => {
    vi.stubEnv("VITE_PERSONALIZATION_API_ENABLED", "true");
    mockedApiClient.get.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 404 },
    });

    const settings = await personalizationApi.getSettings();

    expect(settings.assistant_name).toBe("田掌柜");
    expect(isPersonalizationDemo()).toBe(true);
  });
});
