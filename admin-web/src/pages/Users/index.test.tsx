import { App as AntdApp } from 'antd';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosResponse } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { usersApi, type UserListItem, type UserQuotaOverviewItem } from '../../api/users';
import Users from './index';

vi.mock('../../api/users', () => ({
  usersApi: {
    list: vi.fn(),
    getQuotaOverview: vi.fn(),
    create: vi.fn(),
    getDetail: vi.fn(),
    getQuota: vi.fn(),
    updateQuota: vi.fn(),
    batchUpdateQuota: vi.fn(),
    updateStatus: vi.fn(),
  },
}));

const mockedUsersApi = vi.mocked(usersApi, true);

const axiosResponse = <T,>(data: T) => ({
  data,
  status: 200,
  statusText: 'OK',
  headers: {},
  config: {},
}) as AxiosResponse<T>;

const existingUser: UserListItem = {
  id: 'user-1',
  phone: '19083106293',
  nickname: '系统管理员',
  avatar_url: null,
  role: 'admin',
  status: 'active',
  created_at: '2026-07-24T10:29:18Z',
  farm_name: '管理员农场',
};

const existingQuota: UserQuotaOverviewItem = {
  user_id: 'user-1',
  nickname: '系统管理员',
  phone: '19083106293',
  monthly_limit: 800000,
  monthly_usage: 21624,
  monthly_percent: 0.027,
  weekly_limit: 200000,
  weekly_usage: 21624,
  weekly_percent: 0.108,
  status: 'normal',
};

describe('Users', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUsersApi.list.mockResolvedValue(
      axiosResponse({
        items: [existingUser],
        total: 1,
      }),
    );
    mockedUsersApi.getQuotaOverview.mockResolvedValue(
      axiosResponse({
        items: [existingQuota],
        total: 1,
      }),
    );
    mockedUsersApi.create.mockResolvedValue(
      axiosResponse({
        id: 'user-2',
        phone: '18812345678',
        nickname: '新农友',
        avatar_url: null,
        role: 'user',
        status: 'active',
        created_at: '2026-07-24T11:00:00Z',
        farm_id: 2,
        farm_name: '新农友的农场',
        farm_location: null,
      }),
    );
  });

  it('支持管理员在用户管理页创建用户', async () => {
    const user = userEvent.setup();

    render(
      <AntdApp>
        <Users />
      </AntdApp>,
    );

    await screen.findByText('系统管理员');
    await user.click(screen.getByRole('button', { name: /新建用户/ }));

    expect(await screen.findByRole('dialog', { name: '新建用户' })).toBeInTheDocument();
    await user.type(screen.getByLabelText('手机号'), '18812345678');
    await user.type(screen.getByLabelText('昵称'), '新农友');
    await user.type(screen.getByLabelText('初始密码'), 'password123');
    await user.type(screen.getByLabelText('确认密码'), 'password123');
    await user.click(screen.getByRole('button', { name: /创\s*建/ }));

    await waitFor(() => {
      expect(mockedUsersApi.create).toHaveBeenCalledWith({
        phone: '18812345678',
        nickname: '新农友',
        password: 'password123',
      });
    });
    await waitFor(() => {
      expect(mockedUsersApi.list).toHaveBeenCalledTimes(2);
    });
  });

  it('密码确认不一致时不提交创建请求', async () => {
    const user = userEvent.setup();

    render(
      <AntdApp>
        <Users />
      </AntdApp>,
    );

    await screen.findByText('系统管理员');
    await user.click(screen.getByRole('button', { name: /新建用户/ }));
    await user.type(screen.getByLabelText('手机号'), '18812345678');
    await user.type(screen.getByLabelText('昵称'), '新农友');
    await user.type(screen.getByLabelText('初始密码'), 'password123');
    await user.type(screen.getByLabelText('确认密码'), 'password456');
    await user.click(screen.getByRole('button', { name: /创\s*建/ }));

    expect(await screen.findByText('两次输入的密码不一致')).toBeInTheDocument();
    expect(mockedUsersApi.create).not.toHaveBeenCalled();
    expect(mockedUsersApi.list).toHaveBeenCalledTimes(1);
  });

  it('创建失败时保留弹窗且不刷新列表', async () => {
    const user = userEvent.setup();
    mockedUsersApi.create.mockRejectedValueOnce(new Error('phone exists'));

    render(
      <AntdApp>
        <Users />
      </AntdApp>,
    );

    await screen.findByText('系统管理员');
    await user.click(screen.getByRole('button', { name: /新建用户/ }));
    await user.type(screen.getByLabelText('手机号'), '18812345678');
    await user.type(screen.getByLabelText('昵称'), '新农友');
    await user.type(screen.getByLabelText('初始密码'), 'password123');
    await user.type(screen.getByLabelText('确认密码'), 'password123');
    await user.click(screen.getByRole('button', { name: /创\s*建/ }));

    await waitFor(() => {
      expect(mockedUsersApi.create).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByRole('dialog', { name: '新建用户' })).toBeInTheDocument();
    expect(mockedUsersApi.list).toHaveBeenCalledTimes(1);
  });
});
