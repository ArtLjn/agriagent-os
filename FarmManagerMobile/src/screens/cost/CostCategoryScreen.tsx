import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  Modal,
  StyleSheet,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useCategoryStore } from "../../stores/categoryStore";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const CATEGORY_ICONS: Record<string, string> = {
  种子: "seed",
  化肥: "flask",
  农药: "spray",
  人工: "account-hard-hat",
  机械: "tractor",
  水电: "flash",
  地租: "home-variant",
  销售: "cash-register",
  其他: "dots-horizontal",
};

function getCategoryIcon(name: string): string {
  return CATEGORY_ICONS[name] || "tag-outline";
}

const TAB_CONFIG = {
  cost: {
    label: "支出",
    color: colors.expense,
    bg: colors.expenseBg,
    icon: "arrow-down-circle",
  },
  income: {
    label: "收入",
    color: colors.income,
    bg: colors.incomeBg,
    icon: "arrow-up-circle",
  },
};

const CategoryRow: React.FC<{
  name: string;
  type: "cost" | "income";
  isSystem: boolean;
  onDelete?: () => void;
}> = ({ name, type, isSystem, onDelete }) => {
  const config = TAB_CONFIG[type];
  return (
    <View style={styles.row}>
      <View style={styles.rowLeft}>
        <View style={[styles.rowIcon, { backgroundColor: config.bg }]}>
          <Icon name={getCategoryIcon(name)} size={20} color={config.color} />
        </View>
        <Text style={styles.rowName}>{name}</Text>
      </View>
      {isSystem ? (
        <Text style={styles.rowSystem}>系统</Text>
      ) : (
        <TouchableOpacity
          onPress={onDelete}
          activeOpacity={0.6}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Icon name="close" size={18} color={colors.textTertiary} />
        </TouchableOpacity>
      )}
    </View>
  );
};

export const CostCategoryScreen: React.FC = () => {
  const {
    categories,
    error,
    fetchCategories,
    createCategory,
    deleteCategory,
    clearError,
  } = useCategoryStore();

  const [activeTab, setActiveTab] = useState<"cost" | "income">("cost");
  const [modalVisible, setModalVisible] = useState(false);
  const [newType, setNewType] = useState<"cost" | "income">("cost");
  const [newName, setNewName] = useState("");

  useEffect(() => {
    fetchCategories();
  }, []);

  useEffect(() => {
    if (error) {
      Alert.alert("错误", error);
      clearError();
    }
  }, [error]);

  const filtered = categories.filter((c) => c.type === activeTab);
  const config = TAB_CONFIG[activeTab];

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) {
      Alert.alert("提示", "请输入分类名称");
      return;
    }
    try {
      await createCategory({ name, type: newType, icon: "tag" });
      setModalVisible(false);
      setNewName("");
      setNewType("cost");
    } catch {
      // store 已处理
    }
  };

  const handleDelete = (id: number, name: string) => {
    Alert.alert("确认删除", `确定要删除"${name}"吗？`, [
      { text: "取消", style: "cancel" },
      {
        text: "删除",
        style: "destructive",
        onPress: async () => {
          try {
            await deleteCategory(id);
          } catch {
            // store 已处理
          }
        },
      },
    ]);
  };

  const openModal = () => {
    setNewType(activeTab);
    setNewName("");
    setModalVisible(true);
  };

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        {/* 描述 */}
        <Text style={styles.subtitle}>
          自定义记账分类，让收支更清晰
        </Text>

        {/* 分段切换 */}
        <View style={styles.segmentBg}>
          <TouchableOpacity
            style={[
              styles.segmentBtn,
              activeTab === "cost" && styles.segmentBtnActive,
            ]}
            onPress={() => setActiveTab("cost")}
            activeOpacity={0.8}
          >
            <Icon
              name="arrow-down-circle"
              size={16}
              color={activeTab === "cost" ? colors.expense : colors.textTertiary}
            />
            <Text
              style={[
                styles.segmentText,
                activeTab === "cost" && { color: colors.expense, fontWeight: "700" },
              ]}
            >
              支出
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.segmentBtn,
              activeTab === "income" && styles.segmentBtnActive,
            ]}
            onPress={() => setActiveTab("income")}
            activeOpacity={0.8}
          >
            <Icon
              name="arrow-up-circle"
              size={16}
              color={activeTab === "income" ? colors.income : colors.textTertiary}
            />
            <Text
              style={[
                styles.segmentText,
                activeTab === "income" && { color: colors.income, fontWeight: "700" },
              ]}
            >
              收入
            </Text>
          </TouchableOpacity>
        </View>

        {/* 分类数量 */}
        <View style={styles.countRow}>
          <Text style={styles.countLabel}>
            {config.label}分类
          </Text>
          <Text style={[styles.countValue, { color: config.color }]}>
            {filtered.length}
          </Text>
        </View>

        {/* 列表 */}
        {filtered.length === 0 ? (
          <View style={styles.empty}>
            <View style={[styles.emptyIcon, { backgroundColor: config.bg }]}>
              <Icon name={config.icon} size={32} color={config.color} />
            </View>
            <Text style={styles.emptyTitle}>
              暂无{config.label}分类
            </Text>
            <Text style={styles.emptySub}>
              点击右下角按钮添加第一个分类
            </Text>
          </View>
        ) : (
          <View style={styles.listCard}>
            {filtered.map((cat, i) => (
              <View key={cat.id}>
                <CategoryRow
                  name={cat.name}
                  type={cat.type as "cost" | "income"}
                  isSystem={cat.is_default}
                  onDelete={() => handleDelete(cat.id, cat.name)}
                />
                {i < filtered.length - 1 && <View style={styles.divider} />}
              </View>
            ))}
          </View>
        )}

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* FAB */}
      <TouchableOpacity style={styles.fab} onPress={openModal} activeOpacity={0.8}>
        <Icon name="plus" size={24} color="#FFFFFF" />
      </TouchableOpacity>

      {/* 新增弹窗 */}
      <Modal
        visible={modalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <TouchableOpacity
            style={styles.modalBackdrop}
            onPress={() => setModalVisible(false)}
            activeOpacity={1}
          />
          <View style={styles.modalSheet}>
            <View style={styles.modalHandle} />

            <Text style={styles.modalTitle}>新增{TAB_CONFIG[newType].label}分类</Text>

            {/* 类型切换 */}
            <View style={styles.modalTabs}>
              <TouchableOpacity
                style={[
                  styles.modalTab,
                  newType === "cost" && {
                    backgroundColor: colors.expenseBg,
                    borderColor: colors.expense,
                  },
                ]}
                onPress={() => setNewType("cost")}
              >
                <Icon
                  name="arrow-down-circle"
                  size={18}
                  color={newType === "cost" ? colors.expense : colors.textTertiary}
                />
                <Text
                  style={[
                    styles.modalTabText,
                    newType === "cost" && { color: colors.expense, fontWeight: "700" },
                  ]}
                >
                  支出
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.modalTab,
                  newType === "income" && {
                    backgroundColor: colors.incomeBg,
                    borderColor: colors.income,
                  },
                ]}
                onPress={() => setNewType("income")}
              >
                <Icon
                  name="arrow-up-circle"
                  size={18}
                  color={newType === "income" ? colors.income : colors.textTertiary}
                />
                <Text
                  style={[
                    styles.modalTabText,
                    newType === "income" && { color: colors.income, fontWeight: "700" },
                  ]}
                >
                  收入
                </Text>
              </TouchableOpacity>
            </View>

            {/* 输入 */}
            <View style={styles.inputWrap}>
              <TextInput
                style={styles.input}
                value={newName}
                onChangeText={setNewName}
                placeholder={`输入${TAB_CONFIG[newType].label}分类名称`}
                placeholderTextColor={colors.textTertiary}
                autoFocus
                maxLength={20}
              />
            </View>

            {/* 按钮 */}
            <TouchableOpacity
              style={[styles.createBtn, { backgroundColor: colors.primary }]}
              onPress={handleCreate}
              activeOpacity={0.8}
            >
              <Text style={styles.createBtnText}>创建</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scroll: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.md,
    paddingBottom: spacingV2.xxxl,
  },
  subtitle: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginBottom: spacingV2.lg,
  },
  // 分段控制器
  segmentBg: {
    flexDirection: "row",
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.lg,
    padding: 4,
    marginBottom: spacingV2.lg,
  },
  segmentBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacingV2.xs,
    paddingVertical: 10,
    borderRadius: borderRadiusV2.md,
  },
  segmentBtnActive: {
    backgroundColor: colors.surface,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 3,
    elevation: 2,
  },
  segmentText: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  // 数量
  countRow: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    marginBottom: spacingV2.md,
  },
  countLabel: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
  },
  countValue: {
    fontSize: fontSizeV2.md,
    fontWeight: "800",
  },
  // 列表
  listCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    overflow: "hidden",
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md + 2,
  },
  rowLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
    flex: 1,
  },
  rowIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  rowName: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
    color: colors.text,
  },
  rowSystem: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    fontWeight: "500",
  },
  divider: {
    height: 1,
    backgroundColor: colors.borderLight,
    marginLeft: spacingV2.lg + 40 + spacingV2.md,
  },
  // 空状态
  empty: {
    alignItems: "center",
    paddingVertical: spacingV2.xxxl,
  },
  emptyIcon: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacingV2.lg,
  },
  emptyTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacingV2.xs,
  },
  emptySub: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
  },
  // FAB
  fab: {
    position: "absolute",
    right: spacingV2.lg,
    bottom: spacingV2.lg,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.25,
    shadowRadius: 12,
    elevation: 5,
  },
  // 弹窗
  modalOverlay: {
    flex: 1,
    justifyContent: "flex-end",
  },
  modalBackdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.4)",
  },
  modalSheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadiusV2.xxxl,
    borderTopRightRadius: borderRadiusV2.xxxl,
    paddingHorizontal: spacingV2.lg,
    paddingBottom: spacingV2.xxxl,
    paddingTop: spacingV2.sm,
  },
  modalHandle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    alignSelf: "center",
    marginBottom: spacingV2.lg,
  },
  modalTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
    textAlign: "center",
    marginBottom: spacingV2.lg,
  },
  modalTabs: {
    flexDirection: "row",
    gap: spacingV2.md,
    marginBottom: spacingV2.lg,
  },
  modalTab: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacingV2.sm,
    paddingVertical: spacingV2.md,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.background,
    borderWidth: 1.5,
    borderColor: colors.borderLight,
  },
  modalTabText: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  inputWrap: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadiusV2.lg,
    paddingHorizontal: spacingV2.md,
    backgroundColor: colors.background,
    marginBottom: spacingV2.lg,
  },
  input: {
    paddingVertical: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.text,
  },
  createBtn: {
    paddingVertical: spacingV2.md,
    borderRadius: borderRadiusV2.lg,
    alignItems: "center",
  },
  createBtnText: {
    fontSize: fontSizeV2.md,
    color: "#FFFFFF",
    fontWeight: "700",
  },
});
