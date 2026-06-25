import { Button, Card, Checkbox, Collapse, Empty, Space, Tag, Typography, type CollapseProps } from 'antd';
import { type CSSProperties } from 'react';

import type { ReviewIssueChainDetail, ReviewIssueChainTimelineTurn } from '../../../api/dataFlywheel';
import { cardStyle, palette } from '../../../styles/theme';
import { evidenceStatusLabel, timelineRoleText } from './reviewLabels';

interface ReviewIssueChainTimelineProps {
  detail: ReviewIssueChainDetail | null;
  contextTurnIds: number[];
  resultTurnIds: number[];
  loading: boolean;
  onContextTurnIdsChange: (turnIds: number[]) => void;
  onResultTurnIdsChange: (turnIds: number[]) => void;
}

export default function ReviewIssueChainTimeline({
  detail,
  contextTurnIds,
  resultTurnIds,
  loading,
  onContextTurnIdsChange,
  onResultTurnIdsChange,
}: ReviewIssueChainTimelineProps) {
  if (!detail && !loading) {
    return (
        <Card title="会话时间线" style={timelineCardStyle}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选择左侧 session 后查看问题链" />
      </Card>
    );
  }

  return (
    <Card
        title="会话时间线"
      loading={loading}
      style={timelineCardStyle}
      styles={{ body: timelineBodyStyle }}
    >
      <Space direction="vertical" size={10} style={{ width: '100%' }}>
        {detail?.timeline.map((turn) => {
          const role = roleForTurn(turn, detail, contextTurnIds, resultTurnIds);
          return (
          <article
            key={turn.turn_id}
            id={`turn-${turn.turn_id}`}
            style={turnCardStyle(role)}
          >
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Space wrap size={6}>
                  <Tag color={roleColor(role)}>
                    {timelineRoleText(role)}
                  </Tag>
                  <Tag>turn #{turn.turn_id}</Tag>
                  <Tag color={turn.event_log_status === 'missing' ? 'orange' : 'green'}>
                    事件 {evidenceStatusLabel(turn.event_log_status)}
                  </Tag>
                <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
                  {turn.request_id || '-'}
                </Typography.Text>
              </Space>
              <Typography.Text style={{ ...lineClampStyle(role), color: palette.text }}>
                  用户：{turn.user_input_preview || userMessage(turn) || '无用户摘要'}
              </Typography.Text>
              <Typography.Text style={{ ...lineClampStyle(role), color: palette.textMuted }}>
                  助手：{turn.assistant_reply_preview || assistantMessage(turn) || '无回复摘要'}
              </Typography.Text>
              <Space wrap size={6}>
                  <Tag>路由选择：{turn.selected_tools.length > 0 ? turn.selected_tools.join(', ') : '-'}</Tag>
                  <Tag>实际调用：{actualTools(turn).length > 0 ? actualTools(turn).join(', ') : '-'}</Tag>
                  <Tag color={turn.pending_lifecycle.length > 0 ? 'blue' : 'default'}>
                    确认流程：{turn.pending_lifecycle.length > 0 ? '有' : '无'}
                </Tag>
              </Space>
              <Space wrap>
                {turn.turn_id !== detail.chain.trigger_turn_id && (
                  <>
                    <Checkbox
                      checked={contextTurnIds.includes(turn.turn_id)}
                      onChange={(event) => {
                        onContextTurnIdsChange(toggleTurnId(contextTurnIds, turn.turn_id, event.target.checked));
                        if (event.target.checked) {
                          onResultTurnIdsChange(toggleTurnId(resultTurnIds, turn.turn_id, false));
                        }
                      }}
                    >
                        设为上下文
                    </Checkbox>
                    <Checkbox
                      checked={resultTurnIds.includes(turn.turn_id)}
                      onChange={(event) => {
                        onResultTurnIdsChange(toggleTurnId(resultTurnIds, turn.turn_id, event.target.checked));
                        if (event.target.checked) {
                          onContextTurnIdsChange(toggleTurnId(contextTurnIds, turn.turn_id, false));
                        }
                      }}
                    >
                        设为结果
                    </Checkbox>
                  </>
                )}
              </Space>
              <Collapse
                size="small"
                ghost
                items={debugItems(turn, debugSummaryForTurn(detail, turn.turn_id))}
              />
            </Space>
          </article>
          );
        })}
      </Space>
    </Card>
  );
}

function debugItems(turn: ReviewIssueChainTimelineTurn, traceDebugSummary: unknown): CollapseProps['items'] {
  return [
    {
      key: 'debug',
      label: <Button type="link" size="small">展开详情</Button>,
      children: (
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <DebugBlock title="对话消息" value={turn.messages} />
            <DebugBlock title="工具事件" value={turn.tool_events} />
            <DebugBlock title="确认流程" value={turn.pending_lifecycle} />
            <DebugBlock title="路由决策" value={turn.router_decision} />
            <DebugBlock title="Trace 摘要" value={traceDebugSummary} />
            <DebugBlock title="来源事件" value={turn.source} />
        </Space>
      ),
    },
  ];
}

function debugSummaryForTurn(detail: ReviewIssueChainDetail, turnId: number): unknown {
  return detail.turn_debug_summaries[String(turnId)] ?? detail.turn_debug_summaries[turnId] ?? null;
}

function DebugBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <div style={debugBlockStyle}>
      <Typography.Text strong style={{ color: palette.text }}>{title}</Typography.Text>
      <pre style={preStyle}>{JSON.stringify(value, null, 2)}</pre>
    </div>
  );
}

function roleForTurn(
  turn: ReviewIssueChainTimelineTurn,
  detail: ReviewIssueChainDetail,
  contextTurnIds: number[],
  resultTurnIds: number[]
): string {
  if (turn.turn_id === detail.chain.trigger_turn_id) return 'trigger';
  if (contextTurnIds.includes(turn.turn_id)) return 'context';
  if (resultTurnIds.includes(turn.turn_id)) return 'result';
  return 'unrelated';
}

function toggleTurnId(turnIds: number[], turnId: number, checked: boolean): number[] {
  const next = new Set(turnIds);
  if (checked) {
    next.add(turnId);
  } else {
    next.delete(turnId);
  }
  return Array.from(next).sort((a, b) => a - b);
}

function actualTools(turn: ReviewIssueChainTimelineTurn): string[] {
  return turn.tool_events
    .map((event) => {
      const payload = event.payload;
      if (payload && typeof payload === 'object' && 'tool_name' in payload) {
        return String(payload.tool_name);
      }
      if ('tool_name' in event) return String(event.tool_name);
      if ('name' in event) return String(event.name);
      return null;
    })
    .filter((tool): tool is string => Boolean(tool));
}

function userMessage(turn: ReviewIssueChainTimelineTurn): string | null {
  return turn.messages.find((message) => message.role === 'user')?.content ?? null;
}

function assistantMessage(turn: ReviewIssueChainTimelineTurn): string | null {
  return turn.messages.find((message) => message.role === 'assistant')?.content ?? null;
}

function roleColor(role: string): string {
  if (role === 'trigger') return 'red';
  if (role === 'context') return 'blue';
  if (role === 'result') return 'green';
  return 'default';
}

function lineClampStyle(role: string): CSSProperties {
  return {
    display: '-webkit-box',
    WebkitBoxOrient: 'vertical',
    WebkitLineClamp: role === 'trigger' ? 4 : 2,
    overflow: 'hidden',
    wordBreak: 'break-word',
  };
}

const timelineCardStyle: CSSProperties = {
  ...cardStyle,
  height: '100%',
  minHeight: 0,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
};

const timelineBodyStyle: CSSProperties = {
  padding: 12,
  minHeight: 0,
  flex: 1,
  overflowY: 'auto',
  overflowX: 'hidden',
  scrollbarGutter: 'stable',
};

function turnCardStyle(role: string): CSSProperties {
  const color = role === 'trigger'
    ? palette.danger
    : role === 'context'
      ? palette.accent
      : role === 'result'
        ? palette.success
        : palette.borderSoft;
  return {
    border: `1px solid ${color}`,
    borderRadius: 8,
    padding: 12,
    background: role === 'unrelated' ? 'rgba(33, 38, 45, 0.46)' : palette.bgPanel,
    opacity: role === 'unrelated' ? 0.66 : 1,
  };
}

const debugBlockStyle: CSSProperties = {
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  padding: 8,
  background: palette.bg,
};

const preStyle: CSSProperties = {
  margin: '6px 0 0',
  whiteSpace: 'pre-wrap',
  color: palette.textMuted,
  fontSize: 12,
};
