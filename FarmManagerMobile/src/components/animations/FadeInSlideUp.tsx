import React, { useEffect, useRef } from "react";
import { Animated, Easing, ViewStyle } from "react-native";
import { animationConfig } from "../../theme/animations";

interface FadeInSlideUpProps {
  children: React.ReactNode;
  delay?: number;
  style?: ViewStyle;
}

export const FadeInSlideUp: React.FC<FadeInSlideUpProps> = ({
  children,
  delay = 0,
  style,
}) => {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(
    new Animated.Value(animationConfig.entrance.translateY)
  ).current;

  useEffect(() => {
    const enter = animationConfig.easing.enter;
    const cfg = {
      duration: animationConfig.entrance.duration,
      delay,
      useNativeDriver: animationConfig.entrance.useNativeDriver,
    };

    Animated.timing(opacity, { ...cfg, toValue: 1, easing: enter }).start();
    Animated.timing(translateY, { ...cfg, toValue: 0, easing: enter }).start();
  }, [opacity, translateY, delay]);

  return (
    <Animated.View
      style={[
        style,
        {
          opacity,
          transform: [{ translateY }],
        },
      ]}
    >
      {children}
    </Animated.View>
  );
};
