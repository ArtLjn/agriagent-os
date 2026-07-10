import { describe, expect, it, vi } from 'vitest';

import { copyAsyncText } from './clipboard';

describe('copyAsyncText', () => {
  it('先同步写入占位内容，再用异步结果更新剪贴板', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });

    const result = await copyAsyncText({
      placeholder: '正在准备调试 JSON...',
      loadText: async () => '真实调试 JSON',
    });

    expect(result).toBe(true);
    expect(writeText).toHaveBeenNthCalledWith(1, '正在准备调试 JSON...');
    expect(writeText).toHaveBeenNthCalledWith(2, '真实调试 JSON');
  });

  it('浏览器剪贴板不可用时返回 false', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: undefined,
    });

    const result = await copyAsyncText({
      placeholder: '占位',
      loadText: async () => '真实内容',
    });

    expect(result).toBe(false);
  });
});
