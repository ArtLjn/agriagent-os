import { Button, Tooltip } from 'antd';
import { CheckCircleOutlined, ClockCircleOutlined, MessageOutlined, ProfileOutlined, RobotOutlined, StopOutlined, ThunderboltOutlined } from '@ant-design/icons';
import type { PendingAction, PendingPlan } from '../../api/agent';
import { MarkdownContent } from '../../components/MarkdownContent';
import { palette } from '../../styles/theme';
import { canConfirmAssistantMessage, hasPendingConfirmationControls, type PendingResolution } from './pendingPlanControls';
import type { ExecutionEvent } from './executionEvents';
import { ExecutionTimeline } from './ExecutionTimeline';
import { jsonText } from './executionTimelineModel';

const TEXT = palette.text;

/* ── 执行状态标签（统一 pg-chip 样式，不用 emoji 表达状态） ── */
function ExecutionStatus({ skills, events, loading, pendingAction, pendingPlan, pendingResolution }: { skills?: string[]; events?: ExecutionEvent[]; loading: boolean; pendingAction?: PendingAction | null; pendingPlan?: boolean; pendingResolution?: PendingResolution | null }) {
  if (pendingResolution) {
    const canceled = pendingResolution === 'canceled';
    return (
      <span className={`pg-chip ${canceled ? 'pg-chip--muted' : 'pg-chip--success'}`}>
        {canceled ? <StopOutlined /> : <CheckCircleOutlined />}
        {canceled ? '已取消执行' : '已确认执行'}
      </span>
    );
  }
  if (pendingAction || pendingPlan) {
    return (
      <span className="pg-chip pg-chip--warning">
        <ClockCircleOutlined />
        待确认执行
      </span>
    );
  }
  if (skills && skills.length > 0) {
    return (
      <span className="pg-chip pg-chip--success" title={skills.join(', ')}>
        <CheckCircleOutlined />
        真实执行了 {skills.length} 个函数
      </span>
    );
  }
  // 工具调用次数已由回答卡片的执行过程给出，这里不再重复。
  if (events?.length) return null;
  if (loading) return null;
  return (
    <span className="pg-chip pg-chip--muted">
      <MessageOutlined />
      纯文本生成
    </span>
  );
}

/* ── 聊天气泡组件 ── */
export function ChatBubble({
  role, content, events, skills, loading, pendingAction, pendingPlan, pendingResolution,
  turnId, traceId, onAction, onViewDetails,
}: {
  role: 'user' | 'assistant';
  content: string;
  events?: ExecutionEvent[];
  skills?: string[];
  loading: boolean;
  pendingAction?: PendingAction | null;
  pendingPlan?: PendingPlan | null;
  pendingResolution?: PendingResolution | null;
  turnId?: string | null;
  traceId?: string | null;
  onAction?: (action: string) => void;
  onViewDetails?: (turnId: string) => void;
}) {
  const isUser = role === 'user';
  const hasConfirmationControls = hasPendingConfirmationControls({ role, content, pendingAction, pendingPlan, pendingResolution });
  const canConfirm = canConfirmAssistantMessage({ role, content, pendingAction, pendingPlan, pendingResolution });
  const confirmationDisabled = !canConfirm || !onAction;
  // 实时执行链路已经内联可展开，不再需要额外的「执行详情」入口；历史消息仍保留。
  const showTurnDetails = Boolean(turnId && onViewDetails && !events?.length);
  const showStatus = Boolean(
    skills?.length
    || showTurnDetails
    || pendingAction
    || pendingPlan
    || pendingResolution
    || (!events?.length && content),
  );
  const rawRisk = pendingAction?.raw && typeof pendingAction.raw.risk_level === 'string'
    ? pendingAction.raw.risk_level
    : '';
  const riskLabel = rawRisk === 'write_high'
    ? '高风险写操作'
    : rawRisk === 'write_confirm' ? '需确认的写操作' : '';
  const approvalRationale = pendingAction?.raw && typeof pendingAction.raw.rationale === 'string'
    ? pendingAction.raw.rationale
    : '';
  const paramsText = pendingAction ? jsonText(pendingAction.params) : '';
  const showParams = Boolean(paramsText) && !['{}', 'null', 'undefined'].includes(paramsText);
  // 流式开始前既无执行事件也无正文时，由消息区统一的「正在思考」占位表达。
  if (!isUser && !content && !events?.length && !pendingAction && !pendingPlan) return null;

  return (
    <div className={`playground-message ${isUser ? "playground-message--user" : "playground-message--assistant"}`}>
      {!isUser && (
        <div className="playground-avatar"><RobotOutlined /></div>
      )}
      <div className="playground-message__content">
        {isUser ? content : (
          <>
            <div className="playground-run">
              {events?.length ? (
                <div className="playground-run__head">
                  <ExecutionTimeline events={events} loading={loading} approvalState={pendingResolution ?? (canConfirm ? 'awaiting' : undefined)} />
                </div>
              ) : null}
              {content ? (
                <div className="playground-run__body">
                  <MarkdownContent content={content} style={{ color: TEXT, lineHeight: 1.75, fontSize: 14 }} />
                </div>
              ) : null}
              {showStatus && (
                <div className="playground-run__foot" role="group" aria-label="任务执行详情">
                  <ExecutionStatus
                    skills={skills}
                    events={events}
                    loading={loading}
                    pendingAction={canConfirm ? pendingAction : null}
                    pendingPlan={canConfirm && !pendingAction}
                    pendingResolution={pendingResolution}
                  />
                  {skills && skills.length > 0 && skills.map((s) => (
                    <span key={s} className="pg-chip pg-chip--accent">
                      <ThunderboltOutlined />
                      {s}
                    </span>
                  ))}
                  {showTurnDetails && turnId && onViewDetails && (
                    <Tooltip title={traceId ? '加载该 Turn 的执行详情与 Trace' : '加载该 Turn 的执行详情'}>
                      <Button
                        type="text"
                        size="small"
                        className="pg-run-details"
                        icon={<ProfileOutlined />}
                        onClick={() => onViewDetails(turnId)}
                      >
                        执行详情
                      </Button>
                    </Tooltip>
                  )}
                </div>
              )}
            </div>
            {hasConfirmationControls && (
              <div className="pg-approval" role="group" aria-label="待确认操作">
                <div className="pg-approval__head">
                  <span className="pg-chip pg-chip--warning">
                    <ClockCircleOutlined />
                    待确认执行
                  </span>
                  <span className="pg-approval__tool">
                    {pendingAction?.skill_name || '执行计划'}
                  </span>
                  {riskLabel && <span className="pg-approval__risk">{riskLabel}</span>}
                </div>
                {pendingAction ? (
                  <>
                    {approvalRationale && (
                      <div className="pg-approval__rationale">{approvalRationale}</div>
                    )}
                    {pendingAction.context?.original_input && (
                      <div className="pg-approval__context">
                        理解：您说的是「{pendingAction.context.original_input}」
                      </div>
                    )}
                    {pendingAction.context?.notes?.map((note, i) => (
                      <div key={i} className="pg-approval__context">{note}</div>
                    ))}
                    {showParams && (
                      <>
                        <div className="pg-approval__label">将执行的参数</div>
                        <pre className="pg-approval__params">{paramsText}</pre>
                      </>
                    )}
                  </>
                ) : (
                  pendingPlan?.goal && <div className="pg-approval__rationale">{pendingPlan.goal}</div>
                )}
                <div className="pg-approval-actions">
                  <button
                    type="button"
                    className="pg-approval-cancel"
                    disabled={confirmationDisabled}
                    onClick={() => {
                      if (!confirmationDisabled) onAction?.('取消');
                    }}
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    className="pg-approval-confirm"
                    disabled={confirmationDisabled}
                    onClick={() => {
                      if (!confirmationDisabled) onAction?.('确认');
                    }}
                  >
                    确认
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
