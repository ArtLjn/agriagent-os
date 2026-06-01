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

const TYPE_COLORS = {
  cost: { dot: colors.expense, text: colors.text },
  income: { dot: colors.income, text: colors.text },
};

const CategoryItem: React.FC<{
  name: string;
  type: "cost" | "income";
  isSystem: boolean;
  onDelete?: () => void;
}> = ({ name, type, isSystem, onDelete }) => {
  const theme = TYPE_COLORS[type];
  return (
    <View style={styles.categoryItem}>
      <View style={styles.categoryLeft}>
        <View style={[styles.categoryDot, { backgroundColor: theme.dot }]} />
        <Icon
          name={getCategoryIcon(name)}
          size={18}
          color={colors.textTertiary}
          style={{ marginRight: spacingV2.sm }}
        />
        <Text style={styles.categoryName}>{name}</Text>
      </View>
      <View style={styles.categoryRight}>
        {isSystem && (
          <Text style={styles.systemTag}>系统预设</Text>
        )}
        {!isSystem && (
          <TouchableOpacity
            style={styles.deleteBtn}
            onPress={onDelete}
            activeOpacity={0.7}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Icon name="trash-can-outline" size={18} color={colors.textTertiary} />
          </TouchableOpacity>
        )}
      </View>
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

  const [modalVisible, setModalVisible] = useState(false);
  const [categoryType, setCategoryType] = useState<"cost" | "income">("cost");
  const [categoryName, setCategoryName] = useState("");

  useEffect(() => {
    fetchCategories();
  }, []);

  useEffect(() => {
    if (error) {
      Alert.alert("错误", error);
      clearError();
    }
  }, [error]);

  const handleCreate = async () => {
    if (!categoryName.trim()) {
      Alert.alert("提示", "请输入分类名称");
      return;
    }

    try {
      await createCategory({
        name: categoryName.trim(),
        type: categoryType,
        icon: "tag",
      });
      setModalVisible(false);
      setCategoryName("");
      setCategoryType("cost");
    } catch {
      // Error 已在 store 中处理
    }
  };

  const handleDelete = (id: number, name: string) => {
    Alert.alert("确认删除", `确定要删除分类"${name}"吗？`, [
      { text: "取消", style: "cancel" },
      {
        text: "删除",
        style: "destructive",
        onPress: async () => {
          try {
            await deleteCategory(id);
          } catch {
            // Error 已在 store 中处理
          }
        },
      },
    ]);
  };

  const expenseCategories = categories.filter((c) => c.type === "cost");
  const incomeCategories = categories.filter((c) => c.type === "income");

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      {/* 页面头部 */}
      <View style={styles.pageHeader}>
        <View>
          <Text style={styles.pageHeaderTitle}>收支分类</Text>
          <Text style={styles.pageHeaderSub}>
            管理记账所需的支出与收入分类
          </Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* 支出分类 */}
        <View style={styles.sectionHeader}>
          <View
            style={[styles.sectionDot, { backgroundColor: colors.expense }]}
          />
          <Text style={styles.sectionTitle}>支出分类</Text>
          <View style={styles.sectionCountBg}>
            <Text style={styles.sectionCount}>
              {expenseCategories.length}
            </Text>
          </View>
        </View>
        {expenseCategories.length === 0 && (
          <View style={styles.emptySection}>
            <Text style={styles.emptySectionText}>暂无自定义支出分类</Text>
          </View>
        )}
        <View style={styles.listCard}>
          {expenseCategories.map((category, index) => (
            <View key={category.id}>
              <CategoryItem
                name={category.name}
                type="cost"
                isSystem={category.is_default}
                onDelete={() => handleDelete(category.id, category.name)}
              />
              {index < expenseCategories.length - 1 && (
                <View style={styles.divider} />
              )}
            </View>
          ))}
        </View>

        {/* 收入分类 */}
        <View style={[styles.sectionHeader, { marginTop: spacingV2.lg }]}>
          <View
            style={[
              styles.sectionDot,
              { backgroundColor: colors.income },
            ]}
          />
          <Text style={styles.sectionTitle}>收入分类</Text>
          <View style={styles.sectionCountBg}>
            <Text style={styles.sectionCount}>
              {incomeCategories.length}
            </Text>
          </View>
        </View>
        {incomeCategories.length === 0 && (
          <View style={styles.emptySection}>
            <Text style={styles.emptySectionText}>暂无自定义收入分类</Text>
          </View>
        )}
        <View style={styles.listCard}>
          {incomeCategories.map((category, index) => (
            <View key={category.id}>
              <CategoryItem
                name={category.name}
                type="income"
                isSystem={category.is_default}
                onDelete={() => handleDelete(category.id, category.name)}
              />
              {index < incomeCategories.length - 1 && (
                <View style={styles.divider} />
              )}
            </View>
          ))}
        </View>

        {/* 新增按钮 */}
        <TouchableOpacity
          style={styles.addBtn}
          onPress={() => setModalVisible(true)}
          activeOpacity={0.7}
        >
          <Icon name="plus-circle" size={20} color="#FFFFFF" />
          <Text style={styles.addBtnText}>新增分类</Text>
        </TouchableOpacity>
      </ScrollView>

      {/* 新增分类弹窗 */}
      <Modal
        visible={modalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHandle} />
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>新增分类</Text>
              <Text style={styles.modalSubtitle}>添加自定义收支分类</Text>
            </View>

            {/* 类型选择 */}
            <Text style={styles.label}>分类类型</Text>
            <View style={styles.typeSelector}>
              <TouchableOpacity
                style={[
                  styles.typeButton,
                  categoryType === "cost" &&
                    styles.typeButtonActiveCost,
                ]}
                onPress={() => setCategoryType("cost")}
                activeOpacity={0.7}
              >
                <Icon
                  name="arrow-down-circle"
                  size={20}
                  color={
                    categoryType === "cost"
                      ? colors.expense
                      : colors.textTertiary
                  }
                />
                <Text
                  style={[
                    styles.typeButtonText,
                    categoryType === "cost" &&
                      styles.typeButtonTextActive,
                  ]}
                >
                  支出
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.typeButton,
                  categoryType === "income" &&
                    styles.typeButtonActiveIncome,
                ]}
                onPress={() => setCategoryType("income")}
                activeOpacity={0.7}
              >
                <Icon
                  name="arrow-up-circle"
                  size={20}
                  color={
                    categoryType === "income"
                      ? colors.income
                      : colors.textTertiary
                  }
                />
                <Text
                  style={[
                    styles.typeButtonText,
                    categoryType === "income" &&
                      styles.typeButtonTextActive,
                  ]}
                >
                  收入
                </Text>
              </TouchableOpacity>
            </View>

            {/* 名称输入 */}
            <Text style={styles.label}>分类名称</Text>
            <View style={styles.inputWrapper}>
              <Icon
                name="pencil"
                size={18}
                color={colors.textTertiary}
                style={{ marginRight: spacingV2.sm }}
              />
              <TextInput
                style={styles.input}
                value={categoryName}
                onChangeText={setCategoryName}
                placeholder="例如：种子、化肥、销售..."
                autoFocus
              />
            </View>

            {/* 按钮组 */}
            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalButton, styles.modalButtonCancel]}
                onPress={() => setModalVisible(false)}
                activeOpacity={0.7}
              >
                <Text style={styles.modalButtonTextCancel}>取消</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.modalButton,
                  styles.modalButtonConfirm,
                ]}
                onPress={handleCreate}
                activeOpacity={0.7}
              >
                <Text style={styles.modalButtonTextConfirm}>确定</Text>
              </TouchableOpacity>
            </View>
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
  pageHeader: {
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.lg,
  },
  pageHeaderTitle: {
    fontSize: fontSizeV2.xl,
    fontWeight: "800",
    color: colors.text,
    letterSpacing: -0.3,
  },
  pageHeaderSub: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 4,
  },
  content: {
    paddingHorizontal: spacingV2.lg,
    paddingBottom: spacingV2.xxxl,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacingV2.sm,
    gap: spacingV2.sm,
  },
  sectionDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  sectionTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
  },
  sectionCountBg: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.sm,
    paddingHorizontal: spacingV2.sm,
    paddingVertical: 2,
    marginLeft: "auto",
  },
  sectionCount: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    fontWeight: "700",
  },
  emptySection: {
    paddingVertical: spacingV2.xl,
    alignItems: "center",
  },
  emptySectionText: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
  },
  listCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    paddingHorizontal: spacingV2.lg,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  categoryItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacingV2.md,
  },
  categoryLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
    flex: 1,
  },
  categoryDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  categoryName: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "500",
    flex: 1,
  },
  categoryRight: {
    flexDirection: "row",
    alignItems: "center",
  },
  systemTag: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    fontWeight: "500",
  },
  deleteBtn: {
    padding: spacingV2.xs,
  },
  divider: {
    height: 1,
    backgroundColor: colors.borderLight,
  },
  addBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primary,
    borderRadius: borderRadiusV2.lg,
    paddingVertical: spacingV2.md,
    marginTop: spacingV2.lg,
    gap: spacingV2.sm,
  },
  addBtnText: {
    color: "#FFFFFF",
    fontSize: fontSizeV2.md,
    fontWeight: "700",
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  modalContent: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadiusV2.xxxl,
    borderTopRightRadius: borderRadiusV2.xxxl,
    padding: spacingV2.lg,
    paddingBottom: spacingV2.xxl,
  },
  modalHandle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    alignSelf: "center",
    marginBottom: spacingV2.md,
  },
  modalHeader: {
    alignItems: "center",
    marginBottom: spacingV2.lg,
  },
  modalTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacingV2.xs,
  },
  modalSubtitle: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  label: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    color: colors.textSecondary,
    marginBottom: spacingV2.sm,
    marginTop: spacingV2.lg,
    letterSpacing: 0.5,
  },
  typeSelector: {
    flexDirection: "row",
    gap: spacingV2.md,
  },
  typeButton: {
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
  typeButtonActiveCost: {
    backgroundColor: colors.expenseBg,
    borderColor: colors.expense,
  },
  typeButtonActiveIncome: {
    backgroundColor: colors.incomeBg,
    borderColor: colors.income,
  },
  typeButtonText: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  typeButtonTextActive: {
    color: colors.text,
    fontWeight: "700",
  },
  inputWrapper: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadiusV2.lg,
    paddingHorizontal: spacingV2.md,
    backgroundColor: colors.background,
  },
  input: {
    flex: 1,
    paddingVertical: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.text,
  },
  modalButtons: {
    flexDirection: "row",
    gap: spacingV2.md,
    marginTop: spacingV2.xl,
  },
  modalButton: {
    flex: 1,
    paddingVertical: spacingV2.md,
    borderRadius: borderRadiusV2.lg,
    alignItems: "center",
  },
  modalButtonCancel: {
    backgroundColor: colors.background,
    borderWidth: 1.5,
    borderColor: colors.borderLight,
  },
  modalButtonConfirm: {
    backgroundColor: colors.primary,
  },
  modalButtonTextCancel: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "600",
  },
  modalButtonTextConfirm: {
    fontSize: fontSizeV2.md,
    color: colors.textInverse,
    fontWeight: "700",
  },
});
