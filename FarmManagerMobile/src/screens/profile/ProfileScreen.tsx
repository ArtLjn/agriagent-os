import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation } from "@react-navigation/native";
import type { CompositeNavigationProp } from "@react-navigation/native";
import type { BottomTabNavigationProp } from "@react-navigation/bottom-tabs";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useAuthStore } from "../../stores/authStore";
import { useSettingsStore } from "../../stores/settingsStore";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import { spacingV2, borderRadiusV2 } from "../../theme/spacing";
import { shadowV2 } from "../../theme/designTokens";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import type { MainTabParamList } from "../../navigation/MainTabNavigator";
import type { RootStackParamList } from "../../navigation/AppNavigator";

type ProfileNavigationProp = CompositeNavigationProp<
  BottomTabNavigationProp<MainTabParamList>,
  NativeStackNavigationProp<RootStackParamList>
>;

const MENU_ITEMS = [
  {
    icon: "cash-multiple",
    iconColor: colors.primary,
    label: "我的账本",
    targetTab: "Costs" as const,
  },
  {
    icon: "robot",
    iconColor: colors.aiPurple,
    label: "我的建议",
    targetTab: "AgentChat" as const,
  },
  {
    icon: "barn",
    iconColor: colors.success,
    label: "我的农场",
    action: "farm" as const,
  },
  {
    icon: "help-circle",
    iconColor: colors.primary,
    label: "帮助与反馈",
    action: "guide" as const,
  },
  {
    icon: "cog",
    iconColor: colors.textTertiary,
    label: "设置",
    action: "settings" as const,
  },
];

export const ProfileScreen: React.FC = () => {
  const navigation = useNavigation<ProfileNavigationProp>();
  const user = useAuthStore((s) => s.user);

  const handleMenuPress = (item: (typeof MENU_ITEMS)[number]) => {
    if (item.targetTab) {
      (navigation as any).navigate(item.targetTab);
    } else if (item.action === "settings") {
      // Settings 在 RootStack 中，需要通过 parent navigator 访问
      const parentNav = navigation.getParent();
      if (parentNav) {
        parentNav.navigate("Settings");
      }
    } else if (item.action === "guide") {
      // Guide 在 RootStack 中，需要通过 parent navigator 访问
      const parentNav = navigation.getParent();
      if (parentNav) {
        parentNav.navigate("Guide");
      }
    } else if (item.action === "farm") {
      // 我的农场 - 显示农场信息
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Profile Header */}
        <View style={styles.profileCard}>
          <View style={styles.avatar}>
            <Icon name="account" size={40} color={colors.primary} />
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.profileName}>{user?.nickname || "农友"}</Text>
            <Text style={styles.profileSub}>让种植更简单</Text>
          </View>
        </View>

        {/* Menu List */}
        <View style={styles.menuCard}>
          {MENU_ITEMS.map((item, index) => (
            <TouchableOpacity
              key={item.label}
              style={[
                styles.menuItem,
                index < MENU_ITEMS.length - 1 && styles.menuItemBorder,
              ]}
              onPress={() => handleMenuPress(item)}
              activeOpacity={0.6}
            >
              <View style={styles.menuLeft}>
                <View
                  style={[
                    styles.menuIcon,
                    { backgroundColor: item.iconColor + "12" },
                  ]}
                >
                  <Icon name={item.icon} size={20} color={item.iconColor} />
                </View>
                <Text style={styles.menuText}>{item.label}</Text>
              </View>
              <Icon
                name="chevron-right"
                size={20}
                color={colors.textTertiary}
              />
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.settingsBg,
  },
  scrollContent: {
    padding: spacing.lg,
    gap: spacing.lg,
  },
  profileCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    padding: spacingV2.lg,
    ...shadowV2.light,
  },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  profileInfo: {
    flex: 1,
  },
  profileName: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.text,
  },
  profileSub: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 4,
  },
  menuCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    overflow: "hidden",
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
});
