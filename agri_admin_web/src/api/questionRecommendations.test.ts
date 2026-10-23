import { describe, expect, it, vi } from 'vitest';
import apiClient from './client';
import { getQuestionRecommendations } from './questionRecommendations';

vi.mock('./client', () => ({ default: { post: vi.fn() } }));

describe('推荐接口', () => {
  it('模拟用户令牌随请求发送，不传用户 ID 或农场 ID', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { items: [], mode: 'explore' } });
    const signal = new AbortController().signal;
    await getQuestionRecommendations(['上次的问题'], 'acting-user-token', signal);
    expect(apiClient.post).toHaveBeenCalledWith('/agent/me/question-recommendations', { exclude: ['上次的问题'] }, {
      signal, silent: true, headers: { Authorization: 'Bearer acting-user-token' },
    });
  });
});
