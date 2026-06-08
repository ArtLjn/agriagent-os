import dayjs from 'dayjs';
import type { CropTemplateParseResponse } from '../../api/crops';
import type { CycleParseResponse } from '../../api/cycles';
import type { CostParseResponse } from '../../api/costs';
import type { SmartFillScenario } from '../../api/smartFill';

export type SmartCreateResult =
  | { scene: 'crop.template'; draft: CropTemplateParseResponse }
  | { scene: 'crop.cycle'; draft: CycleParseResponse }
  | { scene: 'ledger.record'; draft: CostParseResponse }
  | { scene: 'unsupported'; sourceScene: string; draft: unknown };

export interface SmartCreateMeta {
  missingFields: string[];
  warnings: string[];
}

export const SMART_FILL_FALLBACK_SCENARIOS: SmartFillScenario[] = [
  {
    key: 'crop.template',
    title: '智能作物模板',
    description: '解析作物与生长阶段模板',
    legacy_endpoint: '/crops/templates/parse',
    enabled: true,
    request_example: '我要种 8424 西瓜，生成完整生长阶段',
  },
  {
    key: 'crop.cycle',
    title: '智能茬口',
    description: '解析种植茬口',
    legacy_endpoint: '/cycles/parse',
    enabled: true,
    request_example: '4 月 1 日在东棚种一茬 8424 西瓜',
  },
  {
    key: 'ledger.record',
    title: '智能记账',
    description: '解析收支记账记录',
    legacy_endpoint: '/costs/parse',
    enabled: true,
    request_example: '今天买复合肥 128.5 元，记到春季西瓜',
  },
];

export interface TemplateFormValues {
  name: string;
  variety?: string;
  stages: Array<{
    name: string;
    duration_days: number;
    key_tasks?: string;
  }>;
}

export interface CycleFormValues {
  name: string;
  crop_template_id?: number;
  start_date: dayjs.Dayjs;
  field_name?: string;
}

export function buildTemplateFormValues(parsed: CropTemplateParseResponse): TemplateFormValues {
  return {
    name: parsed.name,
    variety: parsed.variety ?? undefined,
    stages: parsed.stages.map((stage) => ({
      name: stage.name,
      duration_days: stage.duration_days,
      key_tasks: stage.key_tasks ?? undefined,
    })),
  };
}

export function buildCycleFormValues(parsed: CycleParseResponse): CycleFormValues {
  return {
    name: parsed.name,
    crop_template_id: parsed.crop_template_id ?? undefined,
    start_date: dayjs(parsed.start_date),
    field_name: parsed.field_name ?? undefined,
  };
}

export function normalizeSmartResult(scene: string, draft: unknown): SmartCreateResult {
  if (scene === 'crop.template') {
    return { scene, draft: draft as CropTemplateParseResponse };
  }
  if (scene === 'crop.cycle') {
    return { scene, draft: draft as CycleParseResponse };
  }
  if (scene === 'ledger.record') {
    return { scene, draft: draft as CostParseResponse };
  }
  return { scene: 'unsupported', sourceScene: scene, draft };
}
