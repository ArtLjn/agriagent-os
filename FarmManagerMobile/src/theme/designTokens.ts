export const radii = {
  sm: 10,
  md: 14,
  lg: 18,
  xl: 22,
  xxl: 28,
  xxxl: 30,
  full: 999,
} as const;

export const typography = {
  heading1: {
    fontSize: 32,
    fontWeight: '700' as const,
    letterSpacing: -0.5,
  },
  heading2: {
    fontSize: 22,
    fontWeight: '600' as const,
  },
  body: {
    fontSize: 15,
    lineHeight: 24,
  },
  caption: {
    fontSize: 13,
  },
  small: {
    fontSize: 11,
  },
} as const;

export const shadowV2 = {
  card: {
    shadowColor: '#5B8CFF',
    shadowOffset: {width: 0, height: 8},
    shadowOpacity: 0.08,
    shadowRadius: 30,
    elevation: 8,
  },
  light: {
    shadowColor: '#000',
    shadowOffset: {width: 0, height: 4},
    shadowOpacity: 0.04,
    shadowRadius: 16,
    elevation: 4,
  },
  float: {
    shadowColor: '#5B8CFF',
    shadowOffset: {width: 0, height: 6},
    shadowOpacity: 0.15,
    shadowRadius: 20,
    elevation: 10,
  },
} as const;

export const animationTiming = {
  entranceDuration: 450,
  breathingDuration: 3000,
  pressDuration: 100,
  pressScale: 0.96,
  breathingOffset: 4,
  entranceTranslateY: 20,
} as const;
