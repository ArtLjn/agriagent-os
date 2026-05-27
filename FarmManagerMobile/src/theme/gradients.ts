import { colors } from "./colors";

export type GradientColors = readonly string[];

export const appGradients = {
  // Weather card background
  weatherCard: {
    colors: ["#5B8CFF", "#7AA8FF"] as GradientColors,
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
  // User message bubble
  userBubble: {
    colors: ["#5B8CFF", "#7A7DFF"] as GradientColors,
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
  // FAB button
  fab: {
    colors: ["#5B8CFF", "#8B5CF6"] as GradientColors,
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
  // Capsule active tab
  capsuleActive: {
    colors: ["#5B8CFF", "#7A7DFF"] as GradientColors,
    start: { x: 0, y: 0 },
    end: { x: 1, y: 0 },
  },
  // Chat screen background
  chatBg: {
    colors: ["#F7FAFF", "#FFFFFF"] as GradientColors,
    start: { x: 0, y: 0 },
    end: { x: 0, y: 1 },
  },
  // Weather detail page background
  weatherDetail: {
    colors: ["#BFD8FF", "#EAF3FF", "#FFFFFF"] as GradientColors,
    locations: [0, 0.6, 1],
    start: { x: 0, y: 0 },
    end: { x: 0, y: 1 },
  },
  // Emotion cards
  emotionFoggy: {
    colors: [
      colors.emotionFoggyStart,
      colors.emotionFoggyEnd,
    ] as GradientColors,
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
  emotionSunny: {
    colors: [
      colors.emotionSunnyStart,
      colors.emotionSunnyEnd,
    ] as GradientColors,
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
  emotionRainy: {
    colors: [
      colors.emotionRainyStart,
      colors.emotionRainyEnd,
    ] as GradientColors,
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
  emotionCold: {
    colors: [colors.emotionColdStart, colors.emotionColdEnd] as GradientColors,
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
} as const;
