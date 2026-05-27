export const colors = {
  // Primary - Blue
  primary: '#5B8CFF',
  primaryLight: '#7AA8FF',
  primaryDark: '#4A7AEE',
  primaryMuted: 'rgba(91, 140, 255, 0.08)',

  // AI Accent - Purple
  aiPurple: '#8B5CF6',
  aiPurpleLight: '#A78BFA',
  aiPurpleMuted: 'rgba(139, 92, 246, 0.08)',

  // Agriculture - Green
  success: '#3BB273',
  successLight: '#4ADE80',
  successMuted: 'rgba(59, 178, 115, 0.08)',

  // Financial
  income: '#16A34A',
  incomeBg: '#EDFDF3',
  expense: '#EF4444',
  expenseBg: '#FFF1F2',

  // Semantic
  warning: '#E8923C',
  warningLight: '#FDF3E7',
  danger: '#DC4C4C',
  dangerLight: '#FDEBEB',
  info: '#3B82C4',
  infoLight: '#EBF3FB',

  // Background layers
  background: '#F6F8FC',
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

  // Header
  headerBg: '#0F172A',
  headerText: '#FFFFFF',

  // Tab
  tabBg: '#FFFFFF',
  tabActive: '#5B8CFF',
  tabInactive: '#9CA3AF',

  // Overlay
  overlay: 'rgba(0, 0, 0, 0.4)',
  scrim: 'rgba(15, 23, 42, 0.6)',

  disabled: '#D1D5DB',
  disabledBg: '#F3F4F6',

  // Quick action card backgrounds
  qaPlanting: '#EDFDF3',
  qaReminder: '#EEF4FF',
  qaWeather: '#FFF8E8',
  qaPest: '#FFF1F2',

  // AI Pet
  aiPetBg: '#EDF4FF',

  // Chat
  chatBgStart: '#F7FAFF',
  chatBgEnd: '#FFFFFF',
  chatInputBg: '#F3F6FB',
  chatAiBorder: '#EEF2F7',

  // Settings
  settingsBg: '#F8FAFC',

  // Weather detail
  weatherDetailStart: '#BFD8FF',
  weatherDetailMid: '#EAF3FF',
  weatherDetailEnd: '#FFFFFF',

  // Emotion card gradients (solid fallbacks)
  emotionFoggyStart: '#EAF3FF',
  emotionFoggyEnd: '#F7F9FF',
  emotionSunnyStart: '#FFF4D6',
  emotionSunnyEnd: '#FFF9EA',
  emotionRainyStart: '#DCEBFF',
  emotionRainyEnd: '#EEF5FF',
  emotionColdStart: '#E7F2FF',
  emotionColdEnd: '#F3F8FF',
} as const;

export const gradients = {
  primary: ['#5B8CFF', '#7AA8FF'] as const,
  primaryPurple: ['#5B8CFF', '#8B5CF6'] as const,
  userBubble: ['#5B8CFF', '#7A7DFF'] as const,
  header: ['#0F172A', '#1E293B'] as const,
  card: ['#FFFFFF', '#FAFBFC'] as const,
  success: ['#3BB273', '#4ADE80'] as const,
  danger: ['#DC4C4C', '#F87171'] as const,
  weatherCard: ['#5B8CFF', '#7AA8FF'] as const,
  fab: ['#5B8CFF', '#8B5CF6'] as const,
  titleText: ['#4DA2FF', '#C26CFF'] as const,
  chatBg: ['#F7FAFF', '#FFFFFF'] as const,
  weatherDetail: ['#BFD8FF', '#EAF3FF', '#FFFFFF'] as const,
  emotionFoggy: ['#EAF3FF', '#F7F9FF'] as const,
  emotionSunny: ['#FFF4D6', '#FFF9EA'] as const,
  emotionRainy: ['#DCEBFF', '#EEF5FF'] as const,
  emotionCold: ['#E7F2FF', '#F3F8FF'] as const,
  capsuleActive: ['#5B8CFF', '#7A7DFF'] as const,
} as const;
