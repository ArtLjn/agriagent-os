import dayjs from 'dayjs';
import { describe, expect, it } from 'vitest';

import {
  buildCycleFormValues,
  buildTemplateFormValues,
  inferSmartFillScene,
  normalizeSmartResult,
} from './smartCreateModel';

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

  it('按统一智能填写场景归一化已支持的解析结果', () => {
    const result = normalizeSmartResult('ledger.record', {
      record_type: 'cost',
      category: 'fertilizer',
      amount: '128.50',
      record_date: '2026-04-01',
      note: '复合肥',
    });

    expect(result.scene).toBe('ledger.record');
    if (result.scene === 'ledger.record') {
      expect(result.draft.amount).toBe('128.50');
    }
  });

  it('未知智能填写场景保留原始草稿用于预览', () => {
    const draft = { foo: 'bar' };
    const result = normalizeSmartResult('inventory.item', draft);

    expect(result).toEqual({
      scene: 'unsupported',
      sourceScene: 'inventory.item',
      draft,
    });
  });

  it('根据语义判断作物模板解析场景', () => {
    expect(inferSmartFillScene('我要种8424西瓜，生成完整生长阶段')).toBe('crop.template');
    expect(inferSmartFillScene('帮我新建一个番茄模板')).toBe('crop.template');
  });

  it('根据语义判断茬口解析场景', () => {
    expect(inferSmartFillScene('4月1日在东棚种一茬8424西瓜')).toBe('crop.cycle');
    expect(inferSmartFillScene('春茬辣椒种植在2号棚')).toBe('crop.cycle');
  });

  it('根据语义判断记账解析场景', () => {
    expect(inferSmartFillScene('今天买复合肥128.5元，记到春季西瓜')).toBe('ledger.record');
    expect(inferSmartFillScene('欠老王农药钱两百块')).toBe('ledger.record');
  });
});
