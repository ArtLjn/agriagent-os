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
  key: string;
  value?: unknown;
  text: string;
  conditions: string[];
  source_type: MemorySourceType;
  source_message_ids: string[];
  evidence_count: number;
  confidence?: number | null;
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
  status?: MemoryStatus;
}

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

const NOT_IMPLEMENTED_STATUS = new Set([404, 405, 501]);

/**
 * 后端尚未实现个性化接口时，页面默认使用本地演示数据，避免请求落入
 * 根路径 MCP 中间件返回 401 并触发全局登录跳转。
 * 接口上线后设置 VITE_PERSONALIZATION_API_ENABLED=true 即可切换。
 */
function isApiEnabled(): boolean {
  return import.meta.env.VITE_PERSONALIZATION_API_ENABLED === "true";
}

let demoMode = false;

export function isPersonalizationDemo(): boolean {
  return demoMode;
}

export function resetPersonalizationDemo(): void {
  demoMode = false;
  personalizationDemoStore.reset();
}

function isEndpointMissing(error: unknown): boolean {
  return isAxiosError(error) && NOT_IMPLEMENTED_STATUS.has(error.response?.status ?? 0);
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
  try {
    const response = await request();
    demoMode = false;
    return response.data;
  } catch (error) {
    if (!isEndpointMissing(error)) {
      throw error;
    }
    demoMode = true;
    return fallback();
  }
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
  getSettings: () =>
    requestWithDemo(
      () => apiClient.get<PersonalizationSettings>("/me/personalization", silentConfig()),
      () => personalizationDemoStore.getSettings(),
    ),

  updateSettings: (payload: PersonalizationUpdatePayload) =>
    requestWithDemo(
      () => apiClient.patch<PersonalizationSettings>(
        "/me/personalization",
        payload,
        silentConfig(),
      ),
      () => personalizationDemoStore.updateSettings(payload),
    ),

  listMemories: (params: ListMemoriesParams = {}) =>
    requestWithDemo(
      () => apiClient.get<MemoryListResponse>("/me/memories", silentConfig({ params })),
      () => personalizationDemoStore.listMemories(params),
    ),

  updateMemory: (memoryId: string, payload: MemoryUpdatePayload) =>
    requestWithDemo(
      () => apiClient.patch<MemoryRecord>(
        `/me/memories/${memoryId}`,
        payload,
        silentConfig(),
      ),
      () => personalizationDemoStore.updateMemory(memoryId, payload),
    ),

  deleteMemory: (memoryId: string) =>
    requestWithDemo(
      () => apiClient.delete<DeleteMemoryResponse>(
        `/me/memories/${memoryId}`,
        silentConfig(),
      ),
      () => personalizationDemoStore.deleteMemory(memoryId),
    ),

  clearMemories: () =>
    requestWithDemo(
      () => apiClient.post<ClearMemoriesResponse>(
        "/me/memories/clear",
        {},
        silentConfig(),
      ),
      () => personalizationDemoStore.clearMemories(),
    ),
};
