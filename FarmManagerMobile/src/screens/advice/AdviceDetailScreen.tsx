import React, { useEffect } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { useRoute, useNavigation, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import LinearGradient from "react-native-linear-gradient";
import { SafeAreaView } from "react-native-safe-area-context";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useAgentStore } from "../../stores/agentStore";
import type { AdviceItem } from "../../api/types";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import { appGradients } from "../../theme/gradients";
import { shadowV2 } from "../../theme/designTokens";

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
  sunny: { emoji: "🌾", gradient: appGradients.emotionSunny },
  rainy: { emoji: "🌧️", gradient: appGradients.emotionRainy },
  foggy: { emoji: "🌫️", gradient: appGradients.emotionFoggy },
  cold: { emoji: "❄️", gradient: appGradients.emotionCold },
};

const DEFAULT_FALLBACK = {
  sunny: "阳光正好，适合农作",
  rainy: "雨水充沛，防涝为主",
  foggy: "雾气朦胧，注意排湿",
  cold: "气温骤降，注意防冻",
};

const PRIORITY_COLORS: Record<number, string> = {
  1: colors.danger,
  2: colors.warning,
  3: colors.info,
};

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

  const displayItems: AdviceItem[] = items && items.length > 0
    ? items
    : dailyAdvice?.items || [];

  const displayPreview = preview || dailyAdvice?.preview || "今日农事建议";
  const displayDate = createdAt || dailyAdvice?.created_at || new Date().toLocaleDateString("zh-CN");
  const weatherKey = weatherCondition || "sunny";
  const weatherConf = WEATHER_CONFIG[weatherKey] || WEATHER_CONFIG.sunny;
  const fallbackText = DEFAULT_FALLBACK[weatherKey] || DEFAULT_FALLBACK.sunny;

  const handleConsult = () => {
    navigation.navigate("AgentChat");
  };

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <LinearGradient {...weatherConf.gradient} style={StyleSheet.absoluteFill} />

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Header Area */}
        <View style={styles.header}>
          <Text style={styles.weatherEmoji}>{weatherConf.emoji}</Text>
          <Text style={styles.previewText}>
            {displayPreview || fallbackText}
          </Text>
          <Text style={styles.dateText}>{displayDate}</Text>
        </View>

        {/* Advice List */}
        {loading && displayItems.length === 0 ? (
          <View style={styles.loadingBox}>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={styles.loadingText}>正在获取建议...</Text>
          </View>
        ) : (
          <View style={styles.listContainer}>
            {displayItems.map((item, index) => (
              <View key={index} style={styles.card}>
                <View
                  style={[
                    styles.priorityBar,
                    { backgroundColor: PRIORITY_COLORS[item.priority] || colors.info },
                  ]}
                />
                <View style={styles.cardContent}>
                  <Text style={styles.cardIcon}>{item.icon}</Text>
                  <View style={styles.cardTextBlock}>
                    <Text style={styles.cardTitle}>{item.title}</Text>
                    <Text style={styles.cardDetail}>{item.detail}</Text>
                  </View>
                </View>
              </View>
            ))}
          </View>
        )}
      </ScrollView>

      {/* Bottom Action Button */}
      <View style={styles.bottomBar}>
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={handleConsult}
          activeOpacity={0.8}
        >
          <LinearGradient
            colors={[colors.primary, colors.primaryLight]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={styles.actionBtnGradient}
          >
            <Icon name="chat-processing" size={20} color="#FFFFFF" />
            <Text style={styles.actionBtnText}>咨询农事顾问</Text>
          </LinearGradient>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: spacingV2.xxl,
  },

  // ─── Header ───
  header: {
    alignItems: "center",
    paddingTop: spacingV2.xl,
    paddingBottom: spacingV2.xxl,
    paddingHorizontal: spacingV2.lg,
  },
  weatherEmoji: {
    fontSize: 48,
    marginBottom: spacingV2.md,
  },
  previewText: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
    textAlign: "center",
    marginBottom: spacingV2.sm,
  },
  dateText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    textAlign: "center",
  },

  // ─── Loading ───
  loadingBox: {
    alignItems: "center",
    paddingVertical: spacingV2.xxxl,
  },
  loadingText: {
    marginTop: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
  },

  // ─── List ───
  listContainer: {
    paddingHorizontal: spacingV2.lg,
    gap: 12,
  },
  card: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    overflow: "hidden",
    ...shadowV2.light,
  },
  priorityBar: {
    width: 4,
  },
  cardContent: {
    flexDirection: "row",
    alignItems: "flex-start",
    padding: spacingV2.md,
    flex: 1,
  },
  cardIcon: {
    fontSize: 20,
    marginRight: spacingV2.md,
    marginTop: 2,
  },
  cardTextBlock: {
    flex: 1,
  },
  cardTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    marginBottom: 4,
  },
  cardDetail: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },

  // ─── Bottom Action ───
  bottomBar: {
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  actionBtn: {
    borderRadius: borderRadiusV2.lg,
    overflow: "hidden",
  },
  actionBtnGradient: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 14,
    gap: 8,
  },
  actionBtnText: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
    color: "#FFFFFF",
  },
});
