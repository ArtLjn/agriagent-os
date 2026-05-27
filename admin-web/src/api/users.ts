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
}

export interface UserListResponse {
  items: UserListItem[];
  total: number;
}

export interface UserDetail extends UserListItem {
  farm_id: number | null;
  farm_location: string | null;
}

export interface ListUsersParams {
  page?: number;
  size?: number;
  status?: string;
  phone_keyword?: string;
}

export const usersApi = {
  list: (params?: ListUsersParams) =>
    apiClient.get<UserListResponse>("/admin/users", { params }),

  getDetail: (userId: string) =>
    apiClient.get<UserDetail>(`/admin/users/${userId}`),

  updateStatus: (userId: string, status: string) =>
    apiClient.put(`/admin/users/${userId}/status`, { status }),
};
