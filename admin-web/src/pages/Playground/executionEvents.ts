import type { StreamChunk } from '../../api/agent';

export type ExecutionEvent =
  | { type: 'thought'; content: string }
  | { type: 'plan'; goal?: string; steps: unknown[] }
  | { type: 'plan_step_done'; step_index: number; skill: string; status: string }
  | { type: 'action'; tool_name: string; arguments: Record<string, unknown>; rationale?: string }
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
  | { type: 'error'; code: string; message: string };

export function executionEventFromChunk(chunk: StreamChunk): ExecutionEvent | null {
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
    case 'observation':
      return { type: 'observation', ...chunk.data };
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
    case 'error':
      return { type: 'error', ...chunk.data };
    default:
      return null;
  }
}
