import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { useNavigation } from "@react-navigation/native";
import { BreathingFloat } from "./animations/BreathingFloat";
import { ScalePress } from "./animations/ScalePress";
import { colors } from "../theme/colors";
import { shadowV2 } from "../theme/designTokens";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

export const AIPet: React.FC = () => {
  const navigation = useNavigation();

  const handlePress = () => {
    navigation.navigate("AgentChat" as never);
  };

  return (
    <View style={styles.container}>
      <BreathingFloat>
        <ScalePress onPress={handlePress}>
          <View style={[styles.pet, shadowV2.float]}>
            <Icon name="robot-happy" size={26} color={colors.primary} />
            <View style={styles.pulseDot} />
          </View>
        </ScalePress>
      </BreathingFloat>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: "absolute",
    right: 20,
    bottom: 28,
    zIndex: 100,
  },
  pet: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.aiPetBg,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "rgba(91,140,255,0.12)",
  },
  pulseDot: {
    position: "absolute",
    top: 12,
    right: 12,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.success,
    borderWidth: 1.5,
    borderColor: colors.aiPetBg,
  },
});
