import type { StreamChunk } from '../../api/agent';

type ExecutionEventMetadata = { event_id?: string; seq?: number };

type ExecutionEventPayload =
  | { type: 'thought'; content: string }
  | { type: 'plan'; goal?: string; steps: unknown[] }
  | { type: 'plan_step_done'; step_index: number; skill: string; status: string }
  | { type: 'tool_call_delta'; tool_call_id: string; name: string; index: number; arguments_delta: string }
  | { type: 'action'; tool_name: string; arguments: Record<string, unknown>; rationale?: string }
  | { type: 'tool_started'; turn_id: string; tool_call_id: string; tool_name: string; step: number; arguments: Record<string, unknown> }
  | { type: 'tool_finished'; turn_id: string; tool_call_id: string; tool_name: string; step: number; duration_ms: number; result?: unknown; error?: Record<string, unknown> | null }
  | { type: 'observation'; tool_name: string; result?: unknown; error?: string | null }
  | { type: 'approval_required'; tool_name: string; arguments: Record<string, unknown> }
  | { type: 'approval_result'; decision: 'approved' | 'rejected'; reason?: string }
  | { type: 'operation_committed'; result?: unknown }
  | { type: 'context_usage'; percent: number; level: string; used: number; total: number; step?: number }
  | { type: 'context_compressing'; trigger: string; before_percent: number }
  | { type: 'context_compressed'; after_percent: number; summary_preview?: string }
  | { type: 'doom_loop_warning'; message: string }
  | { type: 'verification_warning'; issues: string[] }
  | { type: 'write_committed_reply_failed'; code: string; message: string }
  | { type: 'retrying'; code: string; category?: string; attempt: number; delay_ms: number }
  | { type: 'progress'; message?: string; phase?: string; tool_name?: string; tool_call_id?: string; step?: number; status?: string; reason?: string; observation_fingerprint?: string; semantic_status?: string; semantic_reason?: string }
  | { type: 'step.started'; step_index: number; status: string }
  | { type: 'step.completed'; step_index: number; status: string; tool_count: number; error?: Record<string, unknown> }
  | { type: 'tool.failed'; tool_call_id: string; tool_name: string; step: number; duration_ms: number; error: Record<string, unknown> }
  | { type: 'turn.completed'; status: 'completed'; stop_reason?: string; step_count?: number; message?: string }
  | { type: 'turn.terminated'; status: 'terminated'; reason: string; message: string; step_count?: number }
  | { type: 'turn.failed'; status: 'failed'; stop_reason: string; error: Record<string, unknown> }
  | { type: 'error'; code: string; message: string; category?: string; phase?: string; retryable?: boolean; attempt?: number; stream_started?: boolean };

export type ExecutionEvent = ExecutionEventMetadata & ExecutionEventPayload;

export function executionEventFromChunk(chunk: StreamChunk): ExecutionEvent | null {
  const event = executionEventFromChunkBase(chunk);
  if (!event) return null;
  const data = chunk.data as unknown as { event_id?: unknown; seq?: unknown };
  return {
    ...event,
    event_id: typeof data.event_id === 'string' ? data.event_id : undefined,
    seq: typeof data.seq === 'number' ? data.seq : undefined,
  };
}

function executionEventFromChunkBase(chunk: StreamChunk): ExecutionEventPayload | null {
  switch (chunk.type) {
    case 'thought':
      return { type: 'thought', content: chunk.data };
    case 'plan':
      return { type: 'plan', steps: chunk.data.steps };
    case 'plan_created':
      return { type: 'plan', goal: chunk.data.goal, steps: chunk.data.steps };
    case 'plan_step_done':
      return { type: 'plan_step_done', ...chunk.data };
    case 'action':
      return { type: 'action', ...chunk.data };
    case 'tool_started':
      return { type: 'tool_started', ...chunk.data };
    case 'tool_finished':
      return { type: 'tool_finished', ...chunk.data };
    case 'tool_call_delta':
      return { type: 'tool_call_delta', ...chunk.data };
    case 'observation':
      return { type: 'observation', ...chunk.data };
    case 'progress':
      return { type: 'progress', ...chunk.data };
    case 'pending_action':
      return {
        type: 'approval_required',
        tool_name: chunk.data.skill_name,
        arguments: chunk.data.params,
      };
    case 'pending_plan':
      return {
        type: 'plan',
        goal: chunk.data.goal,
        steps: chunk.data.steps ?? [],
      };
    case 'approval_result':
      return { type: 'approval_result', ...chunk.data };
    case 'operation_committed':
      return { type: 'operation_committed', result: chunk.data.result };
    case 'context_usage':
      return { type: 'context_usage', ...chunk.data };
    case 'context_compressing':
      return { type: 'context_compressing', ...chunk.data };
    case 'context_compressed':
      return { type: 'context_compressed', ...chunk.data };
    case 'doom_loop_warning':
      return { type: 'doom_loop_warning', ...chunk.data };
    case 'verification_warning':
      return { type: 'verification_warning', ...chunk.data };
    case 'write_committed_reply_failed':
      return { type: 'write_committed_reply_failed', ...chunk.data };
    case 'retrying':
      return { type: 'retrying', ...chunk.data };
    case 'step.started':
      return { type: 'step.started', step_index: chunk.data.step_index, status: chunk.data.status };
    case 'step.completed':
      return { type: 'step.completed', ...chunk.data };
    case 'tool.failed':
      return { type: 'tool.failed', ...chunk.data };
    case 'turn.completed':
      return { type: 'turn.completed', ...chunk.data };
    case 'turn.terminated':
      return { type: 'turn.terminated', ...chunk.data };
    case 'turn.failed':
      return { type: 'turn.failed', ...chunk.data };
    case 'error':
      return { type: 'error', ...chunk.data };
    default:
      return null;
  }
}

export function appendExecutionEvent(
  events: ExecutionEvent[],
  next: ExecutionEvent,
): ExecutionEvent[] {
  const key = next.event_id ?? `${next.type}:${next.seq ?? events.length}`;
  const merged = new Map(
    events.map((event, index) => [event.event_id ?? `${event.type}:${event.seq ?? index}`, event]),
  );
  merged.set(key, next);
  return [...merged.values()].sort((left, right) => {
    if (left.seq === undefined || right.seq === undefined) return 0;
    return left.seq - right.seq;
  });
}
