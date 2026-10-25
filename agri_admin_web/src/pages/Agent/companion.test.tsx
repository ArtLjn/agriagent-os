import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { listCycles } from '../../api/cycles';
import { BusinessContext } from '../../businesses/businessContext';
import type { BusinessContextValue } from '../../businesses/businessContext';
import { businessViews } from '../../businesses/registry';
import Agent from '.';

vi.mock('../../api/agent', () => ({
  streamChat: vi.fn(),
  approveTurn: vi.fn(),
}));
vi.mock('../../api/cycles', () => ({
  listCycles: vi.fn().mockResolvedValue({ items: [] }),
}));
vi.mock('../../api/personalization', () => ({
  personalizationApi: {
    getSettings: vi.fn().mockResolvedValue({ assistant_name: '陪伴助手' }),
  },
}));

const companionView = businessViews.find((view) => view.name === 'companion');

function value(): BusinessContextValue {
  return {
    views: businessViews,
    selectedName: 'companion',
    selectedView: companionView ?? null,
    runtimeItems: [],
    runtimeActive: 'companion',
    loading: false,
    switchingName: null,
    error: null,
    selectBusiness: async () => true,
    refresh: () => {},
    runtimeFor: () => undefined,
  };
}

describe('Agent companion view', () => {
  it('陪伴业务使用独立对话入口，不展示农事标签和茬口选择', async () => {
    render(
      <MemoryRouter>
        <BusinessContext.Provider value={value()}>
          <Agent />
        </BusinessContext.Provider>
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: '陪伴对话' })).toBeInTheDocument();
    expect(screen.queryByText('每日建议')).not.toBeInTheDocument();
    expect(screen.queryByText('关联茬口（可选）')).not.toBeInTheDocument();
    expect(await screen.findByText('可以聊聊今天的心情、想被怎样陪伴，或者只是打个招呼。')).toBeInTheDocument();
    expect(listCycles).not.toHaveBeenCalled();
  });
});
