import { Alert, Button, Card, Space, Typography, message } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';

import {
  createReviewIssueChainCaseDraft,
  createReviewIssueChainRepairPack,
  getDailyReviewInbox,
  getReviewIssueChain,
  saveReviewIssueChainReview,
  type CaseDraft,
  type DailyReviewInboxItem,
  type DailyReviewInboxResponse,
  type DataFlywheelRepairPack,
  type ReviewIssueChainDetail,
  type ReviewIssueChainReviewRequest,
} from '../../../api/dataFlywheel';
import { cardStyle, palette } from '../../../styles/theme';
import IssueChainReviewPanel from './IssueChainReviewPanel';
import ReviewIssueChainTimeline from './ReviewIssueChainTimeline';
import RiskSessionInbox from './RiskSessionInbox';

interface DailyReviewWorkbenchProps {
  onCaseDraftCreated: (draft: CaseDraft) => void;
  onRepairPackCreated: (pack: DataFlywheelRepairPack) => void;
}

export default function DailyReviewWorkbench({
  onCaseDraftCreated,
  onRepairPackCreated,
}: DailyReviewWorkbenchProps) {
  const [inbox, setInbox] = useState<DailyReviewInboxResponse>({ items: [], total: 0 });
  const [selectedItem, setSelectedItem] = useState<DailyReviewInboxItem | null>(null);
  const [detail, setDetail] = useState<ReviewIssueChainDetail | null>(null);
  const [contextTurnIds, setContextTurnIds] = useState<number[]>([]);
  const [resultTurnIds, setResultTurnIds] = useState<number[]>([]);
  const [loadingInbox, setLoadingInbox] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [saving, setSaving] = useState(false);
  const [creatingDraft, setCreatingDraft] = useState(false);
  const [creatingRepairPack, setCreatingRepairPack] = useState(false);
  const inboxRequestSeq = useRef(0);
  const detailRequestSeq = useRef(0);

  const selectedChainId = selectedItem?.highest_risk_chain.chain_id;
  const handledCount = useMemo(
    () => inbox.items.filter((item) => ['accepted', 'rejected', 'not_actionable'].includes(item.status)).length,
    [inbox.items]
  );

  const loadInbox = useCallback(async () => {
    const requestSeq = inboxRequestSeq.current + 1;
    inboxRequestSeq.current = requestSeq;
    setLoadingInbox(true);
    try {
      const result = await getDailyReviewInbox({ limit: 50, offset: 0 });
      if (requestSeq !== inboxRequestSeq.current) return null;
      setInbox(result);
      setSelectedItem((current) => {
        if (current && result.items.some((item) => item.highest_risk_chain.chain_id === current.highest_risk_chain.chain_id)) {
          return current;
        }
        return result.items[0] ?? null;
      });
      return result;
    } catch {
      if (requestSeq === inboxRequestSeq.current) {
        message.error('加载每日质检失败');
      }
      return null;
    } finally {
      if (requestSeq === inboxRequestSeq.current) {
        setLoadingInbox(false);
      }
    }
  }, []);

  const loadChain = useCallback(async (chainId: string) => {
    const requestSeq = detailRequestSeq.current + 1;
    detailRequestSeq.current = requestSeq;
    setLoadingDetail(true);
    try {
      const result = await getReviewIssueChain(chainId);
      if (requestSeq !== detailRequestSeq.current) return;
      setDetail(result);
      setContextTurnIds(result.chain.context_turn_ids);
      setResultTurnIds(result.chain.result_turn_ids);
    } catch {
      if (requestSeq === detailRequestSeq.current) {
        message.error('加载问题链失败');
      }
    } finally {
      if (requestSeq === detailRequestSeq.current) {
        setLoadingDetail(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadInbox();
  }, [loadInbox]);

  useEffect(() => {
    if (!selectedChainId) {
      setDetail(null);
      setContextTurnIds([]);
      setResultTurnIds([]);
      return;
    }
    void loadChain(selectedChainId);
  }, [loadChain, selectedChainId]);

  const handleSelect = (item: DailyReviewInboxItem) => {
    setSelectedItem(item);
  };

  const handleSave = async (body: ReviewIssueChainReviewRequest) => {
    if (!selectedChainId) return;
    setSaving(true);
    try {
      await saveReviewIssueChainReview(selectedChainId, body);
      message.success('问题链审核已保存');
      const latestInbox = await loadInbox();
      const nextItem = nextInboxItem(latestInbox?.items ?? [], selectedChainId);
      if (nextItem) {
        setSelectedItem(nextItem);
      } else {
        await loadChain(selectedChainId);
      }
    } catch {
      message.error('保存问题链审核失败');
    } finally {
      setSaving(false);
    }
  };

  const handleCreateCaseDraft = async () => {
    if (!selectedChainId) return;
    setCreatingDraft(true);
    try {
      const result = await createReviewIssueChainCaseDraft(selectedChainId, 'evaluation_replay');
      onCaseDraftCreated(result);
      message.success('已生成问题链回归草稿');
    } catch {
      message.error('生成问题链回归草稿失败');
    } finally {
      setCreatingDraft(false);
    }
  };

  const handleCreateRepairPack = async () => {
    if (!selectedChainId) return;
    setCreatingRepairPack(true);
    try {
      const result = await createReviewIssueChainRepairPack(selectedChainId);
      onRepairPackCreated(result);
      if (result.deduplicated) {
        message.info(`检测到重复，已复用 pack ${result.pack_id}`);
      } else {
        message.success('已导出问题链修复包');
      }
    } catch {
      message.error('导出问题链修复包失败');
    } finally {
      setCreatingRepairPack(false);
    }
  };

  return (
    <div style={workbenchShellStyle}>
      <Card style={summaryCardStyle} styles={{ body: { padding: 12 } }}>
        <Space wrap style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space direction="vertical" size={2}>
            <Typography.Title level={4} style={{ color: palette.text, margin: 0 }}>
              每日质检
            </Typography.Title>
            <Typography.Text style={{ color: palette.textMuted }}>
              {inbox.total} 个风险 session / 已处理 {handledCount}
            </Typography.Text>
          </Space>
          <Button icon={<ReloadOutlined />} loading={loadingInbox} onClick={() => void loadInbox()}>
            刷新
          </Button>
        </Space>
      </Card>

      <div style={gridStyle}>
        <RiskSessionInbox
          items={inbox.items}
          loading={loadingInbox}
          selectedChainId={selectedChainId}
          onSelect={handleSelect}
        />
        <ReviewIssueChainTimeline
          detail={detail}
          contextTurnIds={contextTurnIds}
          resultTurnIds={resultTurnIds}
          loading={loadingDetail}
          onContextTurnIdsChange={setContextTurnIds}
          onResultTurnIdsChange={setResultTurnIds}
        />
        <IssueChainReviewPanel
          detail={detail}
          contextTurnIds={contextTurnIds}
          resultTurnIds={resultTurnIds}
          saving={saving}
          creatingDraft={creatingDraft}
          creatingRepairPack={creatingRepairPack}
          onSave={handleSave}
          onCreateCaseDraft={handleCreateCaseDraft}
          onCreateRepairPack={handleCreateRepairPack}
        />
      </div>
      {detail?.chain.status === 'needs_evidence' && (
        <Alert
          type="warning"
          showIcon
          message="当前问题链缺少证据，修复包出口会保持阻断。"
        />
      )}
    </div>
  );
}

function nextInboxItem(items: DailyReviewInboxItem[], currentChainId: string): DailyReviewInboxItem | null {
  const index = items.findIndex((item) => item.highest_risk_chain.chain_id === currentChainId);
  if (index < 0) return items[0] ?? null;
  return items[index + 1] ?? items[index - 1] ?? null;
}

const workbenchShellStyle: CSSProperties = {
  minHeight: 0,
  flex: 1,
  display: 'grid',
  gridTemplateRows: 'max-content minmax(560px, 1fr) max-content',
  gap: 12,
};

const summaryCardStyle: CSSProperties = {
  ...cardStyle,
  flexShrink: 0,
};

const gridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'minmax(280px, 0.9fr) minmax(420px, 1.45fr) minmax(320px, 1fr)',
  gap: 12,
  minHeight: 0,
};
