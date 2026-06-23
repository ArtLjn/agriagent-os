import dayjs from 'dayjs';
import { describe, expect, it } from 'vitest';

import { buildCostListParams } from './costFilters';

describe('buildCostListParams', () => {
  it('把月份范围转换成记录日期闭区间', () => {
    const params = buildCostListParams({
      selectedCycle: 7,
      page: 2,
      size: 10,
      monthRange: [dayjs('2026-05-15'), dayjs('2026-07-02')],
    });

    expect(params).toEqual({
      cycle_id: 7,
      page: 2,
      size: 10,
      date_from: '2026-05-01',
      date_to: '2026-07-31',
    });
  });

  it('未选择月份范围时不追加日期参数', () => {
    expect(buildCostListParams({ page: 1, size: 20, monthRange: null })).toEqual({
      page: 1,
      size: 20,
    });
  });
});
