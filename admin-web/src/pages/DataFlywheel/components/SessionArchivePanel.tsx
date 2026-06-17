import { Badge, Card, Empty, Space, Tag, Typography } from 'antd';
import { useEffect, useRef, useState } from 'react';
import type { CSSProperties, MouseEvent as ReactMouseEvent } from 'react';

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
  title?: string | null;
  groups: SessionArchiveItem[];
  total: number;
  issueCount: number;
  aiPrelabelCount: number;
  confirmedIssueCount: number;
  activeKey: string;
  allKey: string;
  issueKey: string;
  aiPrelabelKey: string;
  confirmedIssueKey: string;
  showBuckets?: boolean;
  orientation?: 'vertical' | 'horizontal';
  testIdPrefix?: string;
  onSelect: (key: string) => void;
}

export default function SessionArchivePanel({
  title = '用户 / 会话归档',
  groups,
  total,
  issueCount,
  aiPrelabelCount,
  confirmedIssueCount,
  activeKey,
  allKey,
  issueKey,
  aiPrelabelKey,
  confirmedIssueKey,
  showBuckets = true,
  orientation = 'vertical',
  testIdPrefix = 'archive-session',
  onSelect,
}: SessionArchivePanelProps) {
  const horizontal = orientation === 'horizontal';
  const sessionRowRef = useRef<HTMLDivElement>(null);
  const [scrollState, setScrollState] = useState({ left: 0, max: 0, ratio: 1 });

  const updateScrollState = () => {
    const node = sessionRowRef.current;
    if (!node) return;
    const max = Math.max(0, node.scrollWidth - node.clientWidth);
    setScrollState({
      left: node.scrollLeft,
      max,
      ratio: node.scrollWidth > 0 ? Math.min(1, node.clientWidth / node.scrollWidth) : 1,
    });
  };

  useEffect(() => {
    updateScrollState();
    window.addEventListener('resize', updateScrollState);
    return () => window.removeEventListener('resize', updateScrollState);
  }, [groups.length, horizontal]);

  const handleScrollbarClick = (event: ReactMouseEvent<HTMLDivElement>) => {
    const node = sessionRowRef.current;
    if (!node || scrollState.max <= 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - rect.left) / rect.width;
    node.scrollLeft = ratio * scrollState.max;
    updateScrollState();
  };

  const thumbWidth = `${Math.max(12, scrollState.ratio * 100)}%`;
  const thumbLeft = `${
    scrollState.max > 0 ? (scrollState.left / scrollState.max) * (100 - Math.max(12, scrollState.ratio * 100)) : 0
  }%`;
  const bucketItems = showBuckets ? [
    {
      testId: 'archive-session-all',
      key: allKey,
      title: '全部用户会话',
      description: '当前筛选结果内的会话样本',
      count: total,
      color: palette.accentStrong,
    },
    {
      testId: 'archive-issues',
      key: issueKey,
      title: '规则候选',
      description: '规则命中，仍需人工确认',
      count: issueCount,
      color: palette.danger,
    },
    {
      testId: 'archive-ai-prelabels',
      key: aiPrelabelKey,
      title: 'AI 预判',
      description: '待人工采纳或驳回',
      count: aiPrelabelCount,
      color: palette.accentStrong,
    },
    {
      testId: 'archive-confirmed-issues',
      key: confirmedIssueKey,
      title: '已标注问题',
      description: '人工确认并保存的问题样本',
      count: confirmedIssueCount,
      color: palette.danger,
    },
  ] : [];

  const bucketButtons = bucketItems.map((item) => (
    <button
      key={item.key}
      type="button"
      data-testid={item.testId}
      onClick={() => onSelect(item.key)}
      style={archiveButtonStyle(activeKey === item.key, horizontal)}
    >
      <span>
        <Typography.Text style={{ color: palette.text }}>{item.title}</Typography.Text>
        <Typography.Text style={{ display: 'block', color: palette.textMuted, fontSize: 12 }}>
          {item.description}
        </Typography.Text>
      </span>
      <Badge count={item.count} color={item.color} />
    </button>
  ));

  const groupButtons = groups.map((group) => (
    <button
      key={group.key}
      type="button"
      data-testid={`${testIdPrefix}-${group.sessionId ?? 'unknown'}`}
      onClick={() => onSelect(group.key)}
      style={archiveButtonStyle(activeKey === group.key, horizontal)}
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
  ));

  return (
    <Card
      title={title}
      style={archiveCardStyle}
      styles={{
        body: {
          padding: horizontal ? '10px 12px 12px' : 12,
          minHeight: 0,
          flex: 1,
          overflow: horizontal ? 'visible' : 'hidden',
        },
      }}
    >
      <div style={archiveListStyle(horizontal)}>
        {horizontal && showBuckets ? (
          <>
            <div style={fixedBucketRowStyle}>{bucketButtons}</div>
            <div
              ref={sessionRowRef}
              className="data-flywheel-session-row"
              style={sessionScrollRowStyle}
              onScroll={updateScrollState}
            >
              {groups.length === 0 ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可归档会话" />
              ) : groupButtons}
            </div>
            {groups.length > 0 && scrollState.max > 0 && (
              <div
                aria-hidden
                className="data-flywheel-session-scrollbar"
                style={customScrollbarTrackStyle}
                onClick={handleScrollbarClick}
              >
                <div style={{ ...customScrollbarThumbStyle, width: thumbWidth, left: thumbLeft }} />
              </div>
            )}
          </>
        ) : (
          <>
            {bucketButtons}
            {groups.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可归档会话" />
            ) : groupButtons}
          </>
        )}
      </div>
    </Card>
  );
}

function archiveListStyle(horizontal: boolean): CSSProperties {
  return {
    width: '100%',
    height: '100%',
    minHeight: 0,
    overflowX: 'hidden',
    overflowY: horizontal ? 'visible' : 'auto',
    scrollbarGutter: 'stable',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'stretch',
    gap: horizontal ? 8 : 10,
    paddingBottom: horizontal ? 2 : 0,
  };
}

function archiveButtonStyle(active: boolean, horizontal: boolean): CSSProperties {
  return {
    width: horizontal ? 300 : '100%',
    minWidth: horizontal ? 240 : undefined,
    maxWidth: horizontal ? 360 : undefined,
    minHeight: horizontal ? 72 : undefined,
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

const fixedBucketRowStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
  gap: 10,
  flexShrink: 0,
};

const sessionScrollRowStyle: CSSProperties = {
  display: 'flex',
  gap: 10,
  minWidth: 0,
  overflowX: 'scroll',
  overflowY: 'hidden',
  scrollbarGutter: 'stable',
  flexShrink: 0,
};

const customScrollbarTrackStyle: CSSProperties = {
  position: 'relative',
  height: 10,
  borderRadius: 999,
  background: 'rgba(139, 148, 158, 0.16)',
  cursor: 'pointer',
  flexShrink: 0,
};

const customScrollbarThumbStyle: CSSProperties = {
  position: 'absolute',
  top: 2,
  bottom: 2,
  borderRadius: 999,
  background: palette.border,
};

const archiveCardStyle: CSSProperties = {
  ...cardStyle,
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
  minHeight: 0,
  overflow: 'visible',
};
