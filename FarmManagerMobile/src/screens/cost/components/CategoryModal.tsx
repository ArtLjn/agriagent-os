import React from "react";
import {
  View,
  Text,
  Modal,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import { colors } from "../../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import type { RootStackParamList } from "../../../navigation/AppNavigator";

interface CategoryModalProps {
  visible: boolean;
  categories: string[];
  selectedCategory: string;
  onSelect: (category: string) => void;
  onClose: () => void;
}

export const CategoryModal: React.FC<CategoryModalProps> = ({
  visible,
  categories,
  selectedCategory,
  onSelect,
  onClose,
}) => {
  const navigation = useNavigation();

  const categoryIcons: Record<string, string> = {
    种子: "seed",
    化肥: "flask",
    农药: "spray",
    人工: "account-group",
    机械: "tractor",
    水电: "flash",
    地租: "home-variant",
    销售: "cash-register",
    补贴: "hand-coin",
    其他: "dots-horizontal",
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>选择分类</Text>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
              <Icon name="close" size={24} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>

          <ScrollView
            showsVerticalScrollIndicator={false}
            contentContainerStyle={styles.gridContent}
          >
            <View style={styles.modalGrid}>
              {categories.map((cat) => (
                <TouchableOpacity
                  key={cat}
                  style={[
                    styles.categoryBtn,
                    selectedCategory === cat && styles.categoryBtnActive,
                  ]}
                  onPress={() => onSelect(cat)}
                  activeOpacity={0.7}
                >
                  <Icon
                    name={categoryIcons[cat] || "tag-outline"}
                    size={22}
                    color={
                      selectedCategory === cat ? "#FFFFFF" : colors.primary
                    }
                  />
                  <Text
                    style={[
                      styles.categoryBtnText,
                      selectedCategory === cat && styles.categoryBtnTextActive,
                    ]}
                  >
                    {cat}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </ScrollView>

          <TouchableOpacity
            style={styles.manageCategoriesBtn}
            onPress={() => {
              onClose();
              // @ts-ignore
              navigation.navigate("CostCategory");
            }}
          >
            <Icon name="cog-outline" size={18} color={colors.primary} />
            <Text style={styles.manageCategoriesText}>管理分类</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
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
    maxHeight: "70%",
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.lg,
  },
  modalTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  closeBtn: {
    padding: spacing.sm,
  },
  gridContent: {
    paddingBottom: spacing.md,
  },
  modalGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  categoryBtn: {
    width: "31%",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.md,
    backgroundColor: colors.background,
    borderRadius: borderRadius.lg,
    borderWidth: 1.5,
    borderColor: colors.borderLight,
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  categoryBtnActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  categoryBtnText: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: "600",
  },
  categoryBtnTextActive: {
    color: "#FFFFFF",
  },
  manageCategoriesBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.md,
    marginTop: spacing.sm,
    backgroundColor: colors.primaryMuted,
    borderRadius: borderRadius.lg,
    gap: spacing.sm,
  },
  manageCategoriesText: {
    fontSize: fontSize.md,
    color: colors.primary,
    fontWeight: "600",
  },
});
