import { FileSearchOutlined, ReloadOutlined, CloseOutlined } from '@ant-design/icons';
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
const HEADER_BG = '#161b22';

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
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '48px 24px',
      textAlign: 'center',
    }}>
      <div style={{
        width: 56,
        height: 56,
        borderRadius: 16,
        background: 'rgba(88, 166, 255, 0.08)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 20,
      }}>
        <FileSearchOutlined style={{ fontSize: 24, color: ACCENT, opacity: 0.6 }} />
      </div>
      <div style={{ color: TEXT, fontSize: 15, fontWeight: 600, marginBottom: 8 }}>{title}</div>
      <div style={{ color: TEXT_DIM, fontSize: 13, lineHeight: 1.7, maxWidth: 340 }}>{description}</div>
    </div>
  );
}

export function LlmContextTriggerButton({
  hasSnapshot,
  loading,
  onClick,
}: {
  hasSnapshot: boolean;
  loading: boolean;
  onClick: () => void;
}) {
  const active = hasSnapshot;
  return (
    <Tooltip title="查看最终送入模型的 LLM Context" placement="top">
      <Button
        type={active ? 'primary' : 'default'}
        icon={<FileSearchOutlined />}
        loading={loading}
        onClick={onClick}
        className={active ? undefined : 'playground-toolbar__ghost'}
        style={{
          height: 32,
          borderRadius: 6,
          paddingInline: 12,
          fontSize: 13,
          background: active ? ACCENT : 'transparent',
          borderColor: active ? ACCENT : BORDER,
          color: active ? '#fff' : TEXT_DIM,
          fontWeight: 500,
        }}
      >
        LLM Context
      </Button>
    </Tooltip>
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
    <Drawer
      title="LLM Context 可观测"
      placement="right"
      width="min(860px, calc(100vw - 24px))"
      onClose={() => onOpenChange(false)}
      open={open}
      closable={false}
      styles={{
        body: { background: PANEL_BG, padding: 0 },
        header: { display: 'none' },
        mask: { background: 'rgba(0,0,0,0.4)' },
      }}
    >
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        {/* 自定义 Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 20px',
          background: HEADER_BG,
          borderBottom: `1px solid ${BORDER}`,
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: 'rgba(88, 166, 255, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}>
              <FileSearchOutlined style={{ fontSize: 15, color: ACCENT }} />
            </div>
            <div>
              <div style={{ color: TEXT, fontSize: 15, fontWeight: 600, lineHeight: 1.3 }}>
                LLM Context 可观测
              </div>
              <div style={{ color: TEXT_DIM, fontSize: 12, lineHeight: 1.3, marginTop: 2 }}>
                最终送入模型的上下文快照
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Tooltip title="刷新">
              <Button
                size="small"
                icon={<ReloadOutlined />}
                loading={loading}
                onClick={() => { void onRefresh(); }}
                style={{
                  height: 30,
                  borderRadius: 6,
                  fontSize: 12,
                  color: TEXT_DIM,
                }}
              >
                刷新
              </Button>
            </Tooltip>
            <Button
              type="text"
              size="small"
              icon={<CloseOutlined />}
              onClick={() => onOpenChange(false)}
              style={{
                color: TEXT_DIM,
                height: 30,
                width: 30,
                borderRadius: 6,
              }}
            />
          </div>
        </div>

        {/* 内容区域 */}
        <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
          {snapshot ? (
            <LlmContextVisualView snapshot={snapshot} />
          ) : (
            <EmptyContextState loading={loading} hasTimeline={hasTimeline} />
          )}
        </div>
      </div>
    </Drawer>
  );
}
