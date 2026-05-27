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
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAuthStore } from "../../stores/authStore";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const PHONE_REGEX = /^1[3-9]\d{9}$/;

export const RegisterScreen: React.FC<{
  onNavigateToLogin: () => void;
}> = ({ onNavigateToLogin }) => {
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [loading, setLoading] = useState(false);

  const register = useAuthStore((s) => s.register);

  const handleRegister = useCallback(async () => {
    if (!PHONE_REGEX.test(phone)) {
      Alert.alert("提示", "请输入正确的11位手机号");
      return;
    }
    if (password.length < 8) {
      Alert.alert("提示", "密码至少8位");
      return;
    }
    if (password !== confirmPassword) {
      Alert.alert("提示", "两次密码不一致");
      return;
    }
    setLoading(true);
    try {
      await register({
        phone,
        password,
        nickname: nickname.trim() || undefined,
      });
    } catch (e: any) {
      Alert.alert("注册失败", e.message || "注册失败，请重试");
    } finally {
      setLoading(false);
    }
  }, [phone, password, confirmPassword, nickname, register]);

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={styles.inner}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.header}>
            <Text style={styles.title}>创建账号</Text>
            <Text style={styles.subtitle}>注册后即可使用全部功能</Text>
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
                placeholder="密码（至少8位）"
                placeholderTextColor={colors.textTertiary}
                secureTextEntry
                value={password}
                onChangeText={setPassword}
                editable={!loading}
              />
            </View>

            <View style={styles.inputContainer}>
              <Icon
                name="lock-check"
                size={20}
                color={colors.textTertiary}
                style={styles.inputIcon}
              />
              <TextInput
                style={styles.input}
                placeholder="确认密码"
                placeholderTextColor={colors.textTertiary}
                secureTextEntry
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                editable={!loading}
              />
            </View>

            <View style={styles.inputContainer}>
              <Icon
                name="account"
                size={20}
                color={colors.textTertiary}
                style={styles.inputIcon}
              />
              <TextInput
                style={styles.input}
                placeholder={'昵称（可选，默认"农友"）'}
                placeholderTextColor={colors.textTertiary}
                maxLength={20}
                value={nickname}
                onChangeText={setNickname}
                editable={!loading}
              />
            </View>

            <TouchableOpacity
              style={[styles.registerButton, loading && styles.registerButtonDisabled]}
              onPress={handleRegister}
              disabled={
                loading || phone.length < 11 || !password || !confirmPassword
              }
              activeOpacity={0.8}
            >
              <Text style={styles.registerButtonText}>
                {loading ? "注册中..." : "注册"}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              onPress={onNavigateToLogin}
              disabled={loading}
              style={styles.loginLink}
            >
              <Text style={styles.loginLinkText}>
                已有账号？<Text style={styles.loginLinkHighlight}>去登录</Text>
              </Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
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
  },
  scrollContent: {
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.xxl,
  },
  header: {
    alignItems: "center",
    marginBottom: 40,
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
  registerButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
    height: 52,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.sm,
  },
  registerButtonDisabled: {
    opacity: 0.5,
  },
  registerButtonText: {
    color: "#fff",
    fontSize: fontSize.lg,
    fontWeight: "600",
  },
  loginLink: {
    alignItems: "center",
    marginTop: spacing.md,
  },
  loginLinkText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  loginLinkHighlight: {
    color: colors.primary,
    fontWeight: "600",
  },
});
