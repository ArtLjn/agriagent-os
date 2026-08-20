import type { CSSProperties, ReactNode } from 'react';
import { Card, Empty, Spin } from 'antd';
import { palette, cardStyle } from '../styles/theme';

interface PageShellProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}

interface ToolbarProps {
  left?: ReactNode;
  right?: ReactNode;
  style?: CSSProperties;
}

interface MetricCardProps {
  children: ReactNode;
  accent?: string;
}

interface StateBlockProps {
  loading?: boolean;
  empty?: boolean;
  emptyText?: string;
  children: ReactNode;
}

export function PageShell({ title, description, actions, children }: PageShellProps) {
  return (
    <section className="page-shell">
      <header className="page-shell__header">
        <div>
          <h1 className="page-shell__title">{title}</h1>
          {description && <div className="page-shell__description">{description}</div>}
        </div>
        {actions && <div>{actions}</div>}
      </header>
      {children}
    </section>
  );
}

export function Toolbar({ left, right, style }: ToolbarProps) {
  return (
    <div className="toolbar-panel" style={style}>
      <div className="toolbar-panel__left">{left}</div>
      {right && <div className="toolbar-panel__right">{right}</div>}
    </div>
  );
}

export function MetricCard({ children, accent = palette.accent }: MetricCardProps) {
  return (
    <Card
      className="metric-card"
      style={{ ...cardStyle, borderTop: `2px solid ${accent}` }}
      styles={{ body: { padding: 16 } }}
    >
      {children}
    </Card>
  );
}

export function StateBlock({ loading, empty, emptyText = '暂无数据', children }: StateBlockProps) {
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 56 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (empty) {
    return (
      <div style={{ padding: 48 }}>
        <Empty description={emptyText} />
      </div>
    );
  }

  return <>{children}</>;
}
