import type { CSSProperties } from 'react';
import { Button, Typography } from 'antd';
import {
  LeftOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RightOutlined,
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
      style={workspaceStyle(leftCollapsed, rightCollapsed)}
    >
      <aside style={sidePanelStyle}>
        {leftCollapsed ? (
          <CollapsedRail
            label="归档"
            buttonLabel="展开归档区"
            onToggle={() => onLeftCollapsedChange(false)}
            align="left"
          />
        ) : (
          <PanelShell
            title="用户 / 会话归档"
            buttonLabel="收起归档区"
            onToggle={() => onLeftCollapsedChange(true)}
            icon={<MenuFoldOutlined />}
          >
            {left}
          </PanelShell>
        )}
      </aside>

      <main style={mainPanelStyle}>{main}</main>

      <aside style={sidePanelStyle}>
        {rightCollapsed ? (
          <CollapsedRail
            label="详情"
            buttonLabel="展开详情区"
            onToggle={() => onRightCollapsedChange(false)}
            align="right"
          />
        ) : (
          <PanelShell
            title="样本详情 / 标注"
            buttonLabel="收起详情区"
            onToggle={() => onRightCollapsedChange(true)}
            icon={<MenuUnfoldOutlined />}
          >
            {right}
          </PanelShell>
        )}
      </aside>
    </div>
  );
}

function PanelShell({
  title,
  buttonLabel,
  icon,
  onToggle,
  children,
}: {
  title: string;
  buttonLabel: string;
  icon: React.ReactNode;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div style={panelShellStyle}>
      <div style={panelHeaderStyle}>
        <Typography.Text strong style={{ color: palette.text }}>
          {title}
        </Typography.Text>
        <Button aria-label={buttonLabel} size="small" icon={icon} onClick={onToggle} />
      </div>
      {children}
    </div>
  );
}

function CollapsedRail({
  label,
  buttonLabel,
  align,
  onToggle,
}: {
  label: string;
  buttonLabel: string;
  align: 'left' | 'right';
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={buttonLabel}
      onClick={onToggle}
      style={collapsedRailStyle}
    >
      {align === 'left' ? <RightOutlined /> : <LeftOutlined />}
      <span style={collapsedRailTextStyle}>{label}</span>
    </button>
  );
}

function workspaceStyle(leftCollapsed: boolean, rightCollapsed: boolean): CSSProperties {
  return {
    display: 'grid',
    gridTemplateColumns: `${leftCollapsed ? '52px' : '300px'} minmax(0, 1fr) ${rightCollapsed ? '52px' : 'minmax(380px, 520px)'}`,
    gap: 14,
    alignItems: 'start',
  };
}

const sidePanelStyle: CSSProperties = {
  minWidth: 0,
};

const mainPanelStyle: CSSProperties = {
  minWidth: 0,
};

const panelShellStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 10,
};

const panelHeaderStyle: CSSProperties = {
  minHeight: 36,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
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
