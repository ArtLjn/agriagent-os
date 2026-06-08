import { colors } from "./colors";

export type GradientColors = string[];

export interface GradientConfig {
  colors: GradientColors;
  locations?: number[];
  start: { x: number; y: number };
  end: { x: number; y: number };
}

export const appGradients: Record<string, GradientConfig> = {
  // Weather card background
  weatherCard: {
    colors: ["#5B8CFF", "#7AA8FF"],
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
  // User message bubble — warm slate, no purple
  userBubble: {
    colors: ["#4B6A8A", "#5A7D9A"],
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
  // FAB button
  fab: {
    colors: ["#4B6A8A", "#5A7D9A"],
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
  // Capsule active tab
  capsuleActive: {
    colors: ["#5B8CFF", "#7A7DFF"],
    start: { x: 0, y: 0 },
    end: { x: 1, y: 0 },
  },
  // Chat screen background
  chatBg: {
    colors: ["#F7FAFF", "#FFFFFF"],
    start: { x: 0, y: 0 },
    end: { x: 0, y: 1 },
  },
  // Weather detail page background
  weatherDetail: {
    colors: ["#BFD8FF", "#EAF3FF", "#FFFFFF"],
    locations: [0, 0.6, 1],
    start: { x: 0, y: 0 },
    end: { x: 0, y: 1 },
  },
  // Emotion cards
  emotionFoggy: {
    colors: [colors.emotionFoggyStart, colors.emotionFoggyEnd],
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
  emotionSunny: {
    colors: [colors.emotionSunnyStart, colors.emotionSunnyEnd],
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
  emotionRainy: {
    colors: [colors.emotionRainyStart, colors.emotionRainyEnd],
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
  emotionCold: {
    colors: [colors.emotionColdStart, colors.emotionColdEnd],
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
};
