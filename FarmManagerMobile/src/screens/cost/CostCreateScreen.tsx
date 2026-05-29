import React, { useState, useMemo } from "react";
import {
  View,
  Text,
  TextInput,
  ScrollView,
  StyleSheet,
  Alert,
  TouchableOpacity,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import dayjs from "dayjs";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useCostStore } from "../../stores/costStore";
import { useCategoryStore } from "../../stores/categoryStore";
import { costApi, debtApi } from "../../api/client";
import { BigButton } from "../../components/BigButton";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { AIHelper } from "./components/AIHelper";
import { CategoryModal } from "./components/CategoryModal";
import { DatePickerModal } from "./components/DatePickerModal";

/** 根据收支类型返回对应的主题色 */
const useTheme = (recordType: "cost" | "income") => {
  return useMemo(() => {
    if (recordType === "income") {
      return {
        primary: colors.income,
        primaryMuted: colors.incomeBg,
        primaryLight: colors.successLight,
      };
    }
    return {
      primary: colors.expense,
      primaryMuted: colors.expenseBg,
      primaryLight: "#F5A0A0",
    };
  }, [recordType]);
};

const COST_CATEGORIES = [
  "种子",
  "化肥",
  "农药",
  "人工",
  "水电",
  "地租",
  "其他",
];
const INCOME_CATEGORIES = ["销售", "补贴", "其他"];

type CostCreateNavigationProp = NativeStackNavigationProp<
  RootStackParamList,
  "CostCreate"
>;

export const CostCreateScreen: React.FC = () => {
  const navigation = useNavigation<CostCreateNavigationProp>();
  const { createRecord, error, clearError } = useCostStore();
  const { categories } = useCategoryStore();

  const [recordType, setRecordType] = useState<"cost" | "income">("cost");
  const [category, setCategory] = useState("");
  const [amount, setAmount] = useState("");
  const [recordDate, setRecordDate] = useState(new Date());
  const [note, setNote] = useState("");
  const [aiInput, setAiInput] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [isDebt, setIsDebt] = useState(false);
  const [counterparty, setCounterparty] = useState("");
  const [dueDate, setDueDate] = useState("");

  const theme = useTheme(recordType);

  const availableCategories = useMemo(() => {
    const userCategories = categories
      .filter((c) => c.type === recordType)
      .map((c) => c.name);

    if (userCategories.length === 0) {
      return recordType === "cost" ? COST_CATEGORIES : INCOME_CATEGORIES;
    }

    return userCategories;
  }, [categories, recordType]);

  const handleAiParse = async () => {
    if (!aiInput.trim()) {
      return;
    }
    setAiLoading(true);
    try {
      const res = await costApi.parseRecord(aiInput.trim());
      const data = res.data;
      setRecordType(data.record_type as "cost" | "income");
      setCategory(data.category);
      setAmount(String(data.amount));
      setRecordDate(dayjs(data.record_date).toDate());
      if (data.note) {
        setNote(data.note);
      } else {
        setNote(aiInput.trim());
      }
      setAiInput("");
    } catch (err: any) {
      Alert.alert("解析失败", err.message || "请稍后重试");
    } finally {
      setAiLoading(false);
    }
  };

  const handleCategorySelect = (cat: string) => {
    setCategory(cat);
    setShowCategoryModal(false);
  };

  const handleTypeChange = (type: "cost" | "income") => {
    setRecordType(type);
    setCategory("");
    setIsDebt(false);
  };

  const handleSubmit = async () => {
    if (submitting) {
      return;
    }
    if (!category) {
      Alert.alert("提示", "请选择分类");
      return;
    }
    if (!amount || isNaN(Number(amount))) {
      Alert.alert("提示", "请输入有效金额");
      return;
    }
    if (recordType === "cost" && isDebt && !counterparty.trim()) {
      Alert.alert("提示", "请填写债权人");
      return;
    }

    setSubmitting(true);
    try {
      if (recordType === "cost" && isDebt) {
        await debtApi.createDebt({
          record_type: "cost",
          category,
          amount,
          record_date: dayjs(recordDate).format("YYYY-MM-DD"),
          record_subtype: "赊账",
          counterparty: counterparty.trim(),
          due_date: dueDate.trim() || undefined,
          note: note.trim() || undefined,
        });
        await useCostStore.getState().fetchRecords();
      } else {
        await createRecord({
          record_type: recordType,
          category,
          amount,
          record_date: dayjs(recordDate).format("YYYY-MM-DD"),
          note: note.trim() || undefined,
        });
      }

      if (error) {
        Alert.alert("创建失败", error);
        clearError();
        return;
      }

      navigation.goBack();
    } finally {
      setSubmitting(false);
    }
  };

  const isIncome = recordType === "income";

  return (
    <ScrollView style={styles.container} keyboardShouldPersistTaps="handled">
      <AIHelper
        aiInput={aiInput}
        aiLoading={aiLoading}
        onInputChange={setAiInput}
        onParse={handleAiParse}
      />

      {/* Amount - Primary Focus */}
      <View style={styles.amountSection}>
        <View style={styles.typeToggle}>
          <TouchableOpacity
            style={styles.typeToggleBtn}
            onPress={() => handleTypeChange("cost")}
            activeOpacity={0.7}
          >
            <Text
              style={[
                styles.typeToggleText,
                !isIncome && { color: theme.primary, fontWeight: "600" },
              ]}
            >
              支出
            </Text>
            {!isIncome && (
              <View style={[styles.typeIndicator, { backgroundColor: theme.primary }]} />
            )}
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.typeToggleBtn}
            onPress={() => handleTypeChange("income")}
            activeOpacity={0.7}
          >
            <Text
              style={[
                styles.typeToggleText,
                isIncome && { color: theme.primary, fontWeight: "600" },
              ]}
            >
              收入
            </Text>
            {isIncome && (
              <View style={[styles.typeIndicator, { backgroundColor: theme.primary }]} />
            )}
          </TouchableOpacity>
        </View>

        <View style={styles.amountInputRow}>
          <Text style={[styles.amountSymbol, { color: theme.primary }]}>¥</Text>
          <TextInput
            style={[styles.amountInput, { color: theme.primary }]}
            placeholder="0.00"
            placeholderTextColor={colors.textTertiary}
            keyboardType="decimal-pad"
            value={amount}
            onChangeText={setAmount}
          />
        </View>
      </View>

      {/* Form Fields - Single Card */}
      <View style={styles.formCard}>
        <TouchableOpacity
          style={styles.fieldRow}
          onPress={() => setShowCategoryModal(true)}
        >
          <Text style={styles.fieldLabel}>分类</Text>
          <View style={styles.fieldRight}>
            <Text
              style={category ? styles.fieldValue : styles.fieldPlaceholder}
            >
              {category || "请选择"}
            </Text>
            <Icon
              name="chevron-right"
              size={18}
              color={colors.textTertiary}
            />
          </View>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.fieldRow}
          onPress={() => setShowDatePicker(true)}
        >
          <Text style={styles.fieldLabel}>日期</Text>
          <View style={styles.fieldRight}>
            <Text style={styles.fieldValue}>
              {dayjs(recordDate).format("YYYY年M月D日")}
            </Text>
            <Icon
              name="chevron-right"
              size={18}
              color={colors.textTertiary}
            />
          </View>
        </TouchableOpacity>

        {recordType === "cost" && (
          <TouchableOpacity
            style={styles.fieldRow}
            onPress={() => setIsDebt(!isDebt)}
          >
            <Text style={styles.fieldLabel}>标记为赊账</Text>
            <View style={styles.fieldRight}>
              <View
                style={[
                  styles.toggleTrack,
                  isDebt && { backgroundColor: colors.primary },
                ]}
              >
                <View
                  style={[
                    styles.toggleThumb,
                    isDebt && styles.toggleThumbActive,
                  ]}
                />
              </View>
            </View>
          </TouchableOpacity>
        )}

        {recordType === "cost" && isDebt && (
          <View style={styles.debtFields}>
            <View style={styles.debtField}>
              <Text style={styles.debtLabel}>债权人</Text>
              <TextInput
                style={styles.debtInput}
                placeholder="如：老王农资店"
                placeholderTextColor={colors.textTertiary}
                value={counterparty}
                onChangeText={setCounterparty}
              />
            </View>
            <View style={styles.debtField}>
              <Text style={styles.debtLabel}>到期日（可选）</Text>
              <TextInput
                style={styles.debtInput}
                placeholder="YYYY-MM-DD"
                placeholderTextColor={colors.textTertiary}
                value={dueDate}
                onChangeText={setDueDate}
              />
            </View>
          </View>
        )}

        <View style={styles.noteSection}>
          <Text style={styles.noteLabel}>备注</Text>
          <TextInput
            style={styles.noteInput}
            placeholder="添加备注（可选）"
            placeholderTextColor={colors.textTertiary}
            multiline
            numberOfLines={3}
            textAlignVertical="top"
            value={note}
            onChangeText={setNote}
          />
        </View>
      </View>

      {/* Submit Button */}
      <View style={styles.submitArea}>
        <TouchableOpacity
          style={[
            styles.submitBtn,
            { backgroundColor: colors.primary },
            submitting && styles.submitBtnDisabled,
          ]}
          onPress={handleSubmit}
          disabled={submitting}
          activeOpacity={0.8}
        >
          <Text style={styles.submitBtnText}>
            {submitting ? "保存中..." : "保存"}
          </Text>
        </TouchableOpacity>
      </View>

      <DatePickerModal
        visible={showDatePicker}
        date={recordDate}
        onConfirm={(d) => {
          setRecordDate(d);
          setShowDatePicker(false);
        }}
        onCancel={() => setShowDatePicker(false)}
      />

      <CategoryModal
        visible={showCategoryModal}
        categories={availableCategories}
        selectedCategory={category}
        onSelect={handleCategorySelect}
        onClose={() => setShowCategoryModal(false)}
      />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  amountSection: {
    alignItems: "center",
    paddingVertical: spacingV2.xl,
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.md,
  },
  typeToggle: {
    flexDirection: "row",
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.full,
    padding: 4,
    marginBottom: spacingV2.lg,
  },
  typeToggleBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: borderRadiusV2.full,
    alignItems: "center",
    position: "relative",
  },
  typeToggleText: {
    fontSize: fontSizeV2.md,
    color: colors.textTertiary,
    fontWeight: "500",
  },
  typeIndicator: {
    position: "absolute",
    bottom: 4,
    width: 16,
    height: 3,
    borderRadius: 2,
  },
  amountInputRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  amountSymbol: {
    fontSize: fontSizeV2.xxxl,
    fontWeight: "300",
    color: colors.textSecondary,
    marginRight: spacingV2.sm,
  },
  amountInput: {
    fontSize: fontSizeV2.xxxxl,
    fontWeight: "700",
    color: colors.text,
    padding: 0,
    minWidth: 120,
    textAlign: "center",
    letterSpacing: -1,
  },
  formCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.md,
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.md,
    paddingBottom: spacingV2.lg,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  fieldRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacingV2.md,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(0,0,0,0.04)",
  },
  fieldLabel: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "500",
  },
  fieldRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.xs,
  },
  fieldValue: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  fieldPlaceholder: {
    fontSize: fontSizeV2.md,
    color: colors.textTertiary,
    fontWeight: "500",
  },
  toggleTrack: {
    width: 48,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.surfaceMuted,
    justifyContent: "center",
    paddingHorizontal: 2,
  },
  toggleThumb: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.surface,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  toggleThumbActive: {
    transform: [{ translateX: 20 }],
  },
  debtFields: {
    marginTop: spacingV2.md,
    gap: spacingV2.md,
    paddingLeft: spacingV2.md,
    borderLeftWidth: 3,
    borderLeftColor: colors.expense,
  },
  debtField: {
    gap: spacingV2.xs,
  },
  debtLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  debtInput: {
    borderRadius: borderRadiusV2.lg,
    padding: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.text,
    backgroundColor: colors.surfaceMuted,
  },
  noteSection: {
    marginTop: spacingV2.md,
    gap: spacingV2.xs,
  },
  noteLabel: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "500",
  },
  noteInput: {
    borderRadius: borderRadiusV2.lg,
    padding: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.text,
    backgroundColor: colors.surfaceMuted,
    minHeight: 80,
  },
  submitArea: {
    marginHorizontal: spacingV2.lg,
    marginTop: spacingV2.sm,
    marginBottom: spacingV2.xxxl,
  },
  submitBtn: {
    paddingVertical: 16,
    borderRadius: borderRadiusV2.lg,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 52,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  submitBtnDisabled: {
    opacity: 0.5,
  },
  submitBtnText: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
    color: colors.textInverse,
  },
});
