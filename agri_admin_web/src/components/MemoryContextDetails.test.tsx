import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryContextDetails } from './MemoryContextDetails';

describe('长时记忆证据', () => {
  it('展示语义候选、原文与真正进入请求的依据', () => {
    render(<MemoryContextDetails data={{ stage: 'complete', status: 'ready', injected_count: 1,
      sources: [{ memory_id: 'game' }], retrieval: { status: 'ready', query: '喜欢什么游戏', lexical_count: 2, hit_count: 3,
        cards: [{ memory_id: 'game', revision: 2, text: '喜欢王者荣耀', semantic_rank: 1 }] },
      injection: { status: 'included', text: '<user-personalization>喜欢王者荣耀' } }} />);
    expect(screen.getByText('1 条依据已进入模型请求')).toBeInTheDocument();
    expect(screen.getByText('喜欢什么游戏')).toBeInTheDocument();
    expect(screen.getByText('候选 1 · RAG #1')).toBeInTheDocument();
    expect(screen.getByText('已注入依据')).toBeInTheDocument();
    expect(screen.getByText('<user-personalization>喜欢王者荣耀')).toBeInTheDocument();
  });
  it('旧准备记录及预算删除都不冒充已注入', () => {
    const { rerender } = render(<MemoryContextDetails data={{ status: 'ready', injected_count: 6 }} />);
    expect(screen.getByText('这里只记录了准备结果，不能确认最终发送内容。')).toBeInTheDocument();
    expect(screen.queryByText('6 条依据已进入模型请求')).not.toBeInTheDocument();
    rerender(<MemoryContextDetails data={{ stage: 'complete', status: 'ready', injected_count: 0, retrieval: { status: 'not_configured' }, injection: { status: 'budget_omitted' } }} />);
    expect(screen.getAllByText('最终预算移除了记忆块')).toHaveLength(2);
    expect(screen.getAllByText(/RAG 未配置，仅使用词项检索/).length).toBeGreaterThan(0);
  });
  it('等待结束但没有结果时明确显示流程中断', () => {
    render(<MemoryContextDetails data={{ stage: 'start' }} />);
    expect(screen.getAllByText('流程中断，未收到最终结果').length).toBeGreaterThan(0);
  });
});
