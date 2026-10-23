import type {
  ClearMemoriesResponse,
  DeleteMemoryResponse,
  ListMemoriesParams,
  MemoryListResponse,
  MemoryRecord,
  MemoryUpdatePayload,
  PersonalizationSettings,
  PersonalizationUpdatePayload,
} from "./personalization";

const MINUTE = 60 * 1000;

function minutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * MINUTE).toISOString();
}

function createSettings(): PersonalizationSettings {
  return {
    nickname: "农友",
    assistant_name: "田掌柜",
    reply_style: "default",
    detail_level: "balanced",
    display_format: "auto",
    custom_instructions: "",
    loading_greeting_enabled: true,
    execution_detail_level: "concise",
    auto_learn_enabled: true,
    use_saved_memories: true,
    memory_generation: 1,
    revision: 3,
    updated_at: minutesAgo(2880),
    field_sources: {
      nickname: "explicit",
      reply_style: "default",
      detail_level: "default",
      display_format: "default",
    },
  };
}

function createMemories(): MemoryRecord[] {
  return [
    {
      memory_id: "demo-memory-1",
      scope: "user",
      kind: "preference",
      key: "response.cost_report",
      text: "看成本报表时先给一句话结论，再列出明细。",
      conditions: ["成本报表"],
      source_type: "explicit",
      source_message_ids: ["demo-message-1"],
      evidence_count: 1,
      status: "active",
      revision: 1,
      created_at: minutesAgo(4320),
      updated_at: minutesAgo(4200),
    },
    {
      memory_id: "demo-memory-2",
      scope: "user_farm",
      farm_id: 1,
      farm_name: "示范农场",
      kind: "habit",
      key: "workflow.morning_plan",
      text: "每天早上先看农事排班，再处理其他事项。",
      conditions: ["每日排程"],
      source_type: "inferred",
      source_message_ids: ["demo-message-2", "demo-message-3", "demo-message-4"],
      evidence_count: 3,
      confidence: 0.82,
      status: "candidate",
      revision: 2,
      created_at: minutesAgo(1200),
      updated_at: minutesAgo(300),
    },
    {
      memory_id: "demo-memory-3",
      scope: "user",
      kind: "preference",
      key: "display.format",
      text: "对比类信息优先用表格展示。",
      conditions: [],
      source_type: "explicit",
      source_message_ids: ["demo-message-5"],
      evidence_count: 1,
      status: "active",
      revision: 1,
      created_at: minutesAgo(10080),
      updated_at: minutesAgo(10080),
    },
    {
      memory_id: "demo-memory-4",
      scope: "user",
      kind: "preference",
      key: "response.terminology",
      text: "解释专业术语时尽量用通俗说法。",
      conditions: ["农技解释"],
      source_type: "inferred",
      source_message_ids: ["demo-message-6", "demo-message-7"],
      evidence_count: 2,
      confidence: 0.68,
      status: "candidate",
      revision: 1,
      created_at: minutesAgo(720),
      updated_at: minutesAgo(720),
    },
    {
      memory_id: "demo-memory-5",
      scope: "user_farm",
      farm_id: 1,
      farm_name: "示范农场",
      kind: "episode",
      key: "episode.seedling_notice",
      text: "上周提到过三号棚的辣椒苗需要在本周补一次水肥。",
      conditions: ["三号棚"],
      source_type: "inferred",
      source_message_ids: ["demo-message-8"],
      evidence_count: 1,
      confidence: 0.45,
      status: "expired",
      revision: 1,
      created_at: minutesAgo(20000),
      updated_at: minutesAgo(15000),
    },
  ];
}

interface DemoState {
  settings: PersonalizationSettings;
  memories: MemoryRecord[];
}

let state: DemoState = {
  settings: createSettings(),
  memories: createMemories(),
};

function nextRevision(revision: number): number {
  return revision + 1;
}

export const personalizationDemoStore = {
  reset() {
    state = {
      settings: createSettings(),
      memories: createMemories(),
    };
  },

  getSettings(): PersonalizationSettings {
    return structuredClone(state.settings);
  },

  updateSettings(payload: PersonalizationUpdatePayload): PersonalizationSettings {
    const { expected_revision, ...changes } = payload;
    if (expected_revision !== state.settings.revision) {
      throw new Error("设置已被其他页面更新，请重新加载后再保存");
    }
    state.settings = {
      ...state.settings,
      ...changes,
      revision: nextRevision(state.settings.revision),
      updated_at: new Date().toISOString(),
    };
    return structuredClone(state.settings);
  },

  listMemories(params: ListMemoriesParams): MemoryListResponse {
    const page = params.page ?? 1;
    const pageSize = params.page_size ?? 20;
    const filtered = state.memories.filter((memory) => {
      if (memory.status === "deleted") return false;
      if (params.scope && memory.scope !== params.scope) return false;
      if (params.kind && memory.kind !== params.kind) return false;
      if (params.category && (memory.category ?? "general") !== params.category) return false;
      if (params.status && memory.status !== params.status) return false;
      return true;
    });
    const start = (page - 1) * pageSize;
    return {
      items: structuredClone(filtered.slice(start, start + pageSize)),
      total: filtered.length,
      page,
      page_size: pageSize,
    };
  },

  updateMemory(memoryId: string, payload: MemoryUpdatePayload): MemoryRecord {
    const index = state.memories.findIndex((memory) => memory.memory_id === memoryId);
    if (index < 0) {
      throw new Error("记忆不存在或已被删除");
    }
    const current = state.memories[index];
    const { expected_revision, ...changes } = payload;
    if (expected_revision !== current.revision) {
      throw new Error("记忆已被更新，请刷新后再试");
    }
    const next: MemoryRecord = {
      ...current,
      ...changes,
      source_type: "explicit",
      revision: nextRevision(current.revision),
      updated_at: new Date().toISOString(),
    };
    state.memories[index] = next;
    return structuredClone(next);
  },

  deleteMemory(memoryId: string): DeleteMemoryResponse {
    const index = state.memories.findIndex((memory) => memory.memory_id === memoryId);
    if (index >= 0) {
      state.memories.splice(index, 1);
    }
    return { memory_id: memoryId, deleted: true };
  },

  clearMemories(): ClearMemoriesResponse {
    const cleared = state.memories.length;
    state.memories = [];
    state.settings = {
      ...state.settings,
      memory_generation: nextRevision(state.settings.memory_generation),
      revision: nextRevision(state.settings.revision),
      updated_at: new Date().toISOString(),
    };
    return {
      cleared,
      memory_generation: state.settings.memory_generation,
    };
  },
};
