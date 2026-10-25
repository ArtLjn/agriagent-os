import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import CompanionSpace from '.';

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}

beforeEach(() => {
  window.localStorage.removeItem('tianzhanggui-companion-moods');
});

afterEach(() => {
  window.localStorage.removeItem('tianzhanggui-companion-moods');
});

describe('CompanionSpace', () => {
  it('记录心情并展示对应的关怀建议', () => {
    render(
      <MemoryRouter>
        <CompanionSpace />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: '陪伴空间' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /有点累/ }));

    expect(screen.getByText('看到你了：有点累')).toBeInTheDocument();
    expect(screen.getByText('今天已记录')).toBeInTheDocument();
    expect(
      screen.getByText('放下手里的事，闭眼休息五分钟，让肩膀自然下沉。'),
    ).toBeInTheDocument();

    const stored = JSON.parse(
      window.localStorage.getItem('tianzhanggui-companion-moods') ?? '[]',
    );
    expect(stored).toHaveLength(1);
    expect(stored[0].mood).toBe('tired');
  });

  it('重新进入页面时恢复今天的记录', () => {
    const first = render(
      <MemoryRouter>
        <CompanionSpace />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /焦虑/ }));
    first.unmount();

    render(
      <MemoryRouter>
        <CompanionSpace />
      </MemoryRouter>,
    );

    expect(screen.getByText('看到你了：焦虑')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /焦虑/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('进入陪伴对话页面', () => {
    render(
      <MemoryRouter>
        <CompanionSpace />
        <LocationProbe />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: /和陪伴助手聊聊/ }));

    expect(screen.getByTestId('location')).toHaveTextContent('/companion/chat');
  });
});
