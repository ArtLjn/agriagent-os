import React, { useEffect } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import {
  useRoute,
  useNavigation,
  type RouteProp,
} from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { SafeAreaView } from "react-native-safe-area-context";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useAgentStore } from "../../stores/agentStore";
import type { AdviceItem } from "../../api/types";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";

export type RootStackParamList = {
  AdviceDetail: {
    items?: AdviceItem[];
    preview?: string;
    weatherCondition?: "sunny" | "rainy" | "foggy" | "cold";
    createdAt?: string;
  };
  AgentChat: { cycleId?: number };
};

type RouteParams = RouteProp<RootStackParamList, "AdviceDetail">;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const WEATHER_CONFIG = {
  sunny: { icon: "white-balance-sunny", label: "晴", bg: "#FEF9EE", accent: "#C9A03F" },
  rainy: { icon: "weather-pouring", label: "雨", bg: "#EDF4FF", accent: "#5B8DB8" },
  foggy: { icon: "weather-fog", label: "雾", bg: "#F1F5F9", accent: "#7A8B9A" },
  cold: { icon: "snowflake", label: "寒", bg: "#EBF4FF", accent: "#6B9AD8" },
};

const DEFAULT_FALLBACK = {
  sunny: "阳光正好，适合农作",
  rainy: "雨水充沛，防涝为主",
  foggy: "雾气朦胧，注意排湿",
  cold: "气温骤降，注意防冻",
};

const PRIORITY_CONFIG: Record<
  number,
  { color: string; label: string; bg: string; dot: string }
> = {
  1: { color: colors.danger, label: "紧急", bg: colors.dangerLight, dot: "#C45B5B" },
  2: { color: colors.warning, label: "重要", bg: colors.warningLight, dot: "#D49A4A" },
  3: { color: colors.info, label: "提醒", bg: colors.infoLight, dot: "#5B8DB8" },
};

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  });
}

export const AdviceDetailScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const navigation = useNavigation<NavigationProp>();
  const { items, preview, weatherCondition, createdAt } = route.params || {};

  const { dailyAdvice, fetchDailyAdvice, loading } = useAgentStore();

  useEffect(() => {
    if (!items || items.length === 0) {
      fetchDailyAdvice();
    }
  }, [items, fetchDailyAdvice]);

  const displayItems: AdviceItem[] =
    items && items.length > 0 ? items : dailyAdvice?.items || [];

  const displayPreview =
    preview || dailyAdvice?.preview || "今日农事建议";
  const displayDate =
    createdAt || dailyAdvice?.created_at || new Date().toISOString();
  const weatherKey = weatherCondition || "sunny";
  const weatherConf = WEATHER_CONFIG[weatherKey] || WEATHER_CONFIG.sunny;
  const fallbackText =
    DEFAULT_FALLBACK[weatherKey] || DEFAULT_FALLBACK.sunny;

  // 分离 Hero（最紧急）和其余建议
  const sortedItems = [...displayItems].sort((a, b) => a.priority - b.priority);
  const heroItem = sortedItems[0];
  const remainingItems = sortedItems.slice(1);

  const handleConsult = () => {
    navigation.navigate("AgentChat" as never);
  };

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerTopRow}>
          <TouchableOpacity
            style={styles.backBtn}
            onPress={() => navigation.goBack()}
            activeOpacity={0.7}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Icon name="arrow-left" size={22} color={colors.text} />
          </TouchableOpacity>

          <View style={styles.dateRow}>
            <View
              style={[
                styles.weatherBadge,
                { backgroundColor: weatherConf.bg },
              ]}
            >
              <Icon
                name={weatherConf.icon}
                size={13}
                color={weatherConf.accent}
              />
              <Text style={[styles.weatherLabel, { color: weatherConf.accent }]}>
                {weatherConf.label}
              </Text>
            </View>
            <Text style={styles.dateText}>{formatDate(displayDate)}</Text>
          </View>
        </View>

        <View style={styles.headerContent}>
          <Text style={styles.previewText}>
            {displayPreview || fallbackText}
          </Text>

          <View style={styles.aiBadge}>
            <View style={styles.aiDot} />
            <Text style={styles.aiBadgeText}>AI 农事分析</Text>
          </View>
        </View>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {loading && displayItems.length === 0 ? (
          <View style={styles.loadingBox}>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={styles.loadingText}>正在获取建议...</Text>
          </View>
        ) : (
          <View style={styles.listContainer}>
            {/* Hero Card — 最紧急建议 */}
            {heroItem && (
              <View
                style={[
                  styles.heroCard,
                  { backgroundColor: weatherConf.bg },
                ]}
              >
                <View style={styles.heroContent}>
                  <View style={styles.heroHeader}>
                    <Text style={styles.heroIcon}>{heroItem.icon}</Text>
                    {(() => {
                      const cfg =
                        PRIORITY_CONFIG[heroItem.priority] || PRIORITY_CONFIG[3];
                      return (
                        <View
                          style={[
                            styles.heroPriorityBadge,
                            { backgroundColor: cfg.bg },
                          ]}
                        >
                          <Text
                            style={[
                              styles.heroPriorityText,
                              { color: cfg.color },
                            ]}
                          >
                            {cfg.label}
                          </Text>
                        </View>
                      );
                    })()}
                  </View>
                  <Text style={styles.heroTitle}>{heroItem.title}</Text>
                  <Text style={styles.heroDetail}>{heroItem.detail}</Text>
                </View>

                {/* 装饰圆点 */}
                <View style={[styles.heroDeco, { backgroundColor: weatherConf.accent + "10" }]}>
                  <Text style={[styles.heroDecoIcon, { color: weatherConf.accent + "30" }]}>
                    {heroItem.icon}
                  </Text>
                </View>
              </View>
            )}

            {/* 其余建议列表 */}
            {remainingItems.length > 0 && (
              <>
                <View style={styles.sectionHeader}>
                  <Text style={styles.sectionTitle}>更多建议</Text>
                  <Text style={styles.sectionCount}>
                    {remainingItems.length} 条
                  </Text>
                </View>

                {remainingItems.map((item, index) => {
                  const cfg =
                    PRIORITY_CONFIG[item.priority] || PRIORITY_CONFIG[3];
                  return (
                    <View key={index} style={styles.compactCard}>
                      <View style={styles.compactLeft}>
                        <View
                          style={[
                            styles.priorityDot,
                            { backgroundColor: cfg.dot },
                          ]}
                        />
                      </View>
                      <View style={styles.compactBody}>
                        <View style={styles.compactHeader}>
                          <Text style={styles.compactTitle}>{item.title}</Text>
                          <Text
                            style={[
                              styles.compactPriority,
                              { color: cfg.color },
                            ]}
                          >
                            {cfg.label}
                          </Text>
                        </View>
                        <Text style={styles.compactDetail}>{item.detail}</Text>
                      </View>
                    </View>
                  );
                })}
              </>
            )}
          </View>
        )}
      </ScrollView>

      {/* Bottom Action */}
      <View style={styles.bottomBar}>
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={handleConsult}
          activeOpacity={0.8}
        >
          <Icon name="chat-processing-outline" size={18} color="#FFFFFF" />
          <Text style={styles.actionBtnText}>咨询农事顾问</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.sm,
    paddingBottom: spacingV2.xl,
  },
  headerTopRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.lg,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: borderRadiusV2.md,
    backgroundColor: colors.surfaceMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  dateRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
  },
  weatherBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: borderRadiusV2.sm,
  },
  weatherLabel: {
    fontSize: 12,
    fontWeight: "600",
  },
  dateText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  headerContent: {
    gap: spacingV2.sm,
  },
  previewText: {
    fontSize: fontSizeV2.xxl,
    fontWeight: "800",
    color: colors.text,
    letterSpacing: -0.5,
    lineHeight: 36,
  },
  aiBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    marginTop: 2,
  },
  aiDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: colors.aiPurple,
  },
  aiBadgeText: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.aiPurple,
    letterSpacing: 0.3,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingBottom: spacingV2.xxxl,
  },
  loadingBox: {
    alignItems: "center",
    paddingVertical: spacingV2.xxxl,
  },
  loadingText: {
    marginTop: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
  },
  listContainer: {
    paddingHorizontal: spacingV2.lg,
    gap: spacingV2.lg,
  },
  // Hero Card
  heroCard: {
    borderRadius: borderRadiusV2.xxxl,
    padding: spacingV2.xl,
    overflow: "hidden",
    position: "relative",
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  heroContent: {
    gap: spacingV2.sm,
    zIndex: 1,
  },
  heroHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  heroIcon: {
    fontSize: 32,
  },
  heroPriorityBadge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: borderRadiusV2.sm,
  },
  heroPriorityText: {
    fontSize: 12,
    fontWeight: "700",
  },
  heroTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
    lineHeight: 26,
  },
  heroDetail: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  heroDeco: {
    position: "absolute",
    right: -20,
    bottom: -20,
    width: 100,
    height: 100,
    borderRadius: 50,
    alignItems: "center",
    justifyContent: "center",
  },
  heroDecoIcon: {
    fontSize: 48,
  },
  // Section Header
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacingV2.sm,
    marginBottom: -4,
  },
  sectionTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
  },
  sectionCount: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
  },
  // Compact Card
  compactCard: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.lg,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.03,
    shadowRadius: 8,
    elevation: 1,
    gap: spacingV2.md,
  },
  compactLeft: {
    paddingTop: 4,
  },
  priorityDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  compactBody: {
    flex: 1,
    gap: 2,
  },
  compactHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacingV2.sm,
  },
  compactTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
    color: colors.text,
    flex: 1,
  },
  compactPriority: {
    fontSize: 12,
    fontWeight: "600",
  },
  compactDetail: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  // Bottom
  bottomBar: {
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  actionBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primary,
    borderRadius: borderRadiusV2.lg,
    paddingVertical: 14,
    gap: spacingV2.sm,
    height: 48,
  },
  actionBtnText: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: "#FFFFFF",
  },
});
