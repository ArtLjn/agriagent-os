import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

import { settingsApi } from '../api/client';

interface SettingsState {
  defaultFarmName: string;
  defaultCity: string;
  crops: string[];
  reminderTime: string;
  notificationEnabled: boolean;
  weatherAlertEnabled: boolean;
  displayName: string;
  setDefaultFarmName: (name: string) => void;
  setDefaultCity: (city: string) => void;
  setCrops: (crops: string[]) => void;
  setReminderTime: (time: string) => void;
  setNotificationEnabled: (enabled: boolean) => void;
  setWeatherAlertEnabled: (enabled: boolean) => void;
  setDisplayName: (name: string) => void;
  syncToServer: (city: string, lat: number, lon: number) => Promise<void>;
  loadFromServer: () => Promise<string | null>;
}

export const useSettingsStore = create<
  SettingsState,
  [['zustand/persist', unknown]]
>(
  persist(
    (set) => ({
      defaultFarmName: '睢宁农场',
      defaultCity: '苏州',
      crops: ['西瓜', '豆角'],
      reminderTime: '08:00',
      notificationEnabled: true,
      weatherAlertEnabled: true,
      displayName: '农友',

      setDefaultFarmName: (name) => set({ defaultFarmName: name }),
      setDefaultCity: (city) => set({ defaultCity: city }),
      setCrops: (crops) => set({ crops }),
      setReminderTime: (time) => set({ reminderTime: time }),
      setNotificationEnabled: (enabled) =>
        set({ notificationEnabled: enabled }),
      setWeatherAlertEnabled: (enabled) =>
        set({ weatherAlertEnabled: enabled }),
      setDisplayName: (name) => set({ displayName: name }),

      syncToServer: async (city: string, lat: number, lon: number) => {
        try {
          await settingsApi.update({
            default_city: city,
            default_lat: lat,
            default_lon: lon,
          });
          set({ defaultCity: city });
        } catch {
          // 网络失败时本地已更新，下次重试
        }
      },

      loadFromServer: async () => {
        try {
          const res = await settingsApi.get();
          const data = res.data;
          if (data.default_city) {
            set({ defaultCity: data.default_city });
            return data.default_city;
          }
          return null;
        } catch {
          return null;
        }
      },
    }),
    {
      name: 'settings-store',
      storage: createJSONStorage(() => AsyncStorage),
    }
  )
);
