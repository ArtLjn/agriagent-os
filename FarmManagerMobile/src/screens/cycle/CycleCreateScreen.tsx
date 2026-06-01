import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  Alert,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
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
  const {
    templates,
    loading,
    fetchTemplates,
    createCycle,
    error,
    clearError,
  } = useCycleStore();

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
  }, []);

  useEffect(() => {
    if (error) {
      Alert.alert("错误", error);
      clearError();
    }
  }, [error]);

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
      Alert.alert("解析失败", err.message || "请稍后重试");
    } finally {
      setAiLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!name.trim() || !selectedTemplateId || !startDate.trim()) {
      Alert.alert("提示", "请填写茬口名称、选择作物模板和开始日期");
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
        {/* AI 智能填写 */}
        <View style={styles.aiSection}>
          <View style={styles.aiHeader}>
            <View style={styles.aiIconWrap}>
              <Icon name="auto-fix" size={18} color={colors.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.aiTitle}>AI 智能填写</Text>
              <Text style={styles.aiSubtitle}>
                描述种植计划，自动填写信息
              </Text>
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
              numberOfLines={2}
              textAlignVertical="top"
              maxLength={200}
            />
            <TouchableOpacity
              style={[
                styles.aiParseBtn,
                (aiLoading || !aiInput.trim()) &&
                  styles.aiParseBtnDisabled,
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

          <View style={styles.examplesRow}>
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
          </View>
        </View>

        {/* 分隔线 */}
        <View style={styles.divider} />

        {/* 基本信息 */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>基本信息</Text>

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
            {selectedTemplate ? (
              <View style={styles.selectedChip}>
                <Text style={styles.selectedChipText}>
                  {selectedTemplate.name}
                  {selectedTemplate.variety
                    ? ` · ${selectedTemplate.variety}`
                    : ""}
                </Text>
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
              </View>
            ) : (
              <View style={styles.chipGrid}>
                {templates.map((t) => (
                  <TouchableOpacity
                    key={t.id}
                    style={styles.chip}
                    onPress={() => setSelectedTemplateId(t.id)}
                    activeOpacity={0.7}
                  >
                    <Text style={styles.chipText}>{t.name}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}
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
    paddingBottom: spacingV2.xxl,
  },

  /* AI 智能填写 */
  aiSection: {
    paddingHorizontal: spacingV2.xl,
    paddingTop: spacingV2.xl,
    paddingBottom: spacingV2.lg,
  },
  aiHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacingV2.md,
  },
  aiIconWrap: {
    width: 36,
    height: 36,
    borderRadius: borderRadiusV2.md,
    backgroundColor: colors.primaryMuted,
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacingV2.sm,
  },
  aiTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    lineHeight: 22,
  },
  aiSubtitle: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  aiInputWrap: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacingV2.md,
  },
  aiInput: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    minHeight: 56,
    textAlignVertical: "top",
    lineHeight: 22,
    padding: 0,
  },
  aiParseBtn: {
    alignSelf: "flex-end",
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.primary,
    borderRadius: borderRadiusV2.full,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: 8,
    marginTop: spacingV2.sm,
  },
  aiParseBtnDisabled: {
    backgroundColor: colors.disabled,
  },
  aiParseBtnText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: "#fff",
  },
  examplesRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacingV2.sm,
    marginTop: spacingV2.md,
  },
  exampleChip: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.full,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacingV2.md,
    paddingVertical: 6,
  },
  exampleText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },

  /* 分隔线 */
  divider: {
    height: 8,
    backgroundColor: colors.surfaceMuted,
    marginVertical: spacingV2.sm,
  },

  /* 表单区 */
  section: {
    paddingHorizontal: spacingV2.xl,
    paddingVertical: spacingV2.lg,
  },
  sectionTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacingV2.md,
  },
  fieldRow: {
    marginBottom: spacingV2.md,
  },
  fieldLabel: {
    fontSize: fontSizeV2.sm,
    fontWeight: "500",
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
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm + 2,
    fontSize: fontSizeV2.md,
    color: colors.text,
    height: 44,
  },
  dateTrigger: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm + 2,
    height: 44,
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
    flexWrap: "wrap",
    gap: spacingV2.sm,
  },
  chip: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.full,
    paddingHorizontal: spacingV2.md,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  chipText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  selectedChip: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    backgroundColor: colors.primaryMuted,
    borderRadius: borderRadiusV2.full,
    paddingHorizontal: spacingV2.md,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: "rgba(74, 123, 247, 0.15)",
  },
  selectedChipText: {
    fontSize: fontSizeV2.sm,
    color: colors.primary,
    fontWeight: "600",
  },
  clearChip: {
    marginLeft: spacingV2.sm,
  },

  /* 底部保存 */
  footer: {
    backgroundColor: colors.surface,
    paddingHorizontal: spacingV2.xl,
    paddingTop: spacingV2.md,
    paddingBottom: spacingV2.lg + 4,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  saveBtn: {
    backgroundColor: colors.primary,
    borderRadius: borderRadiusV2.lg,
    paddingVertical: 14,
    alignItems: "center",
    justifyContent: "center",
    height: 48,
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
