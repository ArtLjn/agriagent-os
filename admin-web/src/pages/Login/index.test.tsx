import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import apiClient from '../../api/client';
import Login from './index';
import { authStore } from '../../stores/authStore';

vi.mock('../../api/client', () => ({
  default: {
    post: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('Login', () => {
  beforeEach(() => {
    authStore.clearToken();
    mockedApiClient.post.mockReset();
  });

  it('读取 v2 登录接口返回的 access_token 并完成跳转', async () => {
    mockedApiClient.post.mockResolvedValueOnce({ data: { access_token: 'jwt-token' } });
    const onLogin = vi.fn();
    const user = userEvent.setup();

    render(<Login onLogin={onLogin} />);
    await user.type(screen.getByPlaceholderText('手机号'), '18812345678');
    await user.type(screen.getByPlaceholderText('密码'), 'password123');
    await user.click(screen.getByRole('button', { name: /登\s*录/ }));

    await waitFor(() => expect(onLogin).toHaveBeenCalledOnce());
    expect(authStore.getToken()).toBe('jwt-token');
  });

  it('兼容旧登录响应中的 token 字段', async () => {
    mockedApiClient.post.mockResolvedValueOnce({ data: { token: 'legacy-token' } });
    const onLogin = vi.fn();
    const user = userEvent.setup();

    render(<Login onLogin={onLogin} />);
    await user.type(screen.getByPlaceholderText('手机号'), '18812345678');
    await user.type(screen.getByPlaceholderText('密码'), 'password123');
    await user.click(screen.getByRole('button', { name: /登\s*录/ }));

    await waitFor(() => expect(onLogin).toHaveBeenCalledOnce());
    expect(authStore.getToken()).toBe('legacy-token');
  });
});
