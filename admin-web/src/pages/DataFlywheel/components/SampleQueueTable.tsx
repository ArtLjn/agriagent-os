import { Table, Tag, Typography } from 'antd';
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

export default function SampleQueueTable({ samples, loading, selectedSampleId, onSelect }: SampleQueueTableProps) {
  const columns: ColumnsType<DataFlywheelSample> = [
    {
      title: '标签',
      dataIndex: 'annotation_status',
      width: 128,
      render: (status: string, record) => (
        <div>
          <Tag color={labelColor(status)}>{status}</Tag>
          {record.quality_labels.slice(0, 1).map((label) => (
            <Tag key={label} color="blue" style={{ marginTop: 4 }}>
              {label}
            </Tag>
          ))}
        </div>
      ),
    },
    {
      title: 'session_id',
      dataIndex: 'session_id',
      ellipsis: true,
      width: 160,
      render: (value: string | null) => value || <Typography.Text type="secondary">-</Typography.Text>,
    },
    { title: 'turn_id', dataIndex: 'turn_id', width: 80 },
    {
      title: 'request_id',
      dataIndex: 'request_id',
      ellipsis: true,
      width: 160,
      render: (value: string | null) => value || <Typography.Text type="secondary">-</Typography.Text>,
    },
    {
      title: 'user_input_preview',
      dataIndex: 'user_input_preview',
      ellipsis: true,
      render: (value: string | null) => value || <Typography.Text type="secondary">无输入摘要</Typography.Text>,
    },
    {
      title: '工具',
      width: 112,
      render: (_, record) => `${record.selected_tools.length}/${record.actual_tools.length}`,
    },
    {
      title: 'token / latency',
      width: 150,
      render: (_, record) => (
        <Typography.Text style={{ color: palette.text }}>
          <span>{record.token_total ?? '-'} tokens</span>
          <span style={{ color: palette.textMuted }}> / {record.latency_ms ?? '-'} ms</span>
        </Typography.Text>
      ),
    },
    { title: 'source_type', dataIndex: 'source_type', width: 130, ellipsis: true },
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
      scroll={{ x: 1120 }}
    />
  );
}
