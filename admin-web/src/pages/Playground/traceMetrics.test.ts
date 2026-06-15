import { describe, expect, it } from 'vitest';

import type { TraceTimeline } from '../../api/admin';
import { buildPlaygroundTraceMetrics, hasAutomaticCompression } from './traceMetrics';

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
