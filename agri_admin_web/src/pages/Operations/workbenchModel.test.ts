import { describe, expect, it } from 'vitest';

import { buildRequestBody, calculateLaborAmount, normalizeOperationOptions } from './workbenchModel';

describe('workbenchModel', () => {
  it('计算应付和未付人工金额', () => {
    expect(calculateLaborAmount(3, 120, 200)).toEqual({
      payable: 360,
      unpaid: 160,
    });
  });

  it('把作业类型按内置、作物和排序稳定展示', () => {
    const options = normalizeOperationOptions([
      { name: '采收', crop: '西瓜', is_builtin: true, sort_order: 20 },
      { name: '浇水', crop: null, is_builtin: true, sort_order: 10 },
      { name: '巡田', crop: null, is_builtin: false, sort_order: 1 },
    ]);

    expect(options.map((item) => item.label)).toEqual([
      '浇水 · 通用',
      '采收 · 西瓜',
      '巡田 · 自定义',
    ]);
  });

  it('移除空字段后生成请求体', () => {
    expect(buildRequestBody({
      name: '东棚',
      note: '',
      area_mu: null,
      status: 'active',
      unit_ids: [],
    })).toEqual({
      name: '东棚',
      status: 'active',
      unit_ids: [],
    });
  });
});
