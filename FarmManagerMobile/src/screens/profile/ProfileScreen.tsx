import React, { useEffect } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from "react-native";
import LinearGradient from "react-native-linear-gradient";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation } from "@react-navigation/native";
import type { CompositeNavigationProp } from "@react-navigation/native";
import type { BottomTabNavigationProp } from "@react-navigation/bottom-tabs";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useAuthStore } from "../../stores/authStore";
import { useCycleStore } from "../../stores/cycleStore";
import { colors } from "../../theme/colors";
import { farmTheme } from "../../theme/farmTheme";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import type { MainTabParamList } from "../../navigation/MainTabNavigator";
import type { RootStackParamList } from "../../navigation/AppNavigator";

type ProfileNavigationProp = CompositeNavigationProp<
  BottomTabNavigationProp<MainTabParamList>,
  NativeStackNavigationProp<RootStackParamList>
>;

const FARM_MENU = [
  {
    icon: "view-dashboard",
    iconColor: farmTheme.colors.leaf,
    label: "农场概览",
    action: "dashboard" as const,
  },
  {
    icon: "cash-multiple",
    iconColor: colors.income,
    label: "我的账本",
    targetTab: "Costs" as const,
  },
  {
    icon: "sprout",
    iconColor: colors.success,
    label: "种植规划",
    targetTab: "CycleList" as const,
  },
  {
    icon: "seed",
    iconColor: colors.warning,
    label: "作物模板",
    targetTab: "CropTemplate" as const,
  },
];

const SETTINGS_ITEM = {
  icon: "cog",
  iconColor: colors.textSecondary,
  label: "设置",
  action: "settings" as const,
};

function getFarmAge(cycles: { start_date: string }[]): number {
  if (cycles.length === 0) return 0;
  const earliest = new Date(
    Math.min(...cycles.map((c) => new Date(c.start_date).getTime()))
  );
  const diff = Date.now() - earliest.getTime();
  return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
}

export const ProfileScreen: React.FC = () => {
  const navigation = useNavigation<ProfileNavigationProp>();
  const user = useAuthStore((s) => s.user);
  const { cycles, fetchCycles } = useCycleStore();

  useEffect(() => {
    fetchCycles();
  }, [fetchCycles]);

  const activeCount = cycles.filter((c) => c.status === "active").length;
  const farmAge = getFarmAge(cycles);

  const handleFarmPress = (item: (typeof FARM_MENU)[number]) => {
    if ("action" in item && item.action === "dashboard") {
      const parentNav = navigation.getParent();
      if (parentNav) parentNav.navigate("FarmDashboard");
    } else if ("targetTab" in item && item.targetTab) {
      (navigation as any).navigate(item.targetTab);
    }
  };

  const handleSettingsPress = () => {
    const parentNav = navigation.getParent();
    if (parentNav) parentNav.navigate("Settings");
  };

  const renderFarmMenu = () => (
    <View style={styles.group}>
      <Text style={styles.groupTitle}>农场管理</Text>
      <View style={styles.menuCard}>
        {FARM_MENU.map((item, index) => (
          <TouchableOpacity
            key={item.label}
            style={[
              styles.menuItem,
              index < FARM_MENU.length - 1 && styles.menuItemBorder,
            ]}
            onPress={() => handleFarmPress(item)}
            activeOpacity={0.6}
          >
            <View style={styles.menuLeft}>
              <Icon name={item.icon} size={20} color={item.iconColor} />
              <Text style={styles.menuText}>{item.label}</Text>
            </View>
            <Icon name="chevron-right" size={20} color={colors.textTertiary} />
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Profile Header */}
        <LinearGradient
          colors={["#213327", "#4F8B56", "#EAF6DF"]}
          locations={[0, 0.6, 1]}
          start={{ x: 0, y: 0 }}
          end={{ x: 0, y: 1 }}
          style={styles.profileSection}
        >
          {/* Decorative circles */}
          <View style={styles.decoCircleLarge} />
          <View style={styles.decoCircleSmall} />

          <View style={styles.avatarWrap}>
            <View style={styles.avatar}>
              <Icon name="account" size={36} color={farmTheme.colors.leaf} />
            </View>
          </View>
          <Text style={styles.profileName}>{user?.nickname || "农友"}</Text>
          {farmAge > 0 && (
            <View style={styles.ageBadge}>
              <Text style={styles.ageText}>已种植 {farmAge} 天</Text>
            </View>
          )}
        </LinearGradient>

        {/* Stats */}
        <View style={styles.statsCard}>
          <View style={styles.statItem}>
            <Text style={styles.statNumber}>{cycles.length}</Text>
            <Text style={styles.statLabel}>总茬口</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <Text style={[styles.statNumber, styles.statActive]}>
              {activeCount}
            </Text>
            <Text style={styles.statLabel}>进行中</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <Text style={styles.statNumber}>—</Text>
            <Text style={styles.statLabel}>本月花费</Text>
          </View>
        </View>

        {/* Farm Menu */}
        {renderFarmMenu()}

        {/* Settings Entry */}
        <TouchableOpacity
          style={styles.settingsRow}
          onPress={handleSettingsPress}
          activeOpacity={0.6}
        >
          <View style={styles.settingsLeft}>
            <Icon
              name={SETTINGS_ITEM.icon}
              size={20}
              color={SETTINGS_ITEM.iconColor}
            />
            <Text style={styles.menuText}>{SETTINGS_ITEM.label}</Text>
          </View>
          <Icon name="chevron-right" size={20} color={colors.textTertiary} />
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: farmTheme.colors.page,
  },
  scrollContent: {
    padding: spacingV2.lg,
    paddingBottom: spacingV2.xxxl,
  },
  // Profile Header
  profileSection: {
    alignItems: "center",
    paddingVertical: spacingV2.xl + 8,
    gap: spacingV2.sm,
    borderRadius: borderRadiusV2.xxxl,
    marginBottom: spacingV2.lg,
    overflow: "hidden",
  },
  decoCircleLarge: {
    position: "absolute",
    width: 200,
    height: 200,
    borderRadius: 100,
    backgroundColor: "rgba(216, 240, 188, 0.18)",
    top: -60,
    right: -40,
  },
  decoCircleSmall: {
    position: "absolute",
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: "rgba(255, 255, 255, 0.16)",
    top: 20,
    left: 20,
  },
  avatarWrap: {
    marginBottom: spacingV2.sm,
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: "rgba(22, 182, 122, 0.18)",
  },
  profileName: {
    fontSize: fontSizeV2.xl,
    fontWeight: "800",
    color: colors.text,
    letterSpacing: -0.3,
  },
  ageBadge: {
    backgroundColor: colors.successMuted,
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: borderRadiusV2.full,
    marginTop: 2,
  },
  ageText: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.success,
  },
  // Stats
  statsCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    paddingVertical: spacingV2.xl,
    marginBottom: spacingV2.xxl,
    ...farmTheme.shadow.card,
  },
  statItem: {
    alignItems: "center",
    gap: 4,
    flex: 1,
  },
  statNumber: {
    fontSize: fontSizeV2.xxl,
    fontWeight: "800",
    color: colors.text,
    letterSpacing: -0.5,
  },
  statActive: {
    color: colors.success,
  },
  statLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  statDivider: {
    width: 1,
    height: 32,
    backgroundColor: colors.borderLight,
  },
  // Menu Group
  group: {
    marginBottom: spacingV2.xl,
  },
  groupTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacingV2.md,
    marginLeft: 4,
  },
  menuCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    overflow: "hidden",
    ...farmTheme.shadow.card,
  },
  menuItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacingV2.md + 2,
    paddingHorizontal: spacingV2.lg,
  },
  menuItemBorder: {
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  menuLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
  },
  menuText: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "500",
  },
  // Settings Entry
  settingsRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    paddingVertical: spacingV2.md + 2,
    paddingHorizontal: spacingV2.lg,
    ...farmTheme.shadow.card,
  },
  settingsLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
  },
});
