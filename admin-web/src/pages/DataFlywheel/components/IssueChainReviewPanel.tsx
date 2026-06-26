import { Button, Card, Empty, Form, Input, Radio, Select, Space, Tag, Typography } from 'antd';
import { ExperimentOutlined, FileZipOutlined, LinkOutlined } from '@ant-design/icons';
import { useEffect } from 'react';
import type { CSSProperties } from 'react';
import type { FormInstance } from 'antd';

import type {
  ReviewIssueChainDetail,
  ReviewIssueChainEvidenceItem,
  ReviewIssueChainReviewRequest,
} from '../../../api/dataFlywheel';
import { cardStyle, palette } from '../../../styles/theme';
import {
  dominantSignalText,
  evidenceKeyText,
  evidenceStatusLabel,
  fixTargetOptions,
  fixTargetText,
  missingEvidenceOptions,
  qualityLabelOptions,
  qualityLabelText,
} from './reviewLabels';

interface IssueChainReviewPanelProps {
  detail: ReviewIssueChainDetail | null;
  contextTurnIds: number[];
  resultTurnIds: number[];
  saving: boolean;
  creatingDraft: boolean;
  creatingRepairPack: boolean;
  runningAiJudge: boolean;
  onSave: (body: ReviewIssueChainReviewRequest) => Promise<void>;
  onRunAiJudge: () => Promise<void>;
  onCreateCaseDraft: () => Promise<void>;
  onCreateRepairPack: () => Promise<void>;
}

interface ReviewFormValues {
  status: string;
  root_cause?: string;
  expected_behavior?: string;
  fix_target?: string;
  reviewer_comment?: string;
  false_positive_reason?: string;
  final_labels?: string[];
  missing_evidence?: string[];
}

export default function IssueChainReviewPanel({
  detail,
  contextTurnIds,
  resultTurnIds,
  saving,
  creatingDraft,
  creatingRepairPack,
  runningAiJudge,
  onSave,
  onRunAiJudge,
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
      fix_target: detail.chain.human_review.fix_target ?? detail.chain.repair.fix_target ?? 'unknown',
      reviewer_comment: detail.chain.human_review.reviewer_comment ?? undefined,
      false_positive_reason: detail.chain.human_review.false_positive_reason ?? undefined,
      final_labels: defaultQualityLabels(detail),
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
      final_labels: values.final_labels ?? [],
      root_cause: values.root_cause?.trim(),
      expected_behavior: values.expected_behavior?.trim(),
      fix_target: values.fix_target,
      reviewer_comment: values.reviewer_comment?.trim(),
      false_positive_reason: values.status === 'rejected' ? values.false_positive_reason?.trim() : undefined,
      missing_evidence: values.status === 'needs_evidence' ? values.missing_evidence ?? [] : undefined,
    });
  };

  const closureBlockReason = getClosureBlockReason(detail);
  const closureBlocked = Boolean(closureBlockReason);
  const aiAdvice = buildAiAdvice(detail);
  const traceUrl = buildTraceUrl(detail);

  return (
    <Card title="审核面板" style={panelStyle} styles={{ body: panelBodyStyle }}>
      <div style={panelContentStyle}>
        <section style={compactSectionStyle}>
          <Space wrap size={6}>
            <Tag color={detail.chain.severity === 'P0' ? 'red' : 'orange'}>{detail.chain.severity}</Tag>
            <Tag color="purple">{dominantSignalText(detail.chain.dominant_signal)}</Tag>
            <Tag>{fixTargetText(detail.chain.repair.fix_target)}</Tag>
          </Space>
          <Typography.Title level={5} style={{ color: palette.text, margin: '8px 0 4px' }}>
            {detail.chain.diagnosis.title || '风险问题链'}
          </Typography.Title>
          <Typography.Text style={{ color: palette.textMuted }}>
            {detail.chain.diagnosis.summary || '该问题链需要人工复核。'}
          </Typography.Text>
        </section>

        <section style={compactSectionStyle}>
          <Typography.Text strong style={{ color: palette.text }}>命中原因</Typography.Text>
          <div style={riskReasonGridStyle}>
            <RiskMetric label="最终风险" value={formatRiskScore(detail.chain.risk_context?.risk_score)} />
            <RiskMetric label="规则分" value={formatRiskScore(detail.chain.risk_context?.rule_score)} />
            <RiskMetric label="AI 概率" value={formatRiskScore(detail.chain.risk_context?.judge_bad_prob)} />
          </div>
          <Typography.Paragraph style={riskReasonTextStyle}>
            {detail.chain.risk_context?.trigger_reason || detail.chain.diagnosis.summary || '暂无明确命中原因。'}
          </Typography.Paragraph>
          <Space wrap size={6}>
            <Tag color="purple">{dominantSignalText(detail.chain.risk_context?.dominant_signal || detail.chain.dominant_signal)}</Tag>
            {(detail.chain.risk_context?.rule_hits ?? []).map((rule) => (
              <Tag key={rule} color="orange">{rule}</Tag>
            ))}
            {detail.chain.risk_context?.scoring_rule && (
              <Tag>{detail.chain.risk_context.scoring_rule}</Tag>
            )}
          </Space>
        </section>

        <section style={compactSectionStyle}>
          <Typography.Text strong style={{ color: palette.text }}>证据清单</Typography.Text>
          <div style={evidenceGridStyle}>
            {detail.evidence_checklist.map((item) => (
              <EvidenceRow key={`${item.key}-${item.turn_id ?? 'none'}`} item={item} />
            ))}
          </div>
        </section>

        <section style={compactSectionStyle}>
          <div style={aiHeaderStyle}>
            <Typography.Text strong style={{ color: palette.text }}>AI 预判</Typography.Text>
            <Space size={6} wrap>
              <Button size="small" loading={runningAiJudge} onClick={onRunAiJudge}>
                运行 AI 预判
              </Button>
              <Button size="small" disabled={!aiAdvice} onClick={() => applyAiAdvice(form, aiAdvice)}>
                采纳建议
              </Button>
            </Space>
          </div>
          <div style={aiContentStyle}>
            {aiAdvice ? (
              <>
                <Space wrap size={6}>
                  {aiAdvice.labels.map((label) => (
                    <Tag key={label} color="blue">{qualityLabelText(label)}</Tag>
                  ))}
                  {typeof aiAdvice.confidence === 'number' && (
                    <Tag color="purple">置信度 {Math.round(aiAdvice.confidence * 100)}%</Tag>
                  )}
                  {aiAdvice.model && <Tag>{aiAdvice.model}</Tag>}
                  {aiAdvice.promptVersion && <Tag>{aiAdvice.promptVersion}</Tag>}
                </Space>
                <div style={aiSummaryGridStyle}>
                  <AiAdviceField title="建议根因" value={aiAdvice.rootCause} />
                  <AiAdviceField title="修复建议" value={aiAdvice.recommendedFix} />
                </div>
                {aiAdvice.reason && (
                  <div style={aiReasonBoxStyle}>
                    <Typography.Text strong style={{ color: palette.text }}>判断理由</Typography.Text>
                    <Typography.Paragraph style={aiReasonTextStyle}>
                      {aiAdvice.reason}
                    </Typography.Paragraph>
                  </div>
                )}
              </>
            ) : (
              <Typography.Text style={{ color: palette.textMuted }}>
                暂无 AI 预判；可以手动运行，不会写入最终结论。
              </Typography.Text>
            )}
          </div>
        </section>

        <Form form={form} layout="vertical" onFinish={handleFinish} requiredMark={false}>
          <section style={compactSectionStyle}>
            <Typography.Text strong style={{ color: palette.text }}>人工判断</Typography.Text>
            <Form.Item
              name="status"
              label="处理结论"
              initialValue={defaultStatus(detail)}
              style={compactFormItemStyle}
            >
              <Radio.Group>
                <Radio value="accepted" aria-label="采纳坏例">采纳坏例</Radio>
                <Radio value="rejected" aria-label="驳回误报">驳回误报</Radio>
                <Radio value="not_actionable">暂不处理</Radio>
                <Radio value="needs_evidence">补证据</Radio>
              </Radio.Group>
            </Form.Item>
            <Form.Item
              name="final_labels"
              label="问题标签"
              rules={[{ required: status === 'accepted', message: '采纳坏例时必须选择问题标签' }]}
              style={compactFormItemStyle}
            >
              <Select
                mode="multiple"
                aria-label="问题标签"
                placeholder="选择工具选错、幻觉执行、参数错配等标签"
                options={qualityLabelOptions}
                optionFilterProp="label"
              />
            </Form.Item>
          </section>

          {status === 'accepted' && (
            <>
              <section style={compactSectionStyle}>
                <Typography.Text strong style={{ color: palette.text }}>根因与正确行为</Typography.Text>
                <Form.Item
                  name="root_cause"
                  label="根因说明"
                  rules={[{ required: true, message: '采纳坏例时必须填写根因说明' }]}
                  style={compactFormItemStyle}
                >
                  <Input.TextArea aria-label="根因说明" autoSize={{ minRows: 2, maxRows: 3 }} />
                </Form.Item>
                <Form.Item
                  name="expected_behavior"
                  label="正确行为"
                  rules={[{ required: true, message: '采纳坏例时必须填写正确行为' }]}
                  style={compactFormItemStyle}
                >
                  <Input.TextArea aria-label="正确行为" autoSize={{ minRows: 2, maxRows: 4 }} />
                </Form.Item>
              </section>

              <section style={compactSectionStyle}>
                <Typography.Text strong style={{ color: palette.text }}>修复归属</Typography.Text>
                <Form.Item
                  name="fix_target"
                  label="修复归属"
                  rules={[{ required: true, message: '采纳坏例时必须选择修复归属' }]}
                  style={compactFormItemStyle}
                >
                  <Select options={fixTargetOptions} />
                </Form.Item>
              </section>
            </>
          )}

          {status === 'rejected' && (
            <Form.Item
              name="false_positive_reason"
              label="误报原因"
              rules={[{ required: true, message: '驳回误报时必须填写原因' }]}
              style={compactFormItemStyle}
            >
              <Input.TextArea aria-label="误报原因" autoSize={{ minRows: 3, maxRows: 5 }} />
            </Form.Item>
          )}

          {status === 'needs_evidence' && (
            <Form.Item
              name="missing_evidence"
              label="缺失证据"
              rules={[{ required: true, message: '补证据时必须选择缺失证据' }]}
              style={compactFormItemStyle}
            >
              <Select mode="multiple" options={missingEvidenceOptions} />
            </Form.Item>
          )}

          <Form.Item
            name="reviewer_comment"
            label="审核备注"
            rules={[{
              required: status === 'needs_evidence',
              message: '补证据时必须填写说明',
            }]}
            style={compactFormItemStyle}
          >
            <Input.TextArea aria-label="审核备注" autoSize={{ minRows: 2, maxRows: 3 }} />
          </Form.Item>

          <div style={stickyActionStyle}>
            <Space direction="vertical" size={6} style={{ width: '100%' }}>
              <Space wrap size={8}>
                <Tag color={detail.chain.regression.regression_ready ? 'green' : 'default'}>
                  回归：{detail.chain.regression.regression_ready ? '可生成' : '未就绪'}
                </Tag>
                <Tag color={detail.chain.repair.export_blocked_reason ? 'orange' : 'green'}>
                  修复包：{detail.chain.repair.export_blocked_reason ? '阻断' : '可导出'}
                </Tag>
                {closureBlockReason && <Tag color="gold">阻断：{closureBlockReason}</Tag>}
              </Space>
              <Space wrap size={8}>
                <Button icon={<LinkOutlined />} href={traceUrl}>
                  跳 TraceMonitor
                </Button>
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
              <Button type="primary" htmlType="submit" loading={saving} block>
                保存并下一条
              </Button>
            </Space>
          </div>
        </Form>
      </div>
    </Card>
  );
}

function AiAdviceField({ title, value }: { title: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div style={aiFieldStyle}>
      <Typography.Text strong style={{ color: palette.text }}>{title}</Typography.Text>
      <Typography.Text style={{ color: palette.textMuted }}>{value}</Typography.Text>
    </div>
  );
}

function RiskMetric({ label, value }: { label: string; value: string }) {
  return (
    <div style={riskMetricStyle}>
      <Typography.Text style={{ color: palette.textMuted }}>{label}</Typography.Text>
      <Typography.Text strong style={{ color: palette.text }}>{value}</Typography.Text>
    </div>
  );
}

function EvidenceRow({ item }: { item: ReviewIssueChainEvidenceItem }) {
  const color = item.status === 'missing' ? 'orange' : item.status === 'needs_human' ? 'blue' : 'green';
  return (
    <div style={evidenceRowStyle}>
      <Space wrap size={6}>
        <Tag color={color}>{evidenceStatusLabel(item.status)}</Tag>
        <Typography.Text style={{ color: palette.text }}>{evidenceKeyText(item.key)}</Typography.Text>
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

function defaultQualityLabels(detail: ReviewIssueChainDetail): string[] {
  const reviewedLabels = detail.chain.human_review.quality_labels ?? [];
  if (reviewedLabels.length > 0) return reviewedLabels;
  return detail.chain.diagnosis.suggested_labels ?? [];
}

interface AiAdvice {
  labels: string[];
  confidence?: number | null;
  rootCause?: string | null;
  reason?: string | null;
  recommendedFix?: string | null;
  missingEvidence?: string[];
  model?: string | null;
  promptVersion?: string | null;
}

function buildAiAdvice(detail: ReviewIssueChainDetail): AiAdvice | null {
  const judge = detail.chain.ai_judge ?? {};
  const hasJudgeOutput = Object.values(judge).some((value) => {
    if (Array.isArray(value)) return value.length > 0;
    return value !== null && value !== undefined && value !== '';
  });
  if (!hasJudgeOutput) return null;

  const labels = uniqueStrings([
    stringValue(judge.suggested_label),
    ...arrayValue(judge.suggested_labels),
  ]);
  const confidence = typeof judge.bad_prob === 'number'
    ? judge.bad_prob
    : null;
  const rootCause = stringValue(judge.root_cause);
  const reason = stringValue(judge.reason);
  const recommendedFix = stringValue(judge.recommended_fix);
  const missingEvidence = normalizedMissingEvidence(arrayValue(judge.missing_evidence));
  const model = stringValue(judge.judge_model);
  const promptVersion = stringValue(judge.prompt_version);
  if (
    labels.length === 0
    && confidence === null
    && !rootCause
    && !reason
    && !recommendedFix
    && missingEvidence.length === 0
    && !model
    && !promptVersion
  ) {
    return null;
  }
  return { labels, confidence, rootCause, reason, recommendedFix, missingEvidence, model, promptVersion };
}

function applyAiAdvice(form: FormInstance<ReviewFormValues>, advice: AiAdvice | null) {
  if (!advice) return;
  const current = form.getFieldsValue();
  const acceptedLabels = advice.labels.filter((label) => label !== 'not_actionable');
  const shouldCollectEvidence = acceptedLabels.length === 0 && advice.missingEvidence?.length;
  const finalLabels = uniqueStrings([
    ...(current.final_labels ?? []),
    ...acceptedLabels,
  ]);
  form.setFieldsValue({
    status: shouldCollectEvidence ? 'needs_evidence' : 'accepted',
    final_labels: shouldCollectEvidence ? current.final_labels ?? [] : finalLabels,
    root_cause: shouldCollectEvidence ? current.root_cause : current.root_cause || advice.rootCause || advice.reason || undefined,
    expected_behavior: shouldCollectEvidence ? current.expected_behavior : current.expected_behavior || expectedBehaviorFromAdvice(advice),
    fix_target: shouldCollectEvidence ? current.fix_target : usableFixTarget(current.fix_target) || inferFixTarget(finalLabels, advice),
    missing_evidence: shouldCollectEvidence
      ? uniqueStrings([...(current.missing_evidence ?? []), ...(advice.missingEvidence ?? [])])
      : current.missing_evidence,
    reviewer_comment: current.reviewer_comment || reviewerCommentFromAdvice(advice, Boolean(shouldCollectEvidence)),
  });
}

function expectedBehaviorFromAdvice(advice: AiAdvice): string | undefined {
  if (advice.recommendedFix) return `应修正为：${advice.recommendedFix}`;
  if (advice.reason) return `应基于上下文证据完成用户请求，避免该 AI 预判指出的问题：${advice.reason}`;
  return undefined;
}

function usableFixTarget(value?: string): string | undefined {
  return value && value !== 'unknown' ? value : undefined;
}

function inferFixTarget(labels: string[], advice: AiAdvice): string {
  if (labels.includes('wrong_tool_selection') || labels.includes('tool_parameter_mismatch')) return 'router';
  if (labels.includes('pending_missed')) return 'pending';
  if (labels.includes('hallucinated_execution') || labels.includes('tool_error_ignored')) return 'tool';
  const text = [
    ...labels,
    advice.rootCause,
    advice.reason,
    advice.recommendedFix,
  ].filter(Boolean).join(' ').toLowerCase();
  if (text.includes('router') || text.includes('路由') || text.includes('参数') || text.includes('工具选择')) return 'router';
  if (text.includes('pending') || text.includes('缺少确认')) return 'pending';
  if (text.includes('tool') || text.includes('工具') || text.includes('执行')) return 'tool';
  if (text.includes('数据') || text.includes('工资') || text.includes('工人')) return 'data';
  if (text.includes('提示词') || text.includes('回复') || text.includes('意图')) return 'prompt';
  return 'manual_triage';
}

function reviewerCommentFromAdvice(advice: AiAdvice, collectEvidence: boolean): string {
  const reason = advice.reason || advice.rootCause || advice.recommendedFix;
  if (collectEvidence) {
    return reason ? `采纳 AI 补证据建议：${reason}` : '采纳 AI 补证据建议。';
  }
  return reason ? `已采纳 AI 预判：${reason}` : '已采纳 AI 预判作为人工判断草稿。';
}

function normalizedMissingEvidence(values: string[]): string[] {
  const allowed = new Set(missingEvidenceOptions.map((item) => item.value));
  return uniqueStrings(values.filter((value) => allowed.has(value)));
}

function uniqueStrings(values: Array<string | null | undefined>): string[] {
  return values.filter((value, index, arr): value is string => (
    Boolean(value) && arr.indexOf(value) === index
  ));
}

function stringValue(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function arrayValue(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && Boolean(item)) : [];
}

function formatRiskScore(value: unknown): string {
  return typeof value === 'number' ? value.toFixed(2) : '-';
}

function getClosureBlockReason(detail: ReviewIssueChainDetail): string | null {
  const reviewStatus = detail.chain.human_review.status;
  const chainStatus = reviewStatus && reviewStatus !== 'unreviewed' ? reviewStatus : detail.chain.status;
  if (chainStatus === 'needs_evidence') {
    return '问题链仍需补证据';
  }
  if (chainStatus !== 'accepted') {
    return '问题链尚未采纳';
  }
  if (!detail.chain.human_review.expected_behavior?.trim()) {
    return '缺少正确行为';
  }
  return null;
}

function buildTraceUrl(detail: ReviewIssueChainDetail): string {
  const params = new URLSearchParams();
  const trigger = detail.trigger_turn ?? detail.timeline.find((turn) => turn.turn_id === detail.chain.trigger_turn_id);
  if (trigger?.request_id) params.set('request_id', trigger.request_id);
  params.set('session_id', detail.session_id);
  params.set('turn_id', String(detail.chain.trigger_turn_id));
  return `/dev/traces?${params.toString()}`;
}

const panelStyle: CSSProperties = {
  ...cardStyle,
  height: '100%',
  minHeight: 0,
  display: 'flex',
  flexDirection: 'column',
};

const panelBodyStyle: CSSProperties = {
  padding: 0,
  minHeight: 0,
  overflow: 'hidden',
  display: 'flex',
  flexDirection: 'column',
};

const panelContentStyle: CSSProperties = {
  minHeight: 0,
  overflow: 'auto',
  scrollbarGutter: 'stable',
  padding: 12,
};

const compactSectionStyle: CSSProperties = {
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 8,
  padding: 10,
  background: palette.bg,
  marginBottom: 10,
};

const evidenceRowStyle: CSSProperties = {
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  padding: '6px 8px',
  background: palette.bgElevated,
};

const evidenceGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(142px, 1fr))',
  gap: 6,
  marginTop: 8,
};

const riskReasonGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
  gap: 6,
  marginTop: 8,
};

const riskMetricStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  padding: '6px 8px',
  background: palette.bgElevated,
};

const riskReasonTextStyle: CSSProperties = {
  color: palette.textMuted,
  margin: '8px 0',
  whiteSpace: 'pre-wrap',
};

const aiHeaderStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 8,
  marginBottom: 8,
};

const aiContentStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  minWidth: 0,
};

const aiSummaryGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'minmax(0, 1fr)',
  gap: 8,
};

const aiFieldStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  padding: 8,
  background: palette.bgElevated,
};

const aiReasonBoxStyle: CSSProperties = {
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  padding: 8,
  background: palette.bgElevated,
};

const aiReasonTextStyle: CSSProperties = {
  color: palette.textMuted,
  margin: '4px 0 0',
  maxHeight: 132,
  overflow: 'auto',
  whiteSpace: 'pre-wrap',
};

const compactFormItemStyle: CSSProperties = {
  marginBottom: 10,
};

const stickyActionStyle: CSSProperties = {
  position: 'sticky',
  bottom: 0,
  zIndex: 2,
  borderTop: `1px solid ${palette.borderSoft}`,
  background: palette.bgPanel,
  padding: '10px 0 0',
};
