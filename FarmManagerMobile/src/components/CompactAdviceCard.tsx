import React from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
} from "react-native";
import { colors } from "../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

export interface CompactAdviceCardProps {
  preview: string;
  itemCount: number;
  weatherCondition?: "sunny" | "rainy" | "foggy" | "cold";
  loading?: boolean;
  onPress?: () => void;
  onRefresh?: () => void;
}

const WEATHER_CONFIG = {
  sunny: { icon: "white-balance-sunny", bg: "#FDF6E3", color: "#C9A03F" },
  rainy: { icon: "weather-pouring", bg: "#E8F1FF", color: "#5B8DB8" },
  foggy: { icon: "weather-fog", bg: "#F0F4F8", color: "#7A8B9A" },
  cold: { icon: "snowflake", bg: "#E8F4FF", color: "#6B9AD8" },
};

const DEFAULT_FALLBACK = {
  sunny: "阳光正好，适合农作",
  rainy: "雨水充沛，防涝为主",
  foggy: "雾气朦胧，注意排湿",
  cold: "气温骤降，注意防冻",
};

export const CompactAdviceCard: React.FC<CompactAdviceCardProps> = ({
  preview,
  itemCount,
  weatherCondition = "sunny",
  loading = false,
  onPress,
  onRefresh,
}) => {
  const config = WEATHER_CONFIG[weatherCondition] ?? WEATHER_CONFIG.sunny;
  const displayText =
    preview || DEFAULT_FALLBACK[weatherCondition] || DEFAULT_FALLBACK.sunny;

  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.85}
      style={styles.card}
    >
      <View style={styles.contentRow}>
        <View style={[styles.iconCircle, { backgroundColor: config.bg }]}>
          <Icon name={config.icon} size={24} color={config.color} />
        </View>

        <View style={styles.middle}>
          <View style={styles.labelRow}>
            <View style={styles.aiIndicator}>
              <View style={styles.aiDot} />
              <Text style={styles.aiLabel}>AI 每日建议</Text>
            </View>
          </View>

          {loading ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator size="small" color={colors.primary} />
              <Text style={styles.loadingText}>正在分析农事数据...</Text>
            </View>
          ) : (
            <>
              <Text style={styles.previewText} numberOfLines={1}>
                {displayText}
              </Text>
              <Text style={styles.metaText}>
                {itemCount > 0 ? `${itemCount} 条建议待查看` : "暂无建议"}
              </Text>
            </>
          )}
        </View>

        <View style={styles.right}>
          {onRefresh && !loading && (
            <TouchableOpacity
              onPress={onRefresh}
              activeOpacity={0.7}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              style={styles.refreshBtn}
            >
              <Icon name="refresh" size={16} color={colors.textTertiary} />
            </TouchableOpacity>
          )}
          <Icon
            name="chevron-right"
            size={20}
            color={colors.textTertiary}
          />
        </View>
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    paddingVertical: 20,
    paddingHorizontal: spacingV2.lg,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  contentRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
  },
  iconCircle: {
    width: 48,
    height: 48,
    borderRadius: borderRadiusV2.lg,
    alignItems: "center",
    justifyContent: "center",
  },
  middle: {
    flex: 1,
    justifyContent: "center",
  },
  labelRow: {
    marginBottom: 4,
  },
  aiIndicator: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  aiDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: colors.aiPurple,
  },
  aiLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.aiPurple,
    letterSpacing: 0.3,
  },
  previewText: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    lineHeight: 22,
    marginBottom: 2,
  },
  metaText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  right: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.xs,
  },
  refreshBtn: {
    padding: spacingV2.xs,
  },
  loadingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
  },
  loadingText: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    fontWeight: "500",
  },
});
