import { Card, Col, Descriptions, Empty, Row, Space, Tag, Typography } from 'antd';
import type { CSSProperties } from 'react';

import type { DataFlywheelDetail } from '../../../api/dataFlywheel';
import { cardStyle, palette } from '../../../styles/theme';

interface ReviewEvidencePanelProps {
  detail: DataFlywheelDetail | null;
}

export default function ReviewEvidencePanel({ detail }: ReviewEvidencePanelProps) {
  if (!detail) {
    return (
      <Card title="审核证据" style={evidenceCardStyle} styles={{ body: { padding: 14 } }}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选择待审核样本查看聊天与工具证据" />
      </Card>
    );
  }

  const userInput = findMessage(detail, 'user') || detail.sample.user_input_preview || '';
  const assistantReply = findMessage(detail, 'assistant') || detail.sample.assistant_reply_preview || '';

  return (
    <Card
      title="审核证据"
      extra={
        <Typography.Text style={{ color: palette.textMuted }}>
          turn #{detail.sample.turn_id}
        </Typography.Text>
      }
      style={evidenceCardStyle}
      styles={{ body: { padding: 14 } }}
    >
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Row gutter={[10, 10]}>
          <Col xs={24} lg={12}>
            <EvidenceBlock title="用户输入" content={userInput || '无用户输入'} tone="user" />
          </Col>
          <Col xs={24} lg={12}>
            <EvidenceBlock title="助手回复" content={assistantReply || '无助手回复'} tone="assistant" />
          </Col>
        </Row>

        <div style={toolGridStyle}>
          <ToolList title="selected_tools" tools={detail.sample.selected_tools} color="blue" />
          <ToolList title="actual_tools" tools={detail.sample.actual_tools} color="purple" />
        </div>

        <Descriptions
          size="small"
          column={2}
          styles={{
            label: { color: palette.textMuted },
            content: { color: palette.text },
          }}
        >
          <Descriptions.Item label="pending">
            <Tag color={detail.pending_lifecycle.length > 0 ? 'blue' : 'default'}>
              {pendingSummary(detail.pending_lifecycle)}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="事件">
            <Tag color={eventLogStatusColor(detail.source.event_log_status)}>
              {eventLogStatusText(detail.source.event_log_status)}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="request">{detail.sample.request_id || '-'}</Descriptions.Item>
          <Descriptions.Item label="来源">{chatRecordSourceText(detail.source.chat_record_source)}</Descriptions.Item>
        </Descriptions>
      </Space>
    </Card>
  );
}

function EvidenceBlock({
  title,
  content,
  tone,
}: {
  title: string;
  content: string;
  tone: 'user' | 'assistant';
}) {
  return (
    <div style={{ ...evidenceBlockStyle, background: tone === 'assistant' ? 'rgba(88, 166, 255, 0.08)' : palette.bg }}>
      <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>{title}</Typography.Text>
      <Typography.Paragraph ellipsis={{ rows: 5, expandable: true, symbol: '展开' }} style={evidenceTextStyle}>
        {content}
      </Typography.Paragraph>
    </div>
  );
}

function ToolList({ title, tools, color }: { title: string; tools: string[]; color: string }) {
  return (
    <div style={toolListStyle}>
      <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>{title}</Typography.Text>
      <div style={{ marginTop: 8 }}>
        {tools.length > 0 ? (
          <Space wrap size={[6, 6]}>
            {tools.map((tool) => (
              <Tag key={tool} color={color} style={toolTagStyle} title={tool}>
                {tool}
              </Tag>
            ))}
          </Space>
        ) : (
          <Typography.Text style={{ color: palette.textSubtle }}>无工具</Typography.Text>
        )}
      </div>
    </div>
  );
}

function findMessage(detail: DataFlywheelDetail, role: string) {
  return detail.messages.find((message) => message.role === role)?.content || '';
}

function pendingSummary(items: Array<Record<string, unknown>>) {
  if (items.length === 0) return '无 pending 事件';
  const eventTypes = items.map((item) => String(item.event_type || item.stage || item.type || ''));
  if (eventTypes.some((type) => /cancel|reject/i.test(type))) return '已取消';
  if (eventTypes.some((type) => /confirm|commit|apply|accept/i.test(type))) return '已确认';
  return `${items.length} 个 pending 事件`;
}

function chatRecordSourceText(source?: string) {
  if (source === 'mysql_conversation_messages') return 'MySQL';
  return '未知';
}

function eventLogStatusText(status?: string) {
  if (status === 'available') return 'JSONL 可用';
  if (status === 'missing') return '事件缺失';
  if (status === 'unbound') return '未绑定';
  return '未知';
}

function eventLogStatusColor(status?: string) {
  if (status === 'available') return 'green';
  if (status === 'missing') return 'orange';
  if (status === 'unbound') return 'default';
  return 'default';
}

const evidenceCardStyle: CSSProperties = {
  ...cardStyle,
  flexShrink: 0,
};

const toolGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
  gap: 10,
};

const evidenceBlockStyle: CSSProperties = {
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  padding: '10px 12px',
  minHeight: 132,
};

const evidenceTextStyle: CSSProperties = {
  color: palette.text,
  margin: '6px 0 0',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
};

const toolListStyle: CSSProperties = {
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  background: palette.bg,
  padding: '10px 12px',
};

const toolTagStyle: CSSProperties = {
  maxWidth: 220,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};
