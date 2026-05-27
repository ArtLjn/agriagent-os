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
import { Card } from "../../components/Card";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const CATEGORY_ICONS: Record<string, string> = {
  种子: "seed",
  化肥: "flask",
  农药: "spray",
  人工: "account-group",
  机械: "tractor",
  水电: "flash",
  地租: "home-variant",
  销售: "cash-register",
  其他支出: "dots-horizontal",
  其他收入: "dots-horizontal",
};

function getCategoryIcon(name: string): string {
  return CATEGORY_ICONS[name] || "tag-outline";
}

const CategoryItem: React.FC<{
  name: string;
  type: "expense" | "income";
  isSystem: boolean;
  onDelete?: () => void;
}> = ({ name, type, isSystem, onDelete }) => (
  <Card style={localStyles.categoryItem}>
    <View style={localStyles.categoryRow}>
      <View style={localStyles.categoryLeft}>
        <View
          style={[
            localStyles.categoryIcon,
            {
              backgroundColor:
                type === "expense" ? colors.dangerLight : colors.successLight,
            },
          ]}
        >
          <Icon
            name={getCategoryIcon(name)}
            size={20}
            color={type === "expense" ? colors.danger : colors.success}
          />
        </View>
        <Text style={localStyles.categoryName}>{name}</Text>
      </View>
      <View style={localStyles.categoryTags}>
        {isSystem && (
          <View style={localStyles.systemTagBg}>
            <Text style={localStyles.systemTag}>系统</Text>
          </View>
        )}
        {!isSystem && (
          <TouchableOpacity
            style={localStyles.deleteBtn}
            onPress={onDelete}
            activeOpacity={0.7}
          >
            <Icon name="trash-can-outline" size={18} color={colors.danger} />
          </TouchableOpacity>
        )}
      </View>
    </View>
  </Card>
);

export const CostCategoryScreen: React.FC = () => {
  const {
    categories,
    loading,
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
    } catch (err) {
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
          } catch (err) {
            // Error 已在 store 中处理
          }
        },
      },
    ]);
  };

  const expenseCategories = categories.filter((c) => c.type === "cost");
  const incomeCategories = categories.filter((c) => c.type === "income");

  return (
    <SafeAreaView style={localStyles.container} edges={["bottom"]}>
      {/* 页面头部 */}
      <View style={localStyles.pageHeader}>
        <View style={localStyles.pageHeaderIcon}>
          <Icon name="tag-multiple" size={28} color={colors.primary} />
        </View>
        <View>
          <Text style={localStyles.pageHeaderTitle}>收支分类</Text>
          <Text style={localStyles.pageHeaderSub}>
            管理记账所需的支出与收入分类
          </Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={localStyles.content}>
        {/* 支出分类 */}
        <View style={localStyles.sectionHeader}>
          <View
            style={[localStyles.sectionDot, { backgroundColor: colors.danger }]}
          />
          <Text style={localStyles.sectionTitle}>支出分类</Text>
          <View style={localStyles.sectionCountBg}>
            <Text style={localStyles.sectionCount}>
              {expenseCategories.length}
            </Text>
          </View>
        </View>
        {expenseCategories.length === 0 && (
          <View style={localStyles.emptySection}>
            <Text style={localStyles.emptySectionText}>暂无自定义支出分类</Text>
          </View>
        )}
        {expenseCategories.map((category) => (
          <CategoryItem
            key={category.id}
            name={category.name}
            type="expense"
            isSystem={category.is_default}
            onDelete={() => handleDelete(category.id, category.name)}
          />
        ))}

        {/* 收入分类 */}
        <View style={[localStyles.sectionHeader, { marginTop: spacing.lg }]}>
          <View
            style={[
              localStyles.sectionDot,
              { backgroundColor: colors.success },
            ]}
          />
          <Text style={localStyles.sectionTitle}>收入分类</Text>
          <View style={localStyles.sectionCountBg}>
            <Text style={localStyles.sectionCount}>
              {incomeCategories.length}
            </Text>
          </View>
        </View>
        {incomeCategories.length === 0 && (
          <View style={localStyles.emptySection}>
            <Text style={localStyles.emptySectionText}>暂无自定义收入分类</Text>
          </View>
        )}
        {incomeCategories.map((category) => (
          <CategoryItem
            key={category.id}
            name={category.name}
            type="income"
            isSystem={category.is_default}
            onDelete={() => handleDelete(category.id, category.name)}
          />
        ))}

        {/* 新增按钮 */}
        <TouchableOpacity
          style={localStyles.addBtn}
          onPress={() => setModalVisible(true)}
          activeOpacity={0.7}
        >
          <Icon name="plus-circle" size={20} color="#FFFFFF" />
          <Text style={localStyles.addBtnText}>新增分类</Text>
        </TouchableOpacity>
      </ScrollView>

      {/* 新增分类弹窗 */}
      <Modal
        visible={modalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={localStyles.modalOverlay}>
          <View style={localStyles.modalContent}>
            <View style={localStyles.modalHandle} />
            <View style={localStyles.modalHeader}>
              <View style={localStyles.modalHeaderIcon}>
                <Icon name="tag-plus" size={28} color={colors.primary} />
              </View>
              <Text style={localStyles.modalTitle}>新增分类</Text>
              <Text style={localStyles.modalSubtitle}>添加自定义收支分类</Text>
            </View>

            {/* 类型选择 */}
            <Text style={localStyles.label}>分类类型</Text>
            <View style={localStyles.typeSelector}>
              <TouchableOpacity
                style={[
                  localStyles.typeButton,
                  categoryType === "expense" &&
                    localStyles.typeButtonActiveExpense,
                ]}
                onPress={() => setCategoryType("expense")}
                activeOpacity={0.7}
              >
                <Icon
                  name="arrow-down-circle"
                  size={20}
                  color={
                    categoryType === "expense"
                      ? colors.danger
                      : colors.textTertiary
                  }
                />
                <Text
                  style={[
                    localStyles.typeButtonText,
                    categoryType === "expense" &&
                      localStyles.typeButtonTextActive,
                  ]}
                >
                  支出
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  localStyles.typeButton,
                  categoryType === "income" &&
                    localStyles.typeButtonActiveIncome,
                ]}
                onPress={() => setCategoryType("income")}
                activeOpacity={0.7}
              >
                <Icon
                  name="arrow-up-circle"
                  size={20}
                  color={
                    categoryType === "income"
                      ? colors.success
                      : colors.textTertiary
                  }
                />
                <Text
                  style={[
                    localStyles.typeButtonText,
                    categoryType === "income" &&
                      localStyles.typeButtonTextActive,
                  ]}
                >
                  收入
                </Text>
              </TouchableOpacity>
            </View>

            {/* 名称输入 */}
            <Text style={localStyles.label}>分类名称</Text>
            <View style={localStyles.inputWrapper}>
              <Icon
                name="pencil"
                size={18}
                color={colors.textTertiary}
                style={{ marginRight: spacing.sm }}
              />
              <TextInput
                style={localStyles.input}
                value={categoryName}
                onChangeText={setCategoryName}
                placeholder="例如：种子、化肥、销售..."
                autoFocus
              />
            </View>

            {/* 按钮组 */}
            <View style={localStyles.modalButtons}>
              <TouchableOpacity
                style={[localStyles.modalButton, localStyles.modalButtonCancel]}
                onPress={() => setModalVisible(false)}
                activeOpacity={0.7}
              >
                <Text style={localStyles.modalButtonTextCancel}>取消</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  localStyles.modalButton,
                  localStyles.modalButtonConfirm,
                ]}
                onPress={handleCreate}
                activeOpacity={0.7}
              >
                <Text style={localStyles.modalButtonTextConfirm}>确定</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
};

const localStyles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  pageHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
    gap: spacing.md,
  },
  pageHeaderIcon: {
    width: 48,
    height: 48,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  pageHeaderTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  pageHeaderSub: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  content: {
    padding: spacing.md,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  sectionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  sectionCountBg: {
    backgroundColor: colors.background,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    marginLeft: "auto",
  },
  sectionCount: {
    fontSize: fontSize.sm,
    color: colors.textTertiary,
    fontWeight: "700",
  },
  emptySection: {
    paddingVertical: spacing.xl,
    alignItems: "center",
  },
  emptySectionText: {
    fontSize: fontSize.sm,
    color: colors.textTertiary,
  },
  categoryItem: {
    marginBottom: spacing.sm,
  },
  categoryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  categoryLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    flex: 1,
  },
  categoryIcon: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  categoryName: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "600",
    flex: 1,
  },
  categoryTags: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  systemTagBg: {
    backgroundColor: colors.infoLight,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  systemTag: {
    fontSize: fontSize.xs,
    color: colors.info,
    fontWeight: "600",
  },
  deleteBtn: {
    padding: spacing.sm,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  modalContent: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    padding: spacing.lg,
    paddingBottom: spacing.xl,
  },
  modalHandle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    alignSelf: "center",
    marginBottom: spacing.md,
  },
  modalHeader: {
    alignItems: "center",
    marginBottom: spacing.lg,
  },
  modalHeaderIcon: {
    width: 56,
    height: 56,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
  },
  modalTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacing.xs,
  },
  modalSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.textSecondary,
    marginBottom: spacing.sm,
    marginTop: spacing.lg,
    letterSpacing: 0.5,
  },
  typeSelector: {
    flexDirection: "row",
    gap: spacing.md,
  },
  typeButton: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.background,
    borderWidth: 1.5,
    borderColor: colors.borderLight,
  },
  typeButtonActiveExpense: {
    backgroundColor: colors.dangerLight,
    borderColor: colors.danger,
  },
  typeButtonActiveIncome: {
    backgroundColor: colors.successLight,
    borderColor: colors.success,
  },
  typeButtonText: {
    fontSize: fontSize.md,
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
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.background,
  },
  input: {
    flex: 1,
    paddingVertical: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
  },
  modalButtons: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.xl,
  },
  modalButton: {
    flex: 1,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.lg,
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
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "600",
  },
  modalButtonTextConfirm: {
    fontSize: fontSize.md,
    color: colors.textInverse,
    fontWeight: "700",
  },
  addBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    marginTop: spacing.lg,
    gap: spacing.sm,
  },
  addBtnText: {
    color: "#FFFFFF",
    fontSize: fontSize.md,
    fontWeight: "700",
  },
});
