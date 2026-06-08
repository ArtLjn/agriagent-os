import dayjs from 'dayjs';
import { describe, expect, it } from 'vitest';

import { buildCycleFormValues, buildTemplateFormValues } from './smartCreateModel';

describe('smartCreateModel', () => {
  it('把智能作物模板解析结果转换为表单值', () => {
    expect(buildTemplateFormValues({
      name: '西瓜',
      variety: '8424',
      stages: [
        { name: '育苗期', duration_days: 25, order_index: 1, key_tasks: '控温' },
      ],
    })).toEqual({
      name: '西瓜',
      variety: '8424',
      stages: [
        { name: '育苗期', duration_days: 25, key_tasks: '控温' },
      ],
    });
  });

  it('把智能茬口解析结果转换为表单值', () => {
    const values = buildCycleFormValues({
      name: '春季西瓜',
      crop_template_id: 3,
      start_date: '2026-04-01',
      field_name: '东棚',
    });

    expect(values).toMatchObject({
      name: '春季西瓜',
      crop_template_id: 3,
      field_name: '东棚',
    });
    expect(dayjs.isDayjs(values.start_date)).toBe(true);
    expect(values.start_date.format('YYYY-MM-DD')).toBe('2026-04-01');
  });
});
