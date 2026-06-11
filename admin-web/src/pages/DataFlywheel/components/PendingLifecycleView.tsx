import { Empty, Timeline, Typography } from 'antd';
import type { CSSProperties } from 'react';

import { palette } from '../../../styles/theme';

interface PendingLifecycleViewProps {
  items: Array<Record<string, unknown>>;
}

function getStage(item: Record<string, unknown>) {
  return String(item.stage ?? item.event ?? item.type ?? 'pending.event');
}

function getTime(item: Record<string, unknown>) {
  return String(item.at ?? item.created_at ?? item.timestamp ?? '');
}

function jsonPreview(item: Record<string, unknown>) {
  return JSON.stringify(item.payload ?? item, null, 2);
}

export default function PendingLifecycleView({ items }: PendingLifecycleViewProps) {
  if (items.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无 pending 生命周期事件" />;
  }

  return (
    <Timeline
      style={{ marginTop: 4 }}
      items={items.map((item, index) => ({
        key: `${getStage(item)}-${index}`,
        color: index === items.length - 1 ? palette.accent : palette.textMuted,
        children: (
          <div>
            <Typography.Text style={{ color: palette.text }}>{getStage(item)}</Typography.Text>
            {getTime(item) && (
              <Typography.Text style={{ color: palette.textMuted, marginLeft: 8, fontSize: 12 }}>
                {getTime(item)}
              </Typography.Text>
            )}
            <pre style={jsonBlockStyle}>{jsonPreview(item)}</pre>
          </div>
        ),
      }))}
    />
  );
}

const jsonBlockStyle: CSSProperties = {
  margin: '8px 0 0',
  maxHeight: 160,
  overflow: 'auto',
  whiteSpace: 'pre-wrap',
  color: palette.textMuted,
  background: palette.bg,
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  padding: 10,
};
