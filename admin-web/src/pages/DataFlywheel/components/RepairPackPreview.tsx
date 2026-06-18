import { Button, Modal, Space, Tag, Typography } from 'antd';
import type { CSSProperties } from 'react';

import type { DataFlywheelRepairPack } from '../../../api/dataFlywheel';
import { palette } from '../../../styles/theme';

interface RepairPackPreviewProps {
  pack: DataFlywheelRepairPack | null;
  open: boolean;
  acting: boolean;
  onClose: () => void;
  onResolve: () => void;
  onVerificationFailed: () => void;
}

export default function RepairPackPreview({
  pack,
  open,
  acting,
  onClose,
  onResolve,
  onVerificationFailed,
}: RepairPackPreviewProps) {
  const manifest = pack?.payload?.manifest ?? pack?.manifest ?? {};
  const readme = pack?.payload?.readme ?? '';
  const warnings = Array.isArray(manifest.warnings) ? manifest.warnings : [];
  const commands = Array.isArray(manifest.verification_commands)
    ? manifest.verification_commands
    : [];

  return (
    <Modal
      title="Repair Pack"
      open={open}
      onCancel={onClose}
      width={820}
      footer={[
        <Button key="failed" loading={acting} onClick={onVerificationFailed}>
          记录验证失败
        </Button>,
        <Button key="resolve" type="primary" loading={acting} onClick={onResolve}>
          标记已修复
        </Button>,
      ]}
      styles={{
        content: { background: palette.bgElevated, border: `1px solid ${palette.border}` },
        header: { background: palette.bgElevated },
        body: { color: palette.text },
      }}
    >
      {pack && (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Space size={8} wrap>
            <Tag color="blue">{pack.fix_target}</Tag>
            <Tag>{pack.status}</Tag>
            <Typography.Text style={{ color: palette.textMuted }}>
              {pack.pack_id}
            </Typography.Text>
          </Space>

          <Typography.Text style={{ color: palette.text }}>
            {String(manifest.goal ?? '')}
          </Typography.Text>

          {warnings.length > 0 && (
            <Space direction="vertical" size={4}>
              <Typography.Text style={{ color: palette.warning }}>Warnings</Typography.Text>
              <pre style={jsonBlockStyle}>{JSON.stringify(warnings, null, 2)}</pre>
            </Space>
          )}

          <Space direction="vertical" size={4}>
            <Typography.Text style={{ color: palette.textMuted }}>验证命令</Typography.Text>
            <pre style={jsonBlockStyle}>{commands.join('\n')}</pre>
          </Space>

          <Space direction="vertical" size={4}>
            <Typography.Text style={{ color: palette.textMuted }}>README 预览</Typography.Text>
            <pre style={textBlockStyle}>{readme}</pre>
          </Space>
        </Space>
      )}
    </Modal>
  );
}

const jsonBlockStyle: CSSProperties = {
  margin: 0,
  maxHeight: 160,
  overflow: 'auto',
  whiteSpace: 'pre-wrap',
  color: palette.text,
  background: palette.bg,
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  padding: 10,
};

const textBlockStyle: CSSProperties = {
  ...jsonBlockStyle,
  maxHeight: 300,
};
