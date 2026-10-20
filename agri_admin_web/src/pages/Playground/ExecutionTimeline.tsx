import { useState } from 'react';
import { CheckOutlined, ClockCircleOutlined, DownOutlined, ExclamationCircleOutlined, LoadingOutlined, NodeIndexOutlined } from '@ant-design/icons';
import type { ExecutionEvent } from './executionEvents';
import {
  buildExecutionChain,
  buildTimelineItems,
  chainGroupStatus,
  executionStatus,
  jsonText,
  settledItemStatus,
  type ApprovalDisplayState,
  type ExecutionChainGroup,
  type TimelineStatus,
  type ToolTimelineItem,
} from './executionTimelineModel';
import { EventBody } from './ExecutionEventDetails';
import './playground.css';

export function ExecutionStateIcon({ status }: { status: TimelineStatus }) {
  if (status === 'running') return <LoadingOutlined spin />;
  if (status === 'failed') return <ExclamationCircleOutlined />;
  if (status === 'completed') return <CheckOutlined />;
  return <ClockCircleOutlined />;
}

const STATUS_LABEL: Record<TimelineStatus, string> = {
  waiting: '未完成',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
};

function payloadText(value: unknown): string {
  const text = jsonText(value);
  return ['', 'null', 'undefined', '{}', '[]'].includes(text) ? '' : text;
}

function ExecutionPayload({ label, value }: { label: string; value: unknown }) {
  const text = payloadText(value);
  if (!text) return null;
  return (
    <div>
      <div className="execution-io__label">{label}</div>
      <pre className="execution-io__pre">{text}</pre>
    </div>
  );
}

/* 结果规模提示，让收起状态也能看出工具实际返回了什么。 */
function resultHint(result: unknown): string {
  if (Array.isArray(result)) return `${result.length} 项结果`;
  if (result && typeof result === 'object') {
    const items = (result as Record<string, unknown>).items;
    if (Array.isArray(items)) return `${items.length} 项结果`;
    return '';
  }
  if (typeof result === 'string' && result.trim()) {
    return result.length > 24 ? `${result.slice(0, 24)}…` : result;
  }
  return '';
}

/* 单个工具调用：摘要行常驻，参数与结果按需展开。 */
function ExecutionToolRow({ item, status }: { item: ToolTimelineItem; status: TimelineStatus }) {
  const [open, setOpen] = useState(false);
  const args = item.action?.arguments ?? item.started?.arguments;
  const result = item.observation?.result ?? item.finished?.result;
  const error = item.failed?.error ?? item.observation?.error;
  const rationale = item.action?.rationale;
  const hasDetail = Boolean(payloadText(args) || payloadText(result) || payloadText(error) || rationale);
  const durationMs = item.finished?.duration_ms ?? item.failed?.duration_ms;
  const meta = durationMs !== undefined
    ? `${(durationMs / 1000).toFixed(1)}s${status === 'failed' ? ' · 失败' : ''}`
    : STATUS_LABEL[status];
  const hint = resultHint(result);

  return (
    <details
      className="execution-chain__tool"
      open={open}
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="execution-chain__tool-summary">
        <span className={`execution-dot execution-tone--${status}`}><ExecutionStateIcon status={status} /></span>
        <span className="execution-chain__tool-name">{item.toolName || '业务工具'}</span>
        <span className="execution-chain__tool-meta">{meta}</span>
        {hint && <span className="execution-chain__tool-result">{hint}</span>}
        {hasDetail && (
          <span className={`execution-chain__tool-toggle${open ? '' : ' execution-chain__tool-toggle--closed'}`}>
            {open ? '收起' : '查看参数与结果'}
            <DownOutlined />
          </span>
        )}
      </summary>
      {hasDetail && (
        <div className="execution-chain__io">
          {rationale && <div className="execution-io__rationale">{rationale}</div>}
          <ExecutionPayload label="调用参数" value={args} />
          <ExecutionPayload label="工具结果" value={result} />
          <ExecutionPayload label={status === 'failed' ? '错误信息' : '错误'} value={error} />
        </div>
      )}
    </details>
  );
}

function ExecutionChainGroupView({
  group,
  events,
  loading,
  approvalState,
}: {
  group: ExecutionChainGroup;
  events: ExecutionEvent[];
  loading: boolean;
  approvalState?: ApprovalDisplayState;
}) {
  const stepStatus = chainGroupStatus(group, events, loading, approvalState);
  return (
    <div className="execution-chain__group">
      {group.stepIndex !== undefined && (
        <div className="execution-chain__step" title={`第 ${group.stepIndex} 步 · ${STATUS_LABEL[stepStatus]}`}>
          <span className="execution-chain__index">{group.stepIndex}</span>
          <span className="execution-chain__step-label">第 {group.stepIndex} 步</span>
          <span className={`execution-chain__step-icon execution-tone--${stepStatus}`} role="img" aria-label={STATUS_LABEL[stepStatus]}>
            <ExecutionStateIcon status={stepStatus} />
          </span>
          {(group.tools.length > 0 || group.step?.completed) && (
            <span className="execution-chain__step-meta">
              {group.tools.length > 0 ? `${group.tools.length} 次调用` : '无工具调用'}
            </span>
          )}
        </div>
      )}
      {group.tools.length > 0 && (
        <div className={`execution-chain__tools${group.stepIndex !== undefined ? ' execution-chain__tools--nested' : ''}`}>
          {group.tools.map((item) => (
            <ExecutionToolRow
              key={item.key}
              item={item}
              status={settledItemStatus(item, events, loading, approvalState)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* 执行过程以「步骤 → 工具调用」链路内联在对话里，结果正文紧随其后。 */
export function ExecutionTimeline({ events, loading, approvalState }: {
  events?: ExecutionEvent[];
  loading: boolean;
  approvalState?: ApprovalDisplayState;
}) {
  if (!events?.length) return null;
  const items = buildTimelineItems(events);
  const status = executionStatus(events, loading, approvalState);
  const plan = [...events].reverse().find((event) => event.type === 'plan');
  const tools = items.filter((item) => item.kind === 'tool');
  const chain = buildExecutionChain(items);
  const stepCount = chain.filter((group) => group.stepIndex !== undefined).length;
  const progress = [...events].reverse().find((event) => event.type === 'progress');
  // 调试噪音不展示，异常和审批提示仍保留在对话中，避免隐藏业务阻塞。
  const notices = events.filter((event) => [
    'approval_required', 'approval_result', 'doom_loop_warning', 'verification_warning',
    'write_committed_reply_failed', 'retrying', 'error', 'turn.failed', 'turn.terminated',
  ].includes(event.type));
  const hasRows = tools.length > 0 || stepCount > 0;
  return (
    <section className="execution-inline" aria-label="执行过程">
      <div className="execution-inline__summary">
        <span className={`execution-dot execution-tone--${status.tone}`}>
          {status.running ? <LoadingOutlined spin /> : status.tone === 'completed' ? <CheckOutlined /> : <NodeIndexOutlined />}
        </span>
        <span className="execution-inline__title">{stepCount ? `${stepCount} 个步骤` : '任务执行'} · {tools.length} 次工具调用</span>
        <span className={`execution-inline__status execution-tone--${status.tone}`}>{status.label}</span>
      </div>
      {status.running && (
        <div className="execution-inline__progress" role="status">
          <LoadingOutlined spin /> {progress?.message || '正在分析问题并执行任务…'}
        </div>
      )}
      {chain.length > 0 && (
        <div className="execution-chain">
          {chain.map((group) => (
            <ExecutionChainGroupView
              key={group.key}
              group={group}
              events={events}
              loading={loading}
              approvalState={approvalState}
            />
          ))}
        </div>
      )}
      {!hasRows && plan && <div className="execution-plan"><EventBody event={plan} /></div>}
      {!hasRows && !plan && !status.running && <div className="execution-card__subtitle">{status.label === '已完成' ? '本次回答无需调用工具' : '暂无步骤记录'}</div>}
      {notices.map((event, index) => <div className="execution-notice" key={event.event_id ?? index}><EventBody event={event} /></div>)}
    </section>
  );
}
