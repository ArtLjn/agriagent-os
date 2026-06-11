import { Card, Col, Descriptions, Empty, Row, Space, Spin, Tabs, Typography } from 'antd';
import type { CSSProperties } from 'react';

import type { DataFlywheelDetail } from '../../../api/dataFlywheel';
import { cardStyle, palette } from '../../../styles/theme';
import PendingLifecycleView from './PendingLifecycleView';
import ToolComparison from './ToolComparison';

interface SampleDetailPanelProps {
  detail: DataFlywheelDetail | null;
  loading: boolean;
}

function findMessage(detail: DataFlywheelDetail, role: string) {
  return detail.messages.find((message) => message.role === role)?.content || '';
}

function JsonBlock({ value }: { value: unknown }) {
  return <pre style={jsonBlockStyle}>{JSON.stringify(value ?? {}, null, 2)}</pre>;
}

export default function SampleDetailPanel({ detail, loading }: SampleDetailPanelProps) {
  if (loading) {
    return (
      <Card title="样本详情" style={cardStyle}>
        <Spin />
      </Card>
    );
  }

  if (!detail) {
    return (
      <Card title="样本详情" style={cardStyle}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选择左侧样本查看详情" />
      </Card>
    );
  }

  const userInput = findMessage(detail, 'user') || detail.sample.user_input_preview || '';
  const assistantReply = findMessage(detail, 'assistant') || detail.sample.assistant_reply_preview || '';

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Card title="样本详情" style={cardStyle} styles={{ body: { padding: 14 } }}>
        <Row gutter={[12, 12]}>
          <Col xs={24} lg={12}>
            <Section title="user input">
              <Typography.Paragraph style={paragraphStyle}>{userInput || '无用户输入'}</Typography.Paragraph>
            </Section>
          </Col>
          <Col xs={24} lg={12}>
            <Section title="assistant reply">
              <Typography.Paragraph style={paragraphStyle}>{assistantReply || '无助手回复'}</Typography.Paragraph>
            </Section>
          </Col>
        </Row>
      </Card>

      <Card title="调试上下文" style={cardStyle} styles={{ body: { padding: '4px 14px 14px' } }}>
        <Tabs
          items={[
            {
              key: 'tools',
              label: '工具对比',
              children: <ToolComparison selectedTools={detail.sample.selected_tools} actualTools={detail.sample.actual_tools} />,
            },
            {
              key: 'pending',
              label: 'pending lifecycle',
              children: <PendingLifecycleView items={detail.pending_lifecycle} />,
            },
            {
              key: 'router',
              label: 'router JSON',
              children: <JsonBlock value={detail.router_decision} />,
            },
            {
              key: 'tool-events',
              label: 'tool events',
              children: <JsonBlock value={detail.tool_events} />,
            },
            {
              key: 'debug',
              label: 'debug export',
              children: <JsonBlock value={detail.debug_export} />,
            },
          ]}
        />
      </Card>

      <Card title="样本元信息" style={cardStyle} styles={{ body: { padding: 14 } }}>
        <Descriptions
          size="small"
          column={2}
          styles={{
            label: { color: palette.textMuted },
            content: { color: palette.text },
          }}
        >
          <Descriptions.Item label="token_total">{detail.sample.token_total ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="latency_ms">{detail.sample.latency_ms ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="source event file">{detail.source.event_file ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="event seq">
            {detail.source.event_seq_start ?? '-'} - {detail.source.event_seq_end ?? '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </Space>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={sectionStyle}>
      <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>{title}</Typography.Text>
      <div style={{ marginTop: 8 }}>{children}</div>
    </div>
  );
}

const sectionStyle: CSSProperties = {
  minHeight: 168,
  background: palette.bg,
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  padding: 12,
};

const paragraphStyle: CSSProperties = {
  color: palette.text,
  margin: 0,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
};

const jsonBlockStyle: CSSProperties = {
  margin: 0,
  maxHeight: 360,
  overflow: 'auto',
  whiteSpace: 'pre-wrap',
  color: palette.textMuted,
  background: palette.bg,
  padding: 14,
};
