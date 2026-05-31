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
import { shadowV2 } from "../theme/designTokens";
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
  sunny: { emoji: "🌾", bg: "#FDF6E3" },
  rainy: { emoji: "🌧️", bg: "#E8F1FF" },
  foggy: { emoji: "🌫️", bg: "#F0F4F8" },
  cold: { emoji: "❄️", bg: "#E8F4FF" },
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
      style={[styles.card, shadowV2.light]}
    >
      {/* Left: Weather Emoji Circle */}
      <View style={[styles.iconCircle, { backgroundColor: config.bg }]}>
        <Text style={styles.emoji}>{config.emoji}</Text>
      </View>

      {/* Middle: Preview Text + Item Count */}
      <View style={styles.middle}>
        {loading ? (
          <View style={styles.loadingRow}>
            <ActivityIndicator size="small" color={colors.primary} />
            <Text style={styles.loadingText}>AI 正在分析...</Text>
          </View>
        ) : (
          <>
            <Text style={styles.previewText} numberOfLines={1}>
              {displayText}
            </Text>
            <Text style={styles.itemCountText}>
              {itemCount > 0 ? `${itemCount} 条建议` : "暂无建议"}
            </Text>
          </>
        )}
      </View>

      {/* Right: Chevron or Refresh */}
      <View style={styles.right}>
        {onRefresh && !loading && (
          <TouchableOpacity
            onPress={onRefresh}
            activeOpacity={0.7}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            style={styles.refreshBtn}
          >
            <Icon
              name="refresh"
              size={16}
              color={colors.textTertiary}
            />
          </TouchableOpacity>
        )}
        <Icon
          name="chevron-right"
          size={20}
          color={colors.textTertiary}
        />
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    height: 88,
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    gap: spacingV2.md,
  },
  iconCircle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
  },
  emoji: {
    fontSize: 28,
    lineHeight: 32,
  },
  middle: {
    flex: 1,
    justifyContent: "center",
  },
  previewText: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    lineHeight: 22,
  },
  itemCountText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 2,
    lineHeight: 18,
  },
  right: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
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
    fontWeight: "600",
  },
});
