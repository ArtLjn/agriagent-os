import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  LayoutAnimation,
  Platform,
  UIManager,
} from "react-native";
import LinearGradient from "react-native-linear-gradient";
import { Loading } from "./Loading";
import { MarkdownText } from "./MarkdownText";
import type { AdviceItem } from "../api/types";
import { colors } from "../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../theme/spacing";
import { appGradients } from "../theme/gradients";
import { shadowV2 } from "../theme/designTokens";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

if (Platform.OS === "android") {
  UIManager.setLayoutAnimationEnabledExperimental?.(true);
}

interface AdviceCardProps {
  advice: string | null;
  items?: AdviceItem[] | null;
  loading?: boolean;
  onPress?: () => void;
  onRefresh?: () => void;
  weatherCondition?: "foggy" | "sunny" | "rainy" | "cold";
}

const MAX_LINES = 4;

const getEmotionGradient = (condition?: string) => {
  switch (condition) {
    case "foggy":
      return appGradients.emotionFoggy;
    case "rainy":
      return appGradients.emotionRainy;
    case "cold":
      return appGradients.emotionCold;
    case "sunny":
    default:
      return appGradients.emotionSunny;
  }
};

const getEmotionTitle = (condition?: string) => {
  switch (condition) {
    case "foggy":
      return "雾气朦胧，注意排湿";
    case "rainy":
      return "雨水充沛，防涝为主";
    case "cold":
      return "气温骤降，注意防冻";
    case "sunny":
    default:
      return "阳光正好，适合农作";
  }
};

export const AdviceCard: React.FC<AdviceCardProps> = ({
  advice,
  items,
  loading = false,
  onPress,
  onRefresh,
  weatherCondition = "sunny",
}) => {
  const [expanded, setExpanded] = useState(false);
  const gradient = getEmotionGradient(weatherCondition);

  const handleToggle = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpanded(!expanded);
  };

  const hasItems = items && items.length > 0;

  return (
    <LinearGradient {...gradient} style={[styles.card, shadowV2.light]}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.iconCircle}>
          <Icon name="sprout" size={20} color={colors.success} />
        </View>
        <View style={styles.headerText}>
          <Text style={styles.title}>{getEmotionTitle(weatherCondition)}</Text>
          <Text style={styles.subtitle}>AI 农事顾问</Text>
        </View>
        {onRefresh && (
          <TouchableOpacity
            onPress={onRefresh}
            activeOpacity={0.7}
            style={styles.refreshBtn}
          >
            <Icon name="refresh" size={16} color={colors.textTertiary} />
          </TouchableOpacity>
        )}
      </View>

      {/* Content */}
      {loading && (
        <View style={styles.center}>
          <Loading />
          <Text style={styles.hint}>AI 正在分析天气和作物数据...</Text>
        </View>
      )}

      {!loading && !advice && !hasItems && (
        <View style={styles.center}>
          <Icon
            name="information-outline"
            size={32}
            color={colors.textTertiary}
          />
          <Text style={styles.hint}>暂无建议，请稍后重试</Text>
        </View>
      )}

      {!loading && hasItems && (
        <View style={styles.itemsContainer}>
          {items.map((item, index) => (
            <View key={index} style={styles.itemCard}>
              <View style={styles.itemTopRow}>
                <Text style={styles.itemTitle}>{item.title}</Text>
              </View>
              <Text style={styles.itemDetail} numberOfLines={2}>
                {item.detail}
              </Text>
            </View>
          ))}
        </View>
      )}

      {!loading && !hasItems && advice && (
        <>
          <View
            style={[
              styles.contentWrapper,
              !expanded && styles.contentCollapsed,
            ]}
          >
            <MarkdownText text={advice} baseStyle={styles.adviceText} />
          </View>
          {advice.split("\n").length > MAX_LINES && (
            <TouchableOpacity
              onPress={handleToggle}
              style={styles.toggleBtn}
              activeOpacity={0.7}
            >
              <Text style={styles.toggleText}>
                {expanded ? "收起" : "展开更多"}
              </Text>
              <Icon
                name={expanded ? "chevron-up" : "chevron-down"}
                size={16}
                color={colors.primary}
              />
            </TouchableOpacity>
          )}
        </>
      )}

      {!loading && (advice || hasItems) && (
        <View style={styles.actionBar}>
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={onPress}
            activeOpacity={0.7}
          >
            <Icon
              name="chat-processing-outline"
              size={18}
              color={colors.primary}
            />
            <Text style={styles.actionText}>继续咨询</Text>
          </TouchableOpacity>
        </View>
      )}
    </LinearGradient>
  );
};

const styles = StyleSheet.create({
  card: {
    borderRadius: borderRadiusV2.xxxl,
    padding: spacingV2.xl,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacingV2.md,
    gap: spacingV2.sm,
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.successMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  headerText: {
    flex: 1,
  },
  title: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
  },
  subtitle: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    marginTop: 2,
  },
  refreshBtn: {
    padding: spacingV2.xs,
  },
  center: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacingV2.xl,
    gap: spacingV2.sm,
  },
  hint: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  contentWrapper: {
    overflow: "hidden",
  },
  contentCollapsed: {
    maxHeight: 140,
  },
  adviceText: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    lineHeight: 24,
  },
  toggleBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacingV2.sm,
    paddingVertical: spacingV2.xs,
  },
  toggleText: {
    fontSize: fontSizeV2.sm,
    color: colors.primary,
    fontWeight: "600",
    marginRight: 2,
  },
  itemsContainer: {
    gap: spacingV2.sm,
  },
  itemCard: {
    backgroundColor: "rgba(255,255,255,0.6)",
    borderRadius: borderRadiusV2.lg,
    padding: spacingV2.md,
  },
  itemTopRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacingV2.xs,
  },
  itemTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
  },
  itemDetail: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  actionBar: {
    flexDirection: "row",
    justifyContent: "flex-end",
    marginTop: spacingV2.md,
    paddingTop: spacingV2.md,
    borderTopWidth: 1,
    borderTopColor: "rgba(0,0,0,0.06)",
  },
  actionBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.xs,
    backgroundColor: "rgba(255,255,255,0.7)",
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.md,
  },
  actionText: {
    fontSize: fontSizeV2.sm,
    color: colors.primary,
    fontWeight: "600",
  },
});
