import React, { useEffect, useRef } from "react";
import { Animated, ViewStyle } from "react-native";
import { animationConfig } from "../../theme/animations";

interface FadeInListItemProps {
  children: React.ReactNode;
  index: number;
  style?: ViewStyle;
}

/**
 * 列表项入场动画包装器
 *
 * 基于 index 自动计算 stagger delay，首次渲染时播放
 * fade + slideUp 入场动画。利用 hasAnimated ref 防止
 * FlatList 回收复用时重复触发。
 */
export const FadeInListItem: React.FC<FadeInListItemProps> = ({
  children,
  index,
  style,
}) => {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(
    new Animated.Value(animationConfig.entrance.translateY)
  ).current;
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (hasAnimated.current) return;
    hasAnimated.current = true;

    const delay = Math.min(index * animationConfig.stagger.delay, 300);
    const cfg = {
      duration: animationConfig.entrance.duration,
      delay,
      useNativeDriver: animationConfig.entrance.useNativeDriver,
      easing: animationConfig.easing.enter,
    };

    Animated.timing(opacity, { ...cfg, toValue: 1 }).start();
    Animated.timing(translateY, { ...cfg, toValue: 0 }).start();
  }, [opacity, translateY, index]);

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
