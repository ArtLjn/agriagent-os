export const colors = {
  // Primary - 深青绿，比纯绿更有质感
  primary: '#0D7377',
  primaryLight: '#14A085',
  primaryDark: '#095C5F',
  primaryMuted: 'rgba(13, 115, 119, 0.08)',

  // Accent - 琥珀金，用于强调和收入
  accent: '#D4A843',
  accentLight: '#F0D78C',
  accentMuted: 'rgba(212, 168, 67, 0.08)',

  // Semantic
  success: '#2D9E5F',
  successLight: '#E8F5EE',
  warning: '#E8923C',
  warningLight: '#FDF3E7',
  danger: '#DC4C4C',
  dangerLight: '#FDEBEB',
  info: '#3B82C4',
  infoLight: '#EBF3FB',

  // Background layers
  background: '#F8F9FB',
  surface: '#FFFFFF',
  surfaceElevated: '#FFFFFF',
  surfaceMuted: '#F1F3F5',

  // Text
  text: '#1A1D23',
  textSecondary: '#6B7280',
  textTertiary: '#9CA3AF',
  textInverse: '#FFFFFF',

  // Border & Divider
  border: '#E5E7EB',
  borderLight: '#F3F4F6',
  divider: 'rgba(0, 0, 0, 0.06)',

  // Shadow
  shadow: '#000000',

  // Header - 深色现代感
  headerBg: '#0F172A',
  headerText: '#FFFFFF',

  // Tab
  tabBg: '#FFFFFF',
  tabActive: '#0D7377',
  tabInactive: '#9CA3AF',

  // Overlay
  overlay: 'rgba(0, 0, 0, 0.4)',
  scrim: 'rgba(15, 23, 42, 0.6)',

  disabled: '#D1D5DB',
  disabledBg: '#F3F4F6',
} as const;

export const gradients = {
  primary: ['#0D7377', '#14A085'] as const,
  header: ['#0F172A', '#1E293B'] as const,
  card: ['#FFFFFF', '#FAFBFC'] as const,
  accent: ['#D4A843', '#F0D78C'] as const,
  success: ['#2D9E5F', '#4ADE80'] as const,
  danger: ['#DC4C4C', '#F87171'] as const,
} as const;
