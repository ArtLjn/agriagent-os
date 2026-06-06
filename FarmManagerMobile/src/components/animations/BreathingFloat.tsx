import React, { useEffect, useRef } from "react";
import { Animated, ViewStyle } from "react-native";
import { animationConfig } from "../../theme/animations";

interface BreathingFloatProps {
  children: React.ReactNode;
  style?: ViewStyle;
}

export const BreathingFloat: React.FC<BreathingFloatProps> = ({
  children,
  style,
}) => {
  const translateY = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const half = animationConfig.breathing.duration / 2;
    const breathe = animationConfig.easing.breathe;

    Animated.loop(
      Animated.sequence([
        Animated.timing(translateY, {
          toValue: -animationConfig.breathing.offset,
          duration: half,
          useNativeDriver: animationConfig.breathing.useNativeDriver,
          easing: breathe,
        }),
        Animated.timing(translateY, {
          toValue: animationConfig.breathing.offset,
          duration: half,
          useNativeDriver: animationConfig.breathing.useNativeDriver,
          easing: breathe,
        }),
        Animated.timing(translateY, {
          toValue: 0,
          duration: half,
          useNativeDriver: animationConfig.breathing.useNativeDriver,
          easing: breathe,
        }),
      ])
    ).start();
  }, [translateY]);

  return (
    <Animated.View
      style={[
        style,
        {
          transform: [{ translateY }],
        },
      ]}
    >
      {children}
    </Animated.View>
  );
};
