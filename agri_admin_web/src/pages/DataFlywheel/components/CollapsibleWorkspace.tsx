import type { CSSProperties } from 'react';
import { Button, Typography } from 'antd';
import {
  DownOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UpOutlined,
} from '@ant-design/icons';

import { palette } from '../../../styles/theme';

interface CollapsibleWorkspaceProps {
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  onLeftCollapsedChange: (collapsed: boolean) => void;
  onRightCollapsedChange: (collapsed: boolean) => void;
  left: React.ReactNode;
  main: React.ReactNode;
  right: React.ReactNode;
}

export default function CollapsibleWorkspace({
  leftCollapsed,
  rightCollapsed,
  onLeftCollapsedChange,
  onRightCollapsedChange,
  left,
  main,
  right,
}: CollapsibleWorkspaceProps) {
  return (
    <div
      data-testid="data-flywheel-workspace"
      data-left-collapsed={leftCollapsed}
      data-right-collapsed={rightCollapsed}
      style={workspaceStyle(leftCollapsed)}
    >
      <section style={topPanelStyle}>
        {leftCollapsed ? (
          <CollapsedBar
            label="归档"
            buttonLabel="展开顶部归档区"
            onToggle={() => onLeftCollapsedChange(false)}
          />
        ) : (
          <PanelShell
            title="用户 / 会话归档"
            buttonLabel="收起顶部归档区"
            onToggle={() => onLeftCollapsedChange(true)}
            icon={<UpOutlined />}
          >
            {left}
          </PanelShell>
        )}
      </section>

      <div style={contentGridStyle(rightCollapsed)}>
        <main style={mainPanelStyle}>{main}</main>

        <aside style={sidePanelStyle}>
          {rightCollapsed ? (
            <CollapsedRail
              label="详情"
              buttonLabel="展开详情区"
              onToggle={() => onRightCollapsedChange(false)}
            />
          ) : (
            <PanelShell
              title="样本详情 / 标注"
              buttonLabel="收起详情区"
              onToggle={() => onRightCollapsedChange(true)}
              icon={<MenuUnfoldOutlined />}
              headerSize="comfortable"
            >
              {right}
            </PanelShell>
          )}
        </aside>
      </div>
    </div>
  );
}

function PanelShell({
  title,
  buttonLabel,
  icon,
  onToggle,
  headerSize = 'compact',
  children,
}: {
  title: string;
  buttonLabel: string;
  icon: React.ReactNode;
  onToggle: () => void;
  headerSize?: 'compact' | 'comfortable';
  children: React.ReactNode;
}) {
  return (
    <div style={panelShellStyle(headerSize)}>
      <div style={panelHeaderStyle(headerSize)}>
        <Typography.Text strong style={{ color: palette.text }}>
          {title}
        </Typography.Text>
        <Button aria-label={buttonLabel} size="small" icon={icon} onClick={onToggle} />
      </div>
      <div style={panelBodyStyle(headerSize)}>{children}</div>
    </div>
  );
}

function CollapsedBar({
  label,
  buttonLabel,
  onToggle,
}: {
  label: string;
  buttonLabel: string;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={buttonLabel}
      onClick={onToggle}
      style={collapsedBarStyle}
    >
      <DownOutlined />
      <span>{label}</span>
    </button>
  );
}

function CollapsedRail({
  label,
  buttonLabel,
  onToggle,
}: {
  label: string;
  buttonLabel: string;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={buttonLabel}
      onClick={onToggle}
      style={collapsedRailStyle}
    >
      <MenuFoldOutlined />
      <span style={collapsedRailTextStyle}>{label}</span>
    </button>
  );
}

function workspaceStyle(leftCollapsed: boolean): CSSProperties {
  return {
    display: 'grid',
    gridTemplateRows: `${leftCollapsed ? '42px' : 'max-content'} minmax(0, 1fr)`,
    gap: 14,
    alignItems: 'stretch',
    height: 'auto',
    minHeight: 0,
    overflow: 'visible',
  };
}

function contentGridStyle(rightCollapsed: boolean): CSSProperties {
  return {
    display: 'grid',
    gridTemplateColumns: `minmax(520px, 1fr) ${rightCollapsed ? '48px' : 'minmax(360px, 44%)'}`,
    gap: 14,
    height: 700,
    minHeight: 700,
    overflow: 'hidden',
  };
}

const topPanelStyle: CSSProperties = {
  minWidth: 0,
  minHeight: 0,
  overflow: 'visible',
};

const sidePanelStyle: CSSProperties = {
  minWidth: 0,
  minHeight: 0,
  overflow: 'hidden',
};

const mainPanelStyle: CSSProperties = {
  minWidth: 0,
  minHeight: 0,
  overflow: 'hidden',
};

function panelShellStyle(size: 'compact' | 'comfortable'): CSSProperties {
  return {
    display: 'flex',
    flexDirection: 'column',
    gap: size === 'comfortable' ? 0 : 10,
    height: '100%',
    minHeight: 0,
    ...(size === 'comfortable'
      ? {
          background: palette.bgElevated,
          border: `1px solid ${palette.border}`,
          borderRadius: 8,
          overflow: 'hidden',
        }
      : {}),
  };
}

function panelHeaderStyle(size: 'compact' | 'comfortable'): CSSProperties {
  return {
    minHeight: size === 'comfortable' ? 40 : 32,
    padding: size === 'comfortable' ? '0 16px' : undefined,
    borderBottom: size === 'comfortable' ? `1px solid ${palette.border}` : undefined,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    flexShrink: 0,
  };
}

function panelBodyStyle(size: 'compact' | 'comfortable'): CSSProperties {
  return {
    minHeight: 0,
    flex: 1,
    overflow: 'auto',
    scrollbarGutter: 'stable',
    background: 'transparent',
    padding: size === 'comfortable' ? 12 : undefined,
  };
}

const collapsedBarStyle: CSSProperties = {
  width: '100%',
  height: '100%',
  border: `1px solid ${palette.border}`,
  borderRadius: 8,
  background: palette.bgElevated,
  color: palette.textMuted,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 8,
};

const collapsedRailStyle: CSSProperties = {
  width: '100%',
  minHeight: 180,
  border: `1px solid ${palette.border}`,
  borderRadius: 8,
  background: palette.bgElevated,
  color: palette.textMuted,
  cursor: 'pointer',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 10,
};

const collapsedRailTextStyle: CSSProperties = {
  writingMode: 'vertical-rl',
  letterSpacing: 0,
};
