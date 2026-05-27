import React, { useEffect } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCycleStore } from "../../stores/cycleStore";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { Loading } from "../../components/Loading";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const STATUS_CONFIG: Record<
  string,
  { label: string; color: string; icon: string; bgColor: string }
> = {
  active: {
    label: "进行中",
    color: colors.success,
    icon: "play-circle",
    bgColor: colors.successLight,
  },
  completed: {
    label: "已完成",
    color: colors.info,
    icon: "check-circle",
    bgColor: colors.infoLight,
  },
  abandoned: {
    label: "已废弃",
    color: colors.danger,
    icon: "close-circle",
    bgColor: colors.dangerLight,
  },
};

export const CycleListScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const { cycles, loading, fetchCycles } = useCycleStore();

  useEffect(() => {
    fetchCycles();
  }, [fetchCycles]);

  if (loading && cycles.length === 0) {
    return <Loading message="加载茬口列表..." />;
  }

  if (cycles.length === 0) {
    return (
      <EmptyState
        title="暂无茬口"
        subtitle="点击右下角按钮创建您的第一个种植茬口"
        actionLabel="新建茬口"
        onAction={() => navigation.navigate("CycleCreate")}
        icon="sprout-outline"
      />
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={cycles}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        renderItem={({ item }) => {
          const status = STATUS_CONFIG[item.status] || {
            label: item.status,
            color: colors.textSecondary,
            icon: "help-circle",
            bgColor: colors.surfaceMuted,
          };
          return (
            <TouchableOpacity
              onPress={() =>
                navigation.navigate("CycleDetail", { cycleId: item.id })
              }
              activeOpacity={0.7}
            >
              <Card style={styles.card}>
                <View style={styles.header}>
                  <View style={styles.nameRow}>
                    <View
                      style={[
                        styles.statusIcon,
                        { backgroundColor: status.bgColor },
                      ]}
                    >
                      <Icon name={status.icon} size={16} color={status.color} />
                    </View>
                    <Text style={styles.name}>{item.name}</Text>
                  </View>
                  <View
                    style={[styles.badge, { backgroundColor: status.bgColor }]}
                  >
                    <Text style={[styles.badgeText, { color: status.color }]}>
                      {status.label}
                    </Text>
                  </View>
                </View>
                <View style={styles.divider} />
                <View style={styles.body}>
                  <View style={styles.infoRow}>
                    <Icon name="seed" size={14} color={colors.textTertiary} />
                    <Text style={styles.template}>
                      作物：{item.crop_template_name}
                    </Text>
                  </View>
                  <View style={styles.infoRow}>
                    <Icon
                      name="calendar"
                      size={14}
                      color={colors.textTertiary}
                    />
                    <Text style={styles.meta}>起始：{item.start_date}</Text>
                  </View>
                  {item.current_stage_name && (
                    <View style={styles.stageRow}>
                      <Icon
                        name="progress-clock"
                        size={14}
                        color={colors.primary}
                      />
                      <Text style={styles.stage}>
                        当前阶段：{item.current_stage_name}
                      </Text>
                    </View>
                  )}
                </View>
              </Card>
            </TouchableOpacity>
          );
        }}
      />
      <TouchableOpacity
        style={styles.fab}
        onPress={() => navigation.navigate("CycleCreate")}
      >
        <Icon name="plus" size={24} color={colors.textInverse} />
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  list: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  card: {
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  nameRow: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },
  statusIcon: {
    width: 28,
    height: 28,
    borderRadius: borderRadius.sm,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.sm,
  },
  name: {
    fontSize: fontSize.md,
    fontWeight: "700",
    color: colors.text,
    flex: 1,
  },
  badge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: borderRadius.sm,
  },
  badgeText: {
    fontSize: fontSize.xs,
    fontWeight: "700",
  },
  divider: {
    height: 1,
    backgroundColor: colors.borderLight,
    marginVertical: spacing.sm,
  },
  body: {
    gap: spacing.xs,
  },
  infoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  template: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  meta: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  stageRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  stage: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: "600",
  },
  fab: {
    position: "absolute",
    right: spacing.lg,
    bottom: spacing.lg,
    width: 56,
    height: 56,
    borderRadius: borderRadius.full,
    backgroundColor: colors.primary,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
});
