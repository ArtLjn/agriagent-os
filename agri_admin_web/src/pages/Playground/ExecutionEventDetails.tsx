import { useState } from 'react';
import { palette } from '../../styles/theme';
import type { ExecutionEvent } from './executionEvents';
import { jsonText } from './executionTimelineModel';

const TEXT = palette.text;
const TEXT_DIM = palette.textMuted;
const BORDER = palette.border;

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
      <pre style={{ margin: '8px 0 0', padding: '10px 12px', maxHeight: 280, overflow: 'auto', borderRadius: 6, border: `1px solid ${BORDER}`, background: palette.codeBg, color: TEXT, fontSize: 12, lineHeight: 1.55, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
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
      <pre style={{ margin: '8px 0 0', padding: '10px 12px', maxHeight: 280, overflow: 'auto', borderRadius: 6, border: `1px solid ${BORDER}`, background: palette.codeBg, color: TEXT, fontSize: 12, lineHeight: 1.55, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
        {text}
      </pre>
    </details>
  );
}

export function EventBody({ event }: { event: ExecutionEvent }) {
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
          <DetailDisclosure label="查看调用参数" value={event.arguments} tone={palette.accent} />
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

