import { Button, Card, Empty, Space, Spin, Tag, Typography } from 'antd';

import type {
  DataFlywheelIssueCandidate,
  DataFlywheelSample,
  DataFlywheelSessionReview,
  DataFlywheelSessionTurnReview,
} from '../../../api/dataFlywheel';
import { cardStyle, palette } from '../../../styles/theme';

interface SessionConversationViewProps {
  review: DataFlywheelSessionReview | null;
  loading: boolean;
  selectedSampleId?: string;
  onSelectTurn: (sample: DataFlywheelSample) => void;
}

const issueText: Record<string, string> = {
  hallucinated_execution: '幻觉执行',
  unsafe_write_on_question: '问句触发写入',
  pending_missed: 'pending 漏拦截',
  tool_error_ignored: '工具错误未处理',
  sensitive_info_leak: '参数/提示泄露',
  off_topic: '答非所问',
};

const labelText: Record<string, string> = {
  good_reply: '好回复',
  bad_reply: '坏回复',
  wrong_tool_selection: '工具选错',
  pending_missed: 'pending 漏拦截',
  hallucinated_execution: '幻觉执行',
  off_topic: '答非所问',
  sensitive_info_leak: '参数/提示泄露',
  missing_wage: '工资缺失',
  disabled_worker_used: '禁用工人',
  needs_regression: '需要回归',
  not_actionable: '暂不处理',
};

export default function SessionConversationView({
  review,
  loading,
  selectedSampleId,
  onSelectTurn,
}: SessionConversationViewProps) {
  return (
    <Card
      title="完整对话记录"
      extra={
        <Typography.Text style={{ color: palette.textMuted }}>
          {review ? `${review.turns.length} turn` : '选择左侧会话'}
        </Typography.Text>
      }
      style={cardStyle}
      styles={{ body: { padding: 12, maxHeight: 'calc(100vh - 250px)', overflowY: 'auto' } }}
    >
      <Spin spinning={loading}>
        {!review || review.turns.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无会话 turn" />
        ) : (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            {review.turns.map((turn) => (
              <TurnReviewCard
                key={turn.sample.sample_id}
                turn={turn}
                active={turn.sample.sample_id === selectedSampleId}
                onSelect={() => onSelectTurn(turn.sample)}
              />
            ))}
          </Space>
        )}
      </Spin>
    </Card>
  );
}

function TurnReviewCard({
  turn,
  active,
  onSelect,
}: {
  turn: DataFlywheelSessionTurnReview;
  active: boolean;
  onSelect: () => void;
}) {
  const userMessage = messageContent(turn, 'user') || turn.sample.user_input_preview || '无用户输入';
  const assistantMessage =
    messageContent(turn, 'assistant') || turn.sample.assistant_reply_preview || '无助手回复';
  const routerReason = routerReasonText(turn.router_decision);
  return (
    <article
      style={{
        border: `1px solid ${active ? palette.accentStrong : palette.borderSoft}`,
        borderRadius: 8,
        background: active ? 'rgba(31, 111, 235, 0.12)' : palette.bg,
        padding: 12,
      }}
    >
      <Space direction="vertical" size={10} style={{ width: '100%' }}>
        <Space wrap size={8}>
          <Typography.Text strong style={{ color: palette.text }}>
            #{turn.sample.turn_id}
          </Typography.Text>
          <Typography.Text style={{ color: palette.textMuted }}>
            {turn.sample.request_id || '-'}
          </Typography.Text>
          <Tag color={turn.sample.annotation_status === 'labeled' ? 'success' : 'warning'}>
            {turn.sample.annotation_status}
          </Tag>
          {turn.sample.quality_labels.map((label) => (
            <Tag key={label} color="blue">
              已标注：{labelText[label] ?? label}
            </Tag>
          ))}
          <Typography.Text style={{ color: palette.textMuted }}>
            {turn.sample.token_total ?? '-'} tokens / {turn.sample.latency_ms ?? '-'} ms
          </Typography.Text>
        </Space>

        <MessageBlock role="user" content={userMessage} />
        <MessageBlock role="assistant" content={assistantMessage} />

        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          <EvidenceLine text={`selected: ${toolText(turn.sample.selected_tools)}`} />
          <EvidenceLine text={`actual: ${toolText(turn.sample.actual_tools)}`} />
          <EvidenceLine text={`pending: ${pendingStatus(turn.pending_lifecycle)}`} />
          <EvidenceLine text={`tool: ${toolSummary(turn.tool_events)}`} />
          {routerReason && <EvidenceLine text={`router: ${routerReason}`} />}
        </Space>

        {turn.sample.issue_candidates.length > 0 && (
          <Space wrap size={6}>
            {turn.sample.issue_candidates.map((issue) => (
              <IssueTag key={`${issue.type}-${issue.evidence}`} issue={issue} />
            ))}
          </Space>
        )}

        <Space wrap>
          <Button
            size="small"
            data-testid={`review-select-${turn.sample.sample_id}`}
            onClick={onSelect}
          >
            标注这一轮
          </Button>
          <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
            source: {turn.source.event_file || '-'}
          </Typography.Text>
        </Space>
      </Space>
    </article>
  );
}

function MessageBlock({ role, content }: { role: 'user' | 'assistant'; content: string }) {
  const title = role === 'user' ? 'user' : 'assistant';
  return (
    <div
      style={{
        border: `1px solid ${palette.borderSoft}`,
        borderRadius: 6,
        background: role === 'user' ? palette.bgPanel : 'rgba(88, 166, 255, 0.08)',
        padding: '8px 10px',
      }}
    >
      <Typography.Text style={{ color: palette.textMuted, display: 'block', fontSize: 12 }}>
        {title}
      </Typography.Text>
      <Typography.Paragraph style={{ color: palette.text, margin: 0, whiteSpace: 'pre-wrap' }}>
        {content}
      </Typography.Paragraph>
    </div>
  );
}

function EvidenceLine({ text }: { text: string }) {
  return (
    <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
      {text}
    </Typography.Text>
  );
}

function IssueTag({ issue }: { issue: DataFlywheelIssueCandidate }) {
  const color = issue.severity === 'critical' ? 'red' : 'orange';
  return (
    <Tag color={color} title={issue.reason}>
      规则：{issueText[issue.type] ?? issue.type}
    </Tag>
  );
}

function messageContent(turn: DataFlywheelSessionTurnReview, role: string) {
  return turn.messages.find((message) => message.role === role)?.content;
}

function toolText(tools: string[]) {
  return tools.length > 0 ? tools.join(', ') : '无';
}

function pendingStatus(events: Array<Record<string, unknown>>) {
  if (events.length === 0) return '缺失';
  const eventTypes = events.map((event) => String(event.event_type || ''));
  if (eventTypes.some((type) => /cancel|reject/i.test(type))) return '已取消';
  if (eventTypes.some((type) => /confirm|commit|apply|accept/i.test(type))) return '已确认';
  if (eventTypes.some((type) => type.includes('created'))) return '已创建';
  return `${events.length} 个事件`;
}

function toolSummary(events: Array<Record<string, unknown>>) {
  const success = events.filter((event) => event.event_type === 'tool.call.finished').length;
  const failed = events.filter((event) => event.event_type === 'tool.call.failed').length;
  return `${success} success / ${failed} failed`;
}

function routerReasonText(routerDecision: Record<string, unknown> | null) {
  if (!routerDecision) return '';
  const reason = routerDecision.reason;
  if (typeof reason === 'string') return reason;
  const selectedSkill = routerDecision.selected_skill;
  if (typeof selectedSkill === 'string') return selectedSkill;
  return '';
}
