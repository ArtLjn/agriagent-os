import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { MarkdownContent } from './MarkdownContent';
import { normalizeAssistantMarkdown } from './MarkdownContentModel';

describe('normalizeAssistantMarkdown', () => {
  it('把模型输出里的 HTML 换行转换为 Markdown 换行', () => {
    expect(normalizeAssistantMarkdown('装盘<br>播种<br/>覆土<BR />保湿')).toBe(
      '装盘\n播种\n覆土\n保湿',
    );
  });

  it('修复被双竖线挤到同一行的 Markdown 表格', () => {
    const raw = '| 工人姓名 | 核心任务 || :--- | :--- || 李四 | 基质准备<br>装盘 |';

    expect(normalizeAssistantMarkdown(raw)).toBe(
      '| 工人姓名 | 核心任务 |\n| :--- | :--- |\n| 李四 | 基质准备；装盘 |',
    );
  });
});

describe('MarkdownContent', () => {
  it('按 GFM 表格渲染标准 Markdown 表格', () => {
    render(
      <MarkdownContent
        content={'| 工人姓名 | 核心任务 |\n| --- | --- |\n| 李四 | 基质准备与装盘 |'}
      />,
    );

    const table = screen.getByRole('table');
    expect(within(table).getByRole('columnheader', { name: '工人姓名' })).toBeInTheDocument();
    expect(within(table).getByRole('cell', { name: '基质准备与装盘' })).toBeInTheDocument();
  });
});
