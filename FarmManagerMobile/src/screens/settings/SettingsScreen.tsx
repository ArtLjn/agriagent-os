import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  Switch,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation } from "@react-navigation/native";
import { Card } from "../../components/Card";
import { CityPicker } from "../../components/CityPicker";
import { useSettingsStore } from "../../stores/settingsStore";
import { useAgentStore } from "../../stores/agentStore";
import { useAuthStore } from "../../stores/authStore";
import { colors } from "../../theme/colors";
import {
  spacing,
  fontSize,
  borderRadius,
  spacingV2,
  fontSizeV2,
  borderRadiusV2,
} from "../../theme/spacing";
import { shadowV2 } from "../../theme/designTokens";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import AsyncStorage from "@react-native-async-storage/async-storage";
const ALL_CROPS = [
  "西瓜",
  "豆角",
  "番茄",
  "黄瓜",
  "辣椒",
  "茄子",
  "草莓",
  "葡萄",
];

const showToast = (message: string) => {
  Alert.alert("提示", message, [{ text: "知道了" }]);
};

const SettingsSection: React.FC<{
  title: string;
  children: React.ReactNode;
}> = ({ title, children }) => (
  <View style={styles.section}>
    <Text style={styles.sectionTitle}>{title}</Text>
    <Card elevated={false} style={styles.menuCard}>
      {children}
    </Card>
  </View>
);

const MenuItem: React.FC<{
  icon: string;
  iconColor?: string;
  label: string;
  value?: string;
  onPress?: () => void;
  isLast?: boolean;
}> = ({ icon, iconColor = colors.primary, label, value, onPress, isLast }) => (
  <TouchableOpacity
    style={[styles.menuItem, !isLast && styles.menuItemBorder]}
    onPress={onPress}
    activeOpacity={onPress ? 0.6 : 1}
    disabled={!onPress}
  >
    <View style={styles.menuLeft}>
      <View style={[styles.menuIcon, { backgroundColor: iconColor + "12" }]}>
        <Icon name={icon} size={20} color={iconColor} />
      </View>
      <Text style={styles.menuText}>{label}</Text>
    </View>
    <View style={styles.menuRight}>
      {value ? <Text style={styles.menuValue}>{value}</Text> : null}
      {onPress ? (
        <Icon name="chevron-right" size={20} color={colors.textTertiary} />
      ) : null}
    </View>
  </TouchableOpacity>
);

const ToggleItem: React.FC<{
  icon: string;
  iconColor?: string;
  label: string;
  enabled: boolean;
  onToggle: (v: boolean) => void;
  isLast?: boolean;
}> = ({
  icon,
  iconColor = colors.primary,
  label,
  enabled,
  onToggle,
  isLast,
}) => (
  <View style={[styles.menuItem, !isLast && styles.menuItemBorder]}>
    <View style={styles.menuLeft}>
      <View style={[styles.menuIcon, { backgroundColor: iconColor + "12" }]}>
        <Icon name={icon} size={20} color={iconColor} />
      </View>
      <Text style={styles.menuText}>{label}</Text>
    </View>
    <Switch
      value={enabled}
      onValueChange={onToggle}
      trackColor={{ false: colors.border, true: colors.primaryLight + "80" }}
      thumbColor={enabled ? colors.primary : colors.disabled}
    />
  </View>
);

export const SettingsScreen: React.FC = () => {
  const navigation = useNavigation();
  const [cityPickerVisible, setCityPickerVisible] = useState(false);

  const logout = useAuthStore((s) => s.logout);

  const {
    defaultFarmName,
    defaultCity,
    crops,
    reminderTime,
    notificationEnabled,
    weatherAlertEnabled,
    displayName,
    setDefaultCity,
    setCrops,
    setNotificationEnabled,
    setWeatherAlertEnabled,
    setDisplayName,
    syncToServer,
  } = useSettingsStore();

  const handleLogout = useCallback(() => {
    Alert.alert("退出登录", "确定要退出登录吗？", [
      { text: "取消", style: "cancel" },
      {
        text: "确定",
        style: "destructive",
        onPress: async () => {
          await logout();
        },
      },
    ]);
  }, [logout]);

  const handleFarmPress = useCallback(() => {
    showToast("多农场管理即将上线");
  }, []);

  const handleExportData = useCallback(() => {
    showToast("数据导出即将上线");
  }, []);

  const handleClearCache = useCallback(() => {
    Alert.alert("清除缓存", "确定要清除所有本地缓存数据吗？", [
      { text: "取消", style: "cancel" },
      {
        text: "确定",
        style: "destructive",
        onPress: async () => {
          try {
            await AsyncStorage.clear();
            showToast("缓存已清除");
          } catch (_e) {
            showToast("清除失败，请重试");
          }
        },
      },
    ]);
  }, []);

  const handleDisplayNamePress = useCallback(() => {
    Alert.prompt(
      "AI 称呼我",
      "输入你希望 AI 怎么称呼你",
      [
        { text: "取消", style: "cancel" },
        {
          text: "确定",
          onPress: (value?: string) => {
            const trimmed = (value || "").trim();
            if (trimmed) {
              setDisplayName(trimmed);
            }
          },
        },
      ],
      "plain-text",
      displayName
    );
  }, [displayName, setDisplayName]);

  const handleCropPress = useCallback(() => {
    const currentCrops = new Set(crops);
    const options = ALL_CROPS.map((crop) => ({
      text: `${currentCrops.has(crop) ? "✓ " : ""}${crop}`,
      onPress: () => {
        const next = new Set(currentCrops);
        if (next.has(crop)) {
          next.delete(crop);
        } else {
          next.add(crop);
        }
        setCrops(Array.from(next));
      },
    }));
    Alert.alert("选择常种作物", "可多选（点击切换）", [
      ...options,
      { text: "完成", style: "cancel" },
    ]);
  }, [crops, setCrops]);

  const handleReminderTimePress = useCallback(() => {
    const times = ["06:00", "07:00", "08:00", "09:00", "10:00", "18:00"];
    Alert.alert(
      "选择提醒时间",
      undefined,
      times.map((t) => ({
        text: t,
        onPress: () => useSettingsStore.getState().setReminderTime(t),
      }))
    );
  }, []);

  const handleCitySelect = useCallback(
    (city: { name: string; lat: number; lon: number }) => {
      setDefaultCity(city.name);
      useAgentStore.getState().setCity(city.name, city.lat, city.lon);
      syncToServer(city.name, city.lat, city.lon);
    },
    [setDefaultCity, syncToServer]
  );

  const cropLabel = crops.length > 0 ? crops.join("、") : "未选择";

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity
            onPress={() => navigation.goBack()}
            style={styles.backBtn}
            activeOpacity={0.6}
          >
            <Icon name="chevron-left" size={28} color={colors.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>设置</Text>
          <View style={styles.backBtn} />
        </View>

        {/* Farm Settings */}
        <SettingsSection title="农场设置">
          <MenuItem
            icon="barn"
            iconColor={colors.success}
            label="默认农场"
            value={defaultFarmName}
            onPress={handleFarmPress}
          />
          <MenuItem
            icon="map-marker"
            iconColor={colors.primary}
            label="默认城市"
            value={defaultCity}
            onPress={() => setCityPickerVisible(true)}
            isLast
          />
        </SettingsSection>

        {/* Preference */}
        <SettingsSection title="偏好设置">
          <MenuItem
            icon="account-heart"
            iconColor={colors.aiPurple}
            label="AI 称呼我"
            value={displayName || "农友"}
            onPress={handleDisplayNamePress}
          />
          <MenuItem
            icon="sprout"
            iconColor={colors.success}
            label="常种作物"
            value={cropLabel}
            onPress={handleCropPress}
          />
          <MenuItem
            icon="clock-outline"
            iconColor="#14B8A6"
            label="提醒时间"
            value={reminderTime}
            onPress={handleReminderTimePress}
            isLast
          />
        </SettingsSection>

        {/* Notification */}
        <SettingsSection title="通知设置">
          <ToggleItem
            icon="bell-outline"
            iconColor={colors.aiPurple}
            label="农事提醒"
            enabled={notificationEnabled}
            onToggle={setNotificationEnabled}
          />
          <ToggleItem
            icon="weather-cloudy-alert"
            iconColor={colors.primary}
            label="天气预警"
            enabled={weatherAlertEnabled}
            onToggle={setWeatherAlertEnabled}
            isLast
          />
        </SettingsSection>

        {/* Data */}
        <SettingsSection title="数据管理">
          <MenuItem
            icon="database-export"
            iconColor={colors.primary}
            label="导出数据"
            onPress={handleExportData}
          />
          <MenuItem
            icon="trash-can-outline"
            iconColor={colors.danger}
            label="清除缓存"
            onPress={handleClearCache}
          />
          <MenuItem
            icon="logout"
            iconColor={colors.danger}
            label="退出登录"
            onPress={handleLogout}
            isLast
          />
        </SettingsSection>

        {/* About */}
        <SettingsSection title="关于">
          <MenuItem
            icon="tag"
            iconColor={colors.textTertiary}
            label="版本"
            value="v1.0"
          />
          <MenuItem
            icon="book-open-variant"
            iconColor={colors.success}
            label="使用指南"
            onPress={() => navigation.navigate("Guide" as never)}
          />
          <MenuItem
            icon="information"
            iconColor={colors.primary}
            label="关于"
            value="智能种植管理平台"
            isLast
          />
        </SettingsSection>
      </ScrollView>

      <CityPicker
        visible={cityPickerVisible}
        selectedCity={defaultCity}
        onSelect={handleCitySelect}
        onClose={() => setCityPickerVisible(false)}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.settingsBg,
  },
  scrollContent: {
    paddingBottom: spacing.xxl,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  backBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  section: {
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.lg,
  },
  sectionTitle: {
    fontSize: fontSize.md,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacing.md,
  },
  menuCard: {
    padding: 0,
    overflow: "hidden",
    borderRadius: borderRadiusV2.xxl,
    ...shadowV2.light,
  },
  menuItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacingV2.md,
    paddingHorizontal: spacingV2.md,
    height: 64,
  },
  menuItemBorder: {
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  menuLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  menuRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  menuIcon: {
    width: 36,
    height: 36,
    borderRadius: borderRadius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  menuText: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "500",
  },
  menuValue: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },
});
