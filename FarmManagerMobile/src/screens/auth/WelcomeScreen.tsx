import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import LinearGradient from "react-native-linear-gradient";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

export const WelcomeScreen: React.FC<{
  onNavigateToLogin: () => void;
  onNavigateToRegister: () => void;
}> = ({ onNavigateToLogin, onNavigateToRegister }) => {
  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      <LinearGradient
        colors={["#2563EB", "#4A7BF7", "#7BA4FF"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.gradient}
      >
        {/* 装饰圆 */}
        <View
          style={{
            position: "absolute",
            width: 300,
            height: 300,
            borderRadius: 150,
            backgroundColor: "rgba(255,255,255,0.06)",
            top: -80,
            left: -100,
          }}
        />
        <View
          style={{
            position: "absolute",
            width: 200,
            height: 200,
            borderRadius: 100,
            backgroundColor: "rgba(255,255,255,0.08)",
            top: 40,
            right: -60,
          }}
        />

        {/* 品牌区域 */}
        <View style={styles.brandArea}>
          <View style={styles.iconGlow} />
          <View style={styles.iconBox}>
            <Icon name="sprout" size={52} color="#FFFFFF" />
          </View>
          <Text style={styles.title}>农博社</Text>
          <Text style={styles.subtitle}>智能种植管理平台</Text>
        </View>

        {/* 底部按钮 */}
        <View style={styles.buttonArea}>
          <TouchableOpacity
            onPress={onNavigateToRegister}
            activeOpacity={0.9}
          >
            <View style={styles.primaryButton}>
              <Text style={styles.primaryButtonText}>开始使用</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={onNavigateToLogin}
            activeOpacity={0.7}
          >
            <View style={styles.secondaryButton}>
              <Text style={styles.secondaryButtonText}>
                已有账号？登录
              </Text>
            </View>
          </TouchableOpacity>
        </View>
      </LinearGradient>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  gradient: {
    flex: 1,
    position: "relative",
    overflow: "hidden",
    justifyContent: "space-between",
    paddingHorizontal: 28,
    paddingBottom: 32,
  },

  brandArea: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  iconGlow: {
    position: "absolute",
    width: 140,
    height: 140,
    borderRadius: 70,
    backgroundColor: "rgba(255,255,255,0.08)",
  },
  iconBox: {
    width: 100,
    height: 100,
    borderRadius: 32,
    backgroundColor: "rgba(255,255,255,0.12)",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.2)",
  },
  title: {
    fontSize: 38,
    fontWeight: "800",
    color: "#FFFFFF",
    marginTop: 24,
    letterSpacing: 6,
  },
  subtitle: {
    fontSize: 15,
    color: "rgba(255,255,255,0.7)",
    marginTop: 10,
    letterSpacing: 2,
  },

  buttonArea: {
    width: "100%",
    gap: 14,
  },
  primaryButton: {
    height: 56,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "rgba(0,0,0,0.15)",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 4,
  },
  primaryButtonText: {
    fontSize: 17,
    fontWeight: "700",
    color: "#2563EB",
    letterSpacing: 2,
  },
  secondaryButton: {
    height: 56,
    borderRadius: 16,
    justifyContent: "center",
    alignItems: "center",
  },
  secondaryButtonText: {
    fontSize: 15,
    fontWeight: "600",
    color: "rgba(255,255,255,0.85)",
  },
});
