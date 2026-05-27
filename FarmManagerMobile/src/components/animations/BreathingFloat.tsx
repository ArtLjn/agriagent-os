import React, {useEffect, useRef} from 'react';
import {Animated, ViewStyle} from 'react-native';
import {animationConfig} from '../../theme/animations';

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
    Animated.loop(
      Animated.sequence([
        Animated.timing(translateY, {
          toValue: -animationConfig.breathing.offset,
          duration: animationConfig.breathing.duration / 2,
          useNativeDriver: animationConfig.breathing.useNativeDriver,
        }),
        Animated.timing(translateY, {
          toValue: animationConfig.breathing.offset,
          duration: animationConfig.breathing.duration / 2,
          useNativeDriver: animationConfig.breathing.useNativeDriver,
        }),
        Animated.timing(translateY, {
          toValue: 0,
          duration: animationConfig.breathing.duration / 2,
          useNativeDriver: animationConfig.breathing.useNativeDriver,
        }),
      ]),
    ).start();
  }, [translateY]);

  return (
    <Animated.View
      style={[
        style,
        {
          transform: [{translateY}],
        },
      ]}>
      {children}
    </Animated.View>
  );
};
