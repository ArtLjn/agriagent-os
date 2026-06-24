import { Button, Card, Checkbox, Empty, Form, Input, Radio, Select, Space, Tag, Typography } from 'antd';
import { ExperimentOutlined, FileZipOutlined } from '@ant-design/icons';
import { useEffect } from 'react';
import type { CSSProperties } from 'react';

import type {
  ReviewIssueChainDetail,
  ReviewIssueChainEvidenceItem,
  ReviewIssueChainReviewRequest,
} from '../../../api/dataFlywheel';
import { cardStyle, palette } from '../../../styles/theme';

interface IssueChainReviewPanelProps {
  detail: ReviewIssueChainDetail | null;
  contextTurnIds: number[];
  resultTurnIds: number[];
  saving: boolean;
  creatingDraft: boolean;
  creatingRepairPack: boolean;
  onSave: (body: ReviewIssueChainReviewRequest) => Promise<void>;
  onCreateCaseDraft: () => Promise<void>;
  onCreateRepairPack: () => Promise<void>;
}

interface ReviewFormValues {
  status: string;
  root_cause?: string;
  expected_behavior?: string;
  false_positive_reason?: string;
  final_labels?: string[];
  missing_evidence?: string[];
}

const labelOptions = [
  { label: 'good_reply', value: 'good_reply' },
  { label: 'bad_reply', value: 'bad_reply' },
  { label: 'wrong_tool_selection', value: 'wrong_tool_selection' },
  { label: 'tool_parameter_mismatch', value: 'tool_parameter_mismatch' },
  { label: 'pending_missed', value: 'pending_missed' },
  { label: 'hallucinated_execution', value: 'hallucinated_execution' },
  { label: 'tool_error_ignored', value: 'tool_error_ignored' },
  { label: 'off_topic', value: 'off_topic' },
  { label: 'sensitive_info_leak', value: 'sensitive_info_leak' },
  { label: 'missing_wage', value: 'missing_wage' },
  { label: 'disabled_worker_used', value: 'disabled_worker_used' },
  { label: 'unclear_intent', value: 'unclear_intent' },
  { label: 'not_actionable', value: 'not_actionable' },
  { label: 'needs_regression', value: 'needs_regression' },
];

const missingEvidenceOptions = [
  { label: 'event', value: 'event' },
  { label: 'trace', value: 'trace' },
  { label: 'db_diff', value: 'db_diff' },
  { label: 'context', value: 'context' },
];

export default function IssueChainReviewPanel({
  detail,
  contextTurnIds,
  resultTurnIds,
  saving,
  creatingDraft,
  creatingRepairPack,
  onSave,
  onCreateCaseDraft,
  onCreateRepairPack,
}: IssueChainReviewPanelProps) {
  const [form] = Form.useForm<ReviewFormValues>();
  const status = Form.useWatch('status', form);

  useEffect(() => {
    if (!detail) return;
    form.setFieldsValue({
      status: defaultStatus(detail),
      root_cause: detail.chain.human_review.root_cause ?? undefined,
      expected_behavior: detail.chain.human_review.expected_behavior ?? undefined,
      false_positive_reason: detail.chain.human_review.false_positive_reason ?? undefined,
      final_labels: detail.chain.human_review.quality_labels ?? detail.chain.diagnosis.suggested_labels ?? [],
      missing_evidence: detail.chain.human_review.missing_evidence ?? missingEvidenceFromChecklist(detail.evidence_checklist),
    });
  }, [detail, form]);

  if (!detail) {
    return (
      <Card title="审核面板" style={panelStyle}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选择问题链后保存人工判断" />
      </Card>
    );
  }

  const handleFinish = async (values: ReviewFormValues) => {
    await onSave({
      status: values.status,
      context_turn_ids: contextTurnIds,
      result_turn_ids: resultTurnIds,
      final_labels: values.status === 'accepted' ? values.final_labels ?? [] : undefined,
      root_cause: values.status === 'accepted' ? values.root_cause?.trim() : undefined,
      expected_behavior: values.status === 'accepted' ? values.expected_behavior?.trim() : undefined,
      false_positive_reason: values.status === 'rejected' ? values.false_positive_reason?.trim() : undefined,
      missing_evidence: values.status === 'needs_evidence' ? values.missing_evidence ?? [] : undefined,
    });
  };

  const closureBlockReason = getClosureBlockReason(detail);
  const closureBlocked = Boolean(closureBlockReason);

  return (
    <Card
      title="审核面板"
      style={panelStyle}
      styles={{ body: { padding: 12, minHeight: 0, overflow: 'auto', scrollbarGutter: 'stable' } }}
    >
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <section style={sectionStyle}>
          <Space wrap size={6}>
            <Tag color={detail.chain.severity === 'P0' ? 'red' : 'orange'}>{detail.chain.severity}</Tag>
            <Tag color="purple">{detail.chain.dominant_signal}</Tag>
            <Tag>{detail.chain.repair.fix_target || 'manual_triage'}</Tag>
          </Space>
          <Typography.Title level={5} style={{ color: palette.text, margin: '8px 0 4px' }}>
            {detail.chain.diagnosis.title || 'risk_turn'}
          </Typography.Title>
          <Typography.Text style={{ color: palette.textMuted }}>
            {detail.chain.diagnosis.summary || '该问题链需要人工复核。'}
          </Typography.Text>
        </section>

        <section style={sectionStyle}>
          <Typography.Text strong style={{ color: palette.text }}>证据 checklist</Typography.Text>
          <Space direction="vertical" size={6} style={{ width: '100%', marginTop: 8 }}>
            {detail.evidence_checklist.map((item) => (
              <EvidenceRow key={`${item.key}-${item.turn_id ?? 'none'}`} item={item} />
            ))}
          </Space>
        </section>

        <Form form={form} layout="vertical" onFinish={handleFinish} requiredMark={false}>
          <Form.Item name="status" label="人工判断" initialValue={defaultStatus(detail)}>
            <Radio.Group>
              <Radio value="accepted" aria-label="采纳坏例">采纳坏例</Radio>
              <Radio value="rejected" aria-label="驳回误报">驳回误报</Radio>
              <Radio value="not_actionable">暂不处理</Radio>
              <Radio value="needs_evidence">补证据</Radio>
            </Radio.Group>
          </Form.Item>

          {status === 'accepted' && (
            <>
              <Form.Item
                name="root_cause"
                label="Root cause"
                rules={[{ required: true, message: 'accepted 必填 root cause' }]}
              >
                <Input.TextArea aria-label="Root cause" autoSize={{ minRows: 2, maxRows: 4 }} />
              </Form.Item>
              <Form.Item
                name="expected_behavior"
                label="Expected behavior"
                rules={[{ required: true, message: 'accepted 必填 expected behavior' }]}
              >
                <Input.TextArea aria-label="Expected behavior" autoSize={{ minRows: 3, maxRows: 6 }} />
              </Form.Item>
              <Form.Item
                name="final_labels"
                label="Final labels"
                rules={[{ required: true, message: 'accepted 必填 final labels' }]}
              >
                <Checkbox.Group options={labelOptions} />
              </Form.Item>
            </>
          )}

          {status === 'rejected' && (
            <Form.Item
              name="false_positive_reason"
              label="误报原因"
              rules={[{ required: true, message: 'rejected 必填误报原因' }]}
            >
              <Input.TextArea aria-label="误报原因" autoSize={{ minRows: 3, maxRows: 5 }} />
            </Form.Item>
          )}

          {status === 'needs_evidence' && (
            <Form.Item
              name="missing_evidence"
              label="缺失证据"
              rules={[{ required: true, message: 'needs_evidence 必填缺失证据' }]}
            >
              <Select mode="multiple" options={missingEvidenceOptions} />
            </Form.Item>
          )}

          <section style={sectionStyle}>
            <Typography.Text strong style={{ color: palette.text }}>闭环出口</Typography.Text>
            <Space direction="vertical" size={4} style={{ width: '100%', marginTop: 8 }}>
              <Typography.Text style={{ color: palette.textMuted }}>
                regression: {detail.chain.regression.regression_ready ? 'ready' : 'blocked'}
              </Typography.Text>
              <Typography.Text style={{ color: palette.textMuted }}>
                repair: {detail.chain.repair.export_blocked_reason || 'ready'}
              </Typography.Text>
              {closureBlockReason && (
                <Typography.Text type="warning" aria-live="polite">
                  阻断原因：{closureBlockReason}
                </Typography.Text>
              )}
              <Space wrap size={8} style={{ marginTop: 4 }}>
                <Button
                  icon={<ExperimentOutlined />}
                  disabled={closureBlocked}
                  loading={creatingDraft}
                  onClick={onCreateCaseDraft}
                >
                  生成回归草稿
                </Button>
                <Button
                  icon={<FileZipOutlined />}
                  disabled={closureBlocked}
                  loading={creatingRepairPack}
                  onClick={onCreateRepairPack}
                >
                  导出修复包
                </Button>
              </Space>
            </Space>
          </section>

          <Button type="primary" htmlType="submit" loading={saving} block>
            保存并下一条
          </Button>
        </Form>
      </Space>
    </Card>
  );
}

function EvidenceRow({ item }: { item: ReviewIssueChainEvidenceItem }) {
  const color = item.status === 'missing' ? 'orange' : item.status === 'needs_human' ? 'blue' : 'green';
  return (
    <div style={evidenceRowStyle}>
      <Space wrap size={6}>
        <Tag color={color}>{item.status}</Tag>
        <Typography.Text style={{ color: palette.text }}>{item.key}</Typography.Text>
        {typeof item.turn_id === 'number' && (
          <a href={`#turn-${item.turn_id}`} style={{ color: palette.accent }}>
            turn #{item.turn_id}
          </a>
        )}
      </Space>
    </div>
  );
}

function defaultStatus(detail: ReviewIssueChainDetail): string {
  const status = detail.chain.human_review.status;
  if (status && status !== 'unreviewed') return status;
  return detail.chain.status === 'needs_evidence' ? 'needs_evidence' : 'accepted';
}

function missingEvidenceFromChecklist(checklist: ReviewIssueChainEvidenceItem[]): string[] {
  return checklist
    .filter((item) => item.status === 'missing')
    .map((item) => item.key);
}

function getClosureBlockReason(detail: ReviewIssueChainDetail): string | null {
  const reviewStatus = detail.chain.human_review.status;
  const chainStatus = reviewStatus && reviewStatus !== 'unreviewed' ? reviewStatus : detail.chain.status;
  if (chainStatus === 'needs_evidence') {
    return '问题链仍需补证据';
  }
  if (chainStatus !== 'accepted') {
    return '问题链尚未 accepted';
  }
  if (!detail.chain.human_review.expected_behavior?.trim()) {
    return '缺少 expected behavior';
  }
  return null;
}

const panelStyle: CSSProperties = {
  ...cardStyle,
  height: '100%',
  minHeight: 0,
  display: 'flex',
  flexDirection: 'column',
};

const sectionStyle: CSSProperties = {
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 8,
  padding: 10,
  background: palette.bg,
};

const evidenceRowStyle: CSSProperties = {
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  padding: '6px 8px',
  background: palette.bgElevated,
};
