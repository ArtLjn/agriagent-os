export const palette = {
  bg: 'var(--app-bg)',
  bgElevated: 'var(--app-surface)',
  bgPanel: 'var(--app-surface-strong)',
  bgSoft: 'var(--app-fill)',
  bgSoftStrong: 'var(--app-fill-strong)',
  codeBg: 'var(--app-code-bg)',
  border: 'var(--app-border)',
  borderSoft: 'var(--app-border-soft)',
  text: 'var(--app-text)',
  textMuted: 'var(--app-secondary)',
  textSubtle: 'var(--app-tertiary)',
  accent: 'var(--app-accent)',
  accentStrong: 'var(--app-accent-strong)',
  accentFill: 'var(--app-accent-fill)',
  accentSoft: 'var(--app-accent-soft)',
  success: 'var(--app-green)',
  warning: 'var(--app-orange)',
  danger: 'var(--app-red)',
  purple: 'var(--app-purple)',
  glow: 'var(--app-glow)',
  glowStrong: 'var(--app-glow-strong)',
};

export const layout = {
  contentMaxWidth: 1440,
  radius: 8,
  radiusLg: 8,
  headerHeight: 56,
};

const glassBlur = 'none';

export const cardStyle = {
  background: palette.bgElevated,
  borderColor: palette.borderSoft,
  borderRadius: layout.radiusLg,
  backdropFilter: glassBlur,
  WebkitBackdropFilter: glassBlur,
  boxShadow: 'none',
};

export const panelStyle = {
  background: palette.bgPanel,
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: layout.radiusLg,
  backdropFilter: glassBlur,
  WebkitBackdropFilter: glassBlur,
  boxShadow: 'none',
};

export const fieldLabelStyle = {
  color: palette.textMuted,
  fontSize: 12,
  marginBottom: 6,
};
