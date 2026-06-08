import dayjs from 'dayjs';
import type { CropTemplateParseResponse } from '../../api/crops';
import type { CycleParseResponse } from '../../api/cycles';

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
