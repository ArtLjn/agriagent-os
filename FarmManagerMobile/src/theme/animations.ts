import { Easing } from "react-native";

/**
 * 动画配置中心
 *
 * Easing 规范（对应 CSS cubic-bezier）：
 * - enter:  (0.22, 1, 0.36, 1)  入场 / transform hover
 * - move:   (0.25, 1, 0.5, 1)   滑动、drawer、panel
 * - drawer: (0.32, 0.72, 0, 1)  iOS-style drawer
 * - breathe: inOut(ease)        呼吸浮动
 */
export const animationConfig = {
  easing: {
    enter: Easing.bezier(0.22, 1, 0.36, 1),
    move: Easing.bezier(0.25, 1, 0.5, 1),
    drawer: Easing.bezier(0.32, 0.72, 0, 1),
    breathe: Easing.inOut(Easing.ease),
  },

  // Card entrance: fade in + slide up
  entrance: {
    duration: 300,
    translateY: 20,
    useNativeDriver: true,
  },

  // Breathing float: continuous up/down
  breathing: {
    duration: 3000,
    offset: 4,
    useNativeDriver: true,
  },

  // Press feedback: scale down
  press: {
    durationIn: 100,
    durationOut: 160,
    scale: 0.96,
    useNativeDriver: true,
  },

  // Stagger delay for multiple cards — 30-50ms per item
  stagger: {
    delay: 50,
  },
} as const;

/** activeOpacity 规范 */
export const touchOpacity = {
  primary: 0.75,   // 主操作按钮
  secondary: 0.85, // 次要操作按钮
  card: 0.8,       // 卡片 / 列表项
  icon: 0.7,       // 小图标按钮
} as const;
