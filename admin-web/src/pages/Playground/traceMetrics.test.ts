import { describe, expect, it } from 'vitest';

import type { TraceTimeline } from '../../api/admin';
import {
  buildPlaygroundTraceMetrics,
  extractLatestLlmContextSnapshot,
  hasAutomaticCompression,
} from './traceMetrics';

describe('buildPlaygroundTraceMetrics', () => {
  it('从 trace timeline 汇总上下文、最终 prompt 和模型 token', () => {
    const timeline: TraceTimeline = {
      request_id: 'req-1',
      rounds: [
        {
          round_index: 0,
          nodes: [
            {
              node_type: 'context_build',
              node_name: 'context_bundle',
              duration_ms: 8,
              status: 'success',
              token_usage: { context_tokens: 900 },
              start_time: null,
              error_message: null,
              input_data: { block_count: 4 },
              output_data: {
                token_budget: 1200,
                token_estimate: 900,
                compressed_blocks: [{ key: 'conversation' }],
                dropped_blocks: [{ key: 'retrieval' }],
              },
            },
            {
              node_type: 'prompt_budget',
              node_name: 'final_prompt',
              duration_ms: 2,
              status: 'success',
              token_usage: { prompt_tokens: 2100 },
              start_time: null,
              error_message: null,
              input_data: {},
              output_data: {
                total_tokens: 2100,
                max_tokens: 6000,
                actions: ['summarize_old_messages'],
              },
            },
            {
              node_type: 'llm_call',
              node_name: 'gpt-test',
              duration_ms: 300,
              status: 'success',
              token_usage: {
                prompt_tokens: 2000,
                completion_tokens: 300,
                total_tokens: 2300,
              },
              start_time: null,
              error_message: null,
              input_data: '你好',
              output_data: '回复',
            },
            {
              node_type: 'llm_call',
              node_name: 'gpt-test',
              duration_ms: 120,
              status: 'success',
              token_usage: {
                prompt_tokens: 500,
                completion_tokens: 100,
              },
              start_time: null,
              error_message: null,
              input_data: '重试',
              output_data: '回复',
            },
          ],
        },
      ],
    };

    const metrics = buildPlaygroundTraceMetrics(timeline);

    expect(metrics.contextTokens).toBe(900);
    expect(metrics.contextBudget).toBe(1200);
    expect(metrics.contextCompressedCount).toBe(1);
    expect(metrics.contextDroppedCount).toBe(1);
    expect(metrics.promptTokens).toBe(2100);
    expect(metrics.promptMaxTokens).toBe(6000);
    expect(metrics.promptActions).toEqual(['summarize_old_messages']);
    expect(metrics.llmPromptTokens).toBe(2500);
    expect(metrics.llmCompletionTokens).toBe(400);
    expect(metrics.llmTotalTokens).toBe(2900);
    expect(hasAutomaticCompression(metrics)).toBe(true);
  });

  it('没有压缩动作时返回未触发自动压缩', () => {
    const metrics = buildPlaygroundTraceMetrics({
      request_id: 'req-2',
      rounds: [
        {
          round_index: 0,
          nodes: [
            {
              node_type: 'context_build',
              node_name: 'context_bundle',
              duration_ms: 3,
              status: 'success',
              token_usage: { context_tokens: 300 },
              start_time: null,
              error_message: null,
              input_data: {},
              output_data: {
                token_budget: 1200,
                token_estimate: 300,
                compressed_blocks: [],
                dropped_blocks: [],
              },
            },
          ],
        },
      ],
    });

    expect(metrics.contextTokens).toBe(300);
    expect(metrics.llmTotalTokens).toBe(0);
    expect(hasAutomaticCompression(metrics)).toBe(false);
  });
});

describe('extractLatestLlmContextSnapshot', () => {
  it('从 final_llm_context 节点提取最终送入模型的上下文快照', () => {
    const timeline: TraceTimeline = {
      request_id: 'req-context',
      rounds: [
        {
          round_index: 0,
          nodes: [
            {
              node_type: 'prompt_budget',
              node_name: 'final_prompt',
              duration_ms: 0,
              status: 'success',
              token_usage: { prompt_tokens: 300 },
              start_time: null,
              error_message: null,
              input_data: {},
              output_data: { total_tokens: 300 },
            },
            {
              node_type: 'prompt_budget',
              node_name: 'final_llm_context',
              duration_ms: 0,
              status: 'success',
              token_usage: { prompt_tokens: 420 },
              start_time: null,
              error_message: null,
              input_data: { message_count: 2 },
              output_data: {
                system_prompt: '系统提示\n<runtime_context>农场状态</runtime_context>',
                messages: [
                  { index: 0, role: 'user', type: 'human', content: '我的农场情况' },
                  {
                    index: 1,
                    role: 'assistant',
                    type: 'ai',
                    content: '',
                    tool_calls: [{ id: 'call-1', name: 'get_farm_status' }],
                  },
                ],
                context_blocks: ['farm', 'ledger'],
                budget: {
                  total_tokens: 420,
                  max_tokens: 6000,
                  actions: ['summarize_old_messages'],
                },
              },
            },
          ],
        },
      ],
    };

    const snapshot = extractLatestLlmContextSnapshot(timeline);

    expect(snapshot?.systemPrompt).toContain('<runtime_context>');
    expect(snapshot?.messages).toHaveLength(2);
    expect(snapshot?.messages[1].tool_calls?.[0]).toEqual({
      id: 'call-1',
      name: 'get_farm_status',
    });
    expect(snapshot?.contextBlocks).toEqual(['farm', 'ledger']);
    expect(snapshot?.promptTokens).toBe(420);
    expect(snapshot?.maxTokens).toBe(6000);
    expect(snapshot?.actions).toEqual(['summarize_old_messages']);
  });

  it('旧 trace 没有 final_llm_context 时不返回快照', () => {
    const timeline: TraceTimeline = {
      request_id: 'req-old',
      rounds: [
        {
          round_index: 0,
          nodes: [
            {
              node_type: 'prompt_budget',
              node_name: 'final_prompt',
              duration_ms: 0,
              status: 'success',
              token_usage: null,
              start_time: null,
              error_message: null,
              input_data: {},
              output_data: { total_tokens: 300 },
            },
          ],
        },
      ],
    };

    expect(extractLatestLlmContextSnapshot(timeline)).toBeNull();
  });
});
