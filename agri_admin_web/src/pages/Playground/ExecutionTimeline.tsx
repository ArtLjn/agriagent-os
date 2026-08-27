import { type ReactNode, useState } from 'react';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CodeOutlined,
  DownOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
  LoadingOutlined,
  NodeIndexOutlined,
  SafetyCertificateOutlined,
  ToolOutlined,
  UpOutlined,
} from '@ant-design/icons';
import { Tag } from 'antd';
import { palette } from '../../styles/theme';
import type { ExecutionEvent } from './executionEvents';

const TEXT = palette.text;
const TEXT_DIM = palette.textMuted;
const BORDER = palette.border;

const eventMeta: Record<ExecutionEvent['type'], { label: string; color: string }> = {
  thought: { label: '思考', color: palette.purple },
  plan: { label: '执行计划', color: '#79c0ff' },
  plan_step_done: { label: '计划步骤', color: palette.success },
  tool_call_delta: { label: '准备调用', color: '#79c0ff' },
  action: { label: '工具调用', color: '#79c0ff' },
  tool_started: { label: '执行中', color: '#79c0ff' },
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
  progress: { label: '执行进度', color: '#79c0ff' },
  'step.started': { label: '执行中', color: '#79c0ff' },
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

type TimelineItem =
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

type TimelineStatus = 'waiting' | 'running' | 'completed' | 'failed';

const statusMeta: Record<TimelineStatus, { label: string; color: string }> = {
  waiting: { label: '准备中', color: TEXT_DIM },
  running: { label: '执行中', color: '#79c0ff' },
  completed: { label: '已完成', color: palette.success },
  failed: { label: '失败', color: palette.danger },
};

function EventIcon({ type }: { type: ExecutionEvent['type'] }) {
  const props = { style: { color: eventMeta[type].color, fontSize: 15 } };
  switch (type) {
    case 'thought': return <NodeIndexOutlined {...props} />;
    case 'plan': return <FileTextOutlined {...props} />;
    case 'action':
    case 'tool_call_delta':
    case 'tool_started':
    case 'tool_finished': return <ToolOutlined {...props} />;
    case 'observation': return <CodeOutlined {...props} />;
    case 'approval_required': return <SafetyCertificateOutlined {...props} />;
    case 'approval_result':
    case 'operation_committed':
    case 'context_compressed':
    case 'turn.completed':
    case 'plan_step_done': return <CheckCircleOutlined {...props} />;
    case 'context_usage': return <ClockCircleOutlined {...props} />;
    case 'progress':
    case 'step.started': return <LoadingOutlined {...props} />;
    case 'step.completed': return <CheckCircleOutlined {...props} />;
    case 'tool.failed':
    case 'error':
    case 'turn.failed':
    case 'doom_loop_warning': return <ExclamationCircleOutlined {...props} />;
    case 'turn.terminated': return <ClockCircleOutlined {...props} />;
    default: return <LoadingOutlined {...props} />;
  }
}

function StatusIcon({ status }: { status: TimelineStatus }) {
  const props = { style: { color: statusMeta[status].color, fontSize: 15 } };
  if (status === 'running') return <LoadingOutlined spin {...props} />;
  if (status === 'failed') return <ExclamationCircleOutlined {...props} />;
  if (status === 'completed') return <CheckCircleOutlined {...props} />;
  return <ClockCircleOutlined {...props} />;
}

function jsonText(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? String(value);
  } catch {
    return String(value);
  }
}

function DetailDisclosure({ label, value, tone = TEXT }: { label: string; value: unknown; tone?: string }) {
  const [open, setOpen] = useState(false);
  const text = jsonText(value);
  if (!text || text === '{}' || text === 'null' || text === 'undefined') return null;
  return (
    <details open={open} onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)} style={{ marginTop: 9 }}>
      <summary style={{ color: TEXT_DIM, cursor: 'pointer', fontSize: 12, userSelect: 'none' }}>
        <span style={{ color: tone, fontWeight: 600 }}>{label}</span>
        <span style={{ marginLeft: 8 }}>展开查看 · {text.length} 字符</span>
      </summary>
      <pre style={{ margin: '8px 0 0', padding: '10px 12px', maxHeight: 280, overflow: 'auto', borderRadius: 6, border: `1px solid ${BORDER}`, background: 'rgba(0, 0, 0, 0.2)', color: TEXT, fontSize: 12, lineHeight: 1.55, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
        {text}
      </pre>
    </details>
  );
}

function TextDisclosure({ label, text, tone = TEXT }: { label: string; text: string; tone?: string }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  return (
    <details open={open} onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)} style={{ marginTop: 9 }}>
      <summary style={{ color: TEXT_DIM, cursor: 'pointer', fontSize: 12, userSelect: 'none' }}>
        <span style={{ color: tone, fontWeight: 600 }}>{label}</span>
        <span style={{ marginLeft: 8 }}>展开查看 · {text.length} 字符</span>
      </summary>
      <pre style={{ margin: '8px 0 0', padding: '10px 12px', maxHeight: 280, overflow: 'auto', borderRadius: 6, border: `1px solid ${BORDER}`, background: 'rgba(0, 0, 0, 0.2)', color: TEXT, fontSize: 12, lineHeight: 1.55, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
        {text}
      </pre>
    </details>
  );
}

function EventBody({ event }: { event: ExecutionEvent }) {
  switch (event.type) {
    case 'thought':
      return <TextDisclosure label="查看模型思考" text={event.content} tone={palette.purple} />;
    case 'plan':
      return (
        <ol style={{ margin: '8px 0 0 20px', padding: 0, color: TEXT, lineHeight: 1.65 }}>
          {event.steps.map((step, index) => <li key={index}>{typeof step === 'string' ? step : jsonText(step)}</li>)}
        </ol>
      );
    case 'plan_step_done':
      return <span style={{ color: TEXT_DIM }}>步骤 {event.step_index + 1} · {event.skill} · {event.status}</span>;
    case 'tool_call_delta':
      return <span style={{ color: TEXT_DIM }}>正在组装调用参数 · {event.tool_call_id}</span>;
    case 'action':
      return (
        <>
          {event.rationale && <div style={{ color: TEXT_DIM, lineHeight: 1.55 }}>{event.rationale}</div>}
          <DetailDisclosure label="查看调用参数" value={event.arguments} tone="#79c0ff" />
        </>
      );
    case 'observation':
      return event.error
        ? <div style={{ color: palette.danger, whiteSpace: 'pre-wrap' }}>{event.error}</div>
        : <DetailDisclosure label="查看工具结果" value={event.result} tone={palette.success} />;
    case 'approval_required':
      return <DetailDisclosure label="查看待确认参数" value={event.arguments} tone={palette.warning} />;
    case 'approval_result':
      return <span style={{ color: TEXT }}>{event.decision === 'approved' ? '用户已确认执行' : '用户已拒绝执行'}{event.reason ? ` · ${event.reason}` : ''}</span>;
    case 'operation_committed':
      return <DetailDisclosure label="查看提交结果" value={event.result} tone={palette.success} />;
    case 'context_usage':
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: TEXT_DIM }}>
          <div style={{ flex: 1, height: 6, borderRadius: 99, background: 'rgba(139,148,158,0.16)', overflow: 'hidden' }}>
            <div style={{ width: `${Math.min(event.percent, 100)}%`, height: '100%', background: event.level === 'red' ? palette.danger : event.level === 'yellow' ? palette.warning : palette.success }} />
          </div>
          <span style={{ fontFamily: 'monospace' }}>{event.percent}% · {(event.used / 1000).toFixed(1)}K / {(event.total / 1000).toFixed(0)}K</span>
        </div>
      );
    case 'context_compressing':
      return <span style={{ color: TEXT_DIM }}>触发：{event.trigger} · 压缩前占用 {event.before_percent}%</span>;
    case 'context_compressed':
      return <span style={{ color: TEXT_DIM }}>上下文占用降至 {event.after_percent}%{event.summary_preview ? ` · ${event.summary_preview}` : ''}</span>;
    case 'doom_loop_warning':
      return <span style={{ color: palette.danger, whiteSpace: 'pre-wrap' }}>{event.message}</span>;
    case 'verification_warning':
      return <ul style={{ margin: 0, paddingLeft: 20, color: TEXT }}>{event.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul>;
    case 'write_committed_reply_failed':
      return <span style={{ color: palette.warning }}>{event.code} · {event.message}</span>;
    case 'retrying':
      return <span style={{ color: palette.warning }}>{event.code} · {event.category ?? 'transient'} · 第 {event.attempt} 次，等待 {event.delay_ms}ms</span>;
    case 'progress':
      return <span style={{ color: TEXT_DIM }}>{event.message}{event.phase ? ` · ${event.phase}` : ''}</span>;
    case 'turn.completed':
      return <span style={{ color: palette.success }}>{event.message ?? `停止原因：${event.stop_reason ?? 'completed'}${event.step_count === undefined ? '' : ` · 共 ${event.step_count} 步`}`}</span>;
    case 'turn.terminated':
      return <span style={{ color: palette.warning }}>{event.reason} · {event.message}{event.step_count === undefined ? '' : ` · 共 ${event.step_count} 步`}</span>;
    case 'turn.failed':
      return <span style={{ color: palette.danger }}>停止原因：{event.stop_reason}<DetailDisclosure label="查看错误详情" value={event.error} tone={palette.danger} /></span>;
    case 'tool_started':
    case 'tool_finished':
    case 'step.started':
    case 'step.completed':
    case 'tool.failed':
      return null;
    case 'error':
      return <span style={{ color: palette.danger }}>{event.code} · {event.category ? `${event.category} · ` : ''}{event.message}</span>;
  }
}

function findToolItem(items: TimelineItem[], predicate: (item: Extract<TimelineItem, { kind: 'tool' }>) => boolean) {
  return [...items].reverse().find((item): item is Extract<TimelineItem, { kind: 'tool' }> => item.kind === 'tool' && predicate(item));
}

function buildTimelineItems(events: ExecutionEvent[]): TimelineItem[] {
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

function stepStatus(item: Extract<TimelineItem, { kind: 'step' }>): TimelineStatus {
  if (item.completed?.status === 'failed' || item.completed?.error) return 'failed';
  if (item.completed) return 'completed';
  if (item.started) return 'running';
  return 'waiting';
}

function toolStatus(item: Extract<TimelineItem, { kind: 'tool' }>): TimelineStatus {
  if (item.failed || item.finished?.error || item.observation?.error) return 'failed';
  if (item.finished || item.observation) return 'completed';
  if (item.started) return 'running';
  return 'waiting';
}

function TimelineRow({ icon, title, tag, children, position, isLast }: { icon: ReactNode; title: string; tag: { label: string; color: string }; children?: ReactNode; position: number; isLast: boolean }) {
  return (
    <div style={{ display: 'flex', gap: 12, position: 'relative', paddingBottom: isLast ? 0 : 16 }}>
      {!isLast && <div style={{ position: 'absolute', left: 8, top: 22, bottom: 0, width: 1, background: 'rgba(139,148,158,0.25)' }} />}
      <div style={{ width: 17, height: 17, borderRadius: '50%', display: 'grid', placeItems: 'center', flexShrink: 0, background: palette.bgPanel, zIndex: 1 }}>{icon}</div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 18, flexWrap: 'wrap' }}>
          <span style={{ color: TEXT, fontSize: 13, fontWeight: 600 }}>{title}</span>
          <Tag bordered={false} style={{ margin: 0, color: tag.color, background: `${tag.color}1c`, fontSize: 11, lineHeight: '20px' }}>{tag.label}</Tag>
          <span style={{ color: TEXT_DIM, fontSize: 11 }}>#{position + 1}</span>
        </div>
        {children && <div style={{ marginTop: 6, fontSize: 13 }}>{children}</div>}
      </div>
    </div>
  );
}

function ToolBody({ item }: { item: Extract<TimelineItem, { kind: 'tool' }> }) {
  const result = item.finished?.result ?? item.observation?.result;
  const error = item.failed?.error ?? item.finished?.error ?? item.observation?.error;
  const argumentsValue = item.started?.arguments ?? item.action?.arguments;
  return (
    <>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: TEXT_DIM, fontSize: 12 }}>
        {item.step !== undefined && <span>第 {item.step} 步</span>}
        {item.callId && <span title={item.callId} style={{ fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>· {item.callId}</span>}
        {item.finished && <span>· {item.finished.duration_ms}ms</span>}
      </div>
      {item.action?.rationale && <div style={{ marginTop: 7, color: TEXT_DIM, lineHeight: 1.55 }}>{item.action.rationale}</div>}
      <DetailDisclosure label="查看调用参数" value={argumentsValue} tone="#79c0ff" />
      {error ? <div style={{ marginTop: 9, color: palette.danger, whiteSpace: 'pre-wrap' }}>{jsonText(error)}</div> : <DetailDisclosure label="查看工具结果" value={result} tone={palette.success} />}
    </>
  );
}

function TimelineItemView({ item, index, isLast }: { item: TimelineItem; index: number; isLast: boolean }) {
  if (item.kind === 'step') {
    const status = stepStatus(item);
    return <TimelineRow icon={<StatusIcon status={status} />} title={`第 ${item.stepIndex} 步`} tag={statusMeta[status]} position={index} isLast={isLast}>
      <span style={{ color: TEXT_DIM }}>{item.completed ? `${item.completed.tool_count} 个工具已完成` : '正在等待模型和工具返回'}</span>
    </TimelineRow>;
  }
  if (item.kind === 'tool') {
    const status = toolStatus(item);
    return <TimelineRow icon={<StatusIcon status={status} />} title={item.toolName || '业务工具'} tag={statusMeta[status]} position={index} isLast={isLast}>
      <ToolBody item={item} />
    </TimelineRow>;
  }
  const meta = eventMeta[item.event.type];
  const title = item.event.type === 'plan' && item.event.goal ? item.event.goal : meta.label;
  return <TimelineRow icon={<EventIcon type={item.event.type} />} title={title} tag={meta} position={index} isLast={isLast}>
    <EventBody event={item.event} />
  </TimelineRow>;
}

function headerStatus(events: ExecutionEvent[], loading: boolean): { label: string; color: string; running: boolean } {
  const terminal = [...events].reverse().find((event) => ['turn.completed', 'turn.terminated', 'turn.failed', 'error'].includes(event.type));
  if (terminal?.type === 'turn.failed' || terminal?.type === 'error') return { label: '执行失败', color: palette.danger, running: false };
  if (terminal?.type === 'turn.terminated') return { label: '受控终止', color: palette.warning, running: false };
  if (terminal?.type === 'turn.completed') return { label: '执行完成', color: palette.success, running: false };
  if (loading) return { label: '正在执行', color: '#79c0ff', running: true };
  return { label: '执行记录', color: TEXT_DIM, running: false };
}

export function ExecutionTimeline({ events, loading }: { events?: ExecutionEvent[]; loading: boolean }) {
  const [open, setOpen] = useState(true);
  if (!events || events.length === 0) return null;
  const items = buildTimelineItems(events);
  const status = headerStatus(events, loading);
  const thoughtCount = events.filter((event) => event.type === 'thought').length;
  const toolCount = items.filter((item) => item.kind === 'tool').length;
  const stepCount = items.filter((item) => item.kind === 'step').length;
  return (
    <section aria-live={status.running ? 'polite' : undefined} style={{ marginBottom: 16, border: `1px solid ${BORDER}`, borderRadius: 8, background: palette.bgSoft, overflow: 'hidden' }}>
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '11px 14px', border: 0, background: 'transparent', color: TEXT, cursor: 'pointer', textAlign: 'left' }}>
        <span style={{ width: 28, height: 28, display: 'grid', placeItems: 'center', borderRadius: 7, color: status.color, background: `${status.color}1c` }}>
          {status.running ? <LoadingOutlined spin /> : status.label === '执行完成' ? <CheckCircleOutlined /> : <NodeIndexOutlined />}
        </span>
        <span style={{ display: 'flex', flexDirection: 'column', gap: 3, flex: 1, minWidth: 0 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontWeight: 650, fontSize: 14 }}>
            <span>执行过程</span>
            <Tag bordered={false} style={{ margin: 0, color: status.color, background: `${status.color}1c`, fontSize: 11, lineHeight: '20px' }}>{status.label}</Tag>
          </span>
          <span style={{ color: TEXT_DIM, fontSize: 12 }}>{stepCount ? `${stepCount} 步` : '尚未形成 Step'}{toolCount ? ` · ${toolCount} 次工具` : ''}{thoughtCount ? ` · ${thoughtCount} 段思考` : ''}</span>
        </span>
        {open ? <UpOutlined style={{ color: TEXT_DIM }} /> : <DownOutlined style={{ color: TEXT_DIM }} />}
      </button>
      {open && (
        <div style={{ padding: '2px 14px 14px 18px', borderTop: `1px solid ${palette.borderSoft}` }}>
          {items.map((item, index) => <TimelineItemView key={item.key} item={item} index={index} isLast={index === items.length - 1} />)}
        </div>
      )}
    </section>
  );
}

// 该纯函数仅供时间线回归测试复用，组件文件仍是唯一运行时入口。
// eslint-disable-next-line react-refresh/only-export-components
export { buildTimelineItems };
