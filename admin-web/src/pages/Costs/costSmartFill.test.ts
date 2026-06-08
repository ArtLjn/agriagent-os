import dayjs from 'dayjs';
import { describe, expect, it } from 'vitest';

import { buildCostFormValues } from './costSmartFill';

describe('buildCostFormValues', () => {
  it('把智能记账解析结果转换成表单值', () => {
    const values = buildCostFormValues({
      record_type: 'cost',
      category: '肥料',
      amount: '128.50',
      record_date: '2026-06-07',
      note: '买了复合肥',
    });

    expect(values).toMatchObject({
      record_type: 'cost',
      category: '肥料',
      amount: 128.5,
      note: '买了复合肥',
    });
    expect(dayjs.isDayjs(values.record_date)).toBe(true);
    expect(values.record_date.format('YYYY-MM-DD')).toBe('2026-06-07');
  });
});
