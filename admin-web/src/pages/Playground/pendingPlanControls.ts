import type { PendingAction, PendingPlan } from '../../api/agent';

export type PendingResolution = 'confirmed' | 'canceled';

export type AssistantMessage = {
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
  // 已确认/取消后不再渲染按钮（用户要求"执行过一次就不允许再显示"）。
  if (message.pendingResolution) return false;
  return message.role === 'assistant' && (
    Boolean(message.pendingAction) ||
    hasStructuredPendingPlan(message) ||
    isPendingPlanContent(message.content)
  );
}

/**
 * 切换会话时根据消息顺序重建 pendingResolution。
 *
 * pendingResolution 只存在前端 React state，切换会话会丢失。后端历史消息里
 * pending_action / pending_plan 字段不会被清掉，所以加载后按钮又会变成可执行。
 *
 * 推断规则：assistant 的 pending 消息如果不是最后一条，说明对话已经继续往下走，
 * 当时一定确认或取消过了 —— 标记为 'confirmed'。最后一条 pending 保留可执行，
 * 因为它可能仍处于等待用户确认的活跃状态。
 */
export function applyHistoricalPendingResolution<T extends AssistantMessage>(
  messages: T[],
): T[] {
  const lastIndex = messages.length - 1;
  return messages.map((msg, idx) => {
    if (!hasPendingConfirmationControls(msg)) return msg;
    if (idx === lastIndex) return msg;
    return { ...msg, pendingResolution: 'confirmed' };
  });
}
