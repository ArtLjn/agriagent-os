import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import TraceMonitor from './index';
import { getTimeline, listTraces } from '../../api/admin';

vi.mock('../../api/admin', () => ({
  deleteTracesBefore: vi.fn(),
  getTimeline: vi.fn(),
  listTraces: vi.fn(),
}));

vi.mock('../../components/GanttTimeline', () => ({
  default: () => <div>timeline loaded</div>,
}));

const mockedListTraces = vi.mocked(listTraces);
const mockedGetTimeline = vi.mocked(getTimeline);

describe('TraceMonitor query 初始化', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedListTraces.mockResolvedValue({
      total: 1,
      items: [
        {
          id: 1,
          request_id: 'req-1',
          session_id: 'sess-1',
          farm_id: 1,
          round_index: 0,
          node_type: 'router',
          node_name: 'skill_router',
          duration_ms: 12,
          status: 'success',
          token_usage: null,
          error_message: null,
          created_at: '2026-06-11T10:00:00+08:00',
        },
      ],
    });
    mockedGetTimeline.mockResolvedValue({
      request_id: 'req-1',
      rounds: [],
    });
  });

  it('从 URL query 初始化筛选并自动加载目标 timeline', async () => {
    render(
      <MemoryRouter initialEntries={['/dev/traces?request_id=req-1&session_id=sess-1']}>
        <TraceMonitor />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mockedListTraces).toHaveBeenCalledWith({
        limit: 20,
        offset: 0,
        request_id: 'req-1',
        session_id: 'sess-1',
      });
    });
    await waitFor(() => {
      expect(mockedGetTimeline).toHaveBeenCalledWith('req-1');
    });
    expect(screen.getByDisplayValue('req-1')).toBeInTheDocument();
    expect(screen.getByDisplayValue('sess-1')).toBeInTheDocument();
  });
});
