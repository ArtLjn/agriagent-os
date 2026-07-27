import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getCycle } from '../../api/cycles';
import CycleDetail from './Detail';

vi.mock('../../api/cycles', () => ({
  getCycle: vi.fn(),
  advanceStage: vi.fn(),
}));

const mockedGetCycle = vi.mocked(getCycle);

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}{location.search}</div>;
}

describe('CycleDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('点击地块名跳转到当前茬口的种植单元面积查询', async () => {
    const user = userEvent.setup();
    mockedGetCycle.mockResolvedValue({
      id: 7,
      name: '夏季西瓜',
      crop_template_id: 1,
      start_date: '2026-07-24',
      field_name: '默认地块',
      status: 'active',
      stages: [
        {
          id: 1,
          name: '播种育苗期',
          start_date: '2026-07-24',
          end_date: '2026-08-17',
          order_index: 1,
          is_current: true,
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/cycles/7']}>
        <Routes>
          <Route path="/cycles/:id" element={<CycleDetail />} />
          <Route path="/operations" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    const fieldButton = await screen.findByRole('button', { name: /默认地块/ });
    await user.click(fieldButton);

    expect(screen.getByTestId('location')).toHaveTextContent('/operations?tab=planting&cycle_id=7');
  });
});
