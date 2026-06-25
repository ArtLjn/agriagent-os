import { Modal, Space, Tag, Typography } from 'antd';
import type { CSSProperties } from 'react';

import type { CaseDraft } from '../../../api/dataFlywheel';
import { palette } from '../../../styles/theme';
import { reviewStatusText, targetTypeText } from './reviewLabels';

interface CaseDraftPreviewProps {
  draft: CaseDraft | null;
  open: boolean;
  onClose: () => void;
}

export default function CaseDraftPreview({ draft, open, onClose }: CaseDraftPreviewProps) {
  return (
    <Modal
      title="回归草稿"
      open={open}
      onCancel={onClose}
      footer={null}
      width={760}
      styles={{
        content: { background: palette.bgElevated, border: `1px solid ${palette.border}` },
        header: { background: palette.bgElevated },
        body: { color: palette.text },
      }}
    >
      {draft && (
        <div>
          <Space size={8} wrap>
            <Typography.Text style={{ color: palette.textMuted }}>{draft.draft_id}</Typography.Text>
            <Tag color="blue">{targetTypeText(draft.target_type)}</Tag>
            <Tag>{reviewStatusText(draft.status)}</Tag>
          </Space>
          <pre style={jsonBlockStyle}>{JSON.stringify({ case_json: draft.case_json }, null, 2)}</pre>
        </div>
      )}
    </Modal>
  );
}

const jsonBlockStyle: CSSProperties = {
  marginTop: 12,
  maxHeight: 520,
  overflow: 'auto',
  whiteSpace: 'pre-wrap',
  color: palette.text,
  background: palette.bg,
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  padding: 12,
};
