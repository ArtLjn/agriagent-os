import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import { usersApi } from './users';

vi.mock('./client', () => ({
  default: {
    post: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('users api', () => {
  it('通过管理员接口创建用户', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 'user-1',
        phone: '18812345678',
        nickname: '新农友',
        avatar_url: null,
        role: 'user',
        status: 'active',
        created_at: '2026-07-24T10:00:00Z',
        farm_id: 7,
        farm_name: '新农友的农场',
        farm_location: null,
      },
    });

    const result = await usersApi.create({
      phone: '18812345678',
      password: 'password123',
      nickname: '新农友',
    });

    expect(mockedApiClient.post).toHaveBeenCalledWith('/admin/users', {
      phone: '18812345678',
      password: 'password123',
      nickname: '新农友',
    });
    expect(result.data.farm_name).toBe('新农友的农场');
  });
});
