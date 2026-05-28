import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { cropApi } from "../../api/client";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import type { RootStackParamList } from "../../navigation/AppNavigator";

const EXAMPLE_CROPS = ["番茄", "西瓜", "玉米", "黄瓜", "辣椒"];

type NavigationProp = NativeStackNavigationProp<
  RootStackParamList,
  "CropTemplateCreate"
>;

interface StageForm {
  name: string;
  duration_days: string;
  key_tasks: string;
}

const createEmptyStage = (): StageForm => ({
  name: "",
  duration_days: "",
  key_tasks: "",
});

export const CropTemplateCreateScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();

  const [aiInput, setAiInput] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [name, setName] = useState("");
  const [variety, setVariety] = useState("");
  const [stages, setStages] = useState<StageForm[]>([]);
  const [saving, setSaving] = useState(false);

  const handleAiParse = useCallback(async () => {
    const trimmed = aiInput.trim();
    if (!trimmed) return;
    setAiLoading(true);
    try {
      const res = await cropApi.parseTemplate(trimmed);
      const data = res.data;
      setName(data.name);
      setVariety(data.variety ?? "");
      setStages(
        data.stages.map((s) => ({
          name: s.name,
          duration_days: String(s.duration_days),
          key_tasks: s.key_tasks ?? "",
        }))
      );
      setAiInput("");
    } catch (err: any) {
      Alert.alert("解析失败", err.message || "请稍后重试");
    } finally {
      setAiLoading(false);
    }
  }, [aiInput]);

  const handleAddStage = useCallback(() => {
    setStages((prev) => [...prev, createEmptyStage()]);
  }, []);

  const handleRemoveStage = useCallback((index: number) => {
    setStages((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const updateStage = useCallback(
    (index: number, field: keyof StageForm, value: string) => {
      setStages((prev) =>
        prev.map((s, i) => (i === index ? { ...s, [field]: value } : s))
      );
    },
    []
  );

  const validate = useCallback((): string | null => {
    if (!name.trim()) return "作物名称不能为空";
    if (stages.length === 0) return "至少添加一个生长阶段";
    for (let i = 0; i < stages.length; i++) {
      const s = stages[i];
      if (!s.name.trim()) return `第 ${i + 1} 个阶段名称不能为空`;
      const days = parseInt(s.duration_days, 10);
      if (Number.isNaN(days) || days < 1 || days > 365) {
        return `第 ${i + 1} 个阶段天数须为 1-365 的整数`;
      }
    }
    return null;
  }, [name, stages]);

  const handleSave = useCallback(async () => {
    const error = validate();
    if (error) {
      Alert.alert("提示", error);
      return;
    }
    setSaving(true);
    try {
      await cropApi.createTemplate({
        name: name.trim(),
        variety: variety.trim() || null,
        stages: stages.map((s, idx) => ({
          name: s.name.trim(),
          duration_days: parseInt(s.duration_days, 10),
          order_index: idx,
          key_tasks: s.key_tasks.trim() || null,
        })),
      });
      navigation.goBack();
    } catch (err: any) {
      Alert.alert("创建失败", err.message || "请稍后重试");
    } finally {
      setSaving(false);
    }
  }, [name, variety, stages, validate, navigation]);

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
      >
        {/* 智能输入区 */}
        <View style={styles.aiCard}>
          <Text style={styles.aiTitle}>描述你想种的作物</Text>
          <Text style={styles.aiSubtitle}>
            用自然语言描述，AI 自动生成生长阶段
          </Text>
          <View style={styles.aiInputRow}>
            <TextInput
              style={styles.aiInput}
              placeholder="例如：我要种8424西瓜，大概需要90天成熟"
              placeholderTextColor={colors.textTertiary}
              value={aiInput}
              onChangeText={setAiInput}
              multiline
              maxLength={200}
            />
            <TouchableOpacity
              style={[
                styles.aiParseBtn,
                (aiLoading || !aiInput.trim()) && styles.aiParseBtnDisabled,
              ]}
              onPress={handleAiParse}
              disabled={aiLoading || !aiInput.trim()}
            >
              {aiLoading ? (
                <ActivityIndicator size="small" color={colors.textInverse} />
              ) : (
                <Text style={styles.aiParseBtnText}>智能生成</Text>
              )}
            </TouchableOpacity>
          </View>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.examplesContainer}
          >
            {EXAMPLE_CROPS.map((crop) => (
              <TouchableOpacity
                key={crop}
                style={styles.exampleChip}
                onPress={() =>
                  setAiInput(`我要种${crop}，请帮我生成生长阶段`)
                }
              >
                <Text style={styles.exampleText}>{crop}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        {/* 表单区 */}
        <View style={styles.formCard}>
          <Text style={styles.sectionTitle}>基本信息</Text>
          <View style={styles.field}>
            <Text style={styles.fieldLabel}>
              作物名称 <Text style={styles.required}>*</Text>
            </Text>
            <TextInput
              style={styles.textInput}
              placeholder="如：西瓜"
              placeholderTextColor={colors.textTertiary}
              value={name}
              onChangeText={setName}
            />
          </View>
          <View style={styles.field}>
            <Text style={styles.fieldLabel}>品种（可选）</Text>
            <TextInput
              style={styles.textInput}
              placeholder="如：8424"
              placeholderTextColor={colors.textTertiary}
              value={variety}
              onChangeText={setVariety}
            />
          </View>
        </View>

        <View style={styles.formCard}>
          <View style={styles.stageHeader}>
            <Text style={styles.sectionTitle}>生长阶段</Text>
            <TouchableOpacity
              style={styles.addStageBtn}
              onPress={handleAddStage}
            >
              <Icon name="plus" size={18} color={colors.primary} />
              <Text style={styles.addStageText}>添加阶段</Text>
            </TouchableOpacity>
          </View>

          {stages.length === 0 && (
            <View style={styles.emptyStage}>
              <Text style={styles.emptyStageText}>
                点击上方按钮添加生长阶段
              </Text>
            </View>
          )}

          {stages.map((stage, index) => (
            <View key={index} style={styles.stageCard}>
              <View style={styles.stageCardHeader}>
                <Text style={styles.stageIndex}>阶段 {index + 1}</Text>
                <TouchableOpacity
                  style={styles.deleteBtn}
                  onPress={() => handleRemoveStage(index)}
                >
                  <Icon name="delete-outline" size={20} color={colors.danger} />
                </TouchableOpacity>
              </View>
              <View style={styles.stageField}>
                <Text style={styles.stageFieldLabel}>阶段名称</Text>
                <TextInput
                  style={styles.stageInput}
                  placeholder="如：幼苗期"
                  placeholderTextColor={colors.textTertiary}
                  value={stage.name}
                  onChangeText={(v) => updateStage(index, "name", v)}
                />
              </View>
              <View style={styles.stageRow}>
                <View style={[styles.stageField, styles.stageFieldHalf]}>
                  <Text style={styles.stageFieldLabel}>天数</Text>
                  <View style={styles.daysInputWrap}>
                    <TextInput
                      style={[styles.stageInput, styles.daysInput]}
                      placeholder="30"
                      placeholderTextColor={colors.textTertiary}
                      value={stage.duration_days}
                      onChangeText={(v) =>
                        updateStage(index, "duration_days", v)
                      }
                      keyboardType="numeric"
                      maxLength={3}
                    />
                    <Text style={styles.daysSuffix}>天</Text>
                  </View>
                </View>
                <View style={[styles.stageField, styles.stageFieldHalf]}>
                  <Text style={styles.stageFieldLabel}>关键任务</Text>
                  <TextInput
                    style={styles.stageInput}
                    placeholder="如：浇水、施肥"
                    placeholderTextColor={colors.textTertiary}
                    value={stage.key_tasks}
                    onChangeText={(v) =>
                      updateStage(index, "key_tasks", v)
                    }
                  />
                </View>
              </View>
            </View>
          ))}
        </View>
      </ScrollView>

      {/* 底部保存按钮 */}
      <View style={styles.footer}>
        <TouchableOpacity
          style={[styles.saveBtn, saving && styles.saveBtnDisabled]}
          onPress={handleSave}
          disabled={saving}
        >
          {saving ? (
            <ActivityIndicator size="small" color={colors.textInverse} />
          ) : (
            <Text style={styles.saveBtnText}>保存</Text>
          )}
        </TouchableOpacity>
      </View>
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
    padding: spacingV2.xl,
    paddingBottom: spacingV2.xxxl,
  },
  aiCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    padding: spacingV2.lg,
    marginBottom: spacingV2.lg,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  aiTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacingV2.xs,
  },
  aiSubtitle: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginBottom: spacingV2.md,
  },
  aiInputRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacingV2.sm,
    marginBottom: spacingV2.md,
  },
  aiInput: {
    flex: 1,
    borderRadius: borderRadiusV2.lg,
    padding: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.text,
    backgroundColor: colors.surfaceMuted,
    minHeight: 60,
    textAlignVertical: "top",
  },
  aiParseBtn: {
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.primary,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.md,
    justifyContent: "center",
    alignItems: "center",
    minHeight: 60,
  },
  aiParseBtnDisabled: {
    backgroundColor: colors.disabled,
  },
  aiParseBtnText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: colors.textInverse,
  },
  examplesContainer: {
    gap: spacingV2.sm,
    paddingRight: spacingV2.lg,
  },
  exampleChip: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.full,
    paddingHorizontal: spacingV2.md,
    paddingVertical: 6,
  },
  exampleText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  formCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    padding: spacingV2.lg,
    marginBottom: spacingV2.lg,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacingV2.md,
  },
  field: {
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
  textInput: {
    borderRadius: borderRadiusV2.lg,
    padding: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.text,
    backgroundColor: colors.surfaceMuted,
  },
  stageHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacingV2.md,
  },
  addStageBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.xs,
    backgroundColor: colors.primaryMuted,
    borderRadius: borderRadiusV2.full,
    paddingHorizontal: spacingV2.md,
    paddingVertical: 6,
  },
  addStageText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: colors.primary,
  },
  emptyStage: {
    alignItems: "center",
    paddingVertical: spacingV2.xl,
  },
  emptyStageText: {
    fontSize: fontSizeV2.md,
    color: colors.textTertiary,
  },
  stageCard: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.lg,
    padding: spacingV2.md,
    marginBottom: spacingV2.md,
  },
  stageCardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacingV2.sm,
  },
  stageIndex: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: colors.textSecondary,
  },
  deleteBtn: {
    padding: spacingV2.xs,
  },
  stageField: {
    marginBottom: spacingV2.sm,
  },
  stageFieldLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginBottom: spacingV2.xs,
  },
  stageInput: {
    borderRadius: borderRadiusV2.md,
    padding: spacingV2.sm,
    fontSize: fontSizeV2.md,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  stageRow: {
    flexDirection: "row",
    gap: spacingV2.md,
  },
  stageFieldHalf: {
    flex: 1,
  },
  daysInputWrap: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.md,
    paddingRight: spacingV2.sm,
  },
  daysInput: {
    flex: 1,
    backgroundColor: "transparent",
  },
  daysSuffix: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
  },
  footer: {
    backgroundColor: colors.surface,
    paddingHorizontal: spacingV2.xl,
    paddingTop: spacingV2.md,
    paddingBottom: spacingV2.lg,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  saveBtn: {
    backgroundColor: colors.primary,
    borderRadius: borderRadiusV2.xl,
    paddingVertical: spacingV2.md,
    alignItems: "center",
  },
  saveBtnDisabled: {
    backgroundColor: colors.disabled,
  },
  saveBtnText: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.textInverse,
  },
});
