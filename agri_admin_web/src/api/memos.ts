import apiClient from './client';

export interface Memo {
  id: number;
  title: string;
  content: string;
  pinned: boolean;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export type MemoDraft = Pick<Memo, 'title' | 'content'>;
export type MemoUpdate = Partial<MemoDraft & Pick<Memo, 'pinned' | 'archived'>>;
export const MEMO_PAGE_SIZE = 10;

export const memosApi = {
  async list(params: { keyword: string; archived: boolean; skip: number; limit: number }, signal?: AbortSignal) {
    return (await apiClient.get<{ items: Memo[]; total: number }>('/memos', { params, signal })).data;
  },
  async create(data: MemoDraft & { client_request_id: string }) {
    return (await apiClient.post<Memo>('/memos', data)).data;
  },
  async update(id: number, data: MemoUpdate) {
    return (await apiClient.patch<Memo>(`/memos/${id}`, data)).data;
  },
};
