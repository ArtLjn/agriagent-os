import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import { getConversationMessages, listConversations } from './agent';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('会话身份 token', () => {
  it('使用指定 dev token 获取会话列表', async () => {
    mockedApiClient.get.mockResolvedValueOnce({ data: { items: [] } });

    await listConversations(50, 'dev-token');

    expect(mockedApiClient.get).toHaveBeenCalledWith('/agent/conversations', {
      params: { limit: 50 },
      headers: { Authorization: 'Bearer dev-token' },
    });
  });

  it('使用指定 dev token 获取会话消息', async () => {
    mockedApiClient.get.mockResolvedValueOnce({ data: { items: [] } });

    await getConversationMessages('conversation-1', 'dev-token');

    expect(mockedApiClient.get).toHaveBeenCalledWith('/agent/conversations/conversation-1', {
      params: { limit: 100 },
      headers: { Authorization: 'Bearer dev-token' },
    });
  });
});
