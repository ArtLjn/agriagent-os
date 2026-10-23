import type { AxiosRequestConfig } from 'axios';
import apiClient from './client';

export interface RecommendedQuestion {
  id: string;
  question: string;
  basis: 'memory' | 'explore';
}

export interface QuestionRecommendations {
  items: RecommendedQuestion[];
  mode: 'personalized' | 'explore';
}

export const RECOMMENDATION_HISTORY_LIMIT = 18;

export async function getQuestionRecommendations(
  exclude: string[],
  userToken: string | null,
  signal: AbortSignal,
): Promise<QuestionRecommendations> {
  // 与对话使用同一身份，管理员模拟用户时不能读取管理员自己的画像。
  const config: AxiosRequestConfig & { silent: boolean } = {
    signal,
    silent: true,
    ...(userToken ? { headers: { Authorization: `Bearer ${userToken}` } } : {}),
  };
  const response = await apiClient.post<QuestionRecommendations>(
    '/agent/me/question-recommendations', { exclude }, config,
  );
  return response.data;
}
