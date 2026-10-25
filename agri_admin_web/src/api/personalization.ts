import { isAxiosError } from "axios";
import type { AxiosRequestConfig, AxiosResponse } from "axios";
import apiClient, { parseApiError } from "./client";
import { personalizationDemoStore } from "./personalizationDemo";

export type ReplyStyle = "default" | "friendly" | "professional" | "efficient";
export type DetailLevel = "concise" | "balanced" | "detailed";
export type DisplayFormat = "auto" | "table" | "list";
export type ExecutionDetailLevel = "concise" | "detailed";
export type FieldSource = "explicit" | "inferred" | "default";

export type MemoryScope = "user" | "user_farm";
export type MemoryKind = "preference" | "habit" | "episode";
export type MemorySourceType = "explicit" | "inferred";
export type MemoryStatus = "candidate" | "active" | "superseded" | "expired" | "deleted";

export interface PersonalizationSettings {
  nickname: string;
  assistant_name: string;
  reply_style: ReplyStyle;
  detail_level: DetailLevel;
  display_format: DisplayFormat;
  custom_instructions: string;
  loading_greeting_enabled: boolean;
  execution_detail_level: ExecutionDetailLevel;
  auto_learn_enabled: boolean;
  use_saved_memories: boolean;
  memory_generation: number;
  revision: number;
  updated_at: string;
  business?: string | null;
  field_sources?: Partial<Record<
    | "nickname"
    | "assistant_name"
    | "reply_style"
    | "detail_level"
    | "display_format",
    FieldSource
  >>;
}

export type PersonalizationUpdatePayload = Partial<
  Pick<
    PersonalizationSettings,
    | "nickname"
    | "assistant_name"
    | "reply_style"
    | "detail_level"
    | "display_format"
    | "custom_instructions"
    | "loading_greeting_enabled"
    | "execution_detail_level"
    | "auto_learn_enabled"
    | "use_saved_memories"
  >
> & {
  expected_revision: number;
};

export interface MemoryRecord {
  memory_id: string;
  scope: MemoryScope;
  farm_id?: number | null;
  farm_name?: string | null;
  kind: MemoryKind;
  category?: MemoryCategory;
  key: string;
  value?: unknown;
  text: string;
  conditions: string[];
  source_type: MemorySourceType;
  source_message_ids: string[];
  evidence_count: number;
  confidence?: number | null;
  review_reason?: string;
  conflicts_with?: string | null;
  status: MemoryStatus;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface ListMemoriesParams {
  page?: number;
  page_size?: number;
  scope?: MemoryScope;
  kind?: MemoryKind;
  category?: MemoryCategory;
  status?: MemoryStatus;
}

export type MemoryCategory = "profile" | "preference" | "work" | "response" | "general";

export interface MemoryListResponse {
  items: MemoryRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface MemoryUpdatePayload {
  expected_revision: number;
  text?: string;
  status?: MemoryStatus;
  conditions?: string[];
}

export interface DeleteMemoryResponse {
  memory_id: string;
  deleted: boolean;
}

export interface ClearMemoriesResponse {
  cleared: number;
  memory_generation: number;
}



/** 只有显式关闭真实接口时才允许演示，网络错误绝不回退成保存成功。 */
function isApiEnabled(): boolean {
  return import.meta.env.VITE_PERSONALIZATION_API_ENABLED !== "false";
}

let demoMode = false;

export function isPersonalizationDemo(): boolean {
  return demoMode;
}

export function resetPersonalizationDemo(): void {
  demoMode = false;
  personalizationDemoStore.reset();
}

function silentConfig(config: AxiosRequestConfig = {}): AxiosRequestConfig {
  return { ...config, silent: true } as AxiosRequestConfig;
}

async function requestWithDemo<T>(
  request: () => Promise<AxiosResponse<T>>,
  fallback: () => T,
): Promise<T> {
  if (!isApiEnabled()) {
    demoMode = true;
    return fallback();
  }
  demoMode = false;
  const response = await request();
  return response.data;
}

export function personalizationErrorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const parsed = parseApiError(error.response?.data);
    if (parsed.message) return parsed.message;
    if (parsed.fields.length > 0) return parsed.fields.join("；");
    if (error.response?.status === 404) return "接口尚未接入";
    return "请求失败，请稍后重试";
  }
  return error instanceof Error ? error.message : "请求失败，请稍后重试";
}

export const personalizationApi = {
  createMemory: async (payload: { memory_id: string; key: string; text: string; scope: MemoryScope; conditions?: string[] }) => {
    if (!isApiEnabled()) throw new Error("演示模式不支持新增记忆，请连接真实服务");
    const response = await apiClient.post<MemoryRecord>("/agent/me/memories", payload, silentConfig());
    return response.data;
  },
  getSettings: (business?: string | null) =>
    requestWithDemo(
      () => apiClient.get<PersonalizationSettings>(
        "/agent/me/personalization",
        silentConfig(business ? { params: { business } } : {}),
      ),
      () => personalizationDemoStore.getSettings(),
    ),

  updateSettings: (payload: PersonalizationUpdatePayload, business?: string | null) =>
    requestWithDemo(
      () => apiClient.patch<PersonalizationSettings>(
        "/agent/me/personalization",
        payload,
        silentConfig(business ? { params: { business } } : {}),
      ),
      () => personalizationDemoStore.updateSettings(payload),
    ),

  listMemories: (params: ListMemoriesParams = {}) =>
    requestWithDemo(
      () => apiClient.get<MemoryListResponse>("/agent/me/memories", silentConfig({ params })),
      () => personalizationDemoStore.listMemories(params),
    ),

  updateMemory: (memoryId: string, payload: MemoryUpdatePayload) =>
    requestWithDemo(
      () => apiClient.patch<MemoryRecord>(
        `/agent/me/memories/${memoryId}`,
        payload,
        silentConfig(),
      ),
      () => personalizationDemoStore.updateMemory(memoryId, payload),
    ),

  deleteMemory: (memoryId: string) =>
    requestWithDemo(
      () => apiClient.delete<DeleteMemoryResponse>(
        `/agent/me/memories/${memoryId}`,
        silentConfig(),
      ),
      () => personalizationDemoStore.deleteMemory(memoryId),
    ),

  clearMemories: () =>
    requestWithDemo(
      () => apiClient.post<ClearMemoriesResponse>(
        "/agent/me/memories/clear",
        {},
        silentConfig(),
      ),
      () => personalizationDemoStore.clearMemories(),
    ),
};
