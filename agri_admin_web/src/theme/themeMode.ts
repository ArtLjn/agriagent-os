export type AppThemeMode = 'light' | 'dark';

const THEME_STORAGE_KEY = 'tianzhanggui-theme';
const LEGACY_LOGIN_THEME_KEY = 'tianzhanggui-login-theme';

export function readStoredTheme(): AppThemeMode {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
      ?? window.localStorage.getItem(LEGACY_LOGIN_THEME_KEY);
    return stored === 'light' ? 'light' : 'dark';
  } catch {
    return 'dark';
  }
}

export function storeTheme(mode: AppThemeMode) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, mode);
  } catch {
    // 隐私模式下存储不可用时仅本次会话生效
  }
}
