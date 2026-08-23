import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import {
  getConversationMessages,
  getConversationMessagesPage,
  getConversationTurnDetail,
  getConversationTurns,
  listConversations,
} from './agent';

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

    expect(mockedApiClient.get).toHaveBeenCalledWith('/agent/conversations/conversation-1/messages', {
      params: { limit: 100 },
      headers: { Authorization: 'Bearer dev-token' },
    });
  });

  it('按 cursor 请求更早的历史消息页', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        conversation_id: 'conversation-1',
        items: [],
        has_more: true,
        next_cursor: 'cursor-2',
        pagination: {
          next_cursor: 'cursor-2',
          has_more: true,
          page_count: 0,
          limit: 2,
          direction: 'older',
          snapshot_revision: 4,
          consistency: 'snapshot',
        },
      },
    });

    await getConversationMessagesPage('conversation-1', {
      limit: 2,
      cursor: 'cursor-1',
      userToken: 'dev-token',
    });

    expect(mockedApiClient.get).toHaveBeenCalledWith('/agent/conversations/conversation-1/messages', {
      params: { limit: 2, cursor: 'cursor-1' },
      headers: { Authorization: 'Bearer dev-token' },
    });
  });

  it('查询会话 Turn 列表和详情时保留用户 token', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: { conversation_id: 'conversation-1', items: [], has_more: false },
    });
    await getConversationTurns('conversation-1', { userToken: 'dev-token' });
    expect(mockedApiClient.get).toHaveBeenCalledWith('/agent/conversations/conversation-1/turns', {
      params: { limit: 50 },
      headers: { Authorization: 'Bearer dev-token' },
    });

    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        conversation_id: 'conversation-1',
        turn_id: 'turn-1',
        status: 'completed',
        step_count: 1,
        message_ids: {},
        events_status: 'available',
        steps: [],
        evidence: {},
      },
    });
    await getConversationTurnDetail('conversation-1', 'turn-1', {
      includePayload: true,
      userToken: 'dev-token',
    });
    expect(mockedApiClient.get).toHaveBeenCalledWith(
      '/agent/conversations/conversation-1/turns/turn-1',
      {
        params: { include_payload: true },
        headers: { Authorization: 'Bearer dev-token' },
      },
    );
  });
});
