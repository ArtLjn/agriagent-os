import { Card, Col, Descriptions, Empty, Row, Space, Spin, Tabs, Tag, Typography } from 'antd';
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
      {detail.issue_candidates.length > 0 && (
        <Card title="问题定位" style={cardStyle} styles={{ body: { padding: 14 } }}>
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            {detail.issue_candidates.map((issue) => (
              <div key={`${issue.type}-${issue.evidence}`} style={issueStyle}>
                <Space size={8} wrap>
                  <Tag color={issue.severity === 'critical' ? 'red' : 'orange'}>{issueName(issue.type)}</Tag>
                  <Tag color="blue">建议：{issue.suggested_label}</Tag>
                </Space>
                <Typography.Text style={{ display: 'block', color: palette.text, marginTop: 8 }}>
                  {issue.reason}
                </Typography.Text>
                <Typography.Text style={{ display: 'block', color: palette.textMuted, marginTop: 4 }}>
                  证据：{issue.evidence || '-'}
                </Typography.Text>
              </div>
            ))}
          </Space>
        </Card>
      )}

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

function issueName(type: string) {
  const names: Record<string, string> = {
    hallucinated_execution: '幻觉执行',
    unsafe_write_on_question: '问句触发写入',
    pending_missed: 'pending 漏拦截',
    tool_error_ignored: '工具错误未处理',
    sensitive_info_leak: '参数/提示泄露',
    off_topic: '答非所问',
  };
  return names[type] ?? type;
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

const issueStyle: CSSProperties = {
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  background: palette.bg,
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
