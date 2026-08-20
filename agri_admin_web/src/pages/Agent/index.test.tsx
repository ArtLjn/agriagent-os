import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { getDailyAdvice, refreshDailyAdvice } from '../../api/agent';
import { AdviceTab } from './index';

vi.mock('../../api/agent', () => ({
  getDailyAdvice: vi.fn(),
  refreshDailyAdvice: vi.fn(),
}));

const mockedGetDailyAdvice = vi.mocked(getDailyAdvice);
const mockedRefreshDailyAdvice = vi.mocked(refreshDailyAdvice);

describe('AdviceTab', () => {
  it('再次点击刷新建议时强制刷新今日建议', async () => {
    const user = userEvent.setup();
    mockedGetDailyAdvice.mockResolvedValueOnce({
      advice: '缓存建议',
      created_at: '2026-06-13T09:00:00',
    });
    mockedRefreshDailyAdvice.mockResolvedValueOnce({
      advice: '重新生成的建议',
      created_at: '2026-06-13T10:00:00',
    });

    render(<AdviceTab cycleId={7} />);

    await user.click(screen.getByRole('button', { name: /获取今日建议/ }));

    expect(await screen.findByText('缓存建议')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /刷新建议/ }));

    await waitFor(() => {
      expect(screen.getByText('重新生成的建议')).toBeInTheDocument();
    });
    expect(mockedGetDailyAdvice).toHaveBeenCalledTimes(1);
    expect(mockedGetDailyAdvice).toHaveBeenCalledWith(7);
    expect(mockedRefreshDailyAdvice).toHaveBeenCalledWith(7);
  });
});
