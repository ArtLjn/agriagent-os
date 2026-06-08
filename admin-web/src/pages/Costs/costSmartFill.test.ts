import dayjs from 'dayjs';
import { describe, expect, it } from 'vitest';

import { buildCostCreatePayload, buildCostFormValues } from './costSmartFill';

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

  it('回填结构化赊账字段', () => {
    const values = buildCostFormValues({
      record_type: 'cost',
      category: '种子',
      amount: '195.30',
      record_date: '2026-06-08',
      note: '买苹果种子，向王秉着赊账',
      record_subtype: '赊账',
      counterparty: '王秉着',
      due_date: '2026-06-30',
    });

    expect(values).toMatchObject({
      record_subtype: '赊账',
      counterparty: '王秉着',
      note: '买苹果种子，向王秉着赊账',
    });
    expect(values.due_date?.format('YYYY-MM-DD')).toBe('2026-06-30');
    expect(buildCostCreatePayload(values, 2)).toMatchObject({
      cycle_id: 2,
      record_subtype: '赊账',
      counterparty: '王秉着',
      due_date: '2026-06-30',
    });
  });
});
