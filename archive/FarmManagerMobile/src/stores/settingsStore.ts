import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

import { settingsApi } from '../api/client';

interface CityInfo {
  name: string;
  lat: number;
  lon: number;
}

interface SettingsState {
  defaultFarmName: string;
  defaultCity: string;
  defaultLat: number;
  defaultLon: number;
  crops: string[];
  reminderTime: string;
  notificationEnabled: boolean;
  weatherAlertEnabled: boolean;
  displayName: string;
  setDefaultFarmName: (name: string) => void;
  setCity: (city: CityInfo) => void;
  setCrops: (crops: string[]) => void;
  setReminderTime: (time: string) => void;
  setNotificationEnabled: (enabled: boolean) => void;
  setWeatherAlertEnabled: (enabled: boolean) => void;
  setDisplayName: (name: string) => void;
  syncToServer: () => Promise<void>;
  loadFromServer: () => Promise<CityInfo | null>;
  getCityInfo: () => CityInfo;
}

export const useSettingsStore = create<
  SettingsState,
  [['zustand/persist', unknown]]
>(
  persist(
    (set, get) => ({
      defaultFarmName: '睢宁农场',
      defaultCity: '苏州',
      defaultLat: 31.3,
      defaultLon: 120.6,
      crops: ['西瓜', '豆角'],
      reminderTime: '08:00',
      notificationEnabled: true,
      weatherAlertEnabled: true,
      displayName: '农友',

      setDefaultFarmName: (name) => set({ defaultFarmName: name }),
      setCity: (city) => set({
        defaultCity: city.name,
        defaultLat: city.lat,
        defaultLon: city.lon,
      }),
      setCrops: (crops) => set({ crops }),
      setReminderTime: (time) => set({ reminderTime: time }),
      setNotificationEnabled: (enabled) =>
        set({ notificationEnabled: enabled }),
      setWeatherAlertEnabled: (enabled) =>
        set({ weatherAlertEnabled: enabled }),
      setDisplayName: (name) => set({ displayName: name }),

      getCityInfo: () => {
        const s = get();
        return { name: s.defaultCity, lat: s.defaultLat, lon: s.defaultLon };
      },

      syncToServer: async () => {
        const s = get();
        try {
          await settingsApi.update({
            default_city: s.defaultCity,
            default_lat: s.defaultLat,
            default_lon: s.defaultLon,
          });
        } catch {
          // 网络失败时本地已更新，下次重试
        }
      },

      loadFromServer: async () => {
        try {
          const res = await settingsApi.get();
          const data = res.data;
          if (data.default_city) {
            const cityInfo: CityInfo = {
              name: data.default_city,
              lat: data.default_lat ?? 31.3,
              lon: data.default_lon ?? 120.6,
            };
            set({
              defaultCity: cityInfo.name,
              defaultLat: cityInfo.lat,
              defaultLon: cityInfo.lon,
            });
            return cityInfo;
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
