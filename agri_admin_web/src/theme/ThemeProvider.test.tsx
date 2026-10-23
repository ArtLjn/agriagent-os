import { fireEvent, render, screen, cleanup } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ThemeProvider from './ThemeProvider';
import ThemeToggle from '../components/ThemeToggle';
import { readStoredTheme, storeTheme } from './themeMode';

beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('暮色主题偏好', () => {
  it('首次访问和无效偏好均默认暗色', () => {
    expect(readStoredTheme()).toBe('dark');
    localStorage.setItem('tianzhanggui-theme', 'invalid');
    expect(readStoredTheme()).toBe('dark');
  });

  it('兼容登录页旧偏好，以全局设置为优先', () => {
    localStorage.setItem('tianzhanggui-login-theme', 'light');
    expect(readStoredTheme()).toBe('light');
    storeTheme('dark');
    expect(readStoredTheme()).toBe('dark');
  });

  it('切换后更新页面主题，重新挂载仍保留选择', () => {
    const view = render(<ThemeProvider><ThemeToggle /></ThemeProvider>);
    expect(screen.getByRole('button', { name: '暗色主题' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: '亮色主题' }));
    expect(document.documentElement.dataset.theme).toBe('light');
    view.unmount();
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>);
    expect(screen.getByRole('button', { name: '亮色主题' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('存储被禁用时仍可在本次会话切换', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('存储不可用'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('存储不可用'); });
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>);
    expect(document.documentElement.dataset.theme).toBe('dark');
    fireEvent.click(screen.getByRole('button', { name: '亮色主题' }));
    expect(document.documentElement.dataset.theme).toBe('light');
  });
});
