import React from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from "react-native";
import LinearGradient from "react-native-linear-gradient";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation, useRoute } from "@react-navigation/native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import { shadowV2 } from "../../theme/designTokens";

const SEVERITY_CONFIG: Record<
  string,
  { label: string; color: string; bgColor: string; icon: string; desc: string }
> = {
  RED: {
    label: "红色",
    color: "#C0392B",
    bgColor: "#FDEBEB",
    icon: "alert-octagon",
    desc: "特别严重",
  },
  ORANGE: {
    label: "橙色",
    color: "#E67E22",
    bgColor: "#FEF3E2",
    icon: "alert",
    desc: "严重",
  },
  YELLOW: {
    label: "黄色",
    color: "#D4A017",
    bgColor: "#FEF9E7",
    icon: "alert-circle",
    desc: "较重",
  },
  BLUE: {
    label: "蓝色",
    color: "#2E86C1",
    bgColor: "#EBF5FB",
    icon: "information",
    desc: "一般",
  },
};

const ORDER: Record<string, number> = { RED: 0, ORANGE: 1, YELLOW: 2, BLUE: 3 };

const parseAlert = (raw: string) => {
  const match = raw.match(/^\[(RED|ORANGE|YELLOW|BLUE)\]\s*/);
  if (match) {
    return {
      severity: match[1],
      title: raw.replace(match[0], ""),
      desc: "",
    };
  }
  const parts = raw.split(": ", 2);
  const title = parts[0] ?? raw;
  const desc = parts[1] ?? "";
  let severity = "BLUE";
  if (title.includes("红色")) {
    severity = "RED";
  } else if (title.includes("橙色")) {
    severity = "ORANGE";
  } else if (title.includes("黄色")) {
    severity = "YELLOW";
  }
  return { severity, title, desc };
};

interface AlertCardProps {
  alert: { severity: string; title: string; desc: string };
}

const AlertCard: React.FC<AlertCardProps> = ({ alert }) => {
  const [expanded, setExpanded] = React.useState(false);
  const cfg = SEVERITY_CONFIG[alert.severity] ?? SEVERITY_CONFIG.BLUE;

  return (
    <View style={[styles.card, shadowV2.light]}>
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={() => setExpanded(!expanded)}
        style={styles.cardTouchable}
      >
        {/* 顶部色带 */}
        <View style={[styles.severityStripe, { backgroundColor: cfg.color }]} />

        <View style={styles.cardContent}>
          {/* 严重级别标签 */}
          <View style={styles.cardHeader}>
            <View
              style={[styles.badge, { backgroundColor: cfg.bgColor }]}
            >
              <Icon name={cfg.icon as any} size={14} color={cfg.color} />
              <Text style={[styles.badgeText, { color: cfg.color }]}>
                {cfg.label}预警
              </Text>
            </View>
            <Icon
              name={expanded ? "chevron-up" : "chevron-down"}
              size={18}
              color={colors.textTertiary}
            />
          </View>

          {/* 标题 */}
          <Text style={styles.cardTitle}>{alert.title}</Text>

          {/* 展开详情 */}
          {expanded && (
            <View style={styles.detailBox}>
              <Text style={styles.detailText}>
                {alert.desc ||
                  "请关注当地气象部门发布的最新预警信息，及时采取防护措施，确保人身和财产安全。"}
              </Text>
            </View>
          )}
        </View>
      </TouchableOpacity>
    </View>
  );
};

export const WeatherAlertScreen: React.FC = () => {
  const navigation = useNavigation();
  const route = useRoute() as { params?: { warnings?: string[]; cityName?: string } };
  const { warnings = [], cityName = "" } = route.params ?? {};


  const parsed = warnings.map(parseAlert);
  const sorted = [...parsed].sort(
    (a, b) => (ORDER[a.severity] ?? 3) - (ORDER[b.severity] ?? 3)
  );

  const highest = sorted[0]?.severity ?? "BLUE";
  const highestCfg = SEVERITY_CONFIG[highest] ?? SEVERITY_CONFIG.BLUE;

  // 空状态
  if (!warnings || warnings.length === 0) {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <LinearGradient
          colors={["#BFD8FF", "#EAF3FF", "#FFFFFF"]}
          style={StyleSheet.absoluteFill}
        />
        <View style={styles.header}>
          <TouchableOpacity
            onPress={() => navigation.goBack()}
            style={styles.headerBtn}
          >
            <Icon name="chevron-left" size={28} color={colors.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>天气预警</Text>
          <View style={styles.headerBtn} />
        </View>
        <View style={styles.emptyState}>
          <Icon name="shield-check" size={64} color={colors.primaryLight} />
          <Text style={styles.emptyTitle}>当前无预警</Text>
          <Text style={styles.emptyDesc}>
            {cityName} 地区天气状况平稳
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      {/* 背景渐变 */}
      <LinearGradient
        colors={["#BFD8FF", "#EAF3FF", "#FFFFFF"]}
        style={StyleSheet.absoluteFill}
      />

      {/* 导航栏 */}
      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          style={styles.headerBtn}
        >
          <Icon name="chevron-left" size={28} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{cityName}</Text>
        <View style={styles.headerBtn} />
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {/* 顶部状态摘要 */}
        <View style={styles.statusCard}>
          <View
            style={[
              styles.statusIconWrap,
              { backgroundColor: highestCfg.bgColor },
            ]}
          >
            <Icon
              name={highestCfg.icon as any}
              size={28}
              color={highestCfg.color}
            />
          </View>
          <View style={styles.statusTextWrap}>
            <Text style={styles.statusTitle}>
              共 {sorted.length} 条预警生效中
            </Text>
            <Text style={styles.statusDesc}>
              最高级别：{highestCfg.label}预警（{highestCfg.desc}）
            </Text>
          </View>
        </View>

        {/* 预警列表 */}
        <View style={styles.listSection}>
          <Text style={styles.sectionTitle}>预警详情</Text>
          <View style={styles.list}>
            {sorted.map((alert, i) => (
              <AlertCard key={i} alert={alert} />
            ))}
          </View>
        </View>

        {/* 底部提示 */}
        <View style={styles.footerTip}>
          <Icon
            name="information-outline"
            size={14}
            color={colors.textTertiary}
          />
          <Text style={styles.footerTipText}>
            预警信息来自国家气象部门，请以官方发布为准
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },

  // 导航
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
  },
  headerBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
  },

  scrollContent: {
    paddingHorizontal: spacingV2.lg,
    paddingBottom: spacingV2.xxxl,
  },

  // 状态摘要卡片
  statusCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    padding: spacingV2.xl,
    marginBottom: spacingV2.xl,
  },
  statusIconWrap: {
    width: 52,
    height: 52,
    borderRadius: borderRadiusV2.xl,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacingV2.md,
  },
  statusTextWrap: {
    flex: 1,
  },
  statusTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
  },
  statusDesc: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },

  // 列表区域
  listSection: {
    marginTop: spacingV2.sm,
  },
  sectionTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacingV2.md,
  },
  list: {
    gap: spacingV2.md,
  },

  // 预警卡片
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    overflow: "hidden",
  },
  cardTouchable: {
    flexDirection: "row",
  },
  severityStripe: {
    width: 4,
  },
  cardContent: {
    flex: 1,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.lg,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.sm,
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: borderRadiusV2.sm,
  },
  badgeText: {
    fontSize: fontSizeV2.xs,
    fontWeight: "700",
  },
  cardTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
    color: colors.text,
    lineHeight: 22,
  },
  detailBox: {
    marginTop: spacingV2.md,
    paddingTop: spacingV2.md,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  detailText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },

  // 底部提示
  footerTip: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    marginTop: spacingV2.xl,
    paddingHorizontal: spacingV2.lg,
  },
  footerTipText: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
  },

  // 空状态
  emptyState: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingBottom: spacingV2.xxxl,
  },
  emptyTitle: {
    fontSize: fontSizeV2.xl,
    fontWeight: "700",
    color: colors.text,
    marginTop: spacingV2.lg,
  },
  emptyDesc: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    marginTop: spacingV2.sm,
  },
});
