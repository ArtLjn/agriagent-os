import apiClient from "./client";

export interface UserListItem {
  id: string;
  phone: string;
  nickname: string;
  avatar_url: string | null;
  role: string;
  status: string;
  created_at: string;
  farm_name: string | null;
  quota?: UserQuotaOverviewItem;
}

export interface UserQuotaStatus {
  monthly_limit: number;
  monthly_usage: number;
  monthly_remaining: number;
  monthly_start: string;
  monthly_end: string;
  weekly_limit: number;
  weekly_usage: number;
  weekly_remaining: number;
  weekly_start: string;
  weekly_end: string;
  status: string;
}

export interface UpdateUserQuotaRequest {
  token_monthly_limit?: number | null;
  token_weekly_limit?: number | null;
}

export interface BatchUpdateUserQuotaRequest extends UpdateUserQuotaRequest {
  user_ids: string[];
}

export interface BatchUpdateUserQuotaResponse {
  updated_count: number;
  user_ids: string[];
}

export interface UserQuotaOverviewItem {
  user_id: string;
  nickname: string;
  phone: string;
  monthly_limit: number;
  monthly_usage: number;
  monthly_percent: number;
  weekly_limit: number;
  weekly_usage: number;
  weekly_percent: number;
  status: string;
}

export interface UserQuotaOverviewResponse {
  items: UserQuotaOverviewItem[];
  total: number;
}

export interface UserListResponse {
  items: UserListItem[];
  total: number;
}

export interface UserDetail extends UserListItem {
  farm_id: number | null;
  farm_location: string | null;
}

export interface CurrentUser {
  id: string;
  phone: string;
  nickname: string | null;
  avatar_url?: string | null;
  role?: string;
  status?: string;
}

export interface ListUsersParams {
  page?: number;
  size?: number;
  status?: string;
  phone_keyword?: string;
}

export interface ListQuotaOverviewParams {
  page?: number;
  size?: number;
  status?: string;
}

export const usersApi = {
  getCurrent: () =>
    apiClient.get<CurrentUser>("/auth/me"),

  list: (params?: ListUsersParams) =>
    apiClient.get<UserListResponse>("/admin/users", { params }),

  getDetail: (userId: string) =>
    apiClient.get<UserDetail>(`/admin/users/${userId}`),

  getQuota: (userId: string) =>
    apiClient.get<UserQuotaStatus>(`/admin/users/${userId}/quota`),

  updateQuota: (userId: string, data: UpdateUserQuotaRequest) =>
    apiClient.put<UserQuotaStatus>(`/admin/users/${userId}/quota`, data),

  batchUpdateQuota: (data: BatchUpdateUserQuotaRequest) =>
    apiClient.put<BatchUpdateUserQuotaResponse>("/admin/users/quota/batch", data),

  getQuotaOverview: (params?: ListQuotaOverviewParams) =>
    apiClient.get<UserQuotaOverviewResponse>("/admin/users/quota-overview", { params }),

  updateStatus: (userId: string, status: string) =>
    apiClient.put(`/admin/users/${userId}/status`, { status }),
};
