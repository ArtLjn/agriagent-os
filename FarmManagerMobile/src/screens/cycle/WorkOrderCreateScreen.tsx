import React, { useEffect, useMemo, useState } from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import dayjs from "dayjs";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { plantingApi } from "../../api/client";
import type { OperationType, PlantingUnit, Worker } from "../../api/types";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { BigButton } from "../../components/BigButton";
import { colors } from "../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../theme/spacing";
import { showAlert } from "../../utils/alert";

type RouteParams = RouteProp<RootStackParamList, "WorkOrderCreate">;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

export const WorkOrderCreateScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const navigation = useNavigation<NavigationProp>();
  const { cycleId, cropName } = route.params;
  const today = dayjs().format("YYYY-MM-DD");
  const [operationTypes, setOperationTypes] = useState<OperationType[]>([]);
  const [units, setUnits] = useState<PlantingUnit[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [operationType, setOperationType] = useState("");
  const [selectedUnitIds, setSelectedUnitIds] = useState<number[]>([]);
  const [workerNames, setWorkerNames] = useState("");
  const [unitPrice, setUnitPrice] = useState("200");
  const [paidWorker, setPaidWorker] = useState("");
  const [paidAmount, setPaidAmount] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    Promise.all([
      plantingApi.getOperationTypes(cropName),
      plantingApi.getUnits(cycleId),
      plantingApi.getWorkers(),
    ])
      .then(([typesRes, unitsRes, workersRes]) => {
        setOperationTypes(typesRes.data);
        setUnits(unitsRes.data);
        setWorkers(workersRes.data);
        setOperationType(typesRes.data[0]?.name || "");
      })
      .catch((err) => showAlert("加载失败", err.message));
  }, [cycleId, cropName]);

  const workerNameList = useMemo(
    () =>
      workerNames
        .replace(/，/g, ",")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    [workerNames]
  );

  const toggleUnit = (id: number) => {
    setSelectedUnitIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const ensureWorkers = async () => {
    const result: Worker[] = [];
    for (const name of workerNameList) {
      const existing = workers.find((worker) => worker.name === name);
      if (existing) {
        result.push(existing);
        continue;
      }
      const created = await plantingApi.createWorker({
        name,
        default_pay_type: "daily",
        default_unit_price: unitPrice || undefined,
      });
      result.push(created.data);
    }
    return result;
  };

  const submit = async () => {
    if (!operationType) {
      showAlert("提示", "请选择作业类型");
      return;
    }
    if (workerNameList.length > 0 && (!unitPrice || isNaN(Number(unitPrice)))) {
      showAlert("提示", "请填写有效的工人单价");
      return;
    }
    setSubmitting(true);
    try {
      const resolvedWorkers = await ensureWorkers();
      await plantingApi.createWorkOrder({
        cycle_id: cycleId,
        operation_type: operationType,
        operation_date: today,
        scope_type: selectedUnitIds.length > 0 ? "unit" : "cycle",
        unit_ids: selectedUnitIds,
        note: note.trim() || undefined,
        labor_entries: resolvedWorkers.map((worker) => ({
          worker_id: worker.id,
          pay_type: "daily",
          quantity: "1",
          unit_price: unitPrice,
          paid_amount:
            paidWorker.trim() && paidWorker.trim() === worker.name
              ? paidAmount || "0"
              : "0",
        })),
      });
      navigation.goBack();
    } catch (err: any) {
      showAlert("保存失败", err.message || "请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.dateText}>日期：{today}</Text>

      <Text style={styles.sectionTitle}>作业类型</Text>
      <View style={styles.chipWrap}>
        {operationTypes.map((item) => (
          <TouchableOpacity
            key={item.name}
            style={[
              styles.chip,
              operationType === item.name && styles.chipActive,
            ]}
            onPress={() => setOperationType(item.name)}
          >
            <Text
              style={[
                styles.chipText,
                operationType === item.name && styles.chipTextActive,
              ]}
            >
              {item.name}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.sectionTitle}>作用范围</Text>
      <View style={styles.unitCard}>
        {units.map((unit) => {
          const selected = selectedUnitIds.includes(unit.id);
          return (
            <TouchableOpacity
              key={unit.id}
              style={[styles.unitRow, selected && styles.unitRowSelected]}
              onPress={() => toggleUnit(unit.id)}
            >
              <Icon
                name={selected ? "checkbox-marked-circle" : "checkbox-blank-circle-outline"}
                size={20}
                color={selected ? colors.primary : colors.textTertiary}
              />
              <Text style={styles.unitName}>{unit.name}</Text>
              <Text style={styles.unitArea}>
                {unit.area_mu ? `${Number(unit.area_mu).toFixed(2).replace(/\.00$/, "")}亩` : ""}
              </Text>
            </TouchableOpacity>
          );
        })}
        {units.length === 0 ? (
          <Text style={styles.emptyHint}>未选择单元时，将按整个批次记录。</Text>
        ) : null}
      </View>

      <Text style={styles.sectionTitle}>用工</Text>
      <View style={styles.formCard}>
        <TextInput
          style={styles.input}
          value={workerNames}
          onChangeText={setWorkerNames}
          placeholder="工人姓名，多个用逗号分隔：老王,老李,老张,小赵"
          placeholderTextColor={colors.textTertiary}
        />
        <View style={styles.twoCol}>
          <TextInput
            style={[styles.input, styles.flexInput]}
            value={unitPrice}
            onChangeText={setUnitPrice}
            placeholder="每人单价"
            keyboardType="decimal-pad"
            placeholderTextColor={colors.textTertiary}
          />
          <TextInput
            style={[styles.input, styles.flexInput]}
            value={paidAmount}
            onChangeText={setPaidAmount}
            placeholder="已付金额"
            keyboardType="decimal-pad"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
        <TextInput
          style={styles.input}
          value={paidWorker}
          onChangeText={setPaidWorker}
          placeholder="已付款工人，例如：老王"
          placeholderTextColor={colors.textTertiary}
        />
      </View>

      <Text style={styles.sectionTitle}>备注</Text>
      <TextInput
        style={[styles.input, styles.textArea]}
        value={note}
        onChangeText={setNote}
        placeholder="例如：东大棚 4 个工人给西瓜授粉，每人 200，先付老王 200"
        placeholderTextColor={colors.textTertiary}
        multiline
      />

      <BigButton
        title={submitting ? "保存中..." : "保存作业单"}
        onPress={submit}
        style={styles.submitButton}
      />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacingV2.lg, paddingBottom: spacingV2.xxxxl },
  dateText: { fontSize: fontSizeV2.md, color: colors.textSecondary, marginBottom: spacingV2.lg },
  sectionTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "800",
    color: colors.text,
    marginTop: spacingV2.lg,
    marginBottom: spacingV2.md,
  },
  chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: spacingV2.sm },
  chip: {
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.primaryMuted, borderColor: colors.primary },
  chipText: { fontSize: fontSizeV2.sm, fontWeight: "700", color: colors.textSecondary },
  chipTextActive: { color: colors.primary },
  unitCard: { backgroundColor: colors.surface, borderRadius: borderRadiusV2.xl, overflow: "hidden" },
  unitRow: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacingV2.lg,
    gap: spacingV2.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  unitRowSelected: { backgroundColor: colors.primaryMuted },
  unitName: { flex: 1, fontSize: fontSizeV2.md, fontWeight: "700", color: colors.text },
  unitArea: { fontSize: fontSizeV2.sm, color: colors.textSecondary },
  emptyHint: { padding: spacingV2.lg, fontSize: fontSizeV2.md, color: colors.textSecondary },
  formCard: { gap: spacingV2.md },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadiusV2.md,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  twoCol: { flexDirection: "row", gap: spacingV2.md },
  flexInput: { flex: 1 },
  textArea: { minHeight: 96, textAlignVertical: "top" },
  submitButton: { marginTop: spacingV2.xxl },
});
