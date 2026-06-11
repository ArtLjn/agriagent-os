import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import { listSmartFillScenarios, parseSmartFill } from './smartFill';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('smartFill api', () => {
  it('读取统一智能填写场景列表', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            key: 'ledger.record',
            title: '智能记账',
            description: '解析记账',
            legacy_endpoint: '/costs/parse',
            enabled: true,
            request_example: '买肥料 128 元',
          },
        ],
      },
    });

    const items = await listSmartFillScenarios();

    expect(mockedApiClient.get).toHaveBeenCalledWith('/smart-fill/scenarios');
    expect(items[0].key).toBe('ledger.record');
  });

  it('通过统一入口解析指定场景', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        scene: 'ledger.record',
        draft: { amount: '128.00' },
        missing_fields: [],
        warnings: [],
        trace_id: null,
      },
    });

    const result = await parseSmartFill('ledger.record', '买肥料 128 元', { cycle_id: 2 });

    expect(mockedApiClient.post).toHaveBeenCalledWith('/smart-fill/parse', {
      scene: 'ledger.record',
      text: '买肥料 128 元',
      context: { cycle_id: 2 },
    });
    expect(result.draft.amount).toBe('128.00');
  });

  it('未传上下文时使用空 context 解析', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        scene: 'ledger.record',
        draft: { amount: '200.00' },
        missing_fields: [],
        warnings: [],
        trace_id: null,
      },
    });

    await parseSmartFill('ledger.record', '欠老王农药钱两百块');

    expect(mockedApiClient.post).toHaveBeenCalledWith('/smart-fill/parse', {
      scene: 'ledger.record',
      text: '欠老王农药钱两百块',
      context: {},
    });
  });
});
