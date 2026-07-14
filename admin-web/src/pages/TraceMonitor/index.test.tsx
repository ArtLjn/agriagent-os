import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import TraceMonitor from './index';
import { getTimeline, listTraceRequests, listTraces } from '../../api/admin';

vi.mock('../../api/admin', () => ({
  deleteTracesBefore: vi.fn(),
  getTimeline: vi.fn(),
  listTraceRequests: vi.fn(),
  listTraces: vi.fn(),
}));

vi.mock('../../components/GanttTimeline', () => ({
  default: () => <div>timeline loaded</div>,
}));

const mockedListTraces = vi.mocked(listTraces);
const mockedListTraceRequests = vi.mocked(listTraceRequests);
const mockedGetTimeline = vi.mocked(getTimeline);

describe('TraceMonitor query 初始化', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedListTraceRequests.mockResolvedValue({
      total: 1,
      items: [
        {
          request_id: 'req-1',
          session_id: 'sess-1',
          farm_id: 1,
          node_count: 1,
          total_duration_ms: 12,
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
      expect(mockedListTraceRequests).toHaveBeenCalledWith({
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

  it('空创建时间显示占位符而不是 1970', async () => {
    mockedListTraceRequests.mockResolvedValueOnce({
      total: 1,
      items: [
        {
          request_id: 'req-empty-time',
          session_id: 'sess-empty-time',
          farm_id: 1,
          node_count: 1,
          total_duration_ms: 12,
          created_at: null,
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/dev/traces']}>
        <TraceMonitor />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/req-empty-time/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/1970/)).not.toBeInTheDocument();
    expect(mockedListTraces).not.toHaveBeenCalled();
  });
});
