export const animationConfig = {
  // Card entrance: fade in + slide up
  entrance: {
    duration: 450,
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
    duration: 100,
    scale: 0.96,
    useNativeDriver: true,
  },
  // Stagger delay for multiple cards
  stagger: {
    delay: 80,
  },
} as const;
