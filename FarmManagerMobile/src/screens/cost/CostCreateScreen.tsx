import React, { useState, useMemo } from "react";
import {
  View,
  Text,
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
import { CostAmountPanel } from "./components/CostAmountPanel";
import { CostCategoryPicker } from "./components/CostCategoryPicker";
import { CostCreateHeroHeader } from "./components/CostCreateHeroHeader";
import { CostMetaPanel } from "./components/CostMetaPanel";
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
  const submitText = submitting
    ? "保存中..."
    : isIncome
    ? "保存这笔收入"
    : "保存这笔支出";

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
        <CostCreateHeroHeader onBack={() => navigation.goBack()} />

        <AIHelper
          aiInput={aiInput}
          aiLoading={aiLoading}
          onInputChange={setAiInput}
          onParse={handleAiParse}
          themeColor={theme.primary}
          themeMuted={theme.primaryMuted}
        />

        <CostAmountPanel
          amount={amount}
          recordType={recordType}
          onAmountChange={setAmount}
          onTypeChange={handleTypeChange}
        />

        <CostCategoryPicker
          categories={availableCategories}
          selectedCategory={category}
          themeColor={theme.primary}
          themeMuted={theme.primaryMuted}
          icons={CATEGORY_ICONS}
          onSelect={setCategory}
          onMore={() => setShowCategoryModal(true)}
        />

        <CostMetaPanel
          recordDate={recordDate}
          isIncome={isIncome}
          isDebt={isDebt}
          counterparty={counterparty}
          dueDate={dueDate}
          note={note}
          themeColor={theme.primary}
          onDatePress={() => setShowDatePicker(true)}
          onDebtToggle={() => setIsDebt(!isDebt)}
          onCounterpartyChange={setCounterparty}
          onDueDatePress={() => setShowDueDatePicker(true)}
          onNoteChange={setNote}
        />

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
          <Icon name="check" size={20} color={colors.textInverse} />
          <Text style={styles.submitBtnText}>{submitText}</Text>
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
    paddingTop: 0,
    paddingBottom: 132,
  },
  bottomBar: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    backgroundColor: "rgba(255,255,255,0.96)",
  },
  bottomSpacer: {
    height: spacingV2.xxl,
  },
  submitBtn: {
    flexDirection: "row",
    gap: spacingV2.sm,
    borderRadius: borderRadiusV2.xl,
    alignItems: "center",
    justifyContent: "center",
    height: 54,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.18,
    shadowRadius: 16,
    elevation: 5,
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
