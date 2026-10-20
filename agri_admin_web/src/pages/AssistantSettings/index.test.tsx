import { App as AntdApp } from "antd";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  personalizationApi,
  type MemoryRecord,
  type PersonalizationSettings,
} from "../../api/personalization";
import AssistantSettings from "./index";

vi.mock("../../api/personalization", () => ({
  personalizationApi: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    listMemories: vi.fn(),
    updateMemory: vi.fn(),
    deleteMemory: vi.fn(),
    clearMemories: vi.fn(),
  },
  personalizationErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : "请求失败",
  isPersonalizationDemo: () => false,
}));

const mockedApi = vi.mocked(personalizationApi, true);

const settings: PersonalizationSettings = {
  nickname: "农友",
  assistant_name: "田掌柜",
  reply_style: "default",
  detail_level: "balanced",
  display_format: "auto",
  custom_instructions: "",
  loading_greeting_enabled: true,
  execution_detail_level: "concise",
  auto_learn_enabled: false,
  use_saved_memories: true,
  memory_generation: 1,
  revision: 3,
  updated_at: "2026-10-20T08:00:00Z",
  field_sources: { nickname: "explicit" },
};

const activeMemory: MemoryRecord = {
  memory_id: "memory-1",
  scope: "user",
  kind: "preference",
  key: "response.cost_report",
  text: "看成本报表时先给一句话结论，再列出明细。",
  conditions: ["成本报表"],
  source_type: "explicit",
  source_message_ids: ["message-1"],
  evidence_count: 1,
  status: "active",
  revision: 1,
  created_at: "2026-10-18T08:00:00Z",
  updated_at: "2026-10-18T08:00:00Z",
};

const candidateMemory: MemoryRecord = {
  memory_id: "memory-2",
  scope: "user_farm",
  farm_id: 1,
  farm_name: "示范农场",
  kind: "habit",
  key: "workflow.morning_plan",
  text: "每天早上先看农事排班，再处理其他事项。",
  conditions: ["每日排程"],
  source_type: "inferred",
  source_message_ids: ["message-2", "message-3"],
  evidence_count: 3,
  confidence: 0.82,
  status: "candidate",
  revision: 2,
  created_at: "2026-10-19T08:00:00Z",
  updated_at: "2026-10-19T08:00:00Z",
};

describe("AssistantSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.getSettings.mockResolvedValue(settings);
    mockedApi.updateSettings.mockResolvedValue({ ...settings, revision: 4 });
    mockedApi.listMemories.mockResolvedValue({
      items: [activeMemory, candidateMemory],
      total: 2,
      page: 1,
      page_size: 20,
    });
    mockedApi.updateMemory.mockResolvedValue({
      ...candidateMemory,
      status: "active",
      source_type: "explicit",
      revision: 3,
    });
  });

  it("加载个性化设置并按版本保存修改", async () => {
    const user = userEvent.setup();

    render(
      <AntdApp>
        <AssistantSettings />
      </AntdApp>,
    );

    const nicknameInput = await screen.findByPlaceholderText("例如：李师傅");
    await user.clear(nicknameInput);
    await user.type(nicknameInput, "李师傅");
    await user.click(screen.getByRole("button", { name: /保存设置/ }));

    await waitFor(() => {
      expect(mockedApi.updateSettings).toHaveBeenCalledWith({
        expected_revision: 3,
        nickname: "李师傅",
        assistant_name: "田掌柜",
        reply_style: "default",
        detail_level: "balanced",
        display_format: "auto",
        custom_instructions: "",
        loading_greeting_enabled: true,
        execution_detail_level: "concise",
      });
    });
    expect(await screen.findByText("设置已保存，下一轮对话生效")).toBeInTheDocument();
  });

  it("展示记忆列表并支持确认候选记忆", async () => {
    const user = userEvent.setup();

    render(
      <AntdApp>
        <AssistantSettings />
      </AntdApp>,
    );

    await screen.findByPlaceholderText("例如：李师傅");
    await user.click(screen.getByRole("tab", { name: /记忆管理/ }));

    expect(
      await screen.findByText("看成本报表时先给一句话结论，再列出明细。"),
    ).toBeInTheDocument();
    expect(screen.getByText("每天早上先看农事排班，再处理其他事项。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /确\s*认/ }));

    await waitFor(() => {
      expect(mockedApi.updateMemory).toHaveBeenCalledWith("memory-2", {
        expected_revision: 2,
        status: "active",
      });
    });
    expect(await screen.findByText("已确认，这条记忆将用于后续对话")).toBeInTheDocument();
  });
});
