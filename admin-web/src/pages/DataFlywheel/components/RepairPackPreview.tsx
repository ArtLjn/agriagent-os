import { Button, Empty, Modal, Space, Tag, Typography } from 'antd';
import type { CSSProperties } from 'react';

import type { DataFlywheelRepairPack, RepairPackCase } from '../../../api/dataFlywheel';
import { palette } from '../../../styles/theme';
import { repairPackStatusMeta } from './repairPackStatusMeta';

interface RepairPackPreviewProps {
  pack: DataFlywheelRepairPack | null;
  open: boolean;
  acting: boolean;
  onClose: () => void;
  onResolve: () => void;
  onVerificationFailed: () => void;
  onOpenSample?: (sampleId: string) => void;
}

export default function RepairPackPreview({
  pack,
  open,
  acting,
  onClose,
  onResolve,
  onVerificationFailed,
  onOpenSample,
}: RepairPackPreviewProps) {
  const manifest = pack?.payload?.manifest ?? pack?.manifest ?? {};
  const readme = pack?.payload?.readme ?? '';
  const warnings = Array.isArray(manifest.warnings) ? manifest.warnings : [];
  const commands = Array.isArray(manifest.verification_commands)
    ? manifest.verification_commands
    : [];
  const statusMeta = pack ? repairPackStatusMeta(pack.status) : { label: '', color: 'default' };
  const cases = pack?.cases ?? pack?.payload?.cases_jsonl ?? [];

  return (
    <Modal
      title="Repair Pack"
      open={open}
      onCancel={onClose}
      width={880}
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
        body: { color: palette.text, maxHeight: '70vh', overflowY: 'auto' },
      }}
    >
      {pack && (
        <Space direction="vertical" size={14} style={{ width: '100%' }}>
          <Space size={8} wrap align="center">
            <Tag color="blue">{pack.fix_target}</Tag>
            <Tag color={statusMeta.color}>{statusMeta.label}</Tag>
            <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
              {pack.pack_id}
            </Typography.Text>
          </Space>

          <Section label="修复目标">
            <Typography.Text style={{ color: palette.text }}>
              {String(manifest.goal ?? '—')}
            </Typography.Text>
          </Section>

          {pack.labels.length > 0 && (
            <Section label="关联标签">
              <Space size={6} wrap>
                {pack.labels.map((label) => (
                  <Tag key={label} color="purple">
                    {label}
                  </Tag>
                ))}
              </Space>
            </Section>
          )}

          <Section label="关联样本">
            {pack.source_sample_ids.length === 0 ? (
              <Typography.Text style={{ color: palette.textMuted }}>—</Typography.Text>
            ) : (
              <Space size={6} wrap>
                {pack.source_sample_ids.map((sampleId) => (
                  <Tag
                    key={sampleId}
                    color="cyan"
                    style={{ cursor: onOpenSample ? 'pointer' : 'default' }}
                    onClick={() => onOpenSample?.(sampleId)}
                  >
                    {onOpenSample ? '🔗 ' : ''}
                    {sampleId}
                  </Tag>
                ))}
              </Space>
            )}
          </Section>

          <Section label={`失败案例（${cases.length}）`}>
            {cases.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="未加载到失败案例详情"
                style={{ margin: 0 }}
              />
            ) : (
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                {cases.map((caseItem, index) => (
                  <CaseCard
                    key={`${caseItem.sample_id ?? index}`}
                    caseItem={caseItem}
                    onOpenSample={onOpenSample}
                  />
                ))}
              </Space>
            )}
          </Section>

          {warnings.length > 0 && (
            <Section label="Warnings">
              <pre style={jsonBlockStyle}>{JSON.stringify(warnings, null, 2)}</pre>
            </Section>
          )}

          {commands.length > 0 && (
            <Section label="验证命令">
              <pre style={jsonBlockStyle}>{commands.join('\n')}</pre>
            </Section>
          )}

          {readme && (
            <Section label="README 预览">
              <pre style={textBlockStyle}>{readme}</pre>
            </Section>
          )}
        </Space>
      )}
    </Modal>
  );
}

interface CaseCardProps {
  caseItem: RepairPackCase;
  onOpenSample?: (sampleId: string) => void;
}

function CaseCard({ caseItem, onOpenSample }: CaseCardProps) {
  const labels = Array.isArray(caseItem.labels) ? caseItem.labels : [];
  const sampleId = caseItem.sample_id;
  return (
    <div style={caseCardStyle}>
      <Space direction="vertical" size={6} style={{ width: '100%' }}>
        <Space size={8} wrap align="center">
          <Typography.Text strong style={{ color: palette.text, fontSize: 13 }}>
            案例 #{sampleId ? sampleId.split(':').slice(-1)[0] : '?'}
          </Typography.Text>
          {labels.map((label) => (
            <Tag key={label} color="red">
              {label}
            </Tag>
          ))}
          {typeof caseItem.priority === 'number' && (
            <Tag color="orange">优先级 {caseItem.priority}</Tag>
          )}
          {caseItem.regression_ready && <Tag color="green">可回归</Tag>}
        </Space>

        {sampleId && (
          <Space size={4} wrap align="center">
            <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
              样本：
            </Typography.Text>
            {onOpenSample ? (
              <Typography.Link
                style={{ fontSize: 12 }}
                onClick={() => onOpenSample(sampleId)}
              >
                {sampleId}
              </Typography.Link>
            ) : (
              <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
                {sampleId}
              </Typography.Text>
            )}
          </Space>
        )}

        {caseItem.observed_failure && (
          <DetailBlock title="观测到的失败" content={caseItem.observed_failure} tone="danger" />
        )}
        {caseItem.evidence && (
          <DetailBlock title="具体证据" content={caseItem.evidence} tone="muted" />
        )}
        {caseItem.expected_behavior && (
          <DetailBlock title="期望行为" content={caseItem.expected_behavior} tone="success" />
        )}
        {caseItem.suggested_action && (
          <DetailBlock title="建议动作" content={caseItem.suggested_action} tone="muted" />
        )}
      </Space>
    </div>
  );
}

interface DetailBlockProps {
  title: string;
  content: string;
  tone: 'danger' | 'success' | 'muted';
}

function DetailBlock({ title, content, tone }: DetailBlockProps) {
  const color =
    tone === 'danger'
      ? palette.danger
      : tone === 'success'
        ? palette.success
        : palette.textMuted;
  return (
    <div>
      <Typography.Text style={{ color, fontSize: 12, fontWeight: 600 }}>{title}</Typography.Text>
      <Typography.Paragraph
        style={{ color: palette.text, fontSize: 13, marginTop: 2, marginBottom: 0 }}
      >
        {content}
      </Typography.Paragraph>
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Typography.Text style={{ color: palette.textMuted, fontSize: 12, display: 'block', marginBottom: 6 }}>
        {label}
      </Typography.Text>
      {children}
    </div>
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
  fontSize: 12,
};

const textBlockStyle: CSSProperties = {
  ...jsonBlockStyle,
  maxHeight: 240,
};

const caseCardStyle: CSSProperties = {
  width: '100%',
  padding: 12,
  background: palette.bg,
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 8,
};
