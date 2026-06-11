import { Empty, Space, Tag, Typography } from 'antd';

import { palette } from '../../../styles/theme';

interface ToolComparisonProps {
  selectedTools: string[];
  actualTools: string[];
}

function ToolList({ title, tools, color }: { title: string; tools: string[]; color: string }) {
  return (
    <div>
      <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>{title}</Typography.Text>
      <div style={{ marginTop: 8 }}>
        {tools.length > 0 ? (
          <Space wrap size={[6, 6]}>
            {tools.map((tool) => (
              <Tag key={tool} color={color} style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {tool}
              </Tag>
            ))}
          </Space>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无工具" />
        )}
      </div>
    </div>
  );
}

export default function ToolComparison({ selectedTools, actualTools }: ToolComparisonProps) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
      <ToolList title="selected_tools" tools={selectedTools} color="blue" />
      <ToolList title="actual_tools" tools={actualTools} color="purple" />
    </div>
  );
}
