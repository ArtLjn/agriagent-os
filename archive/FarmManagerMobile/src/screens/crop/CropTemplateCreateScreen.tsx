import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { showAlert } from "../../utils/alert";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { cropApi } from "../../api/client";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import type { RootStackParamList } from "../../navigation/AppNavigator";

const EXAMPLE_CROPS = ["番茄", "西瓜", "玉米", "黄瓜", "辣椒"];

const EXAMPLE_PROMPTS: Record<string, string> = {
  番茄: "我要种番茄，大概100天成熟",
  西瓜: "我要种8424西瓜，大概90天成熟",
  玉米: "我要种甜玉米，大概80天成熟",
  黄瓜: "我要种黄瓜，大概60天成熟",
  辣椒: "我要种辣椒，大概120天成熟",
};

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
      showAlert("解析失败", err.message || "请稍后重试");
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
      showAlert("提示", error);
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
      showAlert("创建失败", err.message || "请稍后重试");
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
        showsVerticalScrollIndicator={false}
      >
        {/* AI 智能输入区 */}
        <View style={styles.aiSection}>
          <View style={styles.aiHeader}>
            <View style={styles.aiIconWrap}>
              <Icon name="auto-fix" size={18} color={colors.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.aiTitle}>AI 智能生成</Text>
              <Text style={styles.aiSubtitle}>
                描述作物，自动生成生长阶段
              </Text>
            </View>
          </View>

          <View style={styles.aiInputWrap}>
            <TextInput
              style={styles.aiInput}
              placeholder="例如：我要种8424西瓜，大概需要90天成熟"
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
                  <Text style={styles.aiParseBtnText}>生成</Text>
                </>
              )}
            </TouchableOpacity>
          </View>

          <View style={styles.examplesRow}>
            {EXAMPLE_CROPS.map((crop) => (
              <TouchableOpacity
                key={crop}
                style={styles.exampleChip}
                onPress={() => setAiInput(EXAMPLE_PROMPTS[crop])}
                activeOpacity={0.7}
              >
                <Text style={styles.exampleText}>{crop}</Text>
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
          <View style={styles.fieldRow}>
            <Text style={styles.fieldLabel}>品种</Text>
            <TextInput
              style={styles.textInput}
              placeholder="如：8424（可选）"
              placeholderTextColor={colors.textTertiary}
              value={variety}
              onChangeText={setVariety}
            />
          </View>
        </View>

        {/* 分隔线 */}
        <View style={styles.divider} />

        {/* 生长阶段 */}
        <View style={styles.section}>
          <View style={styles.stageSectionHeader}>
            <Text style={styles.sectionTitle}>
              生长阶段{" "}
              <Text style={styles.stageCount}>
                {stages.length > 0 ? `(${stages.length})` : ""}
              </Text>
            </Text>
            <TouchableOpacity
              style={styles.addStageBtn}
              onPress={handleAddStage}
              activeOpacity={0.8}
            >
              <Icon name="plus" size={16} color={colors.primary} />
              <Text style={styles.addStageText}>添加</Text>
            </TouchableOpacity>
          </View>

          {stages.length === 0 && (
            <View style={styles.emptyStage}>
              <View style={styles.emptyIconWrap}>
                <Icon
                  name="sprout"
                  size={32}
                  color={colors.textTertiary}
                />
              </View>
              <Text style={styles.emptyTitle}>还没有生长阶段</Text>
              <Text style={styles.emptySubtitle}>
                点击上方"添加"按钮，或试试 AI 智能生成
              </Text>
            </View>
          )}

          {stages.map((stage, index) => (
            <View key={index} style={styles.stageCard}>
              <View style={styles.stageCardHeader}>
                <View style={styles.stageBadge}>
                  <Text style={styles.stageBadgeText}>{index + 1}</Text>
                </View>
                <Text style={styles.stageCardTitle}>阶段 {index + 1}</Text>
                <TouchableOpacity
                  style={styles.deleteBtn}
                  onPress={() => handleRemoveStage(index)}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                >
                  <Icon
                    name="trash-can-outline"
                    size={18}
                    color={colors.danger}
                  />
                </TouchableOpacity>
              </View>

              <View style={styles.stageBody}>
                <TextInput
                  style={styles.stageInput}
                  placeholder="阶段名称，如：幼苗期"
                  placeholderTextColor={colors.textTertiary}
                  value={stage.name}
                  onChangeText={(v) => updateStage(index, "name", v)}
                />
                <View style={styles.stageRow}>
                  <View style={styles.stageCol}>
                    <Text style={styles.stageColLabel}>天数</Text>
                    <View style={styles.daysWrap}>
                      <TextInput
                        style={styles.daysInput}
                        placeholder="30"
                        placeholderTextColor={colors.textTertiary}
                        value={stage.duration_days}
                        onChangeText={(v) =>
                          updateStage(index, "duration_days", v)
                        }
                        keyboardType="numeric"
                        maxLength={3}
                      />
                      <Text style={styles.daysUnit}>天</Text>
                    </View>
                  </View>
                  <View style={[styles.stageCol, { flex: 2 }]}>
                    <Text style={styles.stageColLabel}>关键任务</Text>
                    <TextInput
                      style={styles.stageInput}
                      placeholder="如：浇水施肥"
                      placeholderTextColor={colors.textTertiary}
                      value={stage.key_tasks}
                      onChangeText={(v) =>
                        updateStage(index, "key_tasks", v)
                      }
                    />
                  </View>
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
          activeOpacity={0.8}
        >
          {saving ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Text style={styles.saveBtnText}>保存模板</Text>
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
    paddingBottom: spacingV2.xxl,
  },

  /* AI 智能输入区 */
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

  /* 生长阶段 */
  stageSectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacingV2.md,
  },
  stageCount: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    fontWeight: "400",
  },
  addStageBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
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

  /* 空状态 */
  emptyStage: {
    alignItems: "center",
    paddingVertical: spacingV2.xxl,
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.border,
    borderStyle: "dashed",
  },
  emptyIconWrap: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.surfaceMuted,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: spacingV2.md,
  },
  emptyTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: spacingV2.xs,
  },
  emptySubtitle: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
  },

  /* 阶段卡片 */
  stageCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacingV2.md,
    overflow: "hidden",
  },
  stageCardHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    backgroundColor: colors.surfaceMuted,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  stageBadge: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.primary,
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacingV2.xs,
  },
  stageBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#fff",
  },
  stageCardTitle: {
    flex: 1,
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: colors.textSecondary,
  },
  deleteBtn: {
    padding: spacingV2.xs,
  },
  stageBody: {
    padding: spacingV2.md,
    gap: spacingV2.md,
  },
  stageInput: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.md,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm + 2,
    fontSize: fontSizeV2.md,
    color: colors.text,
    height: 44,
  },
  stageRow: {
    flexDirection: "row",
    gap: spacingV2.md,
  },
  stageCol: {
    flex: 1,
    gap: spacingV2.xs,
  },
  stageColLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  daysWrap: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.md,
    paddingHorizontal: spacingV2.md,
    height: 44,
  },
  daysInput: {
    flex: 1,
    fontSize: fontSizeV2.md,
    color: colors.text,
    padding: 0,
  },
  daysUnit: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginLeft: 2,
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
