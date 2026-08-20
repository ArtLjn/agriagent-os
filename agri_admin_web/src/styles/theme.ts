export const palette = {
  bg: '#0d1117',
  bgElevated: '#161b22',
  bgPanel: '#21262d',
  bgSoft: '#1c2128',
  border: '#30363d',
  borderSoft: 'rgba(139, 148, 158, 0.18)',
  text: '#e6edf3',
  textMuted: '#8b949e',
  textSubtle: '#6e7681',
  accent: '#58a6ff',
  accentStrong: '#1f6feb',
  success: '#3fb950',
  warning: '#d29922',
  danger: '#f85149',
  purple: '#bc8cff',
};

export const layout = {
  contentMaxWidth: 1480,
  radius: 8,
  radiusLg: 10,
  headerHeight: 58,
};

export const cardStyle = {
  background: palette.bgElevated,
  borderColor: palette.border,
  borderRadius: layout.radius,
};

export const panelStyle = {
  background: palette.bgPanel,
  border: `1px solid ${palette.border}`,
  borderRadius: layout.radius,
};

export const fieldLabelStyle = {
  color: palette.textMuted,
  fontSize: 12,
  marginBottom: 6,
};
