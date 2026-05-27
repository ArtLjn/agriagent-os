import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAuthStore } from "../../stores/authStore";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const PHONE_REGEX = /^1[3-9]\d{9}$/;

export const LoginScreen: React.FC<{
  onNavigateToRegister: () => void;
}> = ({ onNavigateToRegister }) => {
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const login = useAuthStore((s) => s.login);

  const handleLogin = useCallback(async () => {
    if (!PHONE_REGEX.test(phone)) {
      Alert.alert("提示", "请输入正确的11位手机号");
      return;
    }
    if (!password) {
      Alert.alert("提示", "请输入密码");
      return;
    }
    setLoading(true);
    try {
      await login({ phone, password });
    } catch (e: any) {
      Alert.alert("登录失败", e.message || "手机号或密码错误");
    } finally {
      setLoading(false);
    }
  }, [phone, password, login]);

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={styles.inner}
      >
        <View style={styles.header}>
          <View style={styles.logoIcon}>
            <Icon name="sprout" size={40} color={colors.primary} />
          </View>
          <Text style={styles.title}>农博社</Text>
          <Text style={styles.subtitle}>智能种植管理平台</Text>
        </View>

        <View style={styles.form}>
          <View style={styles.inputContainer}>
            <Icon
              name="phone"
              size={20}
              color={colors.textTertiary}
              style={styles.inputIcon}
            />
            <TextInput
              style={styles.input}
              placeholder="手机号"
              placeholderTextColor={colors.textTertiary}
              keyboardType="phone-pad"
              maxLength={11}
              value={phone}
              onChangeText={setPhone}
              editable={!loading}
            />
          </View>

          <View style={styles.inputContainer}>
            <Icon
              name="lock"
              size={20}
              color={colors.textTertiary}
              style={styles.inputIcon}
            />
            <TextInput
              style={styles.input}
              placeholder="密码"
              placeholderTextColor={colors.textTertiary}
              secureTextEntry
              value={password}
              onChangeText={setPassword}
              editable={!loading}
            />
          </View>

          <TouchableOpacity
            style={[styles.loginButton, loading && styles.loginButtonDisabled]}
            onPress={handleLogin}
            disabled={loading || phone.length < 11 || !password}
            activeOpacity={0.8}
          >
            <Text style={styles.loginButtonText}>
              {loading ? "登录中..." : "登录"}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={onNavigateToRegister}
            disabled={loading}
            style={styles.registerLink}
          >
            <Text style={styles.registerLinkText}>
              还没有账号？<Text style={styles.registerLinkHighlight}>去注册</Text>
            </Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  inner: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
  },
  header: {
    alignItems: "center",
    marginBottom: 48,
  },
  logoIcon: {
    width: 80,
    height: 80,
    borderRadius: 20,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    color: colors.text,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  form: {
    gap: spacing.md,
  },
  inputContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    paddingHorizontal: spacing.md,
    height: 52,
  },
  inputIcon: {
    marginRight: spacing.sm,
  },
  input: {
    flex: 1,
    fontSize: fontSize.lg,
    color: colors.text,
    padding: 0,
  },
  loginButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
    height: 52,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.sm,
  },
  loginButtonDisabled: {
    opacity: 0.5,
  },
  loginButtonText: {
    color: "#fff",
    fontSize: fontSize.lg,
    fontWeight: "600",
  },
  registerLink: {
    alignItems: "center",
    marginTop: spacing.md,
  },
  registerLinkText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  registerLinkHighlight: {
    color: colors.primary,
    fontWeight: "600",
  },
});
