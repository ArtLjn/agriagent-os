import React, { useRef, useCallback } from "react";
import {
  Animated,
  Pressable,
  ViewStyle,
  GestureResponderEvent,
} from "react-native";
import { animationConfig } from "../../theme/animations";

interface ScalePressProps {
  children: React.ReactNode;
  onPress?: (event: GestureResponderEvent) => void;
  style?: ViewStyle;
  disabled?: boolean;
}

export const ScalePress: React.FC<ScalePressProps> = ({
  children,
  onPress,
  style,
  disabled = false,
}) => {
  const scale = useRef(new Animated.Value(1)).current;

  const handlePressIn = useCallback(() => {
    Animated.timing(scale, {
      toValue: animationConfig.press.scale,
      duration: animationConfig.press.durationIn,
      useNativeDriver: animationConfig.press.useNativeDriver,
      easing: animationConfig.easing.enter,
    }).start();
  }, [scale]);

  const handlePressOut = useCallback(() => {
    Animated.spring(scale, {
      toValue: 1,
      friction: 6,
      tension: 120,
      useNativeDriver: animationConfig.press.useNativeDriver,
    }).start();
  }, [scale]);

  return (
    <Pressable
      onPress={onPress}
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
      disabled={disabled}
    >
      <Animated.View
        style={[
          style,
          {
            transform: [{ scale }],
          },
        ]}
      >
        {children}
      </Animated.View>
    </Pressable>
  );
};
