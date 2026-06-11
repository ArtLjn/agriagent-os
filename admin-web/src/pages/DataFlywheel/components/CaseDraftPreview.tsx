import { Modal, Typography } from 'antd';
import type { CSSProperties } from 'react';

import type { CaseDraft } from '../../../api/dataFlywheel';
import { palette } from '../../../styles/theme';

interface CaseDraftPreviewProps {
  draft: CaseDraft | null;
  open: boolean;
  onClose: () => void;
}

export default function CaseDraftPreview({ draft, open, onClose }: CaseDraftPreviewProps) {
  return (
    <Modal
      title="Case Draft"
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
          <Typography.Text style={{ color: palette.textMuted }}>
            {draft.draft_id} · {draft.target_type} · {draft.status}
          </Typography.Text>
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
