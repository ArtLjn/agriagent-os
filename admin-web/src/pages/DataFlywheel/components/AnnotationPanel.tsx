import { Button, Card, Input, Radio, Space, Typography, message } from 'antd';
import {
  BranchesOutlined,
  BugOutlined,
  CopyOutlined,
  DownloadOutlined,
  ExperimentOutlined,
  SaveOutlined,
} from '@ant-design/icons';

import type { DataFlywheelLabel, DataFlywheelSample } from '../../../api/dataFlywheel';
import { cardStyle, palette } from '../../../styles/theme';

interface AnnotationPanelProps {
  selectedSample: DataFlywheelSample | null;
  label: DataFlywheelLabel;
  comment: string;
  saving: boolean;
  acting: boolean;
  onLabelChange: (label: DataFlywheelLabel) => void;
  onCommentChange: (comment: string) => void;
  onSave: () => void;
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
  { label: '工资缺失', value: 'missing_wage' },
  { label: '禁用工人', value: 'disabled_worker_used' },
  { label: '需要回归', value: 'needs_regression' },
  { label: '暂不处理', value: 'not_actionable' },
];

export default function AnnotationPanel({
  selectedSample,
  label,
  comment,
  saving,
  acting,
  onLabelChange,
  onCommentChange,
  onSave,
  onCopyDebug,
  onExportJsonl,
  onMarkBadCase,
  onCreateRegressionCase,
}: AnnotationPanelProps) {
  const disabled = !selectedSample;

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
        <div>
          <Typography.Text style={{ color: palette.textMuted }}>质量标签</Typography.Text>
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
