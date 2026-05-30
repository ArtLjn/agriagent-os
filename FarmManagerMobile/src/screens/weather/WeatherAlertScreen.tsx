import React from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation } from "@react-navigation/native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";

const SEVERITY: Record<
  string,
  { label: string; color: string; icon: string }
> = {
  RED: { label: "红色", color: "#D32F2F", icon: "alert-octagon" },
  ORANGE: { label: "橙色", color: "#E65100", icon: "alert" },
  YELLOW: { label: "黄色", color: "#F9A825", icon: "alert-circle" },
  BLUE: { label: "蓝色", color: "#1565C0", icon: "information" },
};

const ORDER = { RED: 0, ORANGE: 1, YELLOW: 2, BLUE: 3 };

const parseAlert = (raw: string) => {
  const match = raw.match(/^\[(RED|ORANGE|YELLOW|BLUE)\]\s*/);
  if (match) {
    return { severity: match[1], title: raw.replace(match[0], ""), desc: "" };
  }
  const parts = raw.split(": ", 2);
  const title = parts[0] ?? raw;
  const desc = parts[1] ?? "";
  let severity = "BLUE";
  if (title.includes("红色")) severity = "RED";
  else if (title.includes("橙色")) severity = "ORANGE";
  else if (title.includes("黄色")) severity = "YELLOW";
  return { severity, title, desc };
};

interface AlertItemProps {
  alert: { severity: string; title: string; desc: string };
}

const AlertItem: React.FC<AlertItemProps> = ({ alert }) => {
  const [open, setOpen] = React.useState(false);
  const cfg = SEVERITY[alert.severity] ?? SEVERITY.BLUE;

  return (
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={() => setOpen(!open)}
      style={styles.card}
    >
      {/* 左侧色条 */}
      <View style={[styles.accent, { backgroundColor: cfg.color }]} />

      <View style={styles.cardBody}>
        <View style={styles.cardTop}>
          {/* 级别小圆点 + 标签 */}
          <View style={styles.labelRow}>
            <View style={[styles.dot, { backgroundColor: cfg.color }]} />
            <Text style={[styles.labelText, { color: cfg.color }]}>
              {cfg.label}预警
            </Text>
          </View>
          <Icon
            name={open ? "chevron-up" : "chevron-down"}
            size={18}
            color={colors.textTertiary}
          />
        </View>

        <Text style={styles.cardTitle}>{alert.title}</Text>

        {open && (
          <View style={styles.descWrap}>
            <Text style={styles.descText}>
              {alert.desc ||
                "请关注当地气象部门发布的最新预警信息，及时采取防护措施。"}
            </Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );
};

interface WeatherAlertScreenProps {
  route: {
    params: {
      warnings: string[];
      cityName: string;
    };
  };
}

export const WeatherAlertScreen: React.FC<WeatherAlertScreenProps> = ({
  route,
}) => {
  const navigation = useNavigation();
  const { warnings, cityName } = route.params;

  const parsed = warnings.map(parseAlert);
  const sorted = [...parsed].sort(
    (a, b) => (ORDER[a.severity] ?? 3) - (ORDER[b.severity] ?? 3)
  );

  const highest = sorted[0]?.severity ?? "BLUE";
  const highestCfg = SEVERITY[highest] ?? SEVERITY.BLUE;

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      {/* 导航栏 */}
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

      {/* 摘要条 */}
      <View
        style={[
          styles.summary,
          { borderLeftColor: highestCfg.color },
        ]}
      >
        <Icon
          name={highestCfg.icon as any}
          size={18}
          color={highestCfg.color}
        />
        <Text style={[styles.summaryText, { color: highestCfg.color }]}>
          {cityName} · 共 {sorted.length} 条预警生效中
        </Text>
      </View>

      {/* 列表 */}
      <ScrollView
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
      >
        {sorted.map((alert, i) => (
          <AlertItem key={i} alert={alert} />
        ))}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
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

  // 摘要
  summary: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.lg,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.md,
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.md,
    borderLeftWidth: 3,
  },
  summaryText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
  },

  // 列表
  list: {
    paddingHorizontal: spacingV2.lg,
    paddingBottom: spacingV2.xxxl,
    gap: spacingV2.sm,
  },

  // 卡片
  card: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    overflow: "hidden",
  },
  accent: {
    width: 3,
  },
  cardBody: {
    flex: 1,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.md,
  },
  cardTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  labelRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  labelText: {
    fontSize: fontSizeV2.xs,
    fontWeight: "700",
  },
  cardTitle: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: colors.text,
    lineHeight: 20,
    paddingRight: spacingV2.xl,
  },

  // 展开描述
  descWrap: {
    marginTop: spacingV2.sm,
    paddingTop: spacingV2.sm,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  descText: {
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    lineHeight: 18,
  },
});
