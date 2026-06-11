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
  missing_wage: '工资缺失',
  disabled_worker_used: '禁用工人',
  needs_regression: '需要回归',
  not_actionable: '暂不处理',
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
    <Table
      rowKey="sample_id"
      size="small"
      loading={loading}
      columns={columns}
      dataSource={samples}
      pagination={false}
      onRow={(record) => ({
        'data-testid': `sample-row-${record.sample_id}`,
        onClick: () => onSelect(record),
        style: {
          cursor: 'pointer',
          background: record.sample_id === selectedSampleId ? 'rgba(88, 166, 255, 0.12)' : undefined,
        },
      })}
      scroll={{ x: 720 }}
    />
  );
}
