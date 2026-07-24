import type { PendingAction, PendingPlan } from '../../api/agent';

export type PendingResolution = 'confirmed' | 'canceled';

type AssistantMessage = {
  role: 'user' | 'assistant';
  content: string;
  pendingAction?: PendingAction | null;
  pendingPlan?: PendingPlan | null;
  pending_plan?: PendingPlan | null;
  pendingResolution?: PendingResolution | null;
};

export function isPendingPlanContent(content: string): boolean {
  return /请确认将执行\s*\d+\s*步/.test(content) && content.includes('确认执行吗');
}

function hasStructuredPendingPlan(message: AssistantMessage): boolean {
  return Boolean(message.pendingPlan ?? message.pending_plan);
}

export function canConfirmAssistantMessage(message: AssistantMessage): boolean {
  if (message.pendingResolution) return false;
  return message.role === 'assistant' && (
    Boolean(message.pendingAction) ||
    hasStructuredPendingPlan(message) ||
    isPendingPlanContent(message.content)
  );
}

export function hasPendingConfirmationControls(message: AssistantMessage): boolean {
  return message.role === 'assistant' && (
    Boolean(message.pendingAction) ||
    hasStructuredPendingPlan(message) ||
    isPendingPlanContent(message.content)
  );
}
