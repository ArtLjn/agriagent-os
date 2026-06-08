import React, { useState } from "react";
import { showAlert } from "../../utils/alert";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
 
} from "react-native";
import {
  useNavigation,
  useRoute,
  type RouteProp,
} from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { useLogStore } from "../../stores/logStore";
import { BigButton } from "../../components/BigButton";
import { colors } from "../../theme/colors";
import { spacing, fontSize } from "../../theme/spacing";
import dayjs from "dayjs";

type RouteParams = RouteProp<RootStackParamList, "LogCreate">;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const QUICK_ACTIONS = [
  { key: "watering", label: "浇水" },
  { key: "fertilizing", label: "施肥" },
  { key: "weeding", label: "除草" },
  { key: "pest_control", label: "打药" },
  { key: "pruning", label: "修剪" },
  { key: "harvesting", label: "采收" },
  { key: "other", label: "其他" },
];

export const LogCreateScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const navigation = useNavigation<NavigationProp>();
  const { cycleId } = route.params;
  const { createLog, error, clearError } = useLogStore();

  const [selectedType, setSelectedType] = useState("");
  const [note, setNote] = useState("");
  const today = dayjs().format("YYYY-MM-DD");

  const handleSubmit = async () => {
    if (!selectedType) {
      showAlert("提示", "请选择农事类型");
      return;
    }
    await createLog({
      cycle_id: cycleId,
      operation_type: selectedType,
      operation_date: today,
      note: note.trim() || undefined,
    });
    if (!error) {
      navigation.goBack();
    } else {
      showAlert("错误", error);
      clearError();
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.dateLabel}>日期：{today}</Text>
      <Text style={styles.label}>选择农事类型</Text>
      <View style={styles.actionsGrid}>
        {QUICK_ACTIONS.map((action) => (
          <View key={action.key} style={styles.actionWrapper}>
            <BigButton
              title={action.label}
              variant={selectedType === action.key ? "primary" : "secondary"}
              onPress={() => setSelectedType(action.key)}
            />
          </View>
        ))}
      </View>
      <Text style={styles.label}>备注（可选）</Text>
      <TextInput
        style={[styles.input, styles.textArea]}
        value={note}
        onChangeText={setNote}
        placeholder="补充说明..."
        placeholderTextColor={colors.textSecondary}
        multiline
        numberOfLines={3}
      />
      <BigButton
        title="确认打卡"
        onPress={handleSubmit}
        style={styles.submitButton}
      />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  dateLabel: {
    fontSize: fontSize.lg,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  label: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.text,
    marginTop: spacing.lg,
    marginBottom: spacing.md,
  },
  actionsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginHorizontal: -spacing.sm,
  },
  actionWrapper: { width: "50%", padding: spacing.sm },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: spacing.md,
    fontSize: fontSize.lg,
    backgroundColor: colors.surface,
    color: colors.text,
  },
  textArea: { height: 100, textAlignVertical: "top" },
  submitButton: { marginTop: spacing.xl },
});
