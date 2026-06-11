import type { PendingAction, PendingPlan } from '../../api/agent';

type AssistantMessage = {
  role: 'user' | 'assistant';
  content: string;
  pendingAction?: PendingAction | null;
  pendingPlan?: PendingPlan | null;
  pending_plan?: PendingPlan | null;
};

export function isPendingPlanContent(content: string): boolean {
  return /请确认将执行\s*\d+\s*步/.test(content) && content.includes('确认执行吗');
}

function hasStructuredPendingPlan(message: AssistantMessage): boolean {
  return Boolean(message.pendingPlan ?? message.pending_plan);
}

export function canConfirmAssistantMessage(message: AssistantMessage): boolean {
  return message.role === 'assistant' && (
    Boolean(message.pendingAction) ||
    hasStructuredPendingPlan(message) ||
    isPendingPlanContent(message.content)
  );
}
