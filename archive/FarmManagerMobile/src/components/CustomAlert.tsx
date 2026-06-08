import React from "react";
import {
  View,
  Text,
  Modal,
  TouchableOpacity,
  StyleSheet,
  Animated,
} from "react-native";
import { useAlertStore } from "../stores/alertStore";
import { colors } from "../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../theme/spacing";

export const CustomAlert: React.FC = () => {
  const { visible, title, message, buttons, hide } = useAlertStore();
  const fadeAnim = React.useRef(new Animated.Value(0)).current;
  const scaleAnim = React.useRef(new Animated.Value(0.9)).current;

  React.useEffect(() => {
    if (visible) {
      Animated.parallel([
        Animated.timing(fadeAnim, {
          toValue: 1,
          duration: 200,
          useNativeDriver: true,
        }),
        Animated.spring(scaleAnim, {
          toValue: 1,
          friction: 8,
          tension: 100,
          useNativeDriver: true,
        }),
      ]).start();
    } else {
      Animated.timing(fadeAnim, {
        toValue: 0,
        duration: 150,
        useNativeDriver: true,
      }).start();
    }
  }, [visible]);

  const handlePress = (onPress?: () => void) => {
    hide();
    setTimeout(() => onPress?.(), 200);
  };

  const isSingleButton = buttons.length <= 1;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="none"
      onRequestClose={() => handlePress(buttons[buttons.length - 1]?.onPress)}
    >
      <Animated.View style={[styles.overlay, { opacity: fadeAnim }]}>
        <Animated.View
          style={[
            styles.card,
            { transform: [{ scale: scaleAnim }] },
          ]}
        >
          <View style={styles.content}>
            <Text style={styles.title}>{title}</Text>
            {message ? <Text style={styles.message}>{message}</Text> : null}
          </View>

          <View
            style={[
              styles.buttonContainer,
              isSingleButton && styles.singleButtonContainer,
            ]}
          >
            {buttons.map((btn, index) => {
              const isDestructive = btn.style === "destructive";
              const isCancel = btn.style === "cancel";
              const isPrimary =
                !isDestructive && !isCancel && (isSingleButton || index === buttons.length - 1);

              return (
                <TouchableOpacity
                  key={index}
                  style={[
                    styles.button,
                    isSingleButton && styles.buttonFullWidth,
                    isPrimary && styles.buttonPrimary,
                    isDestructive && styles.buttonDestructive,
                    isCancel && styles.buttonCancel,
                    index > 0 && !isSingleButton && styles.buttonLeftBorder,
                  ]}
                  onPress={() => handlePress(btn.onPress)}
                  activeOpacity={0.7}
                >
                  <Text
                    style={[
                      styles.buttonText,
                      isPrimary && styles.buttonTextPrimary,
                      isDestructive && styles.buttonTextDestructive,
                      isCancel && styles.buttonTextCancel,
                    ]}
                  >
                    {btn.text}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </Animated.View>
      </Animated.View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.45)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: spacingV2.xxl,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    width: "100%",
    maxWidth: 300,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.12,
    shadowRadius: 24,
    elevation: 12,
    overflow: "hidden",
  },
  content: {
    paddingHorizontal: spacingV2.xl,
    paddingTop: spacingV2.xl,
    paddingBottom: spacingV2.lg,
    alignItems: "center",
  },
  title: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
    textAlign: "center",
    letterSpacing: -0.3,
  },
  message: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    textAlign: "center",
    marginTop: spacingV2.sm,
    lineHeight: 22,
  },
  buttonContainer: {
    flexDirection: "row",
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  singleButtonContainer: {
    padding: spacingV2.md,
    borderTopWidth: 0,
  },
  button: {
    flex: 1,
    paddingVertical: spacingV2.md,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonFullWidth: {
    backgroundColor: colors.primary,
    borderRadius: borderRadiusV2.lg,
    paddingVertical: spacingV2.md + 2,
  },
  buttonPrimary: {
    backgroundColor: colors.primary,
  },
  buttonDestructive: {
    backgroundColor: colors.dangerLight,
  },
  buttonCancel: {
    backgroundColor: colors.surfaceMuted,
  },
  buttonLeftBorder: {
    borderLeftWidth: 1,
    borderLeftColor: colors.borderLight,
  },
  buttonText: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
    color: colors.textSecondary,
  },
  buttonTextPrimary: {
    color: "#FFFFFF",
    fontWeight: "700",
  },
  buttonTextDestructive: {
    color: colors.danger,
    fontWeight: "700",
  },
  buttonTextCancel: {
    color: colors.textSecondary,
    fontWeight: "600",
  },
});
