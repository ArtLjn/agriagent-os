import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { ThemeModeContext } from './themeContext';
import { readStoredTheme, storeTheme } from './themeMode';
import type { AppThemeMode } from './themeMode';

export default function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<AppThemeMode>(readStoredTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = mode;
    storeTheme(mode);
  }, [mode]);

  const value = useMemo(() => ({ mode, setMode }), [mode]);

  return <ThemeModeContext.Provider value={value}>{children}</ThemeModeContext.Provider>;
}
