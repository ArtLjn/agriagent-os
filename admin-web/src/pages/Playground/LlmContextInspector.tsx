import { FileSearchOutlined, ReloadOutlined } from '@ant-design/icons';
import { Button, Drawer, Tooltip } from 'antd';

import { palette } from '../../styles/theme';
import { LlmContextVisualView } from './LlmContextVisualView';
import type { PlaygroundLlmContextSnapshot } from './traceMetrics';

const BORDER = palette.border;
const TEXT = palette.text;
const TEXT_DIM = palette.textMuted;
const PANEL_BG = '#0d1117';
const PRE_BG = '#161b22';
const ACCENT = palette.accent;

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

export function LlmContextInspector({
  snapshot,
  open,
  onOpenChange,
  loading,
  hasTimeline,
  onRefresh,
}: {
  snapshot: PlaygroundLlmContextSnapshot | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  loading: boolean;
  hasTimeline: boolean;
  requestId?: string;
  nodeCount: number;
  onRefresh: () => void | Promise<unknown>;
}) {
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
        title="LLM Context 可观测"
        placement="right"
        width="min(860px, calc(100vw - 24px))"
        onClose={() => onOpenChange(false)}
        open={open}
        extra={(
          <Button
            size="small"
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={() => {
              void onRefresh();
            }}
          >
            刷新
          </Button>
        )}
        styles={{
          body: { background: PANEL_BG, padding: 16 },
          header: { background: '#161b22', borderBottom: '1px solid #30363d', color: TEXT },
          mask: { background: 'rgba(0,0,0,0.45)' },
        }}
      >
        <div style={{ color: TEXT }}>
          {snapshot ? (
            <LlmContextVisualView snapshot={snapshot} />
          ) : (
            <EmptyContextState loading={loading} hasTimeline={hasTimeline} />
          )}
        </div>
      </Drawer>
    </>
  );
}
