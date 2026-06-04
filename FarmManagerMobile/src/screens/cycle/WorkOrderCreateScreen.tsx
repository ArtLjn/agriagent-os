import React, { useEffect, useMemo, useState } from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import {
  useNavigation,
  useRoute,
  type RouteProp,
} from "@react-navigation/native";
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

const COMMON_LABOR_COUNTS = [2, 4, 6, 8];
const COMMON_PRICES = ["150", "180", "200", "220"];

export const WorkOrderCreateScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const navigation = useNavigation<NavigationProp>();
  const {
    cycleId,
    cropName,
    operationType: presetOperationType,
  } = route.params;
  const today = dayjs().format("YYYY-MM-DD");
  const [operationTypes, setOperationTypes] = useState<OperationType[]>([]);
  const [units, setUnits] = useState<PlantingUnit[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [operationType, setOperationType] = useState(presetOperationType || "");
  const [selectedUnitIds, setSelectedUnitIds] = useState<number[]>([]);
  const [workerNames, setWorkerNames] = useState("");
  const [workerCount, setWorkerCount] = useState("");
  const [unitPrice, setUnitPrice] = useState("200");
  const [paidWorker, setPaidWorker] = useState("");
  const [paidAmount, setPaidAmount] = useState("");
  const [note, setNote] = useState("");
  const [showScope, setShowScope] = useState(false);
  const [showLabor, setShowLabor] = useState(false);
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
        setOperationType((current) => current || typesRes.data[0]?.name || "");
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

  const generatedWorkerNames = useMemo(() => {
    const count = Number(workerCount);
    if (workerNameList.length > 0 || !Number.isInteger(count) || count <= 0) {
      return workerNameList;
    }
    return Array.from({ length: count }, (_, index) => `临时工${index + 1}`);
  }, [workerCount, workerNameList]);

  const selectedUnitsText =
    selectedUnitIds.length > 0
      ? `${selectedUnitIds.length} 个棚/地块`
      : "整茬一起记";
  const laborSummary =
    generatedWorkerNames.length > 0 && unitPrice
      ? `${generatedWorkerNames.length} 人 · 每人 ${unitPrice} 元`
      : "不记人工";

  const toggleUnit = (id: number) => {
    setSelectedUnitIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const ensureWorkers = async () => {
    const result: Worker[] = [];
    for (const name of generatedWorkerNames) {
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
    if (
      generatedWorkerNames.length > 0 &&
      (!unitPrice || isNaN(Number(unitPrice)))
    ) {
      showAlert("提示", "请填写有效的每人金额");
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
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.headerCard}>
        <Text style={styles.headerLabel}>今天 · {today}</Text>
        <Text style={styles.headerTitle}>记一条农事</Text>
        <Text style={styles.headerSub}>
          先把事情记下来，范围、人工和账单需要时再补。
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>做了什么</Text>
        <View style={styles.chipWrap}>
          {operationTypes.map((item) => (
            <TouchableOpacity
              key={item.name}
              style={[
                styles.chip,
                operationType === item.name && styles.chipActive,
              ]}
              onPress={() => setOperationType(item.name)}
              activeOpacity={0.76}
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
      </View>

      <TouchableOpacity
        style={styles.foldCard}
        onPress={() => setShowScope((value) => !value)}
        activeOpacity={0.78}
      >
        <View style={styles.foldIcon}>
          <Icon name="map-marker-radius" size={20} color={colors.primary} />
        </View>
        <View style={styles.foldText}>
          <Text style={styles.foldTitle}>范围</Text>
          <Text style={styles.foldSub}>{selectedUnitsText}</Text>
        </View>
        <Icon
          name={showScope ? "chevron-up" : "chevron-down"}
          size={22}
          color={colors.textTertiary}
        />
      </TouchableOpacity>

      {showScope ? (
        <View style={styles.expandedCard}>
          {units.length > 0 ? (
            units.map((unit) => {
              const selected = selectedUnitIds.includes(unit.id);
              return (
                <TouchableOpacity
                  key={unit.id}
                  style={[styles.unitRow, selected && styles.unitRowSelected]}
                  onPress={() => toggleUnit(unit.id)}
                  activeOpacity={0.76}
                >
                  <Icon
                    name={
                      selected
                        ? "checkbox-marked-circle"
                        : "checkbox-blank-circle-outline"
                    }
                    size={20}
                    color={selected ? colors.primary : colors.textTertiary}
                  />
                  <Text style={styles.unitName}>{unit.name}</Text>
                  <Text style={styles.unitArea}>
                    {unit.area_mu
                      ? `${Number(unit.area_mu)
                          .toFixed(2)
                          .replace(/\.00$/, "")}亩`
                      : ""}
                  </Text>
                </TouchableOpacity>
              );
            })
          ) : (
            <Text style={styles.emptyHint}>
              还没拆棚或地块，默认按整茬记录。
            </Text>
          )}
        </View>
      ) : null}

      <TouchableOpacity
        style={styles.foldCard}
        onPress={() => setShowLabor((value) => !value)}
        activeOpacity={0.78}
      >
        <View style={[styles.foldIcon, styles.laborIcon]}>
          <Icon name="account-hard-hat" size={20} color={colors.success} />
        </View>
        <View style={styles.foldText}>
          <Text style={styles.foldTitle}>人工工资</Text>
          <Text style={styles.foldSub}>{laborSummary}</Text>
        </View>
        <Icon
          name={showLabor ? "chevron-up" : "chevron-down"}
          size={22}
          color={colors.textTertiary}
        />
      </TouchableOpacity>

      {showLabor ? (
        <View style={styles.expandedCard}>
          <Text style={styles.fieldLabel}>今天几个人</Text>
          <View style={styles.quickRow}>
            {COMMON_LABOR_COUNTS.map((count) => (
              <TouchableOpacity
                key={count}
                style={[
                  styles.quickChip,
                  workerCount === String(count) && styles.quickChipActive,
                ]}
                onPress={() => {
                  setWorkerCount(String(count));
                  setWorkerNames("");
                }}
              >
                <Text
                  style={[
                    styles.quickChipText,
                    workerCount === String(count) && styles.quickChipTextActive,
                  ]}
                >
                  {count} 人
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <TextInput
            style={styles.input}
            value={workerNames}
            onChangeText={(value) => {
              setWorkerNames(value);
              if (value.trim()) {
                setWorkerCount("");
              }
            }}
            placeholder="知道姓名就填：老王、老李、老张"
            placeholderTextColor={colors.textTertiary}
          />

          <Text style={styles.fieldLabel}>每人多少钱</Text>
          <View style={styles.quickRow}>
            {COMMON_PRICES.map((price) => (
              <TouchableOpacity
                key={price}
                style={[
                  styles.quickChip,
                  unitPrice === price && styles.quickChipActive,
                ]}
                onPress={() => setUnitPrice(price)}
              >
                <Text
                  style={[
                    styles.quickChipText,
                    unitPrice === price && styles.quickChipTextActive,
                  ]}
                >
                  {price}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <TextInput
            style={styles.input}
            value={unitPrice}
            onChangeText={setUnitPrice}
            placeholder="其他金额"
            keyboardType="decimal-pad"
            placeholderTextColor={colors.textTertiary}
          />

          <View style={styles.twoCol}>
            <TextInput
              style={[styles.input, styles.flexInput]}
              value={paidWorker}
              onChangeText={setPaidWorker}
              placeholder="已付给谁"
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
        </View>
      ) : null}

      <View style={styles.card}>
        <Text style={styles.cardTitle}>补一句备注</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          value={note}
          onChangeText={setNote}
          placeholder="例：东大棚授粉，4个人，每人200，先付老王200"
          placeholderTextColor={colors.textTertiary}
          multiline
        />
      </View>

      <BigButton
        title={submitting ? "保存中..." : "保存"}
        onPress={submit}
        style={styles.submitButton}
      />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacingV2.lg, paddingBottom: spacingV2.xxxxl },
  headerCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.lg,
    marginBottom: spacingV2.md,
  },
  headerLabel: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    color: colors.success,
    marginBottom: spacingV2.xs,
  },
  headerTitle: {
    fontSize: fontSizeV2.xxl,
    fontWeight: "800",
    color: colors.text,
  },
  headerSub: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    lineHeight: 22,
    marginTop: spacingV2.sm,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.lg,
    marginBottom: spacingV2.md,
  },
  cardTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "800",
    color: colors.text,
    marginBottom: spacingV2.md,
  },
  chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: spacingV2.sm },
  chip: {
    minHeight: 40,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    color: colors.textSecondary,
  },
  chipTextActive: { color: colors.textInverse },
  foldCard: {
    minHeight: 64,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.lg,
    marginBottom: spacingV2.sm,
    gap: spacingV2.md,
  },
  foldIcon: {
    width: 40,
    height: 40,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primaryMuted,
  },
  laborIcon: { backgroundColor: colors.successMuted },
  foldText: { flex: 1, minWidth: 0 },
  foldTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "800",
    color: colors.text,
  },
  foldSub: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  expandedCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.lg,
    marginBottom: spacingV2.md,
    gap: spacingV2.md,
  },
  unitRow: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 44,
    gap: spacingV2.sm,
    paddingVertical: spacingV2.sm,
    paddingHorizontal: spacingV2.sm,
    borderRadius: borderRadiusV2.md,
  },
  unitRowSelected: { backgroundColor: colors.primaryMuted },
  unitName: {
    flex: 1,
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
  },
  unitArea: { fontSize: fontSizeV2.sm, color: colors.textSecondary },
  emptyHint: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  fieldLabel: {
    fontSize: fontSizeV2.sm,
    fontWeight: "800",
    color: colors.text,
  },
  quickRow: { flexDirection: "row", flexWrap: "wrap", gap: spacingV2.sm },
  quickChip: {
    minHeight: 36,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.background,
  },
  quickChipActive: { backgroundColor: colors.successMuted },
  quickChipText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    color: colors.textSecondary,
  },
  quickChipTextActive: { color: colors.success },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadiusV2.md,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.text,
    backgroundColor: colors.background,
  },
  twoCol: { flexDirection: "row", gap: spacingV2.md },
  flexInput: { flex: 1 },
  textArea: { minHeight: 92, textAlignVertical: "top" },
  submitButton: { marginTop: spacingV2.lg },
});
