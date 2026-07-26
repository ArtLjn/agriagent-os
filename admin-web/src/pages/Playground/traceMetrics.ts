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

export interface PlaygroundLlmContextMessage {
  index: number;
  role: string;
  type: string;
  content: unknown;
  contentPreview?: string;
  compressed?: boolean;
  status?: string;
  tool_calls?: unknown[];
  invalid_tool_calls?: unknown[];
  tool_call_id?: string;
  name?: string;
}

export interface PlaygroundLlmContextBlockDetail {
  key: string;
  category: string;
  source: string;
  decision: string;
  compressed: boolean;
  dropped: boolean;
  priority: number | null;
  required: boolean;
  tokenEstimate: number | null;
  contentPreview: string;
  content: string;
  reason: string;
}

export interface PlaygroundLlmContextRuntimeSection {
  name: string;
  tokenEstimate: number | null;
  blocks: PlaygroundLlmContextBlockDetail[];
}

export interface PlaygroundLlmContextCompression {
  contextCompressedCount: number;
  contextDroppedCount: number;
  messageCompressedCount: number;
  toolResultCompressedCount: number;
  events: unknown[];
}

export interface PlaygroundLlmContextSnapshot {
  schemaVersion: number | null;
  systemPrompt: string;
  messages: PlaygroundLlmContextMessage[];
  contextBlocks: string[];
  contextBlockDetails: PlaygroundLlmContextBlockDetail[];
  runtimeSections: PlaygroundLlmContextRuntimeSection[];
  budget: Record<string, unknown>;
  compression: PlaygroundLlmContextCompression | null;
  promptTokens: number | null;
  maxTokens: number | null;
  actions: string[];
  truncated: boolean;
  raw: Record<string, unknown>;
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

function toBoolean(value: unknown): boolean {
  return value === true;
}

function toStringValue(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function readTokenUsage(node: TraceNode): Record<string, unknown> | null {
  return asRecord(node.token_usage);
}

function readLlmContextBlockDetail(
  value: unknown,
): PlaygroundLlmContextBlockDetail | null {
  const item = asRecord(value);
  if (!item) return null;
  const key = toStringValue(item.key);
  if (!key) return null;

  return {
    key,
    category: toStringValue(item.category) || 'uncategorized',
    source: toStringValue(item.source),
    decision: toStringValue(item.decision),
    compressed: toBoolean(item.compressed),
    dropped: toBoolean(item.dropped),
    priority: toNumber(item.priority),
    required: toBoolean(item.required),
    tokenEstimate: toNumber(item.token_estimate),
    contentPreview: toStringValue(item.content_preview),
    content: toStringValue(item.content),
    reason: toStringValue(item.reason),
  };
}

function readRuntimeSections(
  value: unknown,
): PlaygroundLlmContextRuntimeSection[] {
  const runtimeContext = asRecord(value);
  return asArray(runtimeContext?.sections)
    .map((sectionValue) => {
      const section = asRecord(sectionValue);
      if (!section) return null;
      const blocks = asArray(section.blocks)
        .map(readLlmContextBlockDetail)
        .filter((item): item is PlaygroundLlmContextBlockDetail => item !== null);
      const name = toStringValue(section.name) || 'runtime_context';
      return {
        name,
        tokenEstimate: toNumber(section.token_estimate),
        blocks,
      };
    })
    .filter((item): item is PlaygroundLlmContextRuntimeSection => item !== null);
}

function readCompression(value: unknown): PlaygroundLlmContextCompression | null {
  const compression = asRecord(value);
  if (!compression) return null;
  return {
    contextCompressedCount: toNumber(compression.context_compressed_count) ?? 0,
    contextDroppedCount: toNumber(compression.context_dropped_count) ?? 0,
    messageCompressedCount: toNumber(compression.message_compressed_count) ?? 0,
    toolResultCompressedCount: toNumber(compression.tool_result_compressed_count) ?? 0,
    events: asArray(compression.events),
  };
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

  const promptNode = [...nodes].reverse().find(
    (node) => node.node_type === 'prompt_budget' && node.node_name === 'final_prompt',
  );
  const finalContextNode = [...nodes].reverse().find(
    (node) => node.node_type === 'prompt_budget' && node.node_name === 'final_llm_context',
  );
  const promptOutput = asRecord(promptNode?.output_data);
  const finalContextOutput = asRecord(finalContextNode?.output_data);
  const finalContextBudget = asRecord(finalContextOutput?.budget);
  const budgetOutput = promptOutput ?? finalContextBudget;
  if (budgetOutput) {
    metrics.promptTokens = toNumber(budgetOutput.total_tokens);
    metrics.promptMaxTokens = toNumber(budgetOutput.max_tokens);
    metrics.promptActions = asArray(budgetOutput.actions).filter(
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

export function extractLatestLlmContextSnapshot(
  timeline: TraceTimeline | null,
): PlaygroundLlmContextSnapshot | null {
  if (!timeline?.rounds) return null;

  const nodes = timeline.rounds.flatMap((round) => round.nodes);
  const contextNode = [...nodes].reverse().find(
    (node) => node.node_type === 'prompt_budget' && node.node_name === 'final_llm_context',
  );
  const output = asRecord(contextNode?.output_data);
  if (!output) return null;

  const budget = asRecord(output.budget) ?? {};
  const usage = contextNode ? readTokenUsage(contextNode) : null;
  const runtimeSections = readRuntimeSections(output.runtime_context);
  const contextBlockDetails = runtimeSections.flatMap((section) => section.blocks);
  const compression = readCompression(output.compression);
  const messages = asArray(output.messages)
    .map((item) => asRecord(item))
    .filter((item): item is Record<string, unknown> => item !== null)
    .map((item, fallbackIndex) => {
      const message: PlaygroundLlmContextMessage = {
        index: toNumber(item.index) ?? fallbackIndex,
        role: typeof item.role === 'string' ? item.role : 'unknown',
        type: typeof item.type === 'string' ? item.type : 'unknown',
        content: item.content,
      };
      if (typeof item.content_preview === 'string') message.contentPreview = item.content_preview;
      if (typeof item.compressed === 'boolean') message.compressed = item.compressed;
      if (typeof item.status === 'string') message.status = item.status;
      const toolCalls = asArray(item.tool_calls);
      const invalidToolCalls = asArray(item.invalid_tool_calls);
      if (toolCalls.length > 0) message.tool_calls = toolCalls;
      if (invalidToolCalls.length > 0) message.invalid_tool_calls = invalidToolCalls;
      if (typeof item.tool_call_id === 'string') message.tool_call_id = item.tool_call_id;
      if (typeof item.name === 'string') message.name = item.name;
      return message;
    });
  return {
    schemaVersion: toNumber(output.schema_version),
    systemPrompt: typeof output.system_prompt === 'string' ? output.system_prompt : '',
    messages,
    contextBlocks: asArray(output.context_blocks).filter(
      (item): item is string => typeof item === 'string',
    ),
    contextBlockDetails,
    runtimeSections,
    budget,
    compression,
    promptTokens: toNumber(budget.total_tokens) ?? toNumber(usage?.prompt_tokens),
    maxTokens: toNumber(budget.max_tokens),
    actions: asArray(budget.actions).filter((item): item is string => typeof item === 'string'),
    truncated: output.__trace_truncated === true,
    raw: output,
  };
}

export function hasAutomaticCompression(metrics: PlaygroundTraceMetrics): boolean {
  return metrics.contextCompressedCount > 0
    || metrics.contextDroppedCount > 0
    || metrics.promptActions.length > 0;
}
