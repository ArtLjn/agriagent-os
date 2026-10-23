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
    createMemory: vi.fn(),
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
  review_reason: "出现相反证据，暂停自动使用，等待用户确认",
  conflicts_with: "older-memory",
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
    expect(screen.getByText("出现相反证据，暂停自动使用，等待用户确认")).toBeInTheDocument();
    expect(screen.getByText("与已有记忆不一致，请核对")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /确\s*认/ }));

    await waitFor(() => {
      expect(mockedApi.updateMemory).toHaveBeenCalledWith("memory-2", {
        expected_revision: 2,
        status: "active",
      });
    });
    expect(await screen.findByText("已确认，这条记忆将用于后续对话")).toBeInTheDocument();
  });
  it("开启自动学习持久化控制，失败不伪装成功", async () => {
    const user = userEvent.setup();
    render(<AntdApp><AssistantSettings /></AntdApp>);
    await screen.findByPlaceholderText("例如：李师傅");
    await user.click(screen.getByRole("tab", { name: /记忆管理/ }));
    const toggle = await screen.findByRole("switch", { name: "自动学习偏好" });
    mockedApi.updateSettings.mockRejectedValueOnce(new Error("存储不可用"));
    await user.click(toggle);
    await waitFor(() => expect(mockedApi.updateSettings).toHaveBeenCalledWith({ expected_revision: 3, auto_learn_enabled: true }));
    await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "false"));
  });

  it("新增记忆提交内容、作用域和稳定标识", async () => {
    const user = userEvent.setup();
    mockedApi.createMemory.mockResolvedValue(activeMemory);
    render(<AntdApp><AssistantSettings /></AntdApp>);
    await screen.findByPlaceholderText("例如：李师傅");
    await user.click(screen.getByRole("tab", { name: /记忆管理/ }));
    await user.click(await screen.findByRole("button", { name: /新增记忆/ }));
    await user.type(screen.getByLabelText("记忆内容"), "先看异常成本");
    await user.click(screen.getByRole("button", { name: /^保\s*存$/ }));
    await waitFor(() => expect(mockedApi.createMemory).toHaveBeenCalledWith(expect.objectContaining({ text: "先看异常成本", scope: "user", conditions: [], memory_id: expect.any(String) })));
  });

  it("确认记忆后开关使用刷新后的聚合版本", async () => {
    const user = userEvent.setup();
    render(<AntdApp><AssistantSettings /></AntdApp>);
    await screen.findByPlaceholderText("例如：李师傅");
    await user.click(screen.getByRole("tab", { name: /记忆管理/ }));
    const toggle = await screen.findByRole("switch", { name: "使用已保存记忆" });
    await waitFor(() => expect(toggle).toBeEnabled());
    mockedApi.getSettings.mockResolvedValue({ ...settings, revision: 4 });
    await user.click(screen.getByRole("button", { name: /确\s*认/ }));
    await screen.findByText("已确认，这条记忆将用于后续对话");
    await waitFor(() => expect(mockedApi.getSettings).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(toggle).toBeEnabled());
    await user.click(toggle);
    await waitFor(() => expect(mockedApi.updateSettings).toHaveBeenCalledWith({ expected_revision: 4, use_saved_memories: false }));
  });

});
