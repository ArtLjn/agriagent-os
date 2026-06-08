import apiClient from './client';

export type SmartFillSceneKey = 'crop.template' | 'crop.cycle' | 'ledger.record' | string;

export interface SmartFillScenario {
  key: SmartFillSceneKey;
  title: string;
  description: string;
  legacy_endpoint?: string | null;
  enabled: boolean;
  request_example: string;
}

export interface SmartFillScenarioListResponse {
  items: SmartFillScenario[];
}

export interface SmartFillParseResponse<TDraft = Record<string, unknown>> {
  scene: SmartFillSceneKey;
  draft: TDraft;
  missing_fields: string[];
  warnings: string[];
  trace_id?: string | null;
}

export async function listSmartFillScenarios(): Promise<SmartFillScenario[]> {
  const res = await apiClient.get<SmartFillScenarioListResponse>('/smart-fill/scenarios');
  return res.data.items;
}

export async function parseSmartFill<TDraft = Record<string, unknown>>(
  scene: SmartFillSceneKey,
  text: string,
  context: Record<string, unknown> = {},
): Promise<SmartFillParseResponse<TDraft>> {
  const res = await apiClient.post<SmartFillParseResponse<TDraft>>('/smart-fill/parse', {
    scene,
    text,
    context,
  });
  return res.data;
}
