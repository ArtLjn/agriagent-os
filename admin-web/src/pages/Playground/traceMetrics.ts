import type { TraceNode, TraceTimeline } from '../../api/admin';

export interface PlaygroundTraceMetrics {
  contextTokens: number | null;
  contextBudget: number | null;
  contextCompressedCount: number;
  contextDroppedCount: number;
  promptTokens: number | null;
  promptMaxTokens: number | null;
  promptActions: string[];
  llmPromptTokens: number;
  llmCompletionTokens: number;
  llmTotalTokens: number;
}

const EMPTY_METRICS: PlaygroundTraceMetrics = {
  contextTokens: null,
  contextBudget: null,
  contextCompressedCount: 0,
  contextDroppedCount: 0,
  promptTokens: null,
  promptMaxTokens: null,
  promptActions: [],
  llmPromptTokens: 0,
  llmCompletionTokens: 0,
  llmTotalTokens: 0,
};

function toNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function readTokenUsage(node: TraceNode): Record<string, unknown> | null {
  return asRecord(node.token_usage);
}

export function buildPlaygroundTraceMetrics(timeline: TraceTimeline | null): PlaygroundTraceMetrics {
  if (!timeline?.rounds) return EMPTY_METRICS;

  const metrics: PlaygroundTraceMetrics = { ...EMPTY_METRICS };
  const nodes = timeline.rounds.flatMap((round) => round.nodes);

  const contextNode = [...nodes].reverse().find((node) => node.node_type === 'context_build');
  const contextOutput = asRecord(contextNode?.output_data);
  if (contextOutput) {
    metrics.contextTokens = toNumber(contextOutput.token_estimate);
    metrics.contextBudget = toNumber(contextOutput.token_budget);
    metrics.contextCompressedCount = asArray(contextOutput.compressed_blocks).length;
    metrics.contextDroppedCount = asArray(contextOutput.dropped_blocks).length;
  }

  const promptNode = [...nodes].reverse().find((node) => node.node_type === 'prompt_budget');
  const promptOutput = asRecord(promptNode?.output_data);
  if (promptOutput) {
    metrics.promptTokens = toNumber(promptOutput.total_tokens);
    metrics.promptMaxTokens = toNumber(promptOutput.max_tokens);
    metrics.promptActions = asArray(promptOutput.actions).filter(
      (item): item is string => typeof item === 'string',
    );
  }

  for (const node of nodes) {
    if (node.node_type !== 'llm_call') continue;
    const usage = readTokenUsage(node);
    if (!usage) continue;
    const prompt = toNumber(usage.prompt_tokens) ?? 0;
    const completion = toNumber(usage.completion_tokens) ?? 0;
    const total = toNumber(usage.total_tokens) ?? prompt + completion;
    metrics.llmPromptTokens += prompt;
    metrics.llmCompletionTokens += completion;
    metrics.llmTotalTokens += total;
  }

  return metrics;
}

export function hasAutomaticCompression(metrics: PlaygroundTraceMetrics): boolean {
  return metrics.contextCompressedCount > 0
    || metrics.contextDroppedCount > 0
    || metrics.promptActions.length > 0;
}
