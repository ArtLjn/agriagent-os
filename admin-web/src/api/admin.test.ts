import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import { getTraceDiagnostics } from './admin';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('admin api', () => {
  it('通过已有 diagnostics 接口读取 Reflection 诊断', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        request_id: 'req:1',
        reflection_checks: [
          {
            trigger: 'pre_write_plan',
            decision: 'block_write',
            reason: '确认文案不一致',
            checks: ['write_plan_consistency'],
            issues: [
              {
                code: 'confirmation_param_mismatch',
                severity: 'blocker',
                message: '确认文案中的对象与参数不一致',
              },
            ],
            input: { tool_name: 'create_cost_record' },
          },
        ],
        reflection_diagnostic: {
          blocked: true,
          decisions: ['block_write'],
          issue_codes: ['confirmation_param_mismatch'],
        },
      },
    });

    const result = await getTraceDiagnostics('req:1');

    expect(mockedApiClient.get).toHaveBeenCalledWith('/admin/traces/req:1/diagnostics');
    expect(result.reflection_checks[0].checks).toEqual(['write_plan_consistency']);
  });
});
