import React, { useEffect, useState } from "react";
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
import { EmptyState } from "../../components/EmptyState";
import { Loading } from "../../components/Loading";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { BulkActionBar } from "../../components/BulkActionBar";
import { SelectionCircle } from "../../components/SelectionCircle";
import { useBulkSelection } from "../../hooks/useBulkSelection";
import { showAlert } from "../../utils/alert";

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

// ─── 作物 emoji 映射 ───
const CROP_EMOJI: Record<string, string> = {
  西瓜: "🍉",
  辣椒: "🌶️",
  番茄: "🍅",
  西红柿: "🍅",
  黄瓜: "🥒",
  茄子: "🍆",
  白菜: "🥬",
  土豆: "🥔",
  马铃薯: "🥔",
  玉米: "🌽",
  水稻: "🌾",
  小麦: "🌾",
  花生: "🥜",
  萝卜: "🥕",
  胡萝卜: "🥕",
  南瓜: "🎃",
  草莓: "🍓",
  葡萄: "🍇",
  苹果: "🍎",
  梨: "🍐",
  桃: "🍑",
  樱桃: "🍒",
  橙子: "🍊",
  柠檬: "🍋",
  香蕉: "🍌",
  菠萝: "🍍",
  芒果: "🥭",
  西瓜皮: "🍉",
  甜瓜: "🍈",
  哈密瓜: "🍈",
};

function getCropEmoji(name: string): string {
  for (const [crop, emoji] of Object.entries(CROP_EMOJI)) {
    if (name.includes(crop)) {
      return emoji;
    }
  }
  return "🌱";
}

// ─── 阶段 → 进度估算 ───
function estimateProgress(stageName: string | null): number {
  if (!stageName) {
    return 0;
  }
  const s = stageName.toLowerCase();
  if (s.includes("收获") || s.includes("完结")) {
    return 1.0;
  }
  if (s.includes("成熟") || s.includes("采收")) {
    return 0.9;
  }
  if (s.includes("结果") || s.includes("坐果")) {
    return 0.75;
  }
  if (s.includes("开花") || s.includes("授粉")) {
    return 0.6;
  }
  if (s.includes("生长") || s.includes("发育") || s.includes("伸蔓")) {
    return 0.45;
  }
  if (s.includes("移栽") || s.includes("定植")) {
    return 0.3;
  }
  if (s.includes("育苗") || s.includes("播种") || s.includes("催芽")) {
    return 0.15;
  }
  return 0.3;
}

// ─── 种植天数 ───
function getDaysSince(startDate: string): number {
  const start = new Date(startDate);
  const now = new Date();
  const diff = now.getTime() - start.getTime();
  return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
}

function formatBatchMeta(item: any, days: number): string {
  const parts = [item.crop_template_name, `已种植 ${days} 天`];
  const area = item.total_area_mu || item.unit_area_mu;
  if (area) {
    parts.push(`${Number(area).toFixed(2).replace(/\.00$/, "")} 亩`);
  }
  if (item.unit_count) {
    parts.push(`${item.unit_count} 个单元`);
  }
  if (item.season) {
    parts.push(item.season);
  }
  return parts.join(" · ");
}

const STATUS_CONFIG: Record<
  string,
  { label: string; color: string; bgColor: string }
> = {
  active: {
    label: "进行中",
    color: colors.success,
    bgColor: colors.successMuted,
  },
  completed: {
    label: "已完成",
    color: colors.info,
    bgColor: colors.infoLight,
  },
  abandoned: {
    label: "已废弃",
    color: colors.danger,
    bgColor: colors.dangerLight,
  },
};

export const CycleListScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const { cycles, loading, fetchCycles, deleteCycles } = useCycleStore();
  const [deleting, setDeleting] = useState(false);
  const selection = useBulkSelection<number>();

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
        subtitle="点击右下角按钮创建您的第一个种植批次"
        actionLabel="新建批次"
        onAction={() => navigation.navigate("CycleCreate" as never)}
        icon="sprout-outline"
      />
    );
  }

  const activeCount = cycles.filter((c) => c.status === "active").length;

  const handleDeleteSelected = () => {
    showAlert(
      "删除种植规划",
      `确定删除选中的 ${selection.selectedCount} 个种植规划吗？相关农事日志和记账也会一起删除。`,
      [
        { text: "取消", style: "cancel" },
        {
          text: "删除",
          style: "destructive",
          onPress: async () => {
            setDeleting(true);
            try {
              await deleteCycles(selection.selectedIds);
              selection.clearSelection();
            } catch (err: any) {
              showAlert("删除失败", err.message || "请稍后重试");
            } finally {
              setDeleting(false);
            }
          },
        },
      ]
    );
  };

  return (
    <View style={styles.container}>
      <FlatList
        data={cycles}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          <View style={styles.header}>
            <View style={styles.statsRow}>
              <View style={styles.statItem}>
                <Text style={styles.statNumber}>{cycles.length}</Text>
                <Text style={styles.statLabel}>总批次</Text>
              </View>
              <View style={styles.statDivider} />
              <View style={styles.statItem}>
                <Text style={[styles.statNumber, styles.statActive]}>
                  {activeCount}
                </Text>
                <Text style={styles.statLabel}>进行中</Text>
              </View>
            </View>
          </View>
        }
        renderItem={({ item, index }) => {
          const status = STATUS_CONFIG[item.status] || {
            label: item.status,
            color: colors.textSecondary,
            bgColor: colors.surfaceMuted,
          };

          const emoji = getCropEmoji(item.crop_template_name || item.name);
          const days = getDaysSince(item.start_date);
          const progress = estimateProgress(item.current_stage_name);

          return (
            <View style={styles.selectableRow}>
              {selection.isSelecting && (
                <View style={styles.selectionSlot}>
                  <SelectionCircle selected={selection.isSelected(item.id)} />
                </View>
              )}
              <TouchableOpacity
                onPress={() => {
                  if (selection.isSelecting) {
                    selection.toggleSelection(item.id);
                    return;
                  }
                  navigation.navigate(
                    "CycleDetail" as never,
                    {
                      cycleId: item.id,
                    } as never
                  );
                }}
                onLongPress={() => selection.beginSelection(item.id)}
                activeOpacity={0.7}
                style={[
                  styles.card,
                  selection.isSelected(item.id) && styles.cardSelected,
                ]}
              >
                <View style={styles.cardInner}>
                  {/* 左侧图标 */}
                  <View style={styles.iconWrap}>
                    <Text style={styles.iconEmoji}>{emoji}</Text>
                  </View>

                  {/* 右侧内容 */}
                  <View style={styles.cardContent}>
                    {/* 名称行 */}
                    <View style={styles.nameRow}>
                      <Text style={styles.cardName} numberOfLines={1}>
                        {item.name}
                      </Text>
                      <View
                        style={[
                          styles.statusPill,
                          { backgroundColor: status.bgColor },
                        ]}
                      >
                        <Text
                          style={[styles.statusText, { color: status.color }]}
                        >
                          {status.label}
                        </Text>
                      </View>
                    </View>

                    {/* 作物 + 天数 */}
                    <Text style={styles.metaText} numberOfLines={1}>
                      {formatBatchMeta(item, days)}
                    </Text>

                    {/* 进度条 */}
                    <View style={styles.progressRow}>
                      <View style={styles.progressTrack}>
                        <View
                          style={[
                            styles.progressFill,
                            {
                              width: `${Math.round(progress * 100)}%`,
                              backgroundColor: status.color,
                            },
                          ]}
                        />
                      </View>
                    </View>

                    {/* 阶段标签 */}
                    {item.current_stage_name && (
                      <View style={styles.stageRow}>
                        <View
                          style={[
                            styles.stagePill,
                            { backgroundColor: status.bgColor },
                          ]}
                        >
                          <View
                            style={[
                              styles.stageDot,
                              { backgroundColor: status.color },
                            ]}
                          />
                          <Text
                            style={[styles.stageText, { color: status.color }]}
                          >
                            {item.current_stage_name}
                          </Text>
                        </View>
                      </View>
                    )}
                  </View>
                </View>

                {/* 装饰序号 */}
                <Text style={styles.indexBadge}>
                  #{String(index + 1).padStart(2, "0")}
                </Text>
              </TouchableOpacity>
            </View>
          );
        }}
      />

      {selection.isSelecting ? (
        <BulkActionBar
          selectedCount={selection.selectedCount}
          deleting={deleting}
          onCancel={selection.clearSelection}
          onDelete={handleDeleteSelected}
        />
      ) : (
        <TouchableOpacity
          style={styles.fab}
          onPress={() => navigation.navigate("CycleCreate" as never)}
          activeOpacity={0.8}
        >
          <Icon name="plus" size={22} color={colors.textInverse} />
        </TouchableOpacity>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  listContent: {
    padding: spacingV2.lg,
    paddingBottom: 100,
  },
  header: {
    marginBottom: spacingV2.xxl,
  },
  selectableRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacingV2.lg,
  },
  selectionSlot: {
    width: 36,
    alignItems: "flex-start",
  },
  statsRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacingV2.xl,
  },
  statItem: {
    alignItems: "flex-start",
  },
  statNumber: {
    fontSize: fontSizeV2.xxxl,
    fontWeight: "800",
    color: colors.text,
    letterSpacing: -1,
    lineHeight: 44,
  },
  statActive: {
    color: colors.success,
  },
  statLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  statDivider: {
    width: 1,
    height: 36,
    backgroundColor: colors.border,
    marginBottom: 4,
  },
  card: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
    overflow: "hidden",
  },
  cardSelected: {
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: "#FBFCFF",
  },
  cardInner: {
    flexDirection: "row",
    alignItems: "flex-start",
    padding: spacingV2.lg,
    gap: spacingV2.md,
  },
  iconWrap: {
    width: 52,
    height: 52,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  iconEmoji: {
    fontSize: 26,
  },
  cardContent: {
    flex: 1,
    gap: 4,
  },
  nameRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacingV2.sm,
  },
  cardName: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
    flex: 1,
  },
  statusPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: borderRadiusV2.sm,
  },
  statusText: {
    fontSize: 11,
    fontWeight: "700",
  },
  metaText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  progressRow: {
    marginTop: 4,
    marginBottom: 2,
  },
  progressTrack: {
    height: 4,
    backgroundColor: colors.borderLight,
    borderRadius: 2,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    borderRadius: 2,
  },
  stageRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 2,
  },
  stagePill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: borderRadiusV2.sm,
  },
  stageDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
  },
  stageText: {
    fontSize: 12,
    fontWeight: "600",
  },
  indexBadge: {
    position: "absolute",
    right: spacingV2.lg,
    bottom: spacingV2.lg,
    fontSize: 11,
    fontWeight: "700",
    color: colors.textTertiary,
    opacity: 0.4,
  },
  fab: {
    position: "absolute",
    right: spacingV2.lg,
    bottom: spacingV2.lg,
    width: 52,
    height: 52,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.primary,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 10,
    elevation: 5,
  },
});
