import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { QuickPrompts } from './QuickPrompts';
import { QUICK_PROMPTS } from './quickPromptList';

describe('QuickPrompts', () => {
  it('渲染所有快捷提示词卡片', () => {
    const onSelect = vi.fn();
    render(<QuickPrompts onSelect={onSelect} />);

    for (const prompt of QUICK_PROMPTS) {
      expect(screen.getByText(prompt.title)).toBeInTheDocument();
      expect(screen.getByText(prompt.description)).toBeInTheDocument();
    }
  });

  it('点击卡片时使用对应 prompt 调用 onSelect', () => {
    const onSelect = vi.fn();
    render(<QuickPrompts onSelect={onSelect} />);

    fireEvent.click(screen.getByText('记一笔账'));
    expect(onSelect).toHaveBeenCalledWith(QUICK_PROMPTS[0].prompt);

    fireEvent.click(screen.getByText('查天气'));
    expect(onSelect).toHaveBeenCalledWith(
      QUICK_PROMPTS.find((p) => p.key === 'weather')?.prompt,
    );
  });

  it('disabled 时按钮禁用且不触发 onSelect', () => {
    const onSelect = vi.fn();
    render(<QuickPrompts onSelect={onSelect} disabled />);

    const card = screen.getByText('记一笔账').closest('button');
    expect(card).toBeDisabled();

    fireEvent.click(card!);
    expect(onSelect).not.toHaveBeenCalled();
  });
});
