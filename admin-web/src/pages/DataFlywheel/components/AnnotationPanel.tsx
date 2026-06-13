import { Button, Card, Input, Radio, Select, Space, Tag, Typography, message } from 'antd';
import {
  BranchesOutlined,
  BugOutlined,
  CheckCircleOutlined,
  CopyOutlined,
  DeleteOutlined,
  DownloadOutlined,
  ExperimentOutlined,
  RobotOutlined,
  SaveOutlined,
} from '@ant-design/icons';

import type {
  DataFlywheelLabel,
  DataFlywheelLabelRecord,
  DataFlywheelPrelabel,
  DataFlywheelSample,
} from '../../../api/dataFlywheel';
import { cardStyle, palette } from '../../../styles/theme';

interface AnnotationPanelProps {
  selectedSample: DataFlywheelSample | null;
  label: DataFlywheelLabel;
  comment: string;
  saving: boolean;
  acting: boolean;
  prelabels?: DataFlywheelPrelabel[];
  canPrelabel: boolean;
  prelabeling: boolean;
  reviewingPrelabel: boolean;
  selectedPrelabelLabels: DataFlywheelLabel[];
  annotationTargetLabel?: string;
  existingLabels?: DataFlywheelLabelRecord[];
  onLabelChange: (label: DataFlywheelLabel) => void;
  onCommentChange: (comment: string) => void;
  onSelectedPrelabelLabelsChange: (labels: DataFlywheelLabel[]) => void;
  onCreatePrelabel: () => void;
  onAcceptPrelabel: () => void;
  onRejectPrelabel: () => void;
  onSave: () => void;
  onDeleteLabel: (label: DataFlywheelLabelRecord) => void;
  onResolveLabel: (label: DataFlywheelLabelRecord) => void;
  onCopyDebug: () => void;
  onExportJsonl: () => void;
  onMarkBadCase: () => void;
  onCreateRegressionCase: () => void;
}

const labelOptions: Array<{ label: string; value: DataFlywheelLabel }> = [
  { label: '好回复', value: 'good_reply' },
  { label: '坏回复', value: 'bad_reply' },
  { label: '工具选错', value: 'wrong_tool_selection' },
  { label: 'pending 漏拦截', value: 'pending_missed' },
  { label: '幻觉执行', value: 'hallucinated_execution' },
  { label: '工具错误被忽略', value: 'tool_error_ignored' },
  { label: '答非所问', value: 'off_topic' },
  { label: '意图不清', value: 'unclear_intent' },
  { label: '参数/提示泄露', value: 'sensitive_info_leak' },
  { label: '工资缺失', value: 'missing_wage' },
  { label: '禁用工人', value: 'disabled_worker_used' },
  { label: '需要回归', value: 'needs_regression' },
  { label: '暂不处理', value: 'not_actionable' },
];

const labelText = Object.fromEntries(
  labelOptions.map((option) => [option.value, option.label])
) as Record<DataFlywheelLabel, string>;

export default function AnnotationPanel({
  selectedSample,
  label,
  comment,
  saving,
  acting,
  prelabels = [],
  canPrelabel,
  prelabeling,
  reviewingPrelabel,
  selectedPrelabelLabels,
  annotationTargetLabel,
  existingLabels = [],
  onLabelChange,
  onCommentChange,
  onSelectedPrelabelLabelsChange,
  onCreatePrelabel,
  onAcceptPrelabel,
  onRejectPrelabel,
  onSave,
  onDeleteLabel,
  onResolveLabel,
  onCopyDebug,
  onExportJsonl,
  onMarkBadCase,
  onCreateRegressionCase,
}: AnnotationPanelProps) {
  const disabled = !selectedSample;
  const prelabelDisabled = disabled || !canPrelabel;
  const latestPrelabel = prelabels[0] ?? selectedSample?.latest_prelabel ?? null;
  const pendingPrelabel = latestPrelabel?.status === 'pending' ? latestPrelabel : null;

  const handleTraceJump = () => {
    if (!selectedSample?.request_id) {
      message.warning('当前样本没有 request_id');
      return;
    }
    const params = new URLSearchParams({ request_id: selectedSample.request_id });
    if (selectedSample.session_id) {
      params.set('session_id', selectedSample.session_id);
    }
    window.location.href = `/dev/traces?${params.toString()}`;
  };

  return (
    <Card title="标注与动作" style={{ ...cardStyle, marginTop: 14 }} styles={{ body: { padding: 14 } }}>
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <div
          style={{
            border: `1px solid ${palette.borderSoft}`,
            borderRadius: 6,
            padding: 12,
            background: palette.bg,
          }}
        >
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Space size={8}>
                <RobotOutlined style={{ color: palette.accent }} />
                <Typography.Text style={{ color: palette.text }}>AI 预判</Typography.Text>
                {latestPrelabel && <Tag>{latestPrelabel.status}</Tag>}
              </Space>
              <Button
                aria-label="AI 预判"
                icon={<RobotOutlined />}
                disabled={prelabelDisabled}
                loading={prelabeling}
                onClick={onCreatePrelabel}
              >
                AI 预判
              </Button>
            </Space>

            {latestPrelabel && (
              <>
                <Space size={6} wrap>
                  {latestPrelabel.labels.map((item) => (
                    <Tag key={item} title={labelText[item] ?? item}>
                      {item}
                    </Tag>
                  ))}
                  <Tag color={latestPrelabel.severity === 'critical' || latestPrelabel.severity === 'high' ? 'red' : 'blue'}>
                    {latestPrelabel.severity}
                  </Tag>
                  <Tag>{Math.round(latestPrelabel.confidence * 100)}%</Tag>
                </Space>
                {latestPrelabel.root_cause && (
                  <Typography.Text style={{ color: palette.text }}>{latestPrelabel.root_cause}</Typography.Text>
                )}
                <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
                  {latestPrelabel.reason}
                </Typography.Text>
                {latestPrelabel.recommended_fix && (
                  <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
                    {latestPrelabel.recommended_fix}
                  </Typography.Text>
                )}
                <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
                  {latestPrelabel.judge_model} · {latestPrelabel.prompt_version}
                </Typography.Text>
              </>
            )}

            {pendingPrelabel && (
              <>
                <Select
                  aria-label="AI 建议标签"
                  mode="multiple"
                  value={selectedPrelabelLabels}
                  options={labelOptions}
                  disabled={prelabelDisabled}
                  onChange={onSelectedPrelabelLabelsChange}
                  style={{ width: '100%' }}
                />
                <Space wrap>
                  <Button
                    type="primary"
                    disabled={prelabelDisabled}
                    loading={reviewingPrelabel}
                    onClick={onAcceptPrelabel}
                  >
                    采纳 AI 预判
                  </Button>
                  <Button
                    disabled={prelabelDisabled}
                    loading={reviewingPrelabel}
                    onClick={onAcceptPrelabel}
                  >
                    修改后保存
                  </Button>
                  <Button
                    danger
                    disabled={prelabelDisabled}
                    loading={reviewingPrelabel}
                    onClick={onRejectPrelabel}
                  >
                    驳回 AI 预判
                  </Button>
                </Space>
              </>
            )}
          </Space>
        </div>

        <div>
          <Typography.Text style={{ color: palette.textMuted }}>
            质量标签{annotationTargetLabel ? ` · ${annotationTargetLabel}` : ''}
          </Typography.Text>
          <Radio.Group
            value={label}
            onChange={(event) => onLabelChange(event.target.value)}
            disabled={disabled}
            style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}
          >
            {labelOptions.map((option) => (
              <Radio key={option.value} value={option.value} style={{ color: palette.text, marginInlineEnd: 0 }}>
                {option.label}
              </Radio>
            ))}
          </Radio.Group>
        </div>

        {existingLabels.length > 0 && (
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Typography.Text style={{ color: palette.textMuted }}>已有标注</Typography.Text>
            {existingLabels.map((item) => {
              const resolved = item.status === 'resolved';
              return (
                <div
                  key={item.id}
                  style={{
                    border: `1px solid ${palette.borderSoft}`,
                    borderRadius: 6,
                    padding: '8px 10px',
                    background: palette.bg,
                  }}
                >
                  <Space align="start" style={{ width: '100%', justifyContent: 'space-between' }}>
                    <Space direction="vertical" size={2}>
                      <Space size={6} wrap>
                        <Typography.Text style={{ color: palette.text }}>
                          {labelText[item.label] ?? item.label}
                        </Typography.Text>
                        {resolved && <Tag color="green">已完成</Tag>}
                      </Space>
                      {item.comment && (
                        <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
                          {item.comment}
                        </Typography.Text>
                      )}
                      {item.annotator_id && (
                        <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
                          {item.annotator_id}
                        </Typography.Text>
                      )}
                    </Space>
                    <Space size={6}>
                      <Button
                        aria-label={resolved ? `已完成 ${item.label}` : `标记已完成 ${item.label}`}
                        size="small"
                        icon={<CheckCircleOutlined />}
                        loading={acting}
                        disabled={resolved}
                        onClick={() => onResolveLabel(item)}
                      >
                        已完成
                      </Button>
                      <Button
                        aria-label={`删除标注 ${item.label}`}
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                        loading={acting}
                        onClick={() => onDeleteLabel(item)}
                      />
                    </Space>
                  </Space>
                </div>
              );
            })}
          </Space>
        )}

        <Input.TextArea
          rows={5}
          value={comment}
          onChange={(event) => onCommentChange(event.target.value)}
          disabled={disabled}
          placeholder="记录判断依据、复现条件或后续处理建议"
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(168px, 1fr))', gap: 8 }}>
          <Button type="primary" icon={<SaveOutlined />} disabled={disabled} loading={saving} onClick={onSave}>
            保存标注
          </Button>
          <Button icon={<CopyOutlined />} disabled={disabled} onClick={onCopyDebug}>
            复制 debug JSON
          </Button>
          <Button icon={<DownloadOutlined />} disabled={disabled} loading={acting} onClick={onExportJsonl}>
            导出 JSONL
          </Button>
          <Button danger icon={<BugOutlined />} disabled={disabled} loading={acting} onClick={onMarkBadCase}>
            标记 bad case
          </Button>
          <Button icon={<ExperimentOutlined />} disabled={disabled} loading={acting} onClick={onCreateRegressionCase}>
            生成 regression case
          </Button>
          <Button icon={<BranchesOutlined />} disabled={disabled} onClick={handleTraceJump}>
            跳转 TraceMonitor
          </Button>
        </div>
      </Space>
    </Card>
  );
}
