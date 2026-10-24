import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AdviceTab } from './index';

describe('AdviceTab', () => {
  it('未接入每日建议时明确提示，不展示可执行的生成按钮', () => {
    render(<AdviceTab cycleId={7} />);

    expect(screen.getByText('每日建议暂未接入 v2 Agent 接口')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
