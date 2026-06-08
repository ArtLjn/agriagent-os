import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { showAlert } from "../../utils/alert";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { useCycleStore } from "../../stores/cycleStore";
import { cycleApi } from "../../api/client";
import { Loading } from "../../components/Loading";
import { DatePickerModal } from "../cost/components/DatePickerModal";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import dayjs from "dayjs";

const EXAMPLE_PROMPTS = [
  "东大棚种8424西瓜，5月1日开始",
  "秋季种辣椒，9月初开始",
  "春季种番茄，3月15日开始",
  "大棚种黄瓜，4月开始",
];

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

export const CycleCreateScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const { templates, loading, fetchTemplates, createCycle, error, clearError } =
    useCycleStore();

  const [name, setName] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(
    null
  );
  const [startDate, setStartDate] = useState("");
  const [recordDate, setRecordDate] = useState(new Date());
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [fieldName, setFieldName] = useState("");

  const [aiInput, setAiInput] = useState("");
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  useEffect(() => {
    if (error) {
      showAlert("错误", error);
      clearError();
    }
  }, [clearError, error]);

  const handleAiParse = async () => {
    const trimmed = aiInput.trim();
    if (!trimmed) return;
    setAiLoading(true);
    try {
      const res = await cycleApi.parseCycle(trimmed);
      const data = res.data;
      setName(data.name);
      setStartDate(data.start_date);
      if (data.field_name) setFieldName(data.field_name);
      if (data.crop_template_id) {
        setSelectedTemplateId(data.crop_template_id);
      }
      setAiInput("");
    } catch (err: any) {
      showAlert("解析失败", err.message || "请稍后重试");
    } finally {
      setAiLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!name.trim() || !selectedTemplateId || !startDate.trim()) {
      showAlert("提示", "请填写茬口名称、选择作物模板和开始日期");
      return;
    }
    await createCycle({
      name: name.trim(),
      crop_template_id: selectedTemplateId,
      start_date: startDate.trim(),
      field_name: fieldName.trim() || undefined,
    });
    navigation.goBack();
  };

  if (loading && templates.length === 0) {
    return <Loading />;
  }

  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId);
  const isFormValid = name.trim() && selectedTemplateId && startDate.trim();
  const templatePreview = selectedTemplate
    ? `${selectedTemplate.name}${
        selectedTemplate.variety ? ` · ${selectedTemplate.variety}` : ""
      }`
    : "选择作物";

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
        <View style={styles.aiSection}>
          <View style={styles.aiHeader}>
            <View style={styles.aiIconWrap}>
              <Icon name="auto-fix" size={18} color={colors.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.aiTitle}>智能填写</Text>
              <Text style={styles.aiSubtitle}>可以先手动填写，AI 只是辅助</Text>
            </View>
          </View>

          <View style={styles.aiInputWrap}>
            <TextInput
              style={styles.aiInput}
              placeholder="例如：我要在东大棚种8424西瓜，从5月1日开始"
              placeholderTextColor={colors.textTertiary}
              value={aiInput}
              onChangeText={setAiInput}
              multiline
              numberOfLines={1}
              textAlignVertical="top"
              maxLength={200}
            />
            <TouchableOpacity
              style={[
                styles.aiParseBtn,
                (aiLoading || !aiInput.trim()) && styles.aiParseBtnDisabled,
              ]}
              onPress={handleAiParse}
              disabled={aiLoading || !aiInput.trim()}
              activeOpacity={0.8}
            >
              {aiLoading ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <>
                  <Icon
                    name="lightning-bolt"
                    size={14}
                    color="#fff"
                    style={{ marginRight: 4 }}
                  />
                  <Text style={styles.aiParseBtnText}>填写</Text>
                </>
              )}
            </TouchableOpacity>
          </View>

          <View style={styles.examplesScroller}>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.examplesRow}
            >
              {EXAMPLE_PROMPTS.map((prompt) => (
                <TouchableOpacity
                  key={prompt}
                  style={styles.exampleChip}
                  onPress={() => setAiInput(prompt)}
                  activeOpacity={0.7}
                >
                  <Text style={styles.exampleText} numberOfLines={1}>
                    {prompt}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        </View>

        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <View>
              <Text style={styles.sectionTitle}>基本信息</Text>
              <Text style={styles.sectionSub}>创建一个种植批次</Text>
            </View>
            <View
              style={[
                styles.formStatus,
                isFormValid ? styles.formStatusReady : null,
              ]}
            >
              <Text
                style={[
                  styles.formStatusText,
                  isFormValid ? styles.formStatusTextReady : null,
                ]}
              >
                {isFormValid ? "可创建" : "待完善"}
              </Text>
            </View>
          </View>

          <View style={styles.fieldRow}>
            <Text style={styles.fieldLabel}>
              茬口名称 <Text style={styles.required}>*</Text>
            </Text>
            <TextInput
              style={styles.textInput}
              placeholder="如：东大棚8424西瓜"
              placeholderTextColor={colors.textTertiary}
              value={name}
              onChangeText={setName}
            />
          </View>

          <View style={styles.fieldRow}>
            <Text style={styles.fieldLabel}>选择作物</Text>
            <View style={styles.templateSummary}>
              <View style={styles.templateIcon}>
                <Icon name="sprout" size={18} color={colors.success} />
              </View>
              <Text
                style={[
                  styles.templateSummaryText,
                  !selectedTemplate && styles.templatePlaceholder,
                ]}
                numberOfLines={1}
              >
                {templatePreview}
              </Text>
              {selectedTemplate ? (
                <TouchableOpacity
                  onPress={() => setSelectedTemplateId(null)}
                  style={styles.clearChip}
                  hitSlop={{
                    top: 8,
                    bottom: 8,
                    left: 8,
                    right: 8,
                  }}
                >
                  <Icon name="close" size={16} color={colors.primary} />
                </TouchableOpacity>
              ) : null}
            </View>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.chipGrid}
            >
              {templates.map((t) => {
                const active = selectedTemplateId === t.id;
                return (
                  <TouchableOpacity
                    key={t.id}
                    style={[styles.chip, active && styles.chipActive]}
                    onPress={() => setSelectedTemplateId(t.id)}
                    activeOpacity={0.7}
                  >
                    <Text
                      style={[styles.chipText, active && styles.chipTextActive]}
                    >
                      {t.name}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </View>

          <View style={styles.fieldRow}>
            <Text style={styles.fieldLabel}>
              开始日期 <Text style={styles.required}>*</Text>
            </Text>
            <TouchableOpacity
              style={styles.dateTrigger}
              onPress={() => setShowDatePicker(true)}
              activeOpacity={0.7}
            >
              <Text
                style={[
                  styles.dateTriggerText,
                  !startDate && styles.dateTriggerPlaceholder,
                ]}
              >
                {startDate || "选择日期"}
              </Text>
              <Icon
                name="calendar-outline"
                size={20}
                color={colors.textTertiary}
              />
            </TouchableOpacity>
          </View>

          <View style={styles.fieldRow}>
            <Text style={styles.fieldLabel}>
              地块名称 <Text style={styles.optional}>可选</Text>
            </Text>
            <TextInput
              style={styles.textInput}
              placeholder="如：东大棚"
              placeholderTextColor={colors.textTertiary}
              value={fieldName}
              onChangeText={setFieldName}
            />
          </View>
        </View>
      </ScrollView>

      {/* 底部创建按钮 */}
      <View style={styles.footer}>
        <TouchableOpacity
          style={[styles.saveBtn, !isFormValid && styles.saveBtnDisabled]}
          onPress={handleSubmit}
          disabled={!isFormValid}
          activeOpacity={0.8}
        >
          <Text style={styles.saveBtnText}>创建茬口</Text>
        </TouchableOpacity>
      </View>

      <DatePickerModal
        visible={showDatePicker}
        date={recordDate}
        onConfirm={(d) => {
          setRecordDate(d);
          setStartDate(dayjs(d).format("YYYY-MM-DD"));
          setShowDatePicker(false);
        }}
        onCancel={() => setShowDatePicker(false)}
        disableFuture={false}
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
    padding: spacingV2.lg,
    paddingBottom: 120,
  },

  aiSection: {
    padding: spacingV2.lg,
    borderRadius: borderRadiusV2.xxl,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
    marginBottom: spacingV2.lg,
  },
  aiHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacingV2.sm,
  },
  aiIconWrap: {
    width: 40,
    height: 40,
    borderRadius: 16,
    backgroundColor: colors.primaryMuted,
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacingV2.md,
  },
  aiTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "900",
    color: colors.text,
  },
  aiSubtitle: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  aiInputWrap: {
    backgroundColor: colors.background,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    minHeight: 58,
    justifyContent: "center",
  },
  aiInput: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    minHeight: 32,
    textAlignVertical: "top",
    lineHeight: 22,
    paddingVertical: 0,
    paddingRight: 104,
  },
  aiParseBtn: {
    position: "absolute",
    right: spacingV2.sm,
    top: spacingV2.sm,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.primary,
    borderRadius: borderRadiusV2.full,
    paddingHorizontal: spacingV2.md,
    paddingVertical: 8,
  },
  aiParseBtnDisabled: {
    backgroundColor: colors.disabled,
  },
  aiParseBtnText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: "#fff",
  },
  examplesScroller: {
    marginHorizontal: -spacingV2.lg,
    marginTop: spacingV2.sm,
  },
  examplesRow: {
    flexDirection: "row",
    gap: spacingV2.sm,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: 2,
  },
  exampleChip: {
    backgroundColor: colors.background,
    borderRadius: borderRadiusV2.full,
    borderWidth: 1,
    borderColor: colors.borderLight,
    paddingHorizontal: spacingV2.md,
    paddingVertical: 7,
  },
  exampleText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },

  section: {
    padding: spacingV2.lg,
    borderRadius: borderRadiusV2.xxl,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacingV2.md,
    marginBottom: spacingV2.lg,
  },
  sectionTitle: {
    fontSize: fontSizeV2.xl,
    fontWeight: "900",
    color: colors.text,
  },
  sectionSub: {
    marginTop: 2,
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  formStatus: {
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.xs,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.surfaceMuted,
  },
  formStatusReady: {
    backgroundColor: colors.successMuted,
  },
  formStatusText: {
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "900",
  },
  formStatusTextReady: {
    color: colors.success,
  },
  fieldRow: {
    marginBottom: spacingV2.lg,
  },
  fieldLabel: {
    fontSize: fontSizeV2.sm,
    fontWeight: "800",
    color: colors.textSecondary,
    marginBottom: spacingV2.xs,
  },
  required: {
    color: colors.danger,
  },
  optional: {
    fontWeight: "400",
    color: colors.textTertiary,
  },
  textInput: {
    backgroundColor: colors.background,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.text,
    minHeight: 52,
  },
  dateTrigger: {
    backgroundColor: colors.background,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacingV2.md,
    minHeight: 52,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  dateTriggerText: {
    fontSize: fontSizeV2.md,
    color: colors.text,
  },
  dateTriggerPlaceholder: {
    color: colors.textTertiary,
  },
  chipGrid: {
    flexDirection: "row",
    gap: spacingV2.sm,
    paddingTop: spacingV2.sm,
  },
  chip: {
    backgroundColor: colors.background,
    borderRadius: borderRadiusV2.full,
    paddingHorizontal: spacingV2.md,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  chipActive: {
    backgroundColor: colors.successMuted,
    borderColor: "rgba(59, 178, 115, 0.18)",
  },
  chipText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "800",
  },
  chipTextActive: {
    color: colors.success,
  },
  templateSummary: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 52,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
    paddingHorizontal: spacingV2.md,
    gap: spacingV2.sm,
  },
  templateIcon: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.successMuted,
  },
  templateSummaryText: {
    flex: 1,
    minWidth: 0,
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "800",
  },
  templatePlaceholder: {
    color: colors.textTertiary,
    fontWeight: "600",
  },
  clearChip: {
    width: 28,
    height: 28,
    alignItems: "center",
    justifyContent: "center",
  },

  footer: {
    backgroundColor: colors.surface,
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.md,
    paddingBottom: spacingV2.lg + 4,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  saveBtn: {
    backgroundColor: colors.primary,
    borderRadius: borderRadiusV2.lg,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 54,
  },
  saveBtnDisabled: {
    backgroundColor: colors.disabled,
  },
  saveBtnText: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: "#fff",
  },
});
