import React from 'react';
import {View, Text, StyleSheet, TouchableOpacity} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import {BreathingFloat} from './animations/BreathingFloat';
import {ScalePress} from './animations/ScalePress';
import {colors} from '../theme/colors';
import {shadowV2} from '../theme/designTokens';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

export const AIPet: React.FC = () => {
  const navigation = useNavigation();

  const handlePress = () => {
    navigation.navigate('AgentChat' as never);
  };

  return (
    <View style={styles.container}>
      <BreathingFloat>
        <ScalePress onPress={handlePress}>
          <View style={[styles.pet, shadowV2.float]}>
            <Icon name="robot-happy" size={32} color={colors.primary} />
            <View style={styles.pulseDot} />
          </View>
        </ScalePress>
      </BreathingFloat>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    right: 20,
    bottom: 100,
    zIndex: 100,
  },
  pet: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.aiPetBg,
    alignItems: 'center',
    justifyContent: 'center',
    opacity: 0.9,
    borderWidth: 2,
    borderColor: 'rgba(91,140,255,0.15)',
  },
  pulseDot: {
    position: 'absolute',
    top: 14,
    right: 14,
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.success,
    borderWidth: 2,
    borderColor: colors.aiPetBg,
  },
});
