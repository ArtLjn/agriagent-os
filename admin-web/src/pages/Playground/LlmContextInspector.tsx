import { FileSearchOutlined } from '@ant-design/icons';
import { Button, Drawer, Tag, Tooltip } from 'antd';

import { palette } from '../../styles/theme';
import { formatTracePayload } from '../../utils/tracePayload';
import type { PlaygroundLlmContextSnapshot } from './traceMetrics';

const BORDER = palette.border;
const TEXT = palette.text;
const TEXT_DIM = palette.textMuted;
const ACCENT = palette.accent;
const PANEL_BG = '#0d1117';
const PRE_BG = '#161b22';

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
      backgroundColor: PRE_BG,
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

function EmptyContextState({
  loading,
  hasTimeline,
}: {
  loading: boolean;
  hasTimeline: boolean;
}) {
  const title = loading ? '等待本轮 trace' : '暂无 LLM 上下文快照';
  const description = hasTimeline
    ? '当前 request timeline 中还没有 final_llm_context 节点。'
    : '发送一轮消息并等待 trace 拉取完成后，这里会展示最终送入模型的上下文。';
  return (
    <div style={{
      border: `1px dashed ${BORDER}`,
      borderRadius: 8,
      color: TEXT_DIM,
      padding: 18,
      background: PRE_BG,
    }}>
      <div style={{ color: TEXT, fontSize: 14, fontWeight: 600, marginBottom: 8 }}>{title}</div>
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>{description}</div>
    </div>
  );
}

function ContextSnapshotDetail({ snapshot }: { snapshot: PlaygroundLlmContextSnapshot }) {
  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', marginBottom: 12 }}>
        <TraceMetricPill label="Prompt Token" value={formatMetricNumber(snapshot.promptTokens)} />
        <TraceMetricPill label="预算" value={formatMetricNumber(snapshot.maxTokens)} />
        <TraceMetricPill label="压缩动作" value={snapshot.actions.length > 0 ? snapshot.actions.join(', ') : '-'} />
        {snapshot.truncated && (
          <Tag color="warning" style={{ fontSize: 11, margin: 0 }}>已结构化截断</Tag>
        )}
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0, flex: '1 1 300px' }}>
          <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 6 }}>System Prompt</div>
          <TracePre maxHeight={260}>{snapshot.systemPrompt || '-'}</TracePre>
        </div>
        <div style={{ minWidth: 0, flex: '1 1 340px' }}>
          <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 6 }}>Messages（压缩后）</div>
          <TracePre maxHeight={260}>{formatTracePayload(snapshot.messages)}</TracePre>
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 6 }}>原始快照 JSON</div>
        <TracePre maxHeight={360}>{formatTracePayload(snapshot.raw)}</TracePre>
      </div>
    </>
  );
}

export function LlmContextInspector({
  snapshot,
  open,
  onOpenChange,
  loading,
  hasTimeline,
}: {
  snapshot: PlaygroundLlmContextSnapshot | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  loading: boolean;
  hasTimeline: boolean;
}) {
  const statusText = snapshot
    ? `messages ${snapshot.messages.length} · blocks ${snapshot.contextBlocks.join(', ') || '-'}`
    : loading
      ? '等待 trace'
      : '暂无快照';

  return (
    <>
      <Tooltip title="查看最终送入模型的 LLM Context" placement="left">
        <Button
          type="primary"
          icon={<FileSearchOutlined />}
          onClick={() => onOpenChange(true)}
          style={{
            position: 'absolute',
            right: 20,
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 12,
            height: 40,
            borderRadius: 20,
            boxShadow: '0 12px 28px rgba(0,0,0,0.32)',
            background: snapshot ? ACCENT : '#30363d',
            borderColor: snapshot ? ACCENT : '#30363d',
            color: TEXT,
          }}
        >
          LLM Context
        </Button>
      </Tooltip>
      <Drawer
        title="LLM 上下文快照"
        placement="right"
        width={720}
        onClose={() => onOpenChange(false)}
        open={open}
        styles={{
          body: { background: PANEL_BG, padding: 16 },
          header: { background: '#161b22', borderBottom: '1px solid #30363d', color: TEXT },
          mask: { background: 'rgba(0,0,0,0.45)' },
        }}
      >
        <div style={{ color: TEXT }}>
          <div style={{
            border: `1px solid ${BORDER}`,
            borderRadius: 8,
            background: PRE_BG,
            padding: 12,
            marginBottom: 14,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <Tag color={snapshot ? 'processing' : 'default'} style={{ margin: 0 }}>
                {snapshot ? 'final_llm_context' : 'waiting'}
              </Tag>
              <span style={{ color: TEXT_DIM, fontSize: 12 }}>{statusText}</span>
            </div>
          </div>
          {snapshot ? (
            <ContextSnapshotDetail snapshot={snapshot} />
          ) : (
            <EmptyContextState loading={loading} hasTimeline={hasTimeline} />
          )}
        </div>
      </Drawer>
    </>
  );
}
