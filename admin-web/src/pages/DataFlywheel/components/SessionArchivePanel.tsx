import { Badge, Card, Empty, Space, Tag, Typography } from 'antd';
import type { CSSProperties } from 'react';

import { cardStyle, palette } from '../../../styles/theme';

export interface SessionArchiveItem {
  key: string;
  sessionId: string | null;
  total: number;
  unannotated: number;
  sessionLabels: number;
  badCases: number;
  latestTurnId: number;
  latestInputPreview: string | null;
}

interface SessionArchivePanelProps {
  groups: SessionArchiveItem[];
  total: number;
  issueCount: number;
  confirmedIssueCount: number;
  activeKey: string;
  allKey: string;
  issueKey: string;
  confirmedIssueKey: string;
  onSelect: (key: string) => void;
}

export default function SessionArchivePanel({
  groups,
  total,
  issueCount,
  confirmedIssueCount,
  activeKey,
  allKey,
  issueKey,
  confirmedIssueKey,
  onSelect,
}: SessionArchivePanelProps) {
  return (
    <Card title="用户 / 会话归档" style={cardStyle} styles={{ body: { padding: 12 } }}>
      <Space direction="vertical" size={10} style={{ width: '100%' }}>
        <button
          type="button"
          data-testid="archive-session-all"
          onClick={() => onSelect(allKey)}
          style={archiveButtonStyle(activeKey === allKey)}
        >
          <span>
            <Typography.Text style={{ color: palette.text }}>全部用户会话</Typography.Text>
            <Typography.Text style={{ display: 'block', color: palette.textMuted, fontSize: 12 }}>
              当前筛选结果内的会话样本
            </Typography.Text>
          </span>
          <Badge count={total} color={palette.accentStrong} />
        </button>

        <button
          type="button"
          data-testid="archive-issues"
          onClick={() => onSelect(issueKey)}
          style={archiveButtonStyle(activeKey === issueKey)}
        >
          <span>
            <Typography.Text style={{ color: palette.text }}>规则候选</Typography.Text>
            <Typography.Text style={{ display: 'block', color: palette.textMuted, fontSize: 12 }}>
              规则命中，仍需人工确认
            </Typography.Text>
          </span>
          <Badge count={issueCount} color={palette.danger} />
        </button>

        <button
          type="button"
          data-testid="archive-confirmed-issues"
          onClick={() => onSelect(confirmedIssueKey)}
          style={archiveButtonStyle(activeKey === confirmedIssueKey)}
        >
          <span>
            <Typography.Text style={{ color: palette.text }}>已标注问题</Typography.Text>
            <Typography.Text style={{ display: 'block', color: palette.textMuted, fontSize: 12 }}>
              人工确认并保存的问题样本
            </Typography.Text>
          </span>
          <Badge count={confirmedIssueCount} color={palette.danger} />
        </button>

        {groups.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可归档会话" />
        ) : (
          groups.map((group) => (
            <button
              key={group.key}
              type="button"
              data-testid={`archive-session-${group.sessionId ?? 'unknown'}`}
              onClick={() => onSelect(group.key)}
              style={archiveButtonStyle(activeKey === group.key)}
            >
              <span style={{ minWidth: 0 }}>
                <Typography.Text ellipsis style={{ color: palette.text, maxWidth: '100%' }}>
                  {group.sessionId ?? '未关联会话'}
                </Typography.Text>
                <Typography.Text
                  ellipsis
                  style={{ display: 'block', color: palette.textMuted, fontSize: 12, marginTop: 4 }}
                >
                  #{group.latestTurnId} {group.latestInputPreview || '无输入摘要'}
                </Typography.Text>
                <Space size={4} wrap style={{ marginTop: 8 }}>
                  <Tag color="blue">{group.total} turn</Tag>
                  {group.unannotated > 0 && <Tag color="gold">{group.unannotated} 未标注</Tag>}
                  {group.sessionLabels > 0 && <Tag color="purple">{group.sessionLabels} 会话标注</Tag>}
                  {group.badCases > 0 && <Tag color="red">{group.badCases} bad</Tag>}
                </Space>
              </span>
            </button>
          ))
        )}
      </Space>
    </Card>
  );
}

function archiveButtonStyle(active: boolean): CSSProperties {
  return {
    width: '100%',
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 10,
    padding: '10px 12px',
    border: `1px solid ${active ? palette.accentStrong : palette.borderSoft}`,
    borderRadius: 8,
    background: active ? 'rgba(31, 111, 235, 0.2)' : palette.bg,
    color: palette.text,
    cursor: 'pointer',
    textAlign: 'left',
  };
}
