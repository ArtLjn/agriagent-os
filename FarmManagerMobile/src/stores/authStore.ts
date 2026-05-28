import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { apiClient } from '../api/client';
import type {
  UserProfile,
  LoginParams,
  RegisterParams,
  TokenResponse,
  UpdateProfileParams,
} from '../api/types';

const TOKEN_KEY = 'farm_manager_auth_token';

interface AuthState {
  token: string | null;
  user: UserProfile | null;
  isLoggedIn: boolean;
  isInitializing: boolean;
  login: (params: LoginParams) => Promise<void>;
  register: (params: RegisterParams) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (params: UpdateProfileParams) => Promise<void>;
  initialize: () => Promise<void>;
  setToken: (token: string) => Promise<void>;
}

let onUnauthorizedCallback: (() => void) | null = null;

export const setOnUnauthorized = (cb: () => void) => {
  onUnauthorizedCallback = cb;
};

export const triggerUnauthorized = () => {
  onUnauthorizedCallback?.();
};

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  isLoggedIn: false,
  isInitializing: true,

  setToken: async (token: string) => {
    await AsyncStorage.setItem(TOKEN_KEY, token);
    set({ token });
  },

  login: async (params: LoginParams) => {
    const res = await apiClient.post<TokenResponse>('/auth/login', params);
    const { access_token, user } = res.data;
    await AsyncStorage.setItem(TOKEN_KEY, access_token);
    set({ token: access_token, user, isLoggedIn: true });
  },

  register: async (params: RegisterParams) => {
    const res = await apiClient.post<TokenResponse>('/auth/register', params);
    const { access_token, user } = res.data;
    await AsyncStorage.setItem(TOKEN_KEY, access_token);
    set({ token: access_token, user, isLoggedIn: true });
  },

  logout: async () => {
    await AsyncStorage.removeItem(TOKEN_KEY);
    // 清理所有业务 store
    const { useAgentStore } = require('./agentStore');
    useAgentStore.getState().clearChat();
    set({ token: null, user: null, isLoggedIn: false });
  },

  updateProfile: async (params: UpdateProfileParams) => {
    const res = await apiClient.post<TokenResponse>('/auth/me', params);
    const user = res.data as unknown as UserProfile;
    set({ user });
  },

  initialize: async () => {
    set({ isInitializing: true });
    try {
      const token = await AsyncStorage.getItem(TOKEN_KEY);
      if (!token) {
        set({ isLoggedIn: false, isInitializing: false });
        return;
      }
      set({ token });
      const res = await apiClient.get<UserProfile>('/auth/me');
      set({ user: res.data, isLoggedIn: true, isInitializing: false });
    } catch {
      await AsyncStorage.removeItem(TOKEN_KEY);
      set({ token: null, user: null, isLoggedIn: false, isInitializing: false });
    }
  },
}));
