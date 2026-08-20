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

  it('归一化智能工人档案解析结果', () => {
    const result = normalizeSmartResult('labor.worker', {
      name: '老王',
      phone: '13800138000',
      default_pay_type: 'daily',
      default_unit_price: '200',
      note: '擅长授粉',
      status: 'active',
    });

    expect(result.scene).toBe('labor.worker');
    if (result.scene === 'labor.worker') {
      expect(result.draft.name).toBe('老王');
      expect(result.draft.default_unit_price).toBe('200');
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
    expect(inferSmartFillScene('我要种西瓜')).toBe('crop.template');
  });

  it('根据语义判断茬口解析场景', () => {
    expect(inferSmartFillScene('4月1日在东棚种一茬8424西瓜')).toBe('crop.cycle');
    expect(inferSmartFillScene('春茬辣椒种植在2号棚')).toBe('crop.cycle');
  });

  it('根据语义判断记账解析场景', () => {
    expect(inferSmartFillScene('今天买复合肥128.5元，记到春季西瓜')).toBe('ledger.record');
    expect(inferSmartFillScene('欠老王农药钱两百块')).toBe('ledger.record');
  });

  it('根据语义判断工人档案解析场景', () => {
    expect(inferSmartFillScene('新增工人老王，电话13800138000，日薪200')).toBe('labor.worker');
    expect(inferSmartFillScene('招了李师傅，计件每亩50，临时工')).toBe('labor.worker');
    expect(inferSmartFillScene('新来王师傅电话13800138000日薪200')).toBe('labor.worker');
    expect(inferSmartFillScene('新来工人张桂梅长工日薪100电话19083106293222222')).toBe('labor.worker');
    expect(inferSmartFillScene('新来一个工人李树梅长工100一天电话190831062933西瓜压瓜厉害')).toBe('labor.worker');
  });

  it('边界语义不会默认误判成作物模板', () => {
    expect(inferSmartFillScene('西瓜压瓜厉害')).toBe('unsupported');
    expect(inferSmartFillScene('今天看看西瓜长势')).toBe('unsupported');
    expect(inferSmartFillScene('老王电话13800138000')).toBe('unsupported');
  });

  it('边界语义不会把交易对象误判成工人档案', () => {
    expect(inferSmartFillScene('找王师傅买农药100元')).toBe('ledger.record');
    expect(inferSmartFillScene('今天付王师傅工资200元')).toBe('ledger.record');
    expect(inferSmartFillScene('欠李师傅农资钱300块')).toBe('ledger.record');
  });
});
