import { useState } from 'react';
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
  'step.started': { label: 'Step 开始', color: '#79c0ff' },
  'step.completed': { label: 'Step 完成', color: palette.success },
  'tool.failed': { label: 'Tool 失败', color: palette.danger },
  'turn.completed': { label: '执行完成', color: palette.success },
  'turn.terminated': { label: '受控终止', color: palette.warning },
  'turn.failed': { label: '执行失败', color: palette.danger },
  error: { label: '执行失败', color: palette.danger },
};

function EventIcon({ type }: { type: ExecutionEvent['type'] }) {
  const props = { style: { color: eventMeta[type].color, fontSize: 15 } };
  switch (type) {
    case 'thought': return <NodeIndexOutlined {...props} />;
    case 'plan': return <FileTextOutlined {...props} />;
    case 'action': return <ToolOutlined {...props} />;
    case 'tool_call_delta': return <ToolOutlined {...props} />;
    case 'observation': return <CodeOutlined {...props} />;
    case 'approval_required': return <SafetyCertificateOutlined {...props} />;
    case 'approval_result':
    case 'operation_committed':
    case 'context_compressed':
    case 'turn.completed':
    case 'plan_step_done': return <CheckCircleOutlined {...props} />;
    case 'context_usage': return <ClockCircleOutlined {...props} />;
    case 'progress': return <LoadingOutlined {...props} />;
    case 'step.started': return <LoadingOutlined {...props} />;
    case 'step.completed': return <CheckCircleOutlined {...props} />;
    case 'tool.failed': return <ExclamationCircleOutlined {...props} />;
    case 'error':
    case 'turn.failed':
    case 'doom_loop_warning': return <ExclamationCircleOutlined {...props} />;
    case 'turn.terminated': return <ClockCircleOutlined {...props} />;
    default: return <LoadingOutlined {...props} />;
  }
}
function jsonText(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function DetailDisclosure({ label, value, tone = TEXT }: { label: string; value: unknown; tone?: string }) {
  const [open, setOpen] = useState(false);
  const text = jsonText(value);
  if (!text || text === '{}' || text === 'null') return null;
  return (
    <details open={open} onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)} style={{ marginTop: 9 }}>
      <summary style={{ color: TEXT_DIM, cursor: 'pointer', fontSize: 12, userSelect: 'none' }}>
        <span style={{ color: tone, fontWeight: 600 }}>{label}</span>
        <span style={{ marginLeft: 8 }}>展开查看 · {text.length} 字符</span>
      </summary>
      <pre style={{ margin: '8px 0 0', padding: '10px 12px', maxHeight: 280, overflow: 'auto', borderRadius: 8, border: `1px solid ${BORDER}`, background: 'rgba(0, 0, 0, 0.2)', color: TEXT, fontSize: 12, lineHeight: 1.55, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
        {text}
      </pre>
    </details>
  );
}

function EventBody({ event }: { event: ExecutionEvent }) {
  switch (event.type) {
    case 'thought':
      return <div style={{ color: TEXT, whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{event.content}</div>;
    case 'plan':
      return (
        <ol style={{ margin: '8px 0 0 20px', padding: 0, color: TEXT, lineHeight: 1.65 }}>
          {event.steps.map((step, index) => <li key={index}>{typeof step === 'string' ? step : jsonText(step)}</li>)}
        </ol>
      );
    case 'plan_step_done':
      return <span style={{ color: TEXT_DIM }}>步骤 {event.step_index + 1} · {event.skill} · {event.status}</span>;
    case 'action':
      return (
        <>
          {event.rationale && <div style={{ color: TEXT_DIM, lineHeight: 1.55 }}>{event.rationale}</div>}
          <DetailDisclosure label="查看调用参数" value={event.arguments} tone="#79c0ff" />
        </>
      );
    case 'tool_call_delta':
      return (
        <div style={{ color: TEXT_DIM, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {event.arguments_delta ? `参数增量：${event.arguments_delta}` : '正在等待完整参数'}
          <div style={{ marginTop: 4, fontSize: 11 }}>调用标识：{event.tool_call_id} · 索引：{event.index}</div>
        </div>
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
    case 'step.started':
      return <span style={{ color: TEXT_DIM }}>第 {event.step_index} 步开始 · {event.status}</span>;
    case 'step.completed':
      return <span style={{ color: TEXT_DIM }}>第 {event.step_index} 步结束 · {event.status} · {event.tool_count} 个 Tool</span>;
    case 'tool.failed':
      return <span style={{ color: palette.danger }}>{event.tool_name} · {event.tool_call_id} · {jsonText(event.error)}</span>;
    case 'turn.completed':
      return <span style={{ color: palette.success }}>{event.message ?? `停止原因：${event.stop_reason ?? 'completed'}${event.step_count === undefined ? '' : ` · 共 ${event.step_count} 步`}`}</span>;
    case 'turn.terminated':
      return <span style={{ color: palette.warning }}>{event.reason} · {event.message}{event.step_count === undefined ? '' : ` · 共 ${event.step_count} 步`}</span>;
    case 'turn.failed':
      return <span style={{ color: palette.danger }}>停止原因：{event.stop_reason}<DetailDisclosure label="查看错误详情" value={event.error} tone={palette.danger} /></span>;
    case 'error':
      return <span style={{ color: palette.danger }}>{event.code} · {event.category ? `${event.category} · ` : ''}{event.message}</span>;
  }
}

function TimelineEvent({ event, index, isLast }: { event: ExecutionEvent; index: number; isLast: boolean }) {
  const meta = eventMeta[event.type];
  const title = event.type === 'action' || event.type === 'observation' || event.type === 'approval_required'
    ? event.tool_name
    : event.type === 'tool_call_delta'
      ? event.name
    : event.type === 'plan' && event.goal
      ? event.goal
      : meta.label;
  return (
    <div style={{ display: 'flex', gap: 12, position: 'relative', paddingBottom: isLast ? 0 : 16 }}>
      {!isLast && <div style={{ position: 'absolute', left: 8, top: 22, bottom: 0, width: 1, background: 'rgba(139,148,158,0.25)' }} />}
      <div style={{ width: 17, height: 17, borderRadius: '50%', display: 'grid', placeItems: 'center', flexShrink: 0, background: palette.bgPanel, zIndex: 1 }}>
        <EventIcon type={event.type} />
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 18, flexWrap: 'wrap' }}>
          <span style={{ color: TEXT, fontSize: 13, fontWeight: 600 }}>{title}</span>
          <Tag bordered={false} style={{ margin: 0, color: meta.color, background: `${meta.color}1c`, fontSize: 11, lineHeight: '20px' }}>{meta.label}</Tag>
          <span style={{ color: TEXT_DIM, fontSize: 11 }}>#{index + 1}</span>
        </div>
        <div style={{ marginTop: 6, fontSize: 13 }}><EventBody event={event} /></div>
      </div>
    </div>
  );
}

export function ExecutionTimeline({ events, loading }: { events?: ExecutionEvent[]; loading: boolean }) {
  const [open, setOpen] = useState(true);
  if (!events || events.length === 0) return null;
  const thoughtCount = events.filter((event) => event.type === 'thought').length;
  const toolCount = events.filter((event) => event.type === 'action').length;
  return (
    <section style={{ marginBottom: 16, border: `1px solid ${BORDER}`, borderRadius: 12, background: 'linear-gradient(135deg, rgba(88,166,255,0.08), rgba(188,140,255,0.04))', overflow: 'hidden' }}>
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '13px 16px', border: 0, background: 'transparent', color: TEXT, cursor: 'pointer', textAlign: 'left' }}>
        <span style={{ width: 28, height: 28, display: 'grid', placeItems: 'center', borderRadius: 9, color: loading ? '#79c0ff' : palette.purple, background: loading ? 'rgba(121,192,255,0.14)' : 'rgba(188,140,255,0.14)' }}>
          {loading ? <LoadingOutlined spin /> : <NodeIndexOutlined />}
        </span>
        <span style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1, minWidth: 0 }}>
          <span style={{ fontWeight: 650, fontSize: 14 }}>{loading ? '正在处理' : '执行过程'}</span>
          <span style={{ color: TEXT_DIM, fontSize: 12 }}>{events.length} 个步骤{thoughtCount ? ` · ${thoughtCount} 段思考` : ''}{toolCount ? ` · ${toolCount} 次工具调用` : ''}</span>
        </span>
        {open ? <UpOutlined style={{ color: TEXT_DIM }} /> : <DownOutlined style={{ color: TEXT_DIM }} />}
      </button>
      {open && (
        <div style={{ padding: '2px 18px 16px 24px' }}>
          {events.map((event, index) => <TimelineEvent key={event.event_id ?? `${event.type}-${event.seq ?? index}`} event={event} index={index} isLast={index === events.length - 1} />)}
        </div>
      )}
    </section>
  );
}
