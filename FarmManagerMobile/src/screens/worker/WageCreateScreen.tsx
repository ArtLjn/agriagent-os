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
import { plantingApi, cycleApi } from "../../api/client";
import type { CropCycleListItem, OperationType, Worker } from "../../api/types";
import { BigButton } from "../../components/BigButton";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { colors } from "../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../theme/spacing";
import { showAlert } from "../../utils/alert";

type RouteParams = RouteProp<RootStackParamList, "WageCreate">;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const QUANTITY_CHIPS = ["0.5", "1", "2", "3", "4"];
const PRICE_CHIPS = ["120", "150", "180", "200", "220", "260"];

function toMoneyNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function getRequestId(cycleId: number, operationType: string, workerName: string, date: string) {
  return `${cycleId}-${operationType}-${workerName}-${date}`;
}

export const WageCreateScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const navigation = useNavigation<NavigationProp>();
  const params = route.params || {};
  const today = dayjs().format("YYYY-MM-DD");
  const [cycles, setCycles] = useState<CropCycleListItem[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [operationTypes, setOperationTypes] = useState<OperationType[]>([]);
  const [selectedCycleId, setSelectedCycleId] = useState<number | null>(
    params.cycleId ?? null
  );
  const [cropName, setCropName] = useState(params.cropName || "");
  const [operationType, setOperationType] = useState(params.operationType || "");
  const [workerQuery, setWorkerQuery] = useState(params.workerName || "");
  const [quantity, setQuantity] = useState("1");
  const [unitPrice, setUnitPrice] = useState(params.unitPrice || "200");
  const [paidAmount, setPaidAmount] = useState("");
  const [workDate, setWorkDate] = useState(today);
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    Promise.all([
      cycleApi.getCycles(),
      plantingApi.getWorkers(),
      plantingApi.getOperationTypes(params.cropName),
    ])
      .then(([cyclesRes, workersRes, typesRes]) => {
        const cycleItems = (cyclesRes.data as any)?.items ?? cyclesRes.data;
        setCycles(cycleItems);
        setWorkers(workersRes.data);
        setOperationTypes(typesRes.data);

        const defaultCycle =
          cycleItems.find((item: CropCycleListItem) => item.id === params.cycleId) ||
          cycleItems.find((item: CropCycleListItem) => item.status === "active") ||
          cycleItems[0];
        if (!selectedCycleId && defaultCycle) {
          setSelectedCycleId(defaultCycle.id);
          setCropName(defaultCycle.name);
        }
        if (!operationType) {
          setOperationType(typesRes.data[0]?.name || "");
        }
      })
      .catch((err) => showAlert("加载失败", err.message || "请稍后重试"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const selected = cycles.find((cycle) => cycle.id === selectedCycleId);
    if (!selected) {
      return;
    }
    setCropName(selected.name);
    plantingApi
      .getOperationTypes(selected.name)
      .then((res) => {
        setOperationTypes(res.data);
        if (!operationType && res.data[0]) {
          setOperationType(res.data[0].name);
        }
      })
      .catch(() => {});
  }, [selectedCycleId]);

  const workerName = workerQuery.trim();
  const selectedCycle = cycles.find((cycle) => cycle.id === selectedCycleId);
  const payable = toMoneyNumber(quantity) * toMoneyNumber(unitPrice);
  const unpaid = Math.max(0, payable - toMoneyNumber(paidAmount || "0"));

  const workerSuggestions = useMemo(() => {
    const normalized = workerName.toLowerCase();
    const list = normalized
      ? workers.filter((worker) => worker.name.toLowerCase().includes(normalized))
      : workers;
    return list.slice(0, 8);
  }, [workerName, workers]);

  const selectWorker = (worker: Worker) => {
    setWorkerQuery(worker.name);
    if (worker.default_unit_price) {
      setUnitPrice(worker.default_unit_price);
    }
  };

  const submit = async () => {
    if (!selectedCycleId) {
      showAlert("提示", "请选择茬口");
      return;
    }
    if (!operationType.trim()) {
      showAlert("提示", "请选择作业");
      return;
    }
    if (!workerName) {
      showAlert("提示", "请选择或输入工人姓名");
      return;
    }
    if (toMoneyNumber(quantity) <= 0 || toMoneyNumber(unitPrice) <= 0) {
      showAlert("提示", "请填写有效人数和单价");
      return;
    }

    setSubmitting(true);
    try {
      await plantingApi.createWage({
        cycle_id: selectedCycleId,
        crop_name: cropName || selectedCycle?.name,
        operation_type: operationType.trim(),
        worker_name: workerName,
        quantity,
        unit_price: unitPrice,
        paid_amount: paidAmount || "0",
        work_date: workDate,
        pay_type: "daily",
        note: note.trim() || undefined,
        client_request_id: getRequestId(
          selectedCycleId,
          operationType.trim(),
          workerName,
          workDate
        ),
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
      <View style={styles.summaryBar}>
        <View>
          <Text style={styles.summaryLabel}>本次应付</Text>
          <Text style={styles.summaryValue}>{payable.toFixed(0)} 元</Text>
        </View>
        <View style={styles.summaryPill}>
          <Text style={styles.summaryPillText}>未结 {unpaid.toFixed(0)} 元</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>这笔工资属于哪里</Text>
        <Text style={styles.sectionHint}>茬口必须选择，作物和作业用于后续核对账单来源。</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
          {cycles.map((cycle) => {
            const active = selectedCycleId === cycle.id;
            return (
              <TouchableOpacity
                key={cycle.id}
                style={[styles.selectChip, active && styles.selectChipActive]}
                onPress={() => setSelectedCycleId(cycle.id)}
              >
                <Text style={[styles.selectChipText, active && styles.selectChipTextActive]}>
                  {cycle.name}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
        <View style={styles.inputRow}>
          <Icon name="sprout-outline" size={18} color={colors.success} />
          <TextInput
            style={styles.inlineInput}
            value={cropName}
            onChangeText={setCropName}
            placeholder="作物或安排，例如 8424 西瓜"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
          {operationTypes.map((item) => {
            const active = operationType === item.name;
            return (
              <TouchableOpacity
                key={item.name}
                style={[styles.selectChip, active && styles.selectChipActive]}
                onPress={() => setOperationType(item.name)}
              >
                <Text style={[styles.selectChipText, active && styles.selectChipTextActive]}>
                  {item.name}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
        <View style={styles.inputRow}>
          <Icon name="clipboard-edit-outline" size={18} color={colors.primary} />
          <TextInput
            style={styles.inlineInput}
            value={operationType}
            onChangeText={setOperationType}
            placeholder="也可以手动输入作业类型"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
        <View style={styles.inputRow}>
          <Icon name="calendar" size={18} color={colors.primary} />
          <TextInput
            style={styles.inlineInput}
            value={workDate}
            onChangeText={setWorkDate}
            placeholder="YYYY-MM-DD"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>选择工人</Text>
        <View style={styles.inputRow}>
          <Icon name="account-hard-hat-outline" size={18} color={colors.primary} />
          <TextInput
            style={styles.inlineInput}
            value={workerQuery}
            onChangeText={setWorkerQuery}
            placeholder="搜索或输入新工人姓名"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
        <View style={styles.workerWrap}>
          {workerSuggestions.map((worker) => {
            const active = worker.name === workerName;
            return (
              <TouchableOpacity
                key={worker.id}
                style={[styles.workerChip, active && styles.workerChipActive]}
                onPress={() => selectWorker(worker)}
              >
                <Text style={[styles.workerChipText, active && styles.workerChipTextActive]}>
                  {worker.name}
                </Text>
              </TouchableOpacity>
            );
          })}
          {workerName && !workers.some((worker) => worker.name === workerName) ? (
            <View style={styles.newWorkerChip}>
              <Icon name="plus-circle-outline" size={15} color={colors.success} />
              <Text style={styles.newWorkerText}>保存时创建 {workerName}</Text>
            </View>
          ) : null}
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>人数和单价</Text>
        <Text style={styles.fieldLabel}>人数/工日</Text>
        <View style={styles.quickGrid}>
          {QUANTITY_CHIPS.map((item) => (
            <TouchableOpacity
              key={`quantity-${item}`}
              style={[styles.quickChip, quantity === item && styles.quickChipActive]}
              onPress={() => setQuantity(item)}
            >
              <Text style={[styles.quickChipText, quantity === item && styles.quickChipTextActive]}>
                {item} 人
              </Text>
            </TouchableOpacity>
          ))}
        </View>
        <View style={styles.inputRow}>
          <Icon name="account-multiple-outline" size={18} color={colors.textSecondary} />
          <TextInput
            style={styles.inlineInput}
            value={quantity}
            onChangeText={setQuantity}
            keyboardType="decimal-pad"
            placeholder="人数或工日"
            placeholderTextColor={colors.textTertiary}
          />
        </View>

        <Text style={styles.fieldLabel}>每人单价</Text>
        <View style={styles.quickGrid}>
          {PRICE_CHIPS.map((item) => (
            <TouchableOpacity
              key={`price-${item}`}
              style={[styles.quickChip, unitPrice === item && styles.quickChipActive]}
              onPress={() => setUnitPrice(item)}
            >
              <Text style={[styles.quickChipText, unitPrice === item && styles.quickChipTextActive]}>
                {item} 元
              </Text>
            </TouchableOpacity>
          ))}
        </View>
        <View style={styles.inputRow}>
          <Icon name="cash" size={18} color={colors.textSecondary} />
          <TextInput
            style={styles.inlineInput}
            value={unitPrice}
            onChangeText={setUnitPrice}
            keyboardType="decimal-pad"
            placeholder="每人单价"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
        <View style={styles.inputRow}>
          <Icon name="cash-check" size={18} color={colors.success} />
          <TextInput
            style={styles.inlineInput}
            value={paidAmount}
            onChangeText={setPaidAmount}
            keyboardType="decimal-pad"
            placeholder="已付金额，不填按 0"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>备注</Text>
        <TextInput
          style={[styles.inputRow, styles.textArea]}
          value={note}
          onChangeText={setNote}
          placeholder="可写地块、班组或结算说明"
          placeholderTextColor={colors.textTertiary}
          multiline
        />
      </View>

      <View style={styles.autoCard}>
        <Icon name="link-variant" size={20} color={colors.primary} />
        <View style={styles.autoInfo}>
          <Text style={styles.autoTitle}>保存后自动关联</Text>
          <Text style={styles.autoText}>生成工资记录，并同步一条来源为“工资记录”的人工成本账单。</Text>
        </View>
      </View>

      <BigButton
        title={submitting ? "保存中..." : loading ? "加载中..." : "保存工资"}
        icon="content-save-outline"
        onPress={submit}
        disabled={submitting || loading}
        style={styles.submitButton}
      />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacingV2.lg, paddingBottom: spacingV2.xxxxl },
  summaryBar: {
    minHeight: 88,
    borderRadius: borderRadiusV2.xxxl,
    padding: spacingV2.xl,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.lg,
  },
  summaryLabel: { fontSize: fontSizeV2.sm, color: colors.textSecondary, fontWeight: "700" },
  summaryValue: {
    marginTop: spacingV2.xs,
    fontSize: fontSizeV2.xxxl,
    color: colors.text,
    fontWeight: "900",
  },
  summaryPill: {
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.expenseBg,
  },
  summaryPillText: { fontSize: fontSizeV2.sm, color: colors.expense, fontWeight: "800" },
  section: {
    marginBottom: spacingV2.lg,
    padding: spacingV2.lg,
    borderRadius: borderRadiusV2.xxl,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  sectionTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "900",
    color: colors.text,
    marginBottom: spacingV2.xs,
  },
  sectionHint: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 19,
    marginBottom: spacingV2.md,
  },
  chipRow: { gap: spacingV2.sm, paddingVertical: spacingV2.sm },
  selectChip: {
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.surfaceMuted,
  },
  selectChipActive: { backgroundColor: colors.primaryMuted },
  selectChipText: { fontSize: fontSizeV2.sm, fontWeight: "700", color: colors.textSecondary },
  selectChipTextActive: { color: colors.primary },
  inputRow: {
    minHeight: 46,
    marginTop: spacingV2.sm,
    paddingHorizontal: spacingV2.md,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
  },
  inlineInput: {
    flex: 1,
    minWidth: 0,
    fontSize: fontSizeV2.md,
    color: colors.text,
    paddingVertical: spacingV2.sm,
  },
  workerWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacingV2.sm,
    marginTop: spacingV2.md,
  },
  workerChip: {
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.surfaceMuted,
  },
  workerChipActive: { backgroundColor: colors.headerBg },
  workerChipText: { fontSize: fontSizeV2.sm, color: colors.textSecondary, fontWeight: "800" },
  workerChipTextActive: { color: colors.textInverse },
  newWorkerChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.successMuted,
  },
  newWorkerText: { fontSize: fontSizeV2.sm, color: colors.success, fontWeight: "800" },
  fieldLabel: {
    marginTop: spacingV2.md,
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "800",
  },
  quickGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacingV2.sm,
    marginTop: spacingV2.sm,
  },
  quickChip: {
    minHeight: 38,
    minWidth: 66,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacingV2.md,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.surfaceMuted,
  },
  quickChipActive: { backgroundColor: colors.successMuted },
  quickChipText: { fontSize: fontSizeV2.sm, color: colors.textSecondary, fontWeight: "800" },
  quickChipTextActive: { color: colors.success },
  textArea: {
    minHeight: 96,
    alignItems: "flex-start",
    paddingTop: spacingV2.md,
    textAlignVertical: "top",
    fontSize: fontSizeV2.md,
    color: colors.text,
  },
  autoCard: {
    flexDirection: "row",
    gap: spacingV2.md,
    padding: spacingV2.lg,
    borderRadius: borderRadiusV2.xxl,
    backgroundColor: colors.primaryMuted,
    marginBottom: spacingV2.lg,
  },
  autoInfo: { flex: 1, minWidth: 0 },
  autoTitle: { fontSize: fontSizeV2.md, color: colors.primary, fontWeight: "900" },
  autoText: {
    marginTop: 3,
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 19,
  },
  submitButton: { minHeight: 52 },
});
