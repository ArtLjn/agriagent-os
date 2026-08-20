import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import { usersApi } from './users';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('users api', () => {
  it('使用当前用户资料与设置接口读取用户设置页数据', async () => {
    mockedApiClient.get
      .mockResolvedValueOnce({
        data: {
          id: 'user-1',
          phone: '18812345678',
          nickname: '农友',
          role: 'admin',
          status: 'active',
          farm: null,
        },
      })
      .mockResolvedValueOnce({
        data: {
          user_id: 'user-1',
          default_city: '苏州市虎丘区',
          default_lat: 31.3,
          default_lon: 120.4,
          assistant_role: 'warm',
        },
      });

    const [profile, settings] = await Promise.all([
      usersApi.getCurrent(),
      usersApi.getSettings(),
    ]);

    expect(mockedApiClient.get).toHaveBeenNthCalledWith(1, '/users/me');
    expect(mockedApiClient.get).toHaveBeenNthCalledWith(2, '/users/me/settings');
    expect(profile.data.nickname).toBe('农友');
    expect(settings.data.default_city).toBe('苏州市虎丘区');
  });

  it('按 users.py 的字段分别更新资料和设置', async () => {
    mockedApiClient.patch
      .mockResolvedValueOnce({ data: { id: 'user-1', nickname: '新昵称' } })
      .mockResolvedValueOnce({ data: { user_id: 'user-1', assistant_role: 'concise' } });

    await usersApi.updateCurrent({ nickname: '新昵称' });
    await usersApi.updateSettings({ assistant_role: 'concise' });

    expect(mockedApiClient.patch).toHaveBeenNthCalledWith(1, '/users/me', { nickname: '新昵称' });
    expect(mockedApiClient.patch).toHaveBeenNthCalledWith(2, '/users/me/settings', { assistant_role: 'concise' });
  });

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
