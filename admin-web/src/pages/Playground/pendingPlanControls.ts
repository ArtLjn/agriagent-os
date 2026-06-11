import type { PendingAction } from '../../api/agent';

type AssistantMessage = {
  role: 'user' | 'assistant';
  content: string;
  pendingAction?: PendingAction | null;
};

export function isPendingPlanContent(content: string): boolean {
  return /请确认将执行\s*\d+\s*步/.test(content) && content.includes('确认执行吗');
}

export function canConfirmAssistantMessage(message: AssistantMessage): boolean {
  return message.role === 'assistant' && (
    Boolean(message.pendingAction) || isPendingPlanContent(message.content)
  );
}
