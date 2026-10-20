import { palette } from '../../styles/theme';
import type { ExecutionEvent } from './executionEvents';

export const eventMeta: Record<ExecutionEvent['type'], { label: string; color: string }> = {
  thought: { label: '思考', color: palette.purple },
  plan: { label: '执行计划', color: palette.accent },
  plan_step_done: { label: '计划步骤', color: palette.success },
  tool_call_delta: { label: '准备调用', color: palette.accent },
  action: { label: '工具调用', color: palette.accent },
  tool_started: { label: '执行中', color: palette.accent },
  tool_finished: { label: '工具完成', color: palette.success },
  observation: { label: '工具结果', color: palette.success },
  approval_required: { label: '等待确认', color: palette.warning },
  approval_result: { label: '审批结果', color: palette.purple },
  operation_committed: { label: '业务提交', color: palette.success },
  context_usage: { label: '上下文', color: '#8b949e' },
  context_compressing: { label: '上下文压缩', color: palette.warning },
  context_compressed: { label: '压缩完成', color: palette.success },
  doom_loop_warning: { label: '循环告警', color: palette.danger },
  verification_warning: { label: '检查告警', color: palette.warning },
  write_committed_reply_failed: { label: '收尾告警', color: palette.warning },
  retrying: { label: '自动重试', color: palette.warning },
  progress: { label: '执行进度', color: palette.accent },
  'step.started': { label: '执行中', color: palette.accent },
  'step.completed': { label: '已完成', color: palette.success },
  'tool.failed': { label: 'Tool 失败', color: palette.danger },
  'turn.completed': { label: '执行完成', color: palette.success },
  'turn.terminated': { label: '受控终止', color: palette.warning },
  'turn.failed': { label: '执行失败', color: palette.danger },
  error: { label: '执行失败', color: palette.danger },
};

type StepStartedEvent = Extract<ExecutionEvent, { type: 'step.started' }>;
type StepCompletedEvent = Extract<ExecutionEvent, { type: 'step.completed' }>;
type ActionEvent = Extract<ExecutionEvent, { type: 'action' }>;
type ToolStartedEvent = Extract<ExecutionEvent, { type: 'tool_started' }>;
type ToolFinishedEvent = Extract<ExecutionEvent, { type: 'tool_finished' }>;
type ObservationEvent = Extract<ExecutionEvent, { type: 'observation' }>;
type ToolFailedEvent = Extract<ExecutionEvent, { type: 'tool.failed' }>;

export type TimelineItem =
  | {
    kind: 'step';
    key: string;
    position: number;
    stepIndex: number;
    started?: StepStartedEvent;
    completed?: StepCompletedEvent;
  }
  | {
    kind: 'tool';
    key: string;
    position: number;
    toolName: string;
    step?: number;
    callId?: string;
    action?: ActionEvent;
    started?: ToolStartedEvent;
    finished?: ToolFinishedEvent;
    observation?: ObservationEvent;
    failed?: ToolFailedEvent;
  }
  | { kind: 'event'; key: string; position: number; event: ExecutionEvent };

export type TimelineStatus = 'waiting' | 'running' | 'completed' | 'failed';

export function jsonText(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? String(value);
  } catch {
    return String(value);
  }
}

export type StepTimelineItem = Extract<TimelineItem, { kind: 'step' }>;
export type ToolTimelineItem = Extract<TimelineItem, { kind: 'tool' }>;

export interface ExecutionChainGroup {
  key: string;
  stepIndex?: number;
  step?: StepTimelineItem;
  tools: ToolTimelineItem[];
}

/** 把扁平的 timeline 归到执行步骤下，保证「N 个步骤」和可见链路一致。 */
export function buildExecutionChain(items: TimelineItem[]): ExecutionChainGroup[] {
  const groups: ExecutionChainGroup[] = [];
  const byStep = new Map<number, ExecutionChainGroup>();
  let orphanGroup: ExecutionChainGroup | null = null;

  const ensureStepGroup = (stepIndex: number): ExecutionChainGroup => {
    const existing = byStep.get(stepIndex);
    if (existing) return existing;
    const group = { key: `step-${stepIndex}`, stepIndex, tools: [] };
    byStep.set(stepIndex, group);
    groups.push(group);
    return group;
  };

  items.forEach((item) => {
    if (item.kind === 'step') {
      ensureStepGroup(item.stepIndex).step = item;
      return;
    }
    if (item.kind !== 'tool') return;
    if (item.step !== undefined) {
      ensureStepGroup(item.step).tools.push(item);
      return;
    }
    if (!orphanGroup) {
      orphanGroup = { key: 'orphan-tools', tools: [] };
      groups.push(orphanGroup);
    }
    orphanGroup.tools.push(item);
  });

  return groups;
}

export function chainGroupStatus(
  group: ExecutionChainGroup,
  events: ExecutionEvent[],
  loading: boolean,
  approvalState?: ApprovalDisplayState,
): TimelineStatus {
  if (group.step) return settledItemStatus(group.step, events, loading, approvalState);
  const statuses = group.tools.map((tool) => settledItemStatus(tool, events, loading, approvalState));
  if (statuses.includes('failed')) return 'failed';
  if (statuses.includes('running')) return 'running';
  if (statuses.length > 0 && statuses.every((status) => status === 'completed')) return 'completed';
  return 'waiting';
}

function findToolItem(items: TimelineItem[], predicate: (item: Extract<TimelineItem, { kind: 'tool' }>) => boolean) {
  return [...items].reverse().find((item): item is Extract<TimelineItem, { kind: 'tool' }> => item.kind === 'tool' && predicate(item));
}

export function buildTimelineItems(events: ExecutionEvent[]): TimelineItem[] {
  const items: TimelineItem[] = [];
  const steps = new Map<number, Extract<TimelineItem, { kind: 'step' }>>();

  events.forEach((event, position) => {
    if (event.type === 'step.started') {
      const existing = steps.get(event.step_index);
      if (existing) existing.started = event;
      else {
        const item = { kind: 'step' as const, key: `step-${event.step_index}`, position, stepIndex: event.step_index, started: event };
        steps.set(event.step_index, item);
        items.push(item);
      }
      return;
    }
    if (event.type === 'step.completed') {
      const existing = steps.get(event.step_index);
      if (existing) existing.completed = event;
      else {
        const item = { kind: 'step' as const, key: `step-${event.step_index}`, position, stepIndex: event.step_index, completed: event };
        steps.set(event.step_index, item);
        items.push(item);
      }
      return;
    }
    if (event.type === 'action') {
      items.push({ kind: 'tool', key: `tool-action-${position}`, position, toolName: event.tool_name, action: event });
      return;
    }
    if (event.type === 'tool_started') {
      const existing = findToolItem(items, (item) => (
        !item.started
        && item.toolName === event.tool_name
        && (item.step === undefined || item.step === event.step)
      ));
      if (existing) {
        existing.started = event;
        existing.callId = event.tool_call_id;
        existing.step = event.step;
      } else {
        items.push({ kind: 'tool', key: `tool-${event.tool_call_id || position}`, position, toolName: event.tool_name, callId: event.tool_call_id, step: event.step, started: event });
      }
      return;
    }
    if (event.type === 'tool_finished') {
      const existing = findToolItem(items, (item) => (
        (item.callId && item.callId === event.tool_call_id)
        || (item.toolName === event.tool_name && item.step === event.step)
      ));
      if (existing) existing.finished = event;
      else items.push({ kind: 'tool', key: `tool-${event.tool_call_id || position}`, position, toolName: event.tool_name, callId: event.tool_call_id, step: event.step, finished: event });
      return;
    }
    if (event.type === 'tool.failed') {
      const existing = findToolItem(items, (item) => (
        (item.callId && item.callId === event.tool_call_id)
        || (item.toolName === event.tool_name && item.step === event.step)
      ));
      if (existing) existing.failed = event;
      else items.push({ kind: 'tool', key: `tool-${event.tool_call_id || position}`, position, toolName: event.tool_name, callId: event.tool_call_id, step: event.step, failed: event });
      return;
    }
    if (event.type === 'observation') {
      const existing = findToolItem(items, (item) => item.toolName === event.tool_name && !item.observation);
      if (existing) existing.observation = event;
      else items.push({ kind: 'tool', key: `tool-observation-${position}`, position, toolName: event.tool_name, observation: event });
      return;
    }
    items.push({ kind: 'event', key: event.event_id ?? `${event.type}-${position}`, position, event });
  });

  return items.sort((left, right) => left.position - right.position);
}

export function stepStatus(item: Extract<TimelineItem, { kind: 'step' }>): TimelineStatus {
  if (item.completed?.status === 'failed' || item.completed?.error) return 'failed';
  if (item.completed) return 'completed';
  if (item.started) return 'running';
  return 'waiting';
}

export function toolStatus(item: Extract<TimelineItem, { kind: 'tool' }>): TimelineStatus {
  if (item.failed || item.finished?.error || item.observation?.error) return 'failed';
  if (item.finished || item.observation) return 'completed';
  if (item.started) return 'running';
  return 'waiting';
}

export type ApprovalDisplayState = 'awaiting' | 'confirmed' | 'canceled';

export function executionStatus(events: ExecutionEvent[], loading: boolean, approvalState?: ApprovalDisplayState) {
  if (approvalState === 'awaiting') return { label: '等待确认', tone: 'warning', running: false } as const;
  if (approvalState === 'confirmed') return { label: '已确认', tone: 'waiting', running: false } as const;
  if (approvalState === 'canceled') return { label: '已取消', tone: 'warning', running: false } as const;
  // 终态与审批都以最新事件为准，避免审批等待被误显示为持续执行。
  const latest = [...events].reverse().find((event) => [
    'turn.completed', 'turn.terminated', 'turn.failed', 'error', 'approval_required', 'approval_result',
  ].includes(event.type));
  if (latest?.type === 'turn.failed' || latest?.type === 'error') return { label: '执行失败', tone: 'failed', running: false } as const;
  if (latest?.type === 'turn.terminated') return { label: '已终止', tone: 'warning', running: false } as const;
  if (latest?.type === 'turn.completed') return { label: '已完成', tone: 'completed', running: false } as const;
  if (latest?.type === 'approval_required') return { label: '等待确认', tone: 'warning', running: false } as const;
  if (latest?.type === 'approval_result' && latest.decision === 'rejected') return { label: '已取消', tone: 'warning', running: false } as const;
  if (loading) return { label: '正在执行', tone: 'running', running: true } as const;
  return { label: '执行记录', tone: 'waiting', running: false } as const;
}

export function settledItemStatus(item: TimelineItem, events: ExecutionEvent[], loading: boolean, approvalState?: ApprovalDisplayState): TimelineStatus {
  const status = item.kind === 'tool' ? toolStatus(item) : item.kind === 'step' ? stepStatus(item) : 'waiting';
  // 只有工具自己的完成事件能证明成功；终止后未结束的调用应保留为中断状态。
  if (status !== 'running' || executionStatus(events, loading, approvalState).running) return status;
  return 'waiting';
}

/* 耗时人性化展示：原始毫秒（如 121544ms）对调试者也不友好 */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return `${minutes}分${seconds}秒`;
}

