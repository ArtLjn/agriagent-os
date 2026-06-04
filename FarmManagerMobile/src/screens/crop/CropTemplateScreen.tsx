import React, { useCallback, useEffect, useState } from "react";
import { showAlert } from "../../utils/alert";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
} from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { cropApi } from "../../api/client";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import { BulkActionBar } from "../../components/BulkActionBar";
import { SelectionCircle } from "../../components/SelectionCircle";
import { useBulkSelection } from "../../hooks/useBulkSelection";

interface GrowthStage {
  id: number;
  name: string;
  duration_days: number;
  order_index: number;
  key_tasks?: string | null;
}

interface CropTemplate {
  id: number;
  name: string;
  variety?: string | null;
  stages: GrowthStage[];
}

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

function getCropEmoji(name: string): string {
  if (name.includes("西瓜")) {
    return "🍉";
  }
  if (name.includes("辣椒")) {
    return "🌶️";
  }
  if (name.includes("番茄") || name.includes("西红柿")) {
    return "🍅";
  }
  if (name.includes("黄瓜")) {
    return "🥒";
  }
  if (name.includes("茄子")) {
    return "🍆";
  }
  if (name.includes("白菜")) {
    return "🥬";
  }
  if (name.includes("玉米")) {
    return "🌽";
  }
  if (name.includes("土豆")) {
    return "🥔";
  }
  if (name.includes("萝卜")) {
    return "🥕";
  }
  return "🌱";
}

export const CropTemplateScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const [templates, setTemplates] = useState<CropTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const selection = useBulkSelection<number>();

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const res = await cropApi.getTemplates();
      const data = res.data as any;
      setTemplates(data.items ?? data ?? []);
    } catch (err: any) {
      showAlert("加载失败", err.message || "请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, []);

  useFocusEffect(
    useCallback(() => {
      fetchTemplates();
    }, [])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchTemplates();
    setRefreshing(false);
  };

  const handleDeleteSelected = () => {
    showAlert(
      "删除作物模板",
      `确定删除选中的 ${selection.selectedCount} 个作物模板吗？使用这些模板的种植规划也会一起删除。`,
      [
        { text: "取消", style: "cancel" },
        {
          text: "删除",
          style: "destructive",
          onPress: async () => {
            setDeleting(true);
            try {
              await Promise.all(
                selection.selectedIds.map((id) => cropApi.deleteTemplate(id))
              );
              selection.clearSelection();
              await fetchTemplates();
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

  const renderTemplateItem = ({ item }: { item: CropTemplate }) => {
    const totalDays = item.stages.reduce((sum, s) => sum + s.duration_days, 0);

    return (
      <View style={styles.selectableRow}>
        {selection.isSelecting && (
          <View style={styles.selectionSlot}>
            <SelectionCircle selected={selection.isSelected(item.id)} />
          </View>
        )}
        <TouchableOpacity
          style={[
            styles.card,
            selection.isSelected(item.id) && styles.cardSelected,
          ]}
          activeOpacity={0.75}
          onLongPress={() => selection.beginSelection(item.id)}
          onPress={() => {
            if (selection.isSelecting) {
              selection.toggleSelection(item.id);
            }
          }}
        >
          <View style={styles.cardHeader}>
            <Text style={styles.emoji}>{getCropEmoji(item.name)}</Text>
            <View style={styles.nameSection}>
              <Text style={styles.templateName}>{item.name}</Text>
              {item.variety && (
                <Text style={styles.variety}>{item.variety}</Text>
              )}
            </View>
          </View>

          <View style={styles.totalRow}>
            <Text style={styles.totalLabel}>全周期</Text>
            <Text style={styles.totalValue}>
              {totalDays}
              <Text style={styles.totalUnit}> 天</Text>
            </Text>
          </View>

          <View style={styles.divider} />

          <View style={styles.stageList}>
            {item.stages.map((stage, index) => (
              <View key={stage.id}>
                <View style={styles.stageRow}>
                  <View style={styles.stageLeft}>
                    <View
                      style={[
                        styles.stageDot,
                        index === 0 && styles.stageDotFirst,
                        index === item.stages.length - 1 && styles.stageDotLast,
                      ]}
                    />
                    <Text style={styles.stageName}>{stage.name}</Text>
                  </View>
                  <Text style={styles.stageDuration}>
                    {stage.duration_days}天
                  </Text>
                </View>
                {index < item.stages.length - 1 && (
                  <View style={styles.stageConnector} />
                )}
              </View>
            ))}
          </View>

          {item.stages.length === 0 && (
            <Text style={styles.emptyStage}>暂无阶段信息</Text>
          )}
        </TouchableOpacity>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <FlatList
        data={templates}
        keyExtractor={(item) => String(item.id)}
        renderItem={renderTemplateItem}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          !loading ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyEmoji}>🌱</Text>
              <Text style={styles.emptyText}>暂无作物模板</Text>
            </View>
          ) : null
        }
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
          onPress={() => navigation.navigate("CropTemplateCreate" as never)}
          activeOpacity={0.8}
        >
          <Icon name="plus" size={24} color={colors.textInverse} />
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
  selectableRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacingV2.lg,
  },
  selectionSlot: {
    width: 36,
    alignItems: "flex-start",
  },
  card: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    padding: spacingV2.lg,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  cardSelected: {
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: "#FBFCFF",
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacingV2.md,
  },
  emoji: {
    fontSize: 32,
    marginRight: spacingV2.md,
  },
  nameSection: {
    flex: 1,
  },
  templateName: {
    fontSize: fontSizeV2.xl,
    fontWeight: "700",
    color: colors.text,
  },
  variety: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    marginTop: 2,
  },
  totalRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: spacingV2.sm,
    marginBottom: spacingV2.md,
  },
  totalLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
  },
  totalValue: {
    fontSize: fontSizeV2.xl,
    fontWeight: "800",
    color: colors.primary,
  },
  totalUnit: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: colors.primary,
  },
  divider: {
    height: 1,
    backgroundColor: colors.borderLight,
    marginBottom: spacingV2.md,
  },
  stageList: {
    paddingLeft: spacingV2.xs,
  },
  stageRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacingV2.sm,
  },
  stageLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
  },
  stageDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.border,
  },
  stageDotFirst: {
    backgroundColor: colors.primary,
  },
  stageDotLast: {
    backgroundColor: colors.success,
  },
  stageConnector: {
    width: 2,
    height: 16,
    backgroundColor: colors.borderLight,
    marginLeft: 3,
  },
  stageName: {
    fontSize: fontSizeV2.md,
    color: colors.text,
  },
  stageDuration: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    fontWeight: "500",
  },
  emptyStage: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    marginTop: spacingV2.sm,
  },
  emptyContainer: {
    alignItems: "center",
    paddingVertical: spacingV2.xxxl,
  },
  emptyEmoji: {
    fontSize: 48,
    marginBottom: spacingV2.md,
  },
  emptyText: {
    color: colors.textTertiary,
    fontSize: fontSizeV2.md,
  },
  fab: {
    position: "absolute",
    right: spacingV2.lg,
    bottom: spacingV2.lg,
    width: 56,
    height: 56,
    borderRadius: borderRadiusV2.full,
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
