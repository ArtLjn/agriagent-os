import dayjs from 'dayjs';
import type { CropTemplateParseResponse } from '../../api/crops';
import type { CycleParseResponse } from '../../api/cycles';
import type { CostParseResponse } from '../../api/costs';
import type { SmartFillScenario, SmartFillSceneKey } from '../../api/smartFill';

export type SupportedSmartCreateScene = 'crop.template' | 'crop.cycle' | 'ledger.record';

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

const MONEY_OR_LEDGER_PATTERN =
  /(收入|支出|记账|账|买|购买|购入|卖|出售|收了|收到|付了|支付|花了|赊账|赊了|欠账|欠款|未付|未收款|还款|结清|工资|人工费|化肥|肥料|农药|种子|柴油|\d+(?:\.\d+)?\s*(?:元|块|块钱|￥|¥)|[一二两三四五六七八九十百千万]+(?:元|块|块钱))/;
const CYCLE_PATTERN =
  /(茬口|一茬|春茬|夏茬|秋茬|冬茬|地块|田块|棚|大棚|东棚|西棚|南棚|北棚|露天|亩|种植|播种|定植|移栽|开种|开始种|种一茬|\d{1,2}\s*月\s*\d{1,2}\s*(?:日|号)?)/;
const TEMPLATE_PATTERN =
  /(模板|作物模板|生长阶段|完整生长|生成.*阶段|阶段模板|建模板|新建模板|创建模板|新增模板)/;

export function inferSmartFillScene(text: string): SupportedSmartCreateScene {
  const normalized = text.trim().replace(/\s+/g, '');
  if (MONEY_OR_LEDGER_PATTERN.test(normalized)) {
    return 'ledger.record';
  }
  if (TEMPLATE_PATTERN.test(normalized)) {
    return 'crop.template';
  }
  if (CYCLE_PATTERN.test(normalized)) {
    return 'crop.cycle';
  }
  return 'crop.template';
}

export function isSupportedSmartCreateScene(scene: SmartFillSceneKey): scene is SupportedSmartCreateScene {
  return scene === 'crop.template' || scene === 'crop.cycle' || scene === 'ledger.record';
}

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
