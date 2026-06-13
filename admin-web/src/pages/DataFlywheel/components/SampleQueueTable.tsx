import { Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import type { DataFlywheelSample } from '../../../api/dataFlywheel';
import { palette } from '../../../styles/theme';

interface SampleQueueTableProps {
  samples: DataFlywheelSample[];
  loading: boolean;
  selectedSampleId?: string;
  onSelect: (sample: DataFlywheelSample) => void;
}

function labelColor(status: string) {
  if (status === 'labeled') return 'success';
  if (status === 'unlabeled') return 'warning';
  return 'default';
}

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

const issueText: Record<string, string> = {
  hallucinated_execution: '幻觉执行',
  unsafe_write_on_question: '问句触发写入',
  pending_missed: 'pending 漏拦截',
  tool_error_ignored: '工具错误未处理',
  sensitive_info_leak: '参数/提示泄露',
  off_topic: '答非所问',
};

export default function SampleQueueTable({ samples, loading, selectedSampleId, onSelect }: SampleQueueTableProps) {
  const columns: ColumnsType<DataFlywheelSample> = [
    {
      title: '状态',
      dataIndex: 'annotation_status',
      width: 106,
      render: (status: string, record) => (
        <div>
          <Tag color={labelColor(status)}>{status}</Tag>
          {record.quality_labels.slice(0, 1).map((label) => (
            <Tag key={label} color="blue" style={{ marginTop: 4 }}>
              {labelText[label] ?? label}
            </Tag>
          ))}
          {record.issue_candidates.slice(0, 1).map((issue) => (
            <Tag key={issue.type} color={issue.severity === 'critical' ? 'red' : 'orange'} style={{ marginTop: 4 }}>
              规则：{issueText[issue.type] ?? issue.type}
            </Tag>
          ))}
        </div>
      ),
    },
    {
      title: 'turn',
      dataIndex: 'turn_id',
      width: 72,
      render: (value: number) => <Typography.Text style={{ color: palette.text }}>#{value}</Typography.Text>,
    },
    {
      title: '输入与链路',
      dataIndex: 'user_input_preview',
      render: (value: string | null, record) => (
        <Space direction="vertical" size={2} style={{ width: '100%' }}>
          <Typography.Text ellipsis style={{ color: palette.text, maxWidth: 330 }}>
            {value || '无输入摘要'}
          </Typography.Text>
          <Typography.Text ellipsis style={{ color: palette.textMuted, fontSize: 12, maxWidth: 330 }}>
            {record.request_id || record.session_id || '-'}
          </Typography.Text>
          {record.issue_candidates[0] && (
            <Typography.Text ellipsis style={{ color: palette.warning, fontSize: 12, maxWidth: 330 }}>
              规则候选：{record.issue_candidates[0].reason}
            </Typography.Text>
          )}
          {record.event_log_status === 'missing' && (
            <Typography.Text ellipsis style={{ color: palette.warning, fontSize: 12, maxWidth: 330 }}>
              事件文件缺失，可同步重建
            </Typography.Text>
          )}
        </Space>
      ),
    },
    {
      title: '工具',
      width: 84,
      render: (_, record) => (
        <Typography.Text style={{ color: palette.text }}>
          {record.selected_tools.length}/{record.actual_tools.length}
        </Typography.Text>
      ),
    },
    {
      title: '成本',
      width: 132,
      render: (_, record) => (
        <Space direction="vertical" size={2}>
          <Typography.Text style={{ color: palette.text }}>{record.token_total ?? '-'} tokens</Typography.Text>
          <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>{record.latency_ms ?? '-'} ms</Typography.Text>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ height: '100%', minHeight: 0 }}>
      <Table
        rowKey="sample_id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={samples}
        pagination={false}
        sticky
        onRow={(record) => ({
          'data-testid': `sample-row-${record.sample_id}`,
          onClick: () => onSelect(record),
          style: {
            cursor: 'pointer',
            background: record.sample_id === selectedSampleId ? 'rgba(88, 166, 255, 0.12)' : undefined,
          },
        })}
        scroll={{ x: 680, y: 'calc(100vh - 312px)' }}
      />
    </div>
  );
}
