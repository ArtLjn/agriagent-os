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
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { useCycleStore } from "../../stores/cycleStore";
import { Loading } from "../../components/Loading";
import { DatePickerModal } from "../cost/components/DatePickerModal";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius, shadows } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import dayjs from "dayjs";

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

  useEffect(() => {
    fetchTemplates();
  }, []);
  useEffect(() => {
    if (error) {
      Alert.alert("错误", error);
      clearError();
    }
  }, [error]);

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

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.card}>
          <View style={styles.field}>
            <Text style={styles.label}>茬口名称</Text>
            <TextInput
              style={styles.input}
              value={name}
              onChangeText={setName}
              placeholder="例如：2024春季西瓜"
              placeholderTextColor={colors.textTertiary}
            />
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>选择作物</Text>
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
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
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

          <View style={styles.field}>
            <Text style={styles.label}>开始日期</Text>
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

          <View style={styles.fieldLast}>
            <Text style={styles.label}>
              地块名称 <Text style={styles.optional}>可选</Text>
            </Text>
            <TextInput
              style={styles.input}
              value={fieldName}
              onChangeText={setFieldName}
              placeholder="例如：东大棚"
              placeholderTextColor={colors.textTertiary}
            />
          </View>
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <TouchableOpacity
          style={[
            styles.submitButton,
            (!name.trim() || !selectedTemplateId || !startDate.trim()) &&
              styles.submitButtonDisabled,
          ]}
          onPress={handleSubmit}
          activeOpacity={0.8}
          disabled={!name.trim() || !selectedTemplateId || !startDate.trim()}
        >
          <Text style={styles.submitText}>创建茬口</Text>
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
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.xxl,
    padding: spacing.lg,
    ...shadows.md,
  },
  field: {
    marginBottom: spacing.xl,
  },
  fieldLast: {
    marginBottom: 0,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: "500",
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  optional: {
    fontWeight: "400",
    color: colors.textTertiary,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.xl,
    paddingHorizontal: spacing.md,
    paddingVertical: 14,
    fontSize: fontSize.md,
    backgroundColor: colors.surface,
    color: colors.text,
    minHeight: 52,
  },
  dateTrigger: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.xl,
    paddingHorizontal: spacing.md,
    paddingVertical: 14,
    backgroundColor: colors.surface,
    minHeight: 52,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  dateTriggerText: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  dateTriggerPlaceholder: {
    color: colors.textTertiary,
  },
  chipGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  chip: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  chipText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  selectedChip: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    backgroundColor: colors.primaryMuted,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: "rgba(74, 123, 247, 0.15)",
  },
  selectedChipText: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: "600",
  },
  clearChip: {
    marginLeft: spacing.sm,
  },
  footer: {
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  submitButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.xxl,
    paddingVertical: 14,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 52,
  },
  submitButtonDisabled: {
    backgroundColor: colors.disabled,
  },
  submitText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.textInverse,
  },
});
