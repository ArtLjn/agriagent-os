import React, { useState, useMemo } from "react";
import {
  View,
  Text,
  TextInput,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { showAlert } from "../../utils/alert";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import dayjs from "dayjs";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useCostStore } from "../../stores/costStore";
import { useCategoryStore } from "../../stores/categoryStore";
import { costApi, debtApi } from "../../api/client";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { AIHelper } from "./components/AIHelper";
import { CategoryModal } from "./components/CategoryModal";
import { DatePickerModal } from "./components/DatePickerModal";

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

const CATEGORY_ICONS: Record<string, string> = {
  种子: "seed",
  化肥: "flask",
  农药: "spray",
  人工: "account-hard-hat",
  水电: "flash",
  地租: "home-variant",
  销售: "cash",
  补贴: "gift",
  其他: "dots-horizontal",
};

const QUICK_AMOUNTS = ["50", "100", "200", "500"];

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
  const [dueDate, setDueDate] = useState<Date | null>(null);
  const [showDueDatePicker, setShowDueDatePicker] = useState(false);

  const isIncome = recordType === "income";
  const theme = useMemo(() => {
    if (isIncome) {
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
  }, [isIncome]);

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
      setNote(data.note || aiInput.trim());
      setAiInput("");
    } catch (err: any) {
      showAlert("解析失败", err.message || "请稍后重试");
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
  };

  const handleSubmit = async () => {
    if (submitting) {
      return;
    }
    if (!category) {
      showAlert("提示", "请选择分类");
      return;
    }
    if (!amount || isNaN(Number(amount))) {
      showAlert("提示", "请输入有效金额");
      return;
    }
    if (isDebt) {
      if (!counterparty.trim()) {
        showAlert("提示", isIncome ? "请填写欠款人" : "请填写债权人");
        return;
      }
      if (!dueDate) {
        showAlert("提示", "请选择预计还款日");
        return;
      }
    }

    setSubmitting(true);
    try {
      if (isDebt) {
        await debtApi.createDebt({
          record_type: recordType,
          category,
          amount,
          record_date: dayjs(recordDate).format("YYYY-MM-DD"),
          record_subtype: "赊账",
          counterparty: counterparty.trim(),
          due_date: dueDate ? dayjs(dueDate).format("YYYY-MM-DD") : undefined,
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
        showAlert("创建失败", error);
        clearError();
        return;
      }
      navigation.goBack();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}
    >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <AIHelper
          aiInput={aiInput}
          aiLoading={aiLoading}
          onInputChange={setAiInput}
          onParse={handleAiParse}
          themeColor={theme.primary}
          themeMuted={theme.primaryMuted}
        />

        {/* Amount Hero Card */}
        <View
          style={[styles.amountCard, { backgroundColor: theme.primaryMuted }]}
        >
          <View style={styles.typeToggle}>
            <TouchableOpacity
              style={[
                styles.typeToggleBtn,
                !isIncome && styles.typeToggleBtnActive,
              ]}
              onPress={() => handleTypeChange("cost")}
              activeOpacity={0.7}
            >
              <Text
                style={[
                  styles.typeToggleText,
                  !isIncome && { color: theme.primary },
                  !isIncome && styles.typeToggleTextActive,
                ]}
              >
                支出
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.typeToggleBtn,
                isIncome && styles.typeToggleBtnActive,
              ]}
              onPress={() => handleTypeChange("income")}
              activeOpacity={0.7}
            >
              <Text
                style={[
                  styles.typeToggleText,
                  isIncome && { color: theme.primary },
                  isIncome && styles.typeToggleTextActive,
                ]}
              >
                收入
              </Text>
            </TouchableOpacity>
          </View>

          <View style={styles.amountInputRow}>
            <Text style={[styles.amountSymbol, { color: theme.primary }]}>
              ¥
            </Text>
            <TextInput
              style={[styles.amountInput, { color: theme.primary }]}
              placeholder="0.00"
              placeholderTextColor={theme.primary + "60"}
              keyboardType="decimal-pad"
              value={amount}
              onChangeText={setAmount}
            />
          </View>
          <View style={styles.quickAmountRow}>
            {QUICK_AMOUNTS.map((value) => (
              <TouchableOpacity
                key={value}
                style={styles.quickAmountChip}
                onPress={() => setAmount(value)}
                activeOpacity={0.7}
              >
                <Text
                  style={[styles.quickAmountText, { color: theme.primary }]}
                >
                  ¥{value}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <TouchableOpacity
            style={styles.recordTimePill}
            onPress={() => setShowDatePicker(true)}
            activeOpacity={0.7}
          >
            <Icon name="clock-outline" size={15} color={colors.textSecondary} />
            <Text style={styles.recordTimeText}>
              {dayjs(recordDate).format("M月D日 HH:mm")}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Category Grid */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionTitle}>选择分类</Text>
          <View style={styles.categoryGrid}>
            {availableCategories.map((cat) => {
              const isActive = category === cat;
              const icon = CATEGORY_ICONS[cat] || "tag";
              return (
                <TouchableOpacity
                  key={cat}
                  style={[
                    styles.categoryChip,
                    isActive && {
                      backgroundColor: theme.primaryMuted,
                      borderColor: theme.primary,
                    },
                  ]}
                  onPress={() => setCategory(cat)}
                  activeOpacity={0.7}
                >
                  <Icon
                    name={icon}
                    size={18}
                    color={isActive ? theme.primary : colors.textSecondary}
                  />
                  <Text
                    style={[
                      styles.categoryChipText,
                      isActive && { color: theme.primary, fontWeight: "700" },
                    ]}
                  >
                    {cat}
                  </Text>
                </TouchableOpacity>
              );
            })}
            <TouchableOpacity
              style={styles.categoryChip}
              onPress={() => setShowCategoryModal(true)}
              activeOpacity={0.7}
            >
              <Icon
                name="dots-horizontal"
                size={18}
                color={colors.textTertiary}
              />
              <Text
                style={[
                  styles.categoryChipText,
                  { color: colors.textTertiary },
                ]}
              >
                更多
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Form Fields */}
        <View style={styles.sectionCard}>
          <TouchableOpacity
            style={styles.fieldRow}
            onPress={() => setShowDatePicker(true)}
          >
            <View style={styles.fieldLeft}>
              <Icon
                name="calendar-clock"
                size={18}
                color={colors.textSecondary}
              />
              <Text style={styles.fieldLabel}>日期</Text>
            </View>
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

          <TouchableOpacity
            style={styles.fieldRow}
            onPress={() => setIsDebt(!isDebt)}
          >
            <View style={styles.fieldLeft}>
              <Icon
                name="account-clock-outline"
                size={18}
                color={colors.textSecondary}
              />
              <View>
                <Text style={styles.fieldLabel}>
                  {isIncome ? "对方先欠着" : "这笔先赊着"}
                </Text>
                <Text style={styles.fieldHint}>
                  {isIncome ? "收入未收款，记为应收" : "支出未付款，记为应付"}
                </Text>
              </View>
            </View>
            <View style={styles.fieldRight}>
              <View
                style={[
                  styles.toggleTrack,
                  isDebt && { backgroundColor: theme.primary },
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

          {isDebt && (
            <View style={styles.debtFields}>
              <View style={styles.debtField}>
                <Text style={styles.debtLabel}>
                  {isIncome ? "欠款人" : "债权人"}
                </Text>
                <TextInput
                  style={styles.debtInput}
                  placeholder={isIncome ? "如：收购商老李" : "如：老王农资店"}
                  placeholderTextColor={colors.textTertiary}
                  value={counterparty}
                  onChangeText={setCounterparty}
                />
              </View>
              <TouchableOpacity
                style={styles.debtField}
                onPress={() => setShowDueDatePicker(true)}
                activeOpacity={0.7}
              >
                <Text style={styles.debtLabel}>预计还款日</Text>
                <View style={styles.debtDateRow}>
                  <Text
                    style={[
                      styles.debtDateValue,
                      !dueDate && { color: colors.textTertiary },
                    ]}
                  >
                    {dueDate
                      ? dayjs(dueDate).format("YYYY-MM-DD")
                      : "请选择预计还款日"}
                  </Text>
                  <Icon
                    name="chevron-right"
                    size={18}
                    color={colors.textTertiary}
                  />
                </View>
              </TouchableOpacity>
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

        <View style={styles.bottomSpacer} />
      </ScrollView>

      {/* Fixed Bottom Submit */}
      <View style={styles.bottomBar}>
        <TouchableOpacity
          style={[
            styles.submitBtn,
            { backgroundColor: theme.primary },
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
        showTimePicker
      />

      <DatePickerModal
        visible={showDueDatePicker}
        date={dueDate || new Date()}
        onConfirm={(d) => {
          setDueDate(d);
          setShowDueDatePicker(false);
        }}
        onCancel={() => setShowDueDatePicker(false)}
        disableFuture={false}
      />

      <CategoryModal
        visible={showCategoryModal}
        categories={availableCategories}
        selectedCategory={category}
        onSelect={handleCategorySelect}
        onClose={() => setShowCategoryModal(false)}
      />
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 128,
  },
  amountCard: {
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.lg,
    borderRadius: borderRadiusV2.xxxl,
    paddingVertical: spacingV2.xl,
    paddingHorizontal: spacingV2.xl,
    alignItems: "center",
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  typeToggle: {
    flexDirection: "row",
    backgroundColor: "rgba(255,255,255,0.6)",
    borderRadius: borderRadiusV2.full,
    padding: 4,
    marginBottom: spacingV2.lg,
    alignSelf: "stretch",
  },
  typeToggleBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: borderRadiusV2.full,
    alignItems: "center",
  },
  typeToggleBtnActive: {
    backgroundColor: colors.surface,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 3,
    elevation: 2,
  },
  typeToggleText: {
    fontSize: fontSizeV2.md,
    color: colors.textTertiary,
    fontWeight: "500",
  },
  typeToggleTextActive: {
    fontWeight: "700",
  },
  amountInputRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  amountSymbol: {
    fontSize: fontSizeV2.xxxl,
    fontWeight: "300",
    marginRight: spacingV2.sm,
  },
  amountInput: {
    fontSize: fontSizeV2.xxxxl,
    fontWeight: "800",
    padding: 0,
    minWidth: 120,
    maxWidth: "78%",
    textAlign: "center",
    letterSpacing: -1,
  },
  quickAmountRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: spacingV2.xs,
    marginTop: spacingV2.lg,
  },
  quickAmountChip: {
    paddingHorizontal: spacingV2.md,
    paddingVertical: 7,
    borderRadius: borderRadiusV2.full,
    backgroundColor: "rgba(255,255,255,0.72)",
  },
  quickAmountText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
  },
  recordTimePill: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.xs,
    marginTop: spacingV2.md,
    paddingHorizontal: spacingV2.md,
    paddingVertical: 7,
    borderRadius: borderRadiusV2.full,
    backgroundColor: "rgba(255,255,255,0.58)",
  },
  recordTimeText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  sectionCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.lg,
    padding: spacingV2.lg,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacingV2.md,
  },
  categoryGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacingV2.sm,
  },
  categoryChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: spacingV2.md,
    paddingVertical: 10,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.surfaceMuted,
  },
  categoryChipText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  fieldRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacingV2.md + 2,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  fieldLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
  },
  fieldLabel: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "500",
  },
  fieldHint: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    marginTop: 2,
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
    padding: spacingV2.md,
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.lg,
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
    backgroundColor: colors.surface,
  },
  debtDateRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderRadius: borderRadiusV2.lg,
    padding: spacingV2.md,
    backgroundColor: colors.surface,
  },
  debtDateValue: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "500",
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
  bottomBar: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  bottomSpacer: {
    height: spacingV2.xxl,
  },
  submitBtn: {
    paddingVertical: 14,
    borderRadius: borderRadiusV2.lg,
    alignItems: "center",
    justifyContent: "center",
    height: 48,
  },
  submitBtnDisabled: {
    opacity: 0.5,
  },
  submitBtnText: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: "#FFFFFF",
  },
});
