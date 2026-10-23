import { createContext, useContext } from 'react';
import type { AppThemeMode } from './themeMode';

export interface ThemeModeContextValue {
  mode: AppThemeMode;
  setMode: (mode: AppThemeMode) => void;
}

export const ThemeModeContext = createContext<ThemeModeContextValue>({
  mode: 'dark',
  setMode: () => {},
});

export function useThemeMode() {
  return useContext(ThemeModeContext);
}
