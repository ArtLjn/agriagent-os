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
import LinearGradient from "react-native-linear-gradient";
import { useAuthStore } from "../../stores/authStore";
import { FadeInSlideUp } from "../../components/animations/FadeInSlideUp";
import { ScalePress } from "../../components/animations/ScalePress";
import { BreathingFloat } from "../../components/animations/BreathingFloat";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const PHONE_REGEX = /^1[3-9]\d{9}$/;

const DecoOrb: React.FC<{
  size: number;
  color: string;
  top?: number;
  left?: number;
  right?: number;
  bottom?: number;
}> = ({ size, color, top, left, right, bottom }) => (
  <BreathingFloat
    style={{ position: "absolute", top, left, right, bottom }}
  >
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: color,
      }}
    />
  </BreathingFloat>
);

// 列表风格输入框 — 无边框，放在灰色容器内
const ListInput: React.FC<{
  label: string;
  value: string;
  onChangeText: (t: string) => void;
  placeholder?: string;
  icon: string;
  keyboardType?: any;
  maxLength?: number;
  secureTextEntry?: boolean;
  editable?: boolean;
  returnKeyType?: any;
  onSubmitEditing?: () => void;
  rightElement?: React.ReactNode;
  showDivider?: boolean;
}> = ({
  label,
  value,
  onChangeText,
  placeholder,
  icon,
  keyboardType,
  maxLength,
  secureTextEntry,
  editable = true,
  returnKeyType,
  onSubmitEditing,
  rightElement,
  showDivider = false,
}) => {
  const [focused, setFocused] = useState(false);

  return (
    <View>
      <View style={styles.listInputRow}>
        <Icon
          name={icon}
          size={20}
          color={focused ? "#4A7BF7" : "#9CA3AF"}
          style={styles.listInputIcon}
        />
        <View style={styles.listInputContent}>
          <Text
            style={[
              styles.listInputLabel,
              focused && { color: "#4A7BF7" },
            ]}
          >
            {label}
          </Text>
          <TextInput
            style={styles.listInputField}
            value={value}
            onChangeText={onChangeText}
            placeholder={placeholder}
            placeholderTextColor="#B8BDC7"
            keyboardType={keyboardType}
            maxLength={maxLength}
            secureTextEntry={secureTextEntry}
            editable={editable}
            returnKeyType={returnKeyType}
            onSubmitEditing={onSubmitEditing}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
          />
        </View>
        {rightElement}
      </View>
      {showDivider && <View style={styles.listInputDivider} />}
    </View>
  );
};

export const LoginScreen: React.FC<{
  onNavigateToRegister: () => void;
}> = ({ onNavigateToRegister }) => {
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [secureText, setSecureText] = useState(true);
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

  const canSubmit = phone.length === 11 && password.length > 0 && !loading;

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.flex}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
          bounces={false}
        >
          {/* 头部渐变 */}
          <LinearGradient
            colors={["#2563EB", "#4A7BF7", "#7BA4FF"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.headerGradient}
          >
            <DecoOrb
              size={300}
              color="rgba(91,140,255,0.06)"
              top={-80}
              left={-100}
            />
            <DecoOrb
              size={200}
              color="rgba(107,154,255,0.08)"
              top={20}
              right={-60}
            />
            <DecoOrb
              size={140}
              color="rgba(91,140,255,0.05)"
              bottom={80}
              left={20}
            />

            <FadeInSlideUp>
              <View style={styles.brandArea}>
                <View style={styles.glowRing} />
                <View style={styles.iconContainer}>
                  <Icon name="sprout" size={46} color="#FFFFFF" />
                </View>
                <Text style={styles.brandTitle}>农博社</Text>
                <Text style={styles.brandSubtitle}>
                  智能种植管理平台
                </Text>
              </View>
            </FadeInSlideUp>
          </LinearGradient>

          {/* 白色卡片 */}
          <View style={styles.card}>
            {/* 顶部拉条 */}
            <View style={styles.handleBar} />

            <FadeInSlideUp delay={120}>
              <View style={styles.titleRow}>
                <View style={styles.titleAccent} />
                <View>
                  <Text style={styles.cardTitle}>欢迎回来</Text>
                  <Text style={styles.cardSubtitle}>
                    登录您的账号以继续
                  </Text>
                </View>
              </View>
            </FadeInSlideUp>

            {/* 表单列表容器 */}
            <FadeInSlideUp delay={200}>
              <View style={styles.formBox}>
                <ListInput
                  label="手机号"
                  value={phone}
                  onChangeText={setPhone}
                  placeholder="请输入11位手机号"
                  icon="phone-outline"
                  keyboardType="phone-pad"
                  maxLength={11}
                  editable={!loading}
                  showDivider
                />
                <ListInput
                  label="密码"
                  value={password}
                  onChangeText={setPassword}
                  placeholder="请输入密码"
                  icon="lock-outline"
                  secureTextEntry={secureText}
                  editable={!loading}
                  returnKeyType="done"
                  onSubmitEditing={canSubmit ? handleLogin : undefined}
                  rightElement={
                    <TouchableOpacity
                      onPress={() => setSecureText((p) => !p)}
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                    >
                      <Icon
                        name={secureText ? "eye-off-outline" : "eye-outline"}
                        size={20}
                        color="#9CA3AF"
                      />
                    </TouchableOpacity>
                  }
                />
              </View>
            </FadeInSlideUp>

            <FadeInSlideUp delay={280}>
              <TouchableOpacity style={styles.forgotLink}>
                <Text style={styles.forgotText}>忘记密码？</Text>
              </TouchableOpacity>
            </FadeInSlideUp>

            <FadeInSlideUp delay={360}>
              <ScalePress>
                <TouchableOpacity
                  onPress={handleLogin}
                  disabled={!canSubmit}
                  activeOpacity={0.9}
                >
                  <LinearGradient
                    colors={
                      canSubmit
                        ? ["#3B6FE0", "#5B9AFF"]
                        : ["#B0C4F7", "#C5D5FF"]
                    }
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 0 }}
                    style={styles.loginButton}
                  >
                    <Text style={styles.loginButtonText}>
                      {loading ? "登录中..." : "登 录"}
                    </Text>
                  </LinearGradient>
                </TouchableOpacity>
              </ScalePress>
            </FadeInSlideUp>

            <FadeInSlideUp delay={440}>
              <View style={styles.bottomArea}>
                <View style={styles.divider}>
                  <View style={styles.dividerLine} />
                  <Text style={styles.dividerText}>还没有账号</Text>
                  <View style={styles.dividerLine} />
                </View>
                <TouchableOpacity
                  onPress={onNavigateToRegister}
                  disabled={loading}
                  activeOpacity={0.7}
                >
                  <Text style={styles.registerLinkText}>创建新账号</Text>
                </TouchableOpacity>
              </View>
            </FadeInSlideUp>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#2563EB",
  },
  flex: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
  },

  headerGradient: {
    height: 360,
    justifyContent: "center",
    alignItems: "center",
    position: "relative",
    overflow: "hidden",
  },

  brandArea: {
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1,
  },
  glowRing: {
    position: "absolute",
    width: 140,
    height: 140,
    borderRadius: 70,
    backgroundColor: "rgba(91,140,255,0.08)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.06)",
  },
  iconContainer: {
    width: 92,
    height: 92,
    borderRadius: 30,
    backgroundColor: "rgba(255,255,255,0.1)",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.15)",
  },
  brandTitle: {
    fontSize: 36,
    fontWeight: "800",
    color: "#FFFFFF",
    marginTop: 20,
    letterSpacing: 6,
  },
  brandSubtitle: {
    fontSize: 14,
    color: "rgba(255,255,255,0.6)",
    marginTop: 8,
    letterSpacing: 3,
  },

  card: {
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 36,
    borderTopRightRadius: 36,
    marginTop: -36,
    paddingHorizontal: 28,
    paddingTop: 12,
    paddingBottom: 48,
    flex: 1,
    minHeight: 420,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: -8 },
    shadowOpacity: 0.08,
    shadowRadius: 24,
    elevation: 8,
  },
  handleBar: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: "#E5E7EB",
    alignSelf: "center",
    marginBottom: 24,
  },

  titleRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 24,
  },
  titleAccent: {
    width: 4,
    height: 40,
    borderRadius: 2,
    backgroundColor: "#4A7BF7",
    marginRight: 12,
    marginTop: 2,
  },
  cardTitle: {
    fontSize: 26,
    fontWeight: "700",
    color: "#1A1D23",
    marginBottom: 4,
    letterSpacing: -0.3,
  },
  cardSubtitle: {
    fontSize: 14,
    color: "#9CA3AF",
  },

  // 表单列表
  formBox: {
    backgroundColor: "#F8F9FB",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingTop: 4,
    paddingBottom: 4,
    marginBottom: 16,
  },
  listInputRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
  },
  listInputIcon: {
    marginRight: 14,
    width: 24,
    textAlign: "center",
  },
  listInputContent: {
    flex: 1,
  },
  listInputLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: "#6B7280",
    marginBottom: 2,
    letterSpacing: 0.5,
  },
  listInputField: {
    fontSize: 16,
    color: "#1A1D23",
    padding: 0,
    height: 24,
  },
  listInputDivider: {
    height: 1,
    backgroundColor: "#EDEFF2",
    marginLeft: 38,
  },

  forgotLink: {
    alignSelf: "flex-end",
    marginBottom: 24,
  },
  forgotText: {
    fontSize: 13,
    color: "#4A7BF7",
    fontWeight: "500",
  },

  loginButton: {
    borderRadius: 16,
    height: 56,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#3B6FE0",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
    elevation: 8,
  },
  loginButtonText: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: 3,
  },

  bottomArea: {
    marginTop: 32,
    alignItems: "center",
  },
  divider: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 16,
    width: "100%",
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: "#F0F1F3",
  },
  dividerText: {
    fontSize: 12,
    color: "#B0B5BF",
    marginHorizontal: 12,
  },
  registerLinkText: {
    fontSize: 15,
    color: "#4A7BF7",
    fontWeight: "600",
    paddingVertical: 4,
  },
});
