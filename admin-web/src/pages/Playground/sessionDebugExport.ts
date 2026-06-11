import type { TracePayload } from '../../utils/tracePayload';
import type { TraceTimeline } from '../../api/admin';
import type { PendingAction } from '../../api/agent';

export interface SessionDebugMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface SessionDebugRouterDiagnostic {
  round_index: number;
  input_data: TracePayload;
  output_data: TracePayload;
}

export interface SessionDebugPendingPlan {
  round_index: number;
  input_data: TracePayload;
  output_data: TracePayload;
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

export interface SessionDebugExport {
  session_id: string;
  messages: SessionDebugMessage[];
  used_skills: string[];
  pending_actions: PendingAction[];
  skill_calls: SessionDebugSkillCall[];
  router_diagnostics: SessionDebugRouterDiagnostic[];
  pending_plans: SessionDebugPendingPlan[];
}

export interface SessionDebugExportMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  skills?: string[];
  pendingAction?: PendingAction | null;
}

export interface BuildSessionDebugExportParams {
  sessionId: string;
  messages: SessionDebugExportMessage[];
  timeline: TraceTimeline | null;
}

export function buildSessionDebugExport({
  sessionId,
  messages,
  timeline,
}: BuildSessionDebugExportParams): SessionDebugExport {
  return {
    session_id: sessionId,
    messages: messages.map((message) => ({
      role: message.role,
      content: message.content,
    })),
    used_skills: uniqueSkills(messages),
    pending_actions: messages
      .map((message) => message.pendingAction)
      .filter((action): action is PendingAction => Boolean(action)),
    skill_calls: extractSkillCalls(timeline),
    router_diagnostics: extractNodes(timeline, 'skill_router'),
    pending_plans: extractPendingPlans(timeline),
  };
}

function uniqueSkills(messages: SessionDebugExportMessage[]): string[] {
  return Array.from(
    new Set(messages.flatMap((message) => message.skills ?? [])),
  );
}

function extractNodes(
  timeline: TraceTimeline | null,
  nodeType: 'skill_router',
): SessionDebugRouterDiagnostic[] {
  if (!timeline?.rounds) {
    return [];
  }

  return timeline.rounds.flatMap((round) =>
    round.nodes
      .filter((node) => node.node_type === nodeType)
      .map((node) => ({
        round_index: round.round_index,
        input_data: node.input_data,
        output_data: node.output_data,
      })),
  );
}

function extractPendingPlans(
  timeline: TraceTimeline | null,
): SessionDebugPendingPlan[] {
  if (!timeline?.rounds) {
    return [];
  }

  return timeline.rounds.flatMap((round) =>
    round.nodes
      .filter(
        (node) =>
          node.node_type === 'pending_plan' ||
          (node.node_type === 'skill_call' && node.node_name === 'pending_plan'),
      )
      .map((node) => ({
        round_index: round.round_index,
        input_data: node.input_data,
        output_data: node.output_data,
      })),
  );
}

function extractSkillCalls(timeline: TraceTimeline | null): SessionDebugSkillCall[] {
  if (!timeline?.rounds) {
    return [];
  }

  return timeline.rounds.flatMap((round) =>
    round.nodes
      .filter(
        (node) =>
          node.node_type === 'skill_call' && node.node_name !== 'pending_plan',
      )
      .map((node) => ({
        round_index: round.round_index,
        skill_name: node.node_name,
        status: node.status,
        duration_ms: node.duration_ms,
        input_data: node.input_data,
        output_data: node.output_data,
        error_message: node.error_message,
      })),
  );
}
