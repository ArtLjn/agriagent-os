import React, {useEffect, useRef} from 'react';
import {Animated, ViewStyle} from 'react-native';
import {animationConfig} from '../../theme/animations';

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
  const translateY = useRef(new Animated.Value(animationConfig.entrance.translateY)).current;

  useEffect(() => {
    Animated.timing(opacity, {
      toValue: 1,
      duration: animationConfig.entrance.duration,
      delay,
      useNativeDriver: animationConfig.entrance.useNativeDriver,
    }).start();
    Animated.timing(translateY, {
      toValue: 0,
      duration: animationConfig.entrance.duration,
      delay,
      useNativeDriver: animationConfig.entrance.useNativeDriver,
    }).start();
  }, [opacity, translateY, delay]);

  return (
    <Animated.View
      style={[
        style,
        {
          opacity,
          transform: [{translateY}],
        },
      ]}>
      {children}
    </Animated.View>
  );
};
