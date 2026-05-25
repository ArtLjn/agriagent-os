import AsyncStorage from '@react-native-async-storage/async-storage';
import {create} from 'zustand';
import {persist, createJSONStorage} from 'zustand/middleware';

interface SettingsState {
  defaultFarmName: string;
  defaultCity: string;
  crops: string[];
  reminderTime: string;
  notificationEnabled: boolean;
  weatherAlertEnabled: boolean;
  setDefaultFarmName: (name: string) => void;
  setDefaultCity: (city: string) => void;
  setCrops: (crops: string[]) => void;
  setReminderTime: (time: string) => void;
  setNotificationEnabled: (enabled: boolean) => void;
  setWeatherAlertEnabled: (enabled: boolean) => void;
}

export const useSettingsStore = create<SettingsState, [['zustand/persist', unknown]]>(
  persist(
    set => ({
      defaultFarmName: '睢宁农场',
      defaultCity: '苏州',
      crops: ['西瓜', '豆角'],
      reminderTime: '08:00',
      notificationEnabled: true,
      weatherAlertEnabled: true,

      setDefaultFarmName: name => set({defaultFarmName: name}),
      setDefaultCity: city => set({defaultCity: city}),
      setCrops: crops => set({crops}),
      setReminderTime: time => set({reminderTime: time}),
      setNotificationEnabled: enabled => set({notificationEnabled: enabled}),
      setWeatherAlertEnabled: enabled => set({weatherAlertEnabled: enabled}),
    }),
    {
      name: 'settings-store',
      storage: createJSONStorage(() => AsyncStorage),
    },
  ),
);
