import { Empty, Select, Space, Spin, Tag, Typography } from 'antd';
import { useMemo, type CSSProperties } from 'react';

import type { DailyReviewInboxItem } from '../../../api/dataFlywheel';
import { cardStyle, palette } from '../../../styles/theme';
import {
  dominantSignalText,
  evidenceStatusLabel,
  nextActionText,
  reviewStatusText,
} from './reviewLabels';

type InboxFilter = 'open' | 'all' | 'p0' | 'needs_evidence' | 'ready_for_review' | 'ai_pending' | 'handled';
type InboxSort = 'risk' | 'evidence' | 'status' | 'recent';

interface RiskSessionInboxProps {
  items: DailyReviewInboxItem[];
  selectedChainId?: string;
  loading: boolean;
  filter: InboxFilter;
  sort: InboxSort;
  onFilterChange: (filter: InboxFilter) => void;
  onSortChange: (sort: InboxSort) => void;
  onSelect: (item: DailyReviewInboxItem) => void;
}

export default function RiskSessionInbox({
  items,
  selectedChainId,
  loading,
  filter,
  sort,
  onFilterChange,
  onSortChange,
  onSelect,
}: RiskSessionInboxProps) {
  const visibleItems = useMemo(
    () => sortInboxItems(items.filter((item) => matchesFilter(item, filter)), sort),
    [filter, items, sort]
  );

  return (
    <section style={inboxShellStyle}>
      <Space direction="vertical" size={10} style={{ width: '100%' }}>
        <Space wrap>
          <Select
            aria-label="质检筛选"
            data-testid="daily-review-queue-filter"
            size="small"
            value={filter}
            onChange={onFilterChange}
            options={[
              { label: '待处理', value: 'open' },
              { label: '需补证据', value: 'needs_evidence' },
              { label: '可审核', value: 'ready_for_review' },
              { label: '未审核', value: 'ai_pending' },
              { label: '已处理', value: 'handled' },
              { label: '全部', value: 'all' },
              { label: 'P0', value: 'p0' },
            ]}
            style={{ width: 150 }}
          />
          <Select
            aria-label="质检排序"
            size="small"
            value={sort}
            onChange={onSortChange}
            options={[
              { label: '最高风险', value: 'risk' },
              { label: '证据完整度', value: 'evidence' },
              { label: '处理状态', value: 'status' },
              { label: '最近时间', value: 'recent' },
            ]}
            style={{ width: 136 }}
          />
        </Space>
      </Space>
      <Spin spinning={loading}>
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          {visibleItems.length === 0 && !loading ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无质检 session" />
          ) : (
            visibleItems.map((item) => (
              <button
                key={item.highest_risk_chain.chain_id}
                type="button"
                data-testid={`risk-session-${item.session_id}`}
                style={sessionCardStyle(item.highest_risk_chain.chain_id === selectedChainId)}
                onClick={() => onSelect(item)}
              >
                <Space direction="vertical" size={8} style={{ width: '100%', textAlign: 'left' }}>
                  <Space wrap size={6}>
                    <Tag color={item.highest_risk_chain.severity === 'P0' ? 'red' : 'orange'}>
                      {item.highest_risk_chain.severity}
                    </Tag>
                    <Tag color={item.evidence_status === 'needs_evidence' ? 'orange' : 'green'}>
                      {evidenceStatusLabel(item.evidence_status)}
                    </Tag>
                    <Tag color={isHandled(item) ? 'green' : 'blue'}>{reviewStatusText(item.status)}</Tag>
                  </Space>
                  <Typography.Text strong ellipsis style={{ color: palette.text, maxWidth: '100%' }}>
                    {item.session_id}
                  </Typography.Text>
                  <Typography.Text ellipsis style={{ color: palette.textMuted, maxWidth: '100%' }}>
                    {item.session_card.summary || '无摘要'}
                  </Typography.Text>
                  <Space wrap size={6}>
                    <Tag color="red">最高风险链</Tag>
                    <Tag>候选链 {item.candidate_chain_count}</Tag>
                    <Tag color="purple">{dominantSignalText(item.dominant_signal)}</Tag>
                    <Tag>{nextActionText(item.next_action)}</Tag>
                  </Space>
                  <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
                    风险 {formatRisk(item.session_card.risk_score)} / 触发 turn #
                    {item.highest_risk_chain.trigger_turn_id}
                  </Typography.Text>
                </Space>
              </button>
            ))
          )}
        </Space>
      </Spin>
    </section>
  );
}

function matchesFilter(item: DailyReviewInboxItem, filter: InboxFilter): boolean {
  if (filter === 'open') return !isHandled(item);
  if (filter === 'all') return true;
  if (filter === 'p0') return item.highest_risk_chain.severity === 'P0';
  if (filter === 'needs_evidence') return item.evidence_status === 'needs_evidence' || item.status === 'needs_evidence';
  if (filter === 'ready_for_review') return item.evidence_status === 'ready_for_review' || item.status === 'ready_for_review';
  if (filter === 'ai_pending') return item.highest_risk_chain.human_review?.status === 'unreviewed';
  return isHandled(item);
}

function sortInboxItems(items: DailyReviewInboxItem[], sort: InboxSort): DailyReviewInboxItem[] {
  const cloned = [...items];
  if (sort === 'evidence') {
    return cloned.sort((a, b) => evidenceRank(b) - evidenceRank(a) || riskScore(b) - riskScore(a));
  }
  if (sort === 'status') {
    return cloned.sort((a, b) => statusRank(a) - statusRank(b) || riskScore(b) - riskScore(a));
  }
  if (sort === 'recent') {
    return cloned.sort((a, b) => Date.parse(b.updated_at || '') - Date.parse(a.updated_at || ''));
  }
  return cloned.sort((a, b) => riskScore(b) - riskScore(a));
}

function riskScore(item: DailyReviewInboxItem): number {
  return item.session_card.risk_score ?? 0;
}

function evidenceRank(item: DailyReviewInboxItem): number {
  return item.evidence_status === 'ready_for_review' ? 2 : 1;
}

function statusRank(item: DailyReviewInboxItem): number {
  if (item.status === 'ready_for_review') return 0;
  if (item.status === 'needs_evidence') return 1;
  return isHandled(item) ? 3 : 2;
}

function isHandled(item: DailyReviewInboxItem): boolean {
  return ['accepted', 'rejected', 'not_actionable'].includes(item.status);
}

function formatRisk(value: number | null): string {
  return typeof value === 'number' ? value.toFixed(2) : '-';
}

const inboxShellStyle: CSSProperties = {
  ...cardStyle,
  minHeight: 0,
  height: '100%',
  overflow: 'auto',
  padding: 12,
  scrollbarGutter: 'stable',
};

function sessionCardStyle(active: boolean): CSSProperties {
  return {
    width: '100%',
    border: `1px solid ${active ? palette.accentStrong : palette.borderSoft}`,
    borderRadius: 8,
    background: active ? 'rgba(31, 111, 235, 0.18)' : palette.bgPanel,
    color: palette.text,
    cursor: 'pointer',
    padding: 12,
  };
}
