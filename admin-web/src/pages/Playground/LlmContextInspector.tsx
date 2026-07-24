import { CaretDownOutlined, CaretUpOutlined, FileSearchOutlined } from '@ant-design/icons';
import { Tag } from 'antd';

import { palette } from '../../styles/theme';
import { formatTracePayload } from '../../utils/tracePayload';
import type { PlaygroundLlmContextSnapshot } from './traceMetrics';

const BORDER = palette.border;
const TEXT = palette.text;
const TEXT_DIM = palette.textMuted;
const ACCENT = palette.accent;

function formatMetricNumber(value: number | null): string {
  if (value === null) return '-';
  return value.toLocaleString('zh-CN');
}

function TraceMetricPill({ label, value }: { label: string; value: string }) {
  return (
    <span style={{
      color: TEXT_DIM,
      fontSize: 12,
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
    }}>
      {label}: <span style={{ color: TEXT, fontFamily: 'monospace' }}>{value}</span>
    </span>
  );
}

function TracePre({ children, maxHeight }: { children: string; maxHeight: number }) {
  return (
    <pre style={{
      backgroundColor: '#161b22',
      border: '1px solid #30363d',
      borderRadius: 6,
      color: TEXT,
      fontSize: 12,
      lineHeight: 1.6,
      margin: 0,
      maxHeight,
      overflow: 'auto',
      padding: 10,
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
    }}>
      {children}
    </pre>
  );
}

export function LlmContextInspector({
  snapshot,
  open,
  onToggle,
}: {
  snapshot: PlaygroundLlmContextSnapshot;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div style={{
      border: `1px solid ${BORDER}`,
      borderRadius: 8,
      background: '#0d1117',
      marginBottom: 10,
      overflow: 'hidden',
      flexShrink: 0,
    }}>
      <button
        type="button"
        onClick={onToggle}
        style={{
          width: '100%',
          border: 'none',
          background: 'transparent',
          color: TEXT,
          padding: '9px 12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <FileSearchOutlined style={{ color: ACCENT, flexShrink: 0 }} />
          <span style={{ fontSize: 13, fontWeight: 600, flexShrink: 0 }}>LLM 上下文快照</span>
          <span style={{ color: TEXT_DIM, fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            最终送入模型 · messages {snapshot.messages.length} · blocks {snapshot.contextBlocks.join(', ') || '-'}
          </span>
          {snapshot.truncated && (
            <Tag color="warning" style={{ fontSize: 11, margin: 0 }}>已结构化截断</Tag>
          )}
        </span>
        {open ? <CaretUpOutlined style={{ color: TEXT_DIM }} /> : <CaretDownOutlined style={{ color: TEXT_DIM }} />}
      </button>
      <div style={{
        maxHeight: open ? 360 : 0,
        opacity: open ? 1 : 0,
        overflow: 'hidden',
        transition: 'max-height 180ms ease, opacity 160ms ease',
      }}>
        <div className="surface-scroll" style={{
          maxHeight: 360,
          overflow: 'auto',
          borderTop: `1px solid ${BORDER}`,
          padding: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', marginBottom: 10 }}>
            <TraceMetricPill label="Prompt Token" value={formatMetricNumber(snapshot.promptTokens)} />
            <TraceMetricPill label="预算" value={formatMetricNumber(snapshot.maxTokens)} />
            <TraceMetricPill label="压缩动作" value={snapshot.actions.length > 0 ? snapshot.actions.join(', ') : '-'} />
          </div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ minWidth: 0, flex: '1 1 260px' }}>
              <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 6 }}>System Prompt</div>
              <TracePre maxHeight={210}>{snapshot.systemPrompt || '-'}</TracePre>
            </div>
            <div style={{ minWidth: 0, flex: '1 1 300px' }}>
              <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 6 }}>Messages（压缩后）</div>
              <TracePre maxHeight={210}>{formatTracePayload(snapshot.messages)}</TracePre>
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 6 }}>原始快照 JSON</div>
            <TracePre maxHeight={260}>{formatTracePayload(snapshot.raw)}</TracePre>
          </div>
        </div>
      </div>
    </div>
  );
}
