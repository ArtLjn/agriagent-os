import type { PendingAction } from '../../api/agent';
import type { TracePayload } from '../../utils/tracePayload';
import type { TraceTimeline } from '../../api/admin';

export interface DebugExportMessage {
  role: 'user' | 'assistant' | string;
  content: string;
  skills?: string[];
  pendingAction?: PendingAction | null;
}

export interface BuildSessionDebugExportArgs {
  sessionId: string;
  simulateUserId?: string | null;
  copiedAt: string;
  messages: DebugExportMessage[];
  timeline?: TraceTimeline | null;
}

export interface SessionDebugSkillCall {
  round_index: number;
  skill_name: string;
  status: string;
  duration_ms: number | null;
  input_data: TracePayload;
  output_data: TracePayload;
  error_message: string | null;
}

export interface SessionDebugPendingAction {
  message_index: number;
  action_id: string;
  skill_name: string;
  params: Record<string, unknown>;
  context?: PendingAction['context'] | null;
}

export interface SessionDebugExport {
  format: 'farm-manager.chat-session-debug.v1';
  session_id: string;
  simulate_user_id: string | null;
  copied_at: string;
  messages: Array<{
    role: string;
    content: string;
    skills?: string[];
    pending_action?: PendingAction | null;
  }>;
  used_skills: string[];
  pending_actions: SessionDebugPendingAction[];
  trace_request_id: string | null;
  skill_calls: SessionDebugSkillCall[];
}

export function buildSessionDebugExport({
  sessionId,
  simulateUserId,
  copiedAt,
  messages,
  timeline,
}: BuildSessionDebugExportArgs): SessionDebugExport {
  const normalizedMessages = messages.map((item) => ({
    role: item.role,
    content: item.content,
    ...(item.skills?.length ? { skills: item.skills } : {}),
    ...(item.pendingAction ? { pending_action: item.pendingAction } : {}),
  }));

  const usedSkills = Array.from(
    new Set(messages.flatMap((item) => item.skills ?? [])),
  );
  const pendingActions = messages.flatMap((item, index) => {
    if (!item.pendingAction) return [];
    return [
      {
        message_index: index,
        action_id: item.pendingAction.action_id,
        skill_name: item.pendingAction.skill_name,
        params: item.pendingAction.params,
        context: item.pendingAction.context,
      },
    ];
  });
  const skillCalls = (timeline?.rounds ?? []).flatMap((round) => (
    round.nodes
      .filter((node) => node.node_type === 'skill_call')
      .map((node) => ({
        round_index: round.round_index,
        skill_name: node.node_name,
        status: node.status,
        duration_ms: node.duration_ms,
        input_data: node.input_data,
        output_data: node.output_data,
        error_message: node.error_message,
      }))
  ));

  return {
    format: 'farm-manager.chat-session-debug.v1',
    session_id: sessionId,
    simulate_user_id: simulateUserId ?? null,
    copied_at: copiedAt,
    messages: normalizedMessages,
    used_skills: usedSkills,
    pending_actions: pendingActions,
    trace_request_id: timeline?.request_id ?? null,
    skill_calls: skillCalls,
  };
}
